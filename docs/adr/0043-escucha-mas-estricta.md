# ADR 0043 — Que no conteste a conversaciones ajenas

**Estado:** aceptado · **Fecha:** Fase 42

## El problema
Hablando con otra persona, KAIROS se puso a contestar.

Y **no es un problema de umbral**: una conversacion normal supera cualquier
umbral razonable de energia. Subirlo solo conseguiria que tampoco oyera al
usuario.

## Tres causas reales, tres arreglos

**La ventana de seguimiento era de 60 s.** Un minuto entero aceptando ordenes
sin repetir el nombre significa que media conversacion entra como ordenes.
Baja a 12 s, que cubre el caso util ("pon musica"... "sube el volumen") sin
dejar la puerta abierta.

**El nombre se buscaba en cualquier posicion.** "...y entonces le dije a
kairos que..." contenia el nombre y disparaba una orden con el resto de la
frase. Ahora tiene que estar en los primeros 12 caracteres.

**Las frases largas se aceptaban en seguimiento.** Las ordenes son cortas; una
parrafada sin el nombre delante es conversacion con otra persona. Se descarta
por encima de 90 caracteres.

## Modo estricto
Un interruptor que elimina la ventana por completo: cada orden exige el
nombre. Es lo que quieres con gente delante, y se recuerda entre sesiones.

## Lo que NO se toca
El umbral de energia. Ya se autocalibra con el ruido de la habitacion y
funciona; el problema estaba en que hacer DESPUES de oir, no en oir.
