# KAIROS OS

Sistema personal de IA **local-first**. Todo el procesamiento por defecto ocurre
en la maquina que lo ejecuta. La salida a Internet es una capacidad opcional que
se activa explicitamente, nunca una dependencia estructural.

**Regla fundacional:** KAIROS nunca depende de Internet para funcionar.
Internet solo anade capacidades; jamas elimina capacidades.

## Estado

Fase 1 — nucleo conversacional con memoria semantica persistente.

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Monorepo, Docker, auth local, chat, memoria semantica, auditoria | en curso |
| 2 | Wake word, Whisper (STT), Piper (TTS), conversacion por voz | pendiente |
| 3 | Camaras, OpenCV, deteccion, reconocimiento facial con consentimiento, OCR | pendiente |
| 4 | Automatizacion del ordenador y del hogar (Home Assistant) | pendiente |
| 5 | Planificacion multiagente, aprendizaje, panel de operacion | pendiente |

## Requisitos

- Docker Engine 24+ y Docker Compose v2
- GPU NVIDIA + NVIDIA Container Toolkit (opcional pero recomendado; en Windows,
  instalado dentro de WSL2)
- ~12 GB de disco para los modelos locales

## Puesta en marcha

```bash
git clone <tu-repo> kairos-os && cd kairos-os
make init          # crea .env y genera secretos aleatorios
make up            # levanta postgres, ollama, core y web
make models        # descarga llama3.1:8b y nomic-embed-text (~6 GB)
make user          # crea tu usuario propietario
```

Abre `http://localhost:3000`.

Comprobacion rapida del nucleo:

```bash
curl -s http://127.0.0.1:8000/api/v1/health | python3 -m json.tool
```

## Criterio de aceptacion de la Fase 1

> Puedo abrir la interfaz local, escribir un mensaje, obtener una respuesta
> generada por un modelo que corre en mi maquina, cerrar la aplicacion,
> volver a abrirla, y que el sistema recupere informacion relevante de
> conversaciones anteriores mediante busqueda semantica — mostrandome
> exactamente que recuerdos uso y con que similitud.

Ver `docs/fase-1-aceptacion.md` para el guion de verificacion completo.

## Estructura

```
apps/core     Nucleo FastAPI: agentes, memoria, auth, auditoria
apps/web      Interfaz Next.js (solo local, sin despliegue publico)
docker        Dockerfiles e inicializacion de Postgres
docs          Arquitectura, modelo de amenazas, ADRs
scripts       Utilidades de operacion
```

## Comandos

```bash
make up        # levantar
make logs      # seguir logs del nucleo
make test      # suite de tests
make lint      # ruff + mypy
make down      # parar (los datos persisten)
make reset     # DESTRUCTIVO: borra volumenes
```

## Privacidad

- Ningun puerto se publica fuera de `127.0.0.1` por defecto.
- `KAIROS_ALLOW_EGRESS=false` bloquea proveedores remotos aunque haya claves.
- La auditoria registra metadatos, nunca el contenido de los mensajes.
- Antes de la Fase 3 (camaras) es **obligatorio** leer y aplicar
  `docs/camaras-y-consentimiento.md`.
