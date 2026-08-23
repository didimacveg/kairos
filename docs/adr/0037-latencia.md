# ADR 0037 — Dejar de pagar por descubrir que algo es conversacion

**Estado:** aceptado · **Fecha:** Fase 34

## El problema
"Que hora es" tardaba varios segundos. La cadena era:

1. clasificar la intencion (llamada completa al modelo)
2. decidir si buscar en la web -> buscar (la heuristica veia "que hora")
3. generar la respuesta (otra llamada)

Tres pasos para responder algo que KAIROS ya tenia en el prompt.

## Dos correcciones

**Prefiltro antes de clasificar.** El clasificador es bueno pero cuesta una
ida y vuelta entera, y se pagaba en cada mensaje. Ahora un patron barato
descarta lo que es inequivocamente conversacion: una pregunta que empieza por
interrogativo y no menciona nada accionable.

Regla del prefiltro: **ante la duda, clasificar.** Perder medio segundo es
mejor que ignorar una orden. Por eso "que cancion suena" si pasa — es
interrogativa pero menciona algo accionable.

**No buscar lo que ya sabe.** La fecha y la hora van en el prompt desde la
Fase 3. La heuristica de busqueda las trataba como "algo de hoy" y salia a
Internet a por ellas.

## El patron
Las dos correcciones son la misma idea: **antes de anadir un paso, comprobar
si el dato ya estaba disponible.** Es el mismo error que cometi con Smith —
pedirle que imitara un estilo que no podia ver— visto desde el otro lado:
buscar algo que ya se tenia.
