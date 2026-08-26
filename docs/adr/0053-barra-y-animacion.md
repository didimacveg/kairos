# ADR 0053 — Menos elementos, mejor ritmo

**Estado:** aceptado · **Fecha:** Fase 53

## La barra
Siete botones en fila. Cada fase anadio el suyo sin mirar los anteriores, y
el resultado era una fila indistinguible donde nada destacaba.

Criterio para repartir: **si se usa varias veces al dia, fuera; si se usa al
empezar o para grabar, dentro del menu.**

Fuera quedan hablar, imagen y enviar. Dentro: escucha ambiente, modo estricto,
modo chat, pantalla en negro y lanzar la secuencia.

## La animacion, tercera reescritura
Las dos versiones anteriores animaban entre 60 y 110 elementos SVG. Aunque
solo se tocaran `transform` y `opacity`, cien capas compuestas por fotograma
es demasiado para un navegador que ademas esta sirviendo la aplicacion.

Esta version anima **once elementos**: cuatro anillos, una luz, la palabra, la
linea y el pie. Divs con borde en vez de SVG. Ni chispas, ni rayos, ni
rejilla, ni barrido.

## Lo que la hace llamativa no es la cantidad
Es el ritmo: la carga que late tres veces antes de romper, la escala que se
pasa y vuelve, y los paneles entrando escalonados detras.

Eso cuesta cero y es lo que se nota en camara. Las setenta chispas no se
distinguian a esa velocidad y costaban la fluidez entera.

## La leccion
Tres intentos aumentando el espectaculo y bajando el rendimiento, cuando el
problema era el numero de elementos, no el tipo de propiedad animada.
**Optimizar el como no arregla un problema de cuanto.**
