# ADR 0032 — Smith relee su propio codigo antes de entregarlo

**Estado:** aceptado · **Fecha:** Fase 29

## El fallo que lo motiva
Primera propuesta real de Smith. El diseno era bueno: reutilizar la
infraestructura HTTP existente, validar la ventana temporal contra una lista
cerrada, no interpolar nada del usuario en la peticion.

Y dentro, esto:

    _VALID_WINDOWS = frozenset({"h": "qdr:h", "d": "qdr:d"})
    ...
    time_filter = _VALID_WINDOWS[window]

`frozenset` sobre un diccionario conserva solo las claves, y un frozenset no
se indexa. Revienta en la primera llamada.

Ademas, la peticion pedia "con su test" y el cambio no traia ninguno.

## Por que pasa
Un modelo escribe de un tiron y no ejecuta nada mientras escribe. Los fallos
que comete son los de alguien que no ha releido lo que acaba de teclear.

## Decision
Una tercera pasada: escribir, **releer**, ensayar.

La revision busca cinco cosas concretas: errores que un interprete pillaria,
tests que faltan, tests que no pasarian, comentarios borrados y contratos
rotos.

## Por que no basta con el forge
El forge detectaria el error de tipos, si. Pero un ciclo del forge cuesta
minutos y una relectura cuesta segundos.

Y hay fallos que los tests no cubren: un comentario borrado que explicaba una
decision, o un test que directamente no existe. Los tests no pueden detectar
la ausencia de tests.

## Si la revision no aporta, no se usa
Cuando la segunda pasada no devuelve ficheros parseables, se conserva la
version original. Una revision que empeora el resultado es peor que ninguna.
