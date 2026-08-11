# ADR 0006 — Streaming SSE antes que la voz

**Estado:** aceptado · **Fecha:** Fase 2A

## Contexto
El plan original abria la Fase 2 con wake word y Whisper. Medido en la maquina
de destino (RTX 4060 Ti 8 GB, llama3.1:8b), la latencia con modelos calientes
es ~1 s, asi que el streaming NO era necesario por latencia percibida.

## Decision
Aun asi, el streaming va primero.

## Motivos
- Para conversar por voz hay que sintetizar la primera frase mientras el
  modelo genera la tercera. Sin flujo incremental, cada respuesta hablada
  arranca con varios segundos de silencio.
- Elimina el parche de timeouts de 300 s que la Fase 1 necesito en el cliente.
- El primer arranque tras `docker compose down` recarga modelos en VRAM y
  tarda minutos; con SSE el usuario ve actividad en vez de una pantalla muerta.

## Por que SSE y no WebSocket
El flujo es unidireccional (servidor -> cliente) y va sobre el mismo POST que
ya lleva la cookie de sesion. Un WebSocket obligaria a un canal aparte, a
reautenticar y a gestionar reconexion, sin aportar nada aqui. Cuando la Fase
2B necesite mandar audio del cliente al servidor de forma continua, ahi si
entra WebSocket — y convivira con esto, no lo sustituye.

## Consecuencias
- `LLMProvider` gana `complete_stream`; todo proveedor futuro debe implementarlo.
- Los agentes con salida incremental implementan el Protocol `StreamingAgent`.
  Se hizo aparte de `Agent` para no obligar a Vision o Device, cuya salida no
  es un chorro de tokens, a devolver generadores.
- La ruta `POST /api/v1/chat` sin streaming se mantiene para depurar con curl.
