# ADR 0035 — Autonomo, no independiente

**Estado:** aceptado · **Fecha:** Fase 32

## La distincion que pide Diego
KAIROS debe poder decidir QUE hace falta. No debe poder decidir SI se hace.

## Como se implementa
Cada hallazgo de la vigilancia puede llevar una accion sugerida, y esa accion
es una CLAVE de una lista cerrada — nunca un comando. Una clave que no este
declarada se descarta al construir el hallazgo, antes de salir del agente.

La lista actual tiene tres entradas y ninguna es destructiva: abrir un perfil,
aplicar una propuesta ya aprobada, repetir un informe. Nada que cierre, borre
o mate procesos.

## La pregunta va en el aviso
Cuando KAIROS propone algo, el aviso lo dice: "Tienes una propuesta aprobada
sin aplicar. ¿La aplico ahora?". La respuesta llega por el panel o por voz.

Sin respuesta no pasa nada. El silencio nunca es un si.

## Por que la lista es tan corta
Podria tener veinte entradas. Tiene tres porque cada una es una cosa que
KAIROS puede sugerirte hacer a las tres de la manana, y esa es la vara de
medir: si no te gustaria que te lo propusiera dormido, no entra en la lista.

## El despertar, por frase exacta
La animacion deja de dispararse con cada orden y pasa a exigir "despierta".

Motivo doble: cuesta rendimiento repetida, y un evento que ocurre siempre deja
de ser un evento. La animacion marca el momento en que el sistema arranca —
si acompanara a cada peticion, no marcaria nada.
