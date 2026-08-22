# ADR 0024 — Cobertura real antes de la auto-mejora

**Estado:** aceptado · **Fecha:** Fase 20

## Por que ahora
La cola de propuestas (ADR 0023) permite que KAIROS proponga cambios a su
propio codigo. La decision de aprobar se apoyara, sobre todo, en si los tests
pasan.

Hasta hoy `make test` cubria contratos y logica pura con dobles. Eso verifica
que el codigo hace lo que dice su firma, no que KAIROS funcione. Un agente que
se autoaprueba con esa cobertura aprobaria sus propios errores el primer dia.

## Lo que se anade
Tests contra Postgres REAL, en una base efimera que se crea y destruye en cada
ejecucion:
- pgvector recupera de verdad, con el indice HNSW
- aislamiento por propietario
- los recuerdos retirados no vuelven
- el trigger append-only de la auditoria aguanta UPDATE y DELETE
- el esquema tiene las columnas que las migraciones deberian haber creado

Ese ultimo es el que mas veces habria ahorrado tiempo: varias veces una
migracion no se aplico y se descubrio por comportamiento raro, no por un test.

## Regla que queda establecida
`make test-todo` es la condicion para que un cambio entre. Cuando exista el
agente generador, una propuesta cuyos tests no pasen ni siquiera llegara a la
cola.
