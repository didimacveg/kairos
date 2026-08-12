# ADR 0015 — Callar primero, decidir despues

**Estado:** aceptado · **Fecha:** Fase 3

## Problema
Al interrumpir a KAIROS hablando, seguia sonando hasta que el sistema
confirmaba la interrupcion: ~260 ms de voz sostenida mas la transcripcion.
Durante ese tiempo se oian dos voces a la vez.

## Decision
Dos umbrales sobre la misma senal del microfono:

1. **Silenciado inmediato** — al primer indicio de voz se corta el audio. Sin
   esperar confirmacion.
2. **Interrupcion** — si la voz se sostiene 220 ms, se aborta la generacion y
   se abre turno nuevo.

Si era un ruido y no el usuario, no pasa nada: el audio se reanuda en la frase
siguiente y la generacion nunca se aborto. El coste de un falso positivo es
una pausa; el de un falso negativo es hablar encima del usuario.

## Por que el umbral no puede ser bajo del todo
El altavoz reproduciendo a KAIROS entra por el microfono. La cancelacion de eco
del navegador ayuda pero no es perfecta: con un umbral igual al de escucha
normal, KAIROS se interrumpiria a si mismo. El margen es 1,9x sobre el ruido
ambiente calibrado.
