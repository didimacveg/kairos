# ADR 0008 — El microfono vive en el navegador; Whisper en un servicio aparte

**Estado:** aceptado · **Fecha:** Fase 2C

## Decision 1: capturar en el navegador
El audio se captura con MediaRecorder en la pestana web, no con un demonio en
el host.

Motivo: WSL2 accede al microfono via WSLg, pero es fragil y depende de la
version. Depurar audio en WSL podia costar dias antes de transcribir una sola
palabra. `getUserMedia` funciona hoy.

Limitacion asumida: un atajo de teclado en el navegador solo responde con la
pestana enfocada. El atajo global de la Fase 2E necesitara el demonio en el
host. Como el VoiceAgent implementa el contrato `Agent`, cambiar la fuente de
audio no toca el nucleo.

## Decision 2: Whisper en su propio contenedor
`faster-whisper` no se instala en la imagen del nucleo.

Motivos:
- CTranslate2 necesita las librerias CUDA y cuDNN. Anadirlas al nucleo lo
  ataria a que exista GPU y multiplicaria el tamano de la imagen.
- La VRAM se gestiona por separado de Ollama.
- Es el primer uso real de la frontera de agentes definida en la Fase 1: el
  VoiceAgent vive en el nucleo y habla por HTTP con el servicio. En la Fase 3
  el Vision Agent hara lo mismo desde otra maquina. Mismo contrato, otro
  transporte.

El servicio no publica puerto al host: solo es accesible por la red interna.

## Decision 3: transcribir NO es enviar
`POST /api/v1/voice/transcribe` devuelve texto al cuadro de escritura. No crea
un mensaje ni un recuerdo.

Motivo: Whisper se equivoca, sobre todo con nombres propios y con ruido. Con
la memoria curada de la Fase 2B, un mensaje enviado puede convertirse en un
hecho permanente. Un error que se ve y se corrige cuesta un segundo; uno que
entra en la memoria hay que ir a buscarlo.

## Modelo y VRAM
Por defecto `medium` con `int8_float16` (~1 GB). Con llama3.1:8b residente
(4,9 GB) caben ambos en los 8 GB de la RTX 4060 Ti, con margen estrecho.

Si Ollama empieza a descargar su modelo al transcribir, bajar a `small`
(KAIROS_WHISPER_MODEL=small). Si no hay GPU disponible, el servicio degrada a
CPU automaticamente: lento, pero KAIROS no se cae.
