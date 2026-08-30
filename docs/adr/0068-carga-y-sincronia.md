# ADR 0068 — Barra de carga, y todo a su tiempo

**Estado:** aceptado · **Fecha:** Fase 68

## Tres correcciones

**El saludo salia a los 2,65 s** de una animacion de 10. Ese retardo venia de
cuando la secuencia duraba 2,8 s y nadie lo actualizo al alargarla. Ahora
suena a los 9,6 s, cuando el velo se disuelve.

**La marca y el subtitulo iban por separado**: el subtitulo entraba 0,9 s
despues y se iba despues. Dos elementos que se leen como uno no pueden entrar
y salir por su cuenta. Ahora van en un mismo bloque, con el mismo retardo y la
misma duracion.

**Faltaba una barra de carga.** Es lo que hacia que no se leyera como un
sistema poniendose en marcha: los anillos giran, pero **girar no es avanzar**.
Ahora hay una barra que progresa de 0 a 100 en 5,4 s con cinco fases nombradas.

## La sensacion "militar" no son los efectos
Es la **densidad de informacion secundaria que no pide ser leida**: escalas
graduadas en los laterales, retículas en las esquinas, un identificador de
nodo con coordenadas.

Nadie lee esos datos. Su funcion es que la pantalla parezca un instrumento en
vez de una presentacion.

## Leccion de sincronia
Cada vez que se cambia la duracion de la animacion hay que revisar TODO lo que
se sincroniza con ella. El saludo llevaba tres versiones desfasado porque su
retardo estaba en otro fichero.
