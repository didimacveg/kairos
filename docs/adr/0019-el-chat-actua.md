# ADR 0019 — El chat ejecuta ordenes, no solo conversa

**Estado:** aceptado · **Fecha:** Fase 10

## El problema
"Abre el modo trabajo" escrito en el chat producia: "No tengo la capacidad de
abrir modos ni ejecutar acciones en tu sistema."

El modelo decia la verdad. El IntentAgent existia desde la Fase 7 pero solo lo
usaba el puente, por voz. Desde la web, el orquestador solo sabia recuperar
memoria, buscar y generar texto.

## Decision
El orquestador clasifica la intencion ANTES de generar. Si es una orden sobre
el escritorio, la ejecuta y confirma; si no, sigue el camino normal.

Que la orden llegue escrita o hablada no cambia nada: misma cadena, mismas
garantias.

## Las garantias no se relajan
- El modelo NO emite ordenes: elige de una lista cerrada de 13 acciones que se
  valida en el IntentAgent.
- Un perfil que no existe se rechaza alli, antes de llegar al puente.
- El puente solo conoce perfiles y acciones declarados por el usuario en su
  fichero de configuracion.
- Toda accion deja fila en `audit_log`.
- Ante cualquier fallo —el puente caido, el clasificador sin respuesta— se
  devuelve `conversar`, que no toca nada. No hacer nada es el modo seguro.

## Sin generacion para las ordenes
Cuando se ejecuta una accion, la respuesta es la confirmacion directa. No se
gasta una llamada al modelo en describir lo que ya se ha hecho: es mas rapido,
mas barato y no puede inventarse un resultado distinto del real.
