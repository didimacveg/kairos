# Fase 1 — guion de verificacion

Ejecuta esto de arriba abajo. Si algun paso falla, la fase no esta cerrada.

## 1. Reproducibilidad desde cero

```bash
make reset && make init && make up && make models && make user
```

Criterio: en una maquina limpia, estos comandos dejan el sistema operativo sin
ninguna intervencion manual adicional.

## 2. Salud del nucleo

```bash
curl -s http://127.0.0.1:8000/api/v1/health | python3 -m json.tool
```

Criterio: `status: ok`, `egress_allowed: false`, ambos agentes presentes.

## 3. Autenticacion

- Login con credenciales correctas → cookie `kairos_session` presente,
  `HttpOnly` marcada.
- Login con contrasena incorrecta → 401 y fila en `audit_log` con
  `outcome=failure`.
- `GET /api/v1/auth/me` sin cookie → 401.

## 4. Conversacion con modelo local

Envia un mensaje desde la interfaz.

Criterio: respuesta en menos de 3 s (RTX 4060 Ti, llama3.1:8b cuantizado), y el
rail de traza muestra `local: true` y el nombre del modelo.

## 5. Memoria persistente — la prueba que de verdad importa

1. Di algo concreto y personal: *"trabajo mejor por las tardes y odio las
   respuestas largas"*.
2. `make down && make up`.
3. Vuelve a entrar y pregunta: *"¿cuando trabajo mejor?"*.

Criterio: la respuesta usa el dato **y** el rail muestra el recuerdo recuperado
con su similitud. Si responde bien pero el rail esta vacio, el modelo lo ha
adivinado del historial: la memoria no funciona.

## 6. Auditoria

```sql
SELECT action, outcome, detail->>'memories_used', created_at
FROM audit_log ORDER BY created_at DESC LIMIT 10;

UPDATE audit_log SET outcome = 'success' WHERE outcome = 'failure';
```

Criterio: el `SELECT` muestra la actividad; el `UPDATE` **falla** con el error
del trigger append-only.

## 7. Aislamiento de red

```bash
docker compose exec core python -c "
import httpx
try:
    httpx.get('https://api.anthropic.com', timeout=5)
    print('HAY SALIDA A INTERNET')
except Exception as e:
    print('sin salida:', type(e).__name__)
"
```

Criterio: con `KAIROS_ALLOW_EGRESS=false`, ningun proveedor remoto es
seleccionable aunque la red exista. Para aislamiento de red real, anade
`network_mode: none` al servicio `core` y comprueba que sigue funcionando contra
Postgres y Ollama por red interna dedicada.

## 8. Calidad

```bash
make test && make lint
```

Criterio: 15/15 tests en verde, ruff y mypy sin errores.
