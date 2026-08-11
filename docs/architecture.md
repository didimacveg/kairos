# Arquitectura

## Principio rector

Un limite arquitectonico solo existe si separa responsabilidades reales. Cada
abstraccion de este documento tiene que justificar por que existe; si no puede,
se elimina.

## Vista general

```
              ┌──────────────────────────────┐
              │  Next.js (solo localhost)    │
              └──────────────┬───────────────┘
                             │ HTTP mismo origen (rewrite)
              ┌──────────────▼───────────────┐
              │        KAIROS Core           │
              │  orquestacion + auditoria    │
              └───┬───────────────────┬──────┘
                  │                   │
        ┌─────────▼──────┐   ┌────────▼────────┐
        │  Memory Agent  │   │ Reasoning Agent │
        └─────────┬──────┘   └────────┬────────┘
                  │                   │
        ┌─────────▼──────┐   ┌────────▼────────┐
        │ Postgres+vector│   │  Ollama (local) │
        └────────────────┘   └─────────────────┘
```

## Que es un agente aqui

Un *bounded context*: posee su estado, expone capacidades con nombre
(`memory.retrieve`, `reasoning.respond`) y no importa modulos internos de otro
agente. Se comunican por `AgentRequest` / `AgentResponse` a traves del registro.

**Hoy corren en el mismo proceso y se invocan por llamada directa.** No hay cola
de mensajes ni event bus, porque no hay ningun problema que lo justifique
todavia. La razon de que el contrato exista igualmente es de mantenibilidad: el
riesgo real de un proyecto de varios anos no es la latencia, es acabar con voz,
vision, memoria y automatizacion acopladas en el mismo fichero.

Cuando un agente necesite correr en otra maquina (Vision en una Raspberry, Fase
3), el registro devolvera un proxy que habla por red. El contrato no cambia y
ningun llamante se entera. Ese es el momento de introducir transporte, no antes.

## Flujo de una peticion de chat

1. `current_user` resuelve la cookie de sesion contra la tabla `sessions`.
2. `KairosCore.chat` recupera o crea la conversacion y sus ultimos 10 turnos.
3. `memory.retrieve` calcula el embedding de la consulta y ordena por distancia
   coseno **en Postgres** (`<=>` con indice HNSW). Filtra por similitud minima.
4. `reasoning.respond` construye el prompt (sistema + memoria + historial +
   mensaje) y llama al proveedor local.
5. Se persisten ambos mensajes; el mensaje del usuario se indexa como memoria.
6. Se escribe una fila en `audit_log` con metadatos, nunca con el contenido.
7. La respuesta incluye la **traza** completa, que la interfaz muestra al lado.

La traza no es logging: se devuelve al cliente. Si el usuario no puede ver por
que el sistema dijo lo que dijo, el sistema no es auditable en la practica.

## Fronteras de extension por fase

| Fase | Agente nuevo | Encaja porque |
|---|---|---|
| 2 | Voice | implementa `Agent` con `voice.transcribe` / `voice.speak` |
| 3 | Vision | primer candidato a proceso remoto; el registro devolvera un proxy |
| 4 | Automation | requiere modelo de permisos propio antes de existir |
| 5 | Planner | orquesta agentes; sustituye la logica fija de `KairosCore.chat` |

## Lo que deliberadamente no hay

- **LangGraph / MCP**: no hay ramificacion, reintentos ni estado de plan que
  justifiquen un framework de orquestacion. Entran en Fase 5, si hacen falta.
- **Alembic**: el esquema cambia a diario. Ver ADR 0004.
- **Node en el backend**: ver ADR 0001.
- **Supabase / Vercel**: ver ADR 0002.
