# ADR 0046 — No todo el audio merece la voz buena

**Estado:** aceptado · **Fecha:** Fase 45

## El problema
El plan gratuito de ElevenLabs son 10.000 caracteres al mes: unos diez
minutos de audio. Con el informe diario (≈500 caracteres) y las respuestas de
conversacion, se agota en tres o cuatro dias.

Y peor: al agotarse, la API devuelve 401 a mitad de una frase.

## Decision
Reparto por importancia. La voz buena se reserva para:

    despertar · urgente · informe · recordatorio

Todo lo demas —respuestas de conversacion, confirmaciones, "son las tres y
media"— va por Deepgram, que es rapido, suena bien y cuesta una fraccion.

**El reparto por defecto es el barato.** Sin motivo declarado, Deepgram. Al
reves, cualquier llamada nueva que alguien anada gastaria cuota sin querer.

## Contador en disco
El gasto del mes vive en un fichero, no en memoria: reiniciar el contenedor no
debe regalar cuota ya gastada. Y el tope se pone en 9.000 de los 10.000
—quedarse sin cuota a mitad de una frase es peor que quedarse corto.

## Lo que esto permite
Sin pagar nada: el despertar, los avisos urgentes, los informes y los
recordatorios con la voz buena. Es exactamente lo que se graba y lo que
importa oir bien.

Si algun dia el uso crece, subir el limite es una linea del .env.
