# ADR 0030 — "Proponte X" no es conversacion

**Estado:** aceptado · **Fecha:** Fase 27

## El fallo
"KAIROS, proponte anadir una capacidad al search agent" acabo en el camino de
conversacion. KAIROS busco en la web y respondio con un ensayo de diseno —
correcto y bien argumentado, y completamente al lado de lo que se pedia.

El motivo: solo el panel de propuestas y el puente por voz enrutaban a Smith.
El chat sabia conversar y ejecutar acciones del escritorio, nada mas.

## Decision
El orquestador detecta las peticiones de cambio ANTES que cualquier otra cosa,
por delante de la memoria, la busqueda y las acciones del escritorio.

## Preambulo explicito, no interpretacion
Se reconocen: "proponte", "propon", "hazte capaz de", "aprende a",
"programate", "haz que puedas", "modificate para".

Deliberadamente NO se deja que el modelo decida si una frase es una peticion
de cambio. Hacerlo generaria propuestas a partir de conversaciones sobre
diseno — hablar de una funcionalidad no es pedir que se implemente, y
confundirlo llenaria la cola de propuestas que nadie pidio.

El detector exige que el preambulo abra la frase. "He estado pensando en que
deberias proponerte mejorar la memoria" es conversacion, y se queda como tal.

## Mismo criterio en los tres caminos
Panel, voz y chat usan el mismo preambulo. Una capacidad que se comporta
distinto segun por donde entres es una capacidad que no se entiende.
