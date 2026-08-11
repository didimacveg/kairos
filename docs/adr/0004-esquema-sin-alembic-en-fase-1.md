# ADR 0004 — Sin Alembic en Fase 1

**Estado:** aceptado · **Fecha:** Fase 1

## Decision
El esquema se crea con `Base.metadata.create_all` mas un trigger de proteccion
para `audit_log`. Alembic entra al cerrar la Fase 2.

## Motivos
El modelo de datos cambia a diario mientras se define. Generar migraciones sobre
un esquema inestable produce docenas de ficheros que nadie va a revisar y da una
falsa sensacion de rigor.

## Consecuencias
- Hasta Fase 2, un cambio de modelo puede requerir `make reset`. Aceptable
  porque no hay datos que perder que no sean de prueba.
- **Condicion de salida:** el dia que exista informacion real que no se pueda
  regenerar, Alembic deja de ser opcional. Esa es la senal, no una fecha.
