# ADR 0041 — Recordatorios fijos y avisos abiertos

**Estado:** aceptado · **Fecha:** Fase 40

## Dos tipos, y la diferencia es lo interesante
- **Fijo**: la peticion trae el momento. "El jueves a las ocho", "en media
  hora". KAIROS calcula la fecha absoluta y espera.
- **Abierto**: el momento hay que averiguarlo. "Cuando juegue el Madrid".
  KAIROS busca por su cuenta cada media hora hasta resolverlo, y entonces lo
  convierte en fijo.

Los abiertos son la autonomia de verdad: KAIROS sale a buscar sin que nadie se
lo pida en ese momento, porque se lo pediste hace dias.

## Nunca inventa una fecha
Si las fuentes no dan una fecha clara, el aviso sigue abierto y se reintenta.
**Un aviso a la hora equivocada es peor que no avisar**: te hace desconfiar de
todos los demas.

## Tope de intentos
Ocho, con hora y media entre ellos. Un aviso abierto que nunca se resuelve
—porque el evento no existe o la pregunta estaba mal— pasa a "abandonado" en
vez de buscar para siempre.

## Se marca antes de decirlo
El aviso pasa a "avisado" ANTES de intentar pronunciarlo. Si el puente esta
caido el aviso queda dado y no se repite en bucle cada minuto. Se pierde el
audio, no se gana un bucle infinito.

## Dos ritmos
Los vencidos se comprueban cada minuto: llegar tarde inutiliza un aviso. Los
abiertos se resuelven cada media hora: buscar cuesta, y una fecha que no se
sabe ahora tampoco se sabra dentro de un minuto.

## Avisa, no ejecuta
Puede decirte que empieza el partido; no puede ponerlo. Cualquier accion sigue
pasando por la lista cerrada del puente y por tu confirmacion.
