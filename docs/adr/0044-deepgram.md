# ADR 0044 — Transcripcion y voz por API

**Estado:** aceptado · **Fecha:** Fase 43

## El problema medido
Una pregunta simple tardaba unos 7 segundos:

    grabar hasta silencio        0,5 s
    Whisper medium en CPU        2-4 s
    memoria + intencion          0,5-1 s
    modelo en la nube            1-2 s
    Piper en CPU                 1-2 s

**Cuatro de esos siete segundos eran CPU haciendo trabajo de GPU.** Ninguna
optimizacion de codigo lo arregla: transcribir y sintetizar en CPU cuesta lo
que cuesta.

## Decision
Nova-3 para transcribir (~300 ms) y Aura-2 para sintetizar (~250 ms al primer
byte). De 7 segundos a menos de 2.

## La regla fundacional sigue intacta
Si Deepgram falla —sin red, sin clave, error de la API— se cae a Whisper y
Piper locales automaticamente. KAIROS sigue funcionando sin Internet: peor,
pero funcionando. Eso no se negocia desde la Fase 1.

Y sin clave configurada, todo funciona exactamente como antes.

## La voz
`aura-2-nestor-es`: castellano peninsular, tono calmado y grave. De las
disponibles es la mas cercana a lo que se buscaba — contenida, sin el tono de
locutor comercial que tienen casi todas las voces sinteticas.

Se cambia en el .env sin tocar codigo.

## Efecto lateral: la animacion
Con la transcripcion fuera del navegador, el hilo que pinta deja de competir
con el analisis de audio. Parte del tiron de la secuencia de arranque venia de
ahi, no del CSS.
