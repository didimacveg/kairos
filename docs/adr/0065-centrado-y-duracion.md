# ADR 0065 — El fallo de centrado, y cinco actos

**Estado:** aceptado · **Fecha:** Fase 65

## Por que se iba arriba a la izquierda
El contenedor usaba `display: grid; place-items: center`. Pero **el grid no
coloca a los hijos con `position: absolute`**: esos los coloca el bloque
contenedor, desde la esquina superior izquierda.

Todo lo absoluto crecia en diagonal desde ahi. Y como cada version anadia mas
elementos absolutos, el problema empeoraba en vez de notarse.

**Solucion:** cada elemento absoluto se centra el mismo con
`top:50%; left:50%; translate:-50% -50%`.

## Y por que se descentraba a mitad de animacion
Las escalas iban en `transform: scale(...)`, que SOBRESCRIBE el
`transform: translate(...)` del centrado. En cuanto el keyframe tocaba
`transform`, el centrado desaparecia.

Ahora la escala va en la propiedad `scale`, que se compone con `translate` sin
anularlo. Son propiedades independientes desde CSS moderno y existen
precisamente para esto.

## Cinco actos, 5,2 segundos
    0.0-1.1  carga: el punto late cuatro veces
    1.1-2.2  rotura: la onda y tres anillos
    2.2-3.0  el arco girando media vuelta
    2.4-4.4  la marca, que se queda el 70% de su tiempo
    4.0-5.2  la confirmacion y los paneles entrando

Las versiones cortas se sentian apresuradas. **Una secuencia de arranque
necesita pausas para leerse como algo que ocurre, no como un parpadeo.**

Sigue siendo ligera: nueve elementos, cero filtros, solo `scale`, `rotate` y
`opacity`.
