# ADR 0057 — Smith lee el error y lo arregla

**Estado:** aceptado · **Fecha:** Fase 57

## Lo que faltaba
Una propuesta con los tests en rojo se quedaba en rojo. Diego la leia, veia el
fallo, y volvia a pedir el cambio.

Pero el error de pytest casi siempre dice exactamente que esta mal y en que
linea, y leer un error es justo lo que un modelo sabe hacer bien.

## El ciclo
    escribir -> releer -> escribir el test -> ensayar
             -> si falla: LEER EL ERROR, corregir, ensayar otra vez

## Un solo reintento
Si el segundo intento tampoco pasa, el problema no es un descuido: es algo que
el modelo no entiende, y reintentar en bucle gastaria llamadas sin converger.

Ahi para y deja la propuesta en rojo con su diagnostico, que es informacion
util: dice donde esta el limite.

## El segundo intento solo se usa si MEJORA
Si tampoco pasa los tests, se conserva el primero. Una correccion que no
arregla nada pero cambia el codigo hace mas dificil entender el fallo
original.

## Lo que el prompt prohibe explicitamente
**Borrar el test que falla.** Es la forma mas facil de poner algo en verde y
la que haria inutil todo el sistema: los tests son lo unico que separa una
propuesta buena de una que rompe KAIROS.

Y admite no saber: "si no entiendes el fallo, dilo en vez de adivinar". Una
propuesta honesta que reconoce un limite es mas util que una que empeora el
codigo intentando tapar un error que no comprende.
