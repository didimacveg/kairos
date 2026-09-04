# ADR 0079 — Medir la calidad, y saber por que fallo

**Estado:** aceptado · **Fecha:** Fase 79

## El agujero
Smith prueba el codigo con tests. **Nadie medía la calidad de lo que KAIROS
dice.** Se puede refactorizar durante meses y que las respuestas empeoren sin
que nada lo detecte.

## Cuatro criterios
- **correccion** — ¿algo falso o inventado? Decir "no lo se" es un 10, no un 5
- **utilidad** — ¿responde a lo que se pregunta?
- **brevedad** — ¿sobra texto?
- **voz** — ¿suena como KAIROS o como un asistente generico?

## Una muestra de diez, no todo
Diez respuestas bastan para ver una tendencia. Puntuar mil costaria mil
llamadas al modelo y la senal no mejoraria.

## Lo util es la serie, no la nota
Un 7 aislado no dice nada. Un 7 despues de tres semanas de 8 dice que algo se
rompio, y con las fechas se puede mirar que cambio en medio.

Por eso `juez.tendencia` compara los ultimos tres dias con los tres
anteriores: una regresion se ve comparando, no mirando un numero.

## Solo avisa si CAE
Un informe diario de "todo bien" se deja de leer a la semana. Y entonces
tampoco se lee el dia que dice algo.

## Quien juzga
El mismo proveedor, con un prompt distinto y sin saber que las respuestas son
suyas. Un modelo juzgandose es optimista, pero detecta las caidas — que es
para lo que sirve.

## Y la introspeccion: `make explicar`
Reune en una pantalla lo que habia que buscar en cinco sitios: agentes
caidos, el ultimo error de cada servicio, las acciones auditadas recientes y
la ultima conversacion.

Nos habria ahorrado varias tardes.
