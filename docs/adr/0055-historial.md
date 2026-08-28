# ADR 0055 — Poder volver a una conversacion

**Estado:** aceptado · **Fecha:** Fase 55

## Lo que faltaba
Los hilos llevaban en Postgres desde la Fase 1. Lo que no habia era forma de
volver a ellos: al recargar la pagina, KAIROS empezaba de cero aunque la
conversacion entera siguiera guardada.

Es la diferencia mas visible entre una herramienta y un juguete.

## El titulo es el primer mensaje
No un resumen generado. Dos motivos: es lo que de verdad recuerdas haber
preguntado, y no cuesta una llamada al modelo por conversacion.

## Borrar el hilo NO borra los recuerdos
Se borran los mensajes; lo que KAIROS aprendio de ellos se queda.

Lo que aprendio no deja de ser cierto porque borres el hilo, y perder memoria
al limpiar el historial seria una sorpresa desagradable — descubrirla el dia
que KAIROS olvida algo importante es peor que no poder borrar.

## El router se genera de lo que existe
A partir de aqui, cualquier parche que toque el router lo escribe leyendo el
disco, no la lista de lo que deberia haber. Tres veces hemos tenido el nucleo
caido porque el router importaba un modulo que un parche a medias nunca
copio.
