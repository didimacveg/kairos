# ADR 0033 — Ensenarle la casa antes de pedirle que imite el estilo

**Estado:** aceptado · **Fecha:** Fase 30

## El fallo
Tras la pasada de revision (ADR 0032), Smith produjo codigo claramente mejor:
corrigio el error de tipos, devolvio un comentario borrado, y anadio una
funcion defensiva que nadie le pidio.

Y siguio sin escribir el test.

## Por que
El prompt decia "mira un test existente del mismo area y copia su forma".
Pero en el contexto no habia ningun test: la seleccion de ficheros la hacia el
modelo y elegia el codigo que iba a tocar, no las pruebas.

Se le pedia imitar un estilo sin ensenarle el estilo.

## Decision
Dos o tres tests reales del repositorio entran SIEMPRE en el contexto, elija
lo que elija el modelo. Si sus ficheros elegidos ya incluyen tests, se usan
esos; si no, se meten de referencia igualmente.

## Falta el test: se avisa, no se bloquea
Si la propuesta toca comportamiento y no trae ningun fichero de tests:
- se anota en la traza,
- el riesgo sube a alto,
- y el motivo lleva el aviso escrito.

No se bloquea porque un cambio sin test puede seguir siendo util. Pero tiene
que verse antes de aprobar, no descubrirse despues.

## El patron, otra vez
Es el tercer fallo de Smith del mismo tipo: pedirle algo sin darle lo que
necesita para hacerlo. Primero un formato de salida propenso a errores, luego
ninguna oportunidad de releerse, ahora un estilo que no puede ver.

**Cuando un modelo falla de forma consistente, mirar primero que le falta en
el contexto — antes de insistir en las instrucciones.**
