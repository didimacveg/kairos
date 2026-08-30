# ADR 0069 — Dos cosas no pueden verse a la vez si una es fondo de la otra

**Estado:** aceptado · **Fecha:** Fase 69

## Los tres fallos tenian la misma raiz
Elementos solapandose cuando no debian.

**El nucleo latia detras de la palabra.** Se veia a traves de las letras. Ahora
el nucleo MUERE en el segundo 1,5 y la marca entra en el 4,1: son dos actos,
no dos capas.

**El velo se levantaba antes que la animacion.** El fondo se volvia
transparente mientras los anillos seguian visibles, asi que durante un segundo
la interfaz se veia A TRAVES de la secuencia. Ahora todo lo de la animacion
desaparece primero y el velo se levanta despues, sobre negro limpio.

**Los paneles entraban durante la secuencia.** Retrasados a los 8,5 s, cuando
ya no queda nada encima.

## El saludo lo dispara la animacion
Antes dependia de un retardo fijo escrito en Console.tsx. Cada vez que
cambiaba la duracion de la secuencia —cinco veces— ese numero se quedaba
desfasado en otro fichero.

Ahora el componente llama a `onMarca()` cuando la marca esta en pantalla. La
sincronia vive donde vive el tiempo.

**Un valor que depende de otro no debe estar en un fichero distinto.**

## La regla
En una secuencia, dos cosas nunca deben verse a la vez si una es fondo de la
otra. **O una sustituye a la otra, o una es capa de la otra — pero no a
medias.** Todo lo translucido que quedaba raro venia de estar a medias.
