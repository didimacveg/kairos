# ADR 0058 — Que la voz no tenga huecos

**Estado:** aceptado · **Fecha:** Fase 58

## El problema
La cola de voz era estrictamente secuencial: pedir una frase, esperar el
audio, reproducirla, y solo entonces pedir la siguiente.

Entre frase y frase hay 300-500 ms de silencio — la ida y vuelta al servicio.
En una respuesta de cinco frases son dos segundos de huecos que hacen que
KAIROS suene entrecortado aunque cada frase suene bien.

## Precarga
Mientras suena la frase 1, se sintetizan la 2 y la 3. Habla continua, sin que
el tiempo total de generacion cambie.

El orden de reproduccion sigue siendo estricto: reproducir la frase 3 antes
que la 2 porque tardo menos en sintetizarse haria el audio incomprensible.
Las peticiones van en paralelo, la reproduccion no.

## Dos por delante, no mas
Cada frase adelantada es audio que quizas no llegue a sonar si el usuario
interrumpe. Con la voz de ElevenLabs, eso es cuota gastada para nada.

Dos cubre el hueco sin desperdiciar apenas.
