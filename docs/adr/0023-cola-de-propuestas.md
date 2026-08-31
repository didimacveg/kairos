# ADR 0023 — KAIROS propone, Diego aprueba

**Estado:** aceptado · **Fecha:** Fase 19

## Origen
El patron viene de OpenJarvis (Stanford, Apache 2.0): su agente proactivo no
ejecuta, deja acciones en una cola de aprobacion. Se coge la idea, no el
codigo — su implementacion asume su arquitectura de sesiones y almacenes.

## Por que no auto-despliegue
Un sistema que reescribe su codigo y se despliega solo se rompe en la tercera
iteracion: introduce un fallo, el fallo impide arrancar, y no queda ni sistema
ni forma de depurarlo. Con propuestas revisables, el peor caso es una rama de
git que se descarta.

Esto no es cautela abstracta: durante la construccion de KAIROS varios parches
fallaron, y se arreglaron porque habia un humano leyendo el error.

## Aprobar y aplicar son estados distintos
Aprobar es una decision; aplicar es una operacion que puede fallar. Si fueran
el mismo estado, un fallo al aplicar dejaria la propuesta marcada como si
hubiera funcionado.

Estados: pendiente, aprobada, rechazada, aplicada, fallida, caducada.

## Las propuestas caducan
A los 7 dias sin decision pasan a caducada. Una cola que crece sin limite deja
de leerse, y una cola que no se lee es peor que no tenerla: da sensacion de
control sin darlo.

## Lo que falta para cerrar el ciclo
Este ADR cubre la cola. Faltan dos piezas:
- El agente que genera la propuesta (lee el codigo, escribe el parche, crea la
  rama, ejecuta los tests).
- El aplicador (hace merge de la rama aprobada y reinicia lo necesario).

Requisito previo para ambas: que `make test` cubra lo importante. Los tests
van a ser lo unico que separe un parche bueno de uno que rompe KAIROS.
