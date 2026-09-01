# ADR 0074 — Una busqueda que no falla en silencio

**Estado:** aceptado · **Fecha:** Fase 74

## El fallo
DuckDuckGo devolvia HTTP 202 con su pagina de inicio en vez de resultados.
`parse_results` extraia cero, y el agente devolvia `ok=True` con la lista
vacia.

Resultado: KAIROS respondia "no tengo informacion de hoy" teniendo la busqueda
web activada. **Durante meses.**

## Por que no se detecto antes
Porque el fallo era silencioso. `ok=True` con lista vacia es
indistinguible de "he buscado y no hay nada", y esa segunda respuesta es
plausible. Nadie sospecha de un sistema que dice algo razonable.

**Un componente que falla devolviendo exito es peor que uno que se cae.**

## Decision
Brave Search API. JSON en vez de HTML raspado, y codigos de estado reales: si
la clave caduca o se agota la cuota, se ve inmediatamente.

Plan gratuito: 2.000 consultas al mes, sin tarjeta.

## Vacio y fallo son cosas distintas
`buscar()` devuelve una lista vacia cuando no hay resultados y `None` cuando
no ha podido buscar. El agente traduce el segundo caso a
`AgentResponse.failure`, y el orquestador lo anota en la traza.

Asi KAIROS puede decir "he intentado buscar y no he podido" en vez de "no
tengo informacion", que suena a que ni lo intento.

## Y el raspado antiguo se queda, pero honesto
Si no hay clave de Brave, se intenta DuckDuckGo. Pero ahora, si no extrae
nada, devuelve `failure` en vez de exito vacio.

Conservarlo tiene sentido —KAIROS debe funcionar con lo que haya— pero
mintiendo no servia de nada.
