# ADR 0063 — Verificar que arranca, no solo que compila

**Estado:** aceptado · **Fecha:** Fase 63

## El agujero
240 tests, todos con dobles. Verifican que cada pieza hace lo que dice su
firma. **Ninguno construia el sistema entero.**

Y ahi es donde KAIROS ha fallado cinco veces esta semana:

    Mapped[Any] sin importar Any     -> compilaba, no arrancaba
    EmbeddingProvider inexistente    -> compilaba, no arrancaba
    routes_tareas que no existia     -> compilaba, no arrancaba
    un yield en el metodo equivocado -> ni compilaba, y ast.parse lo aprobo
    el modelo Task que faltaba       -> compilaba, no arrancaba

Los cinco los habria pillado un test que llame a `build_core()` e importe el
router. Cinco caidas, horas perdidas, y el test que las evitaba son diez
lineas.

## Lo que verifica
- `build_core()` resuelve todos los imports y registra todos los agentes
- el router importa sus rutas y la app de uvicorn se importa
- `configure_mappers()` resuelve las anotaciones de SQLAlchemy
- el router no pide rutas que no existen en disco, y lo dice por nombre
- el bootstrap no importa agentes inexistentes
- todo paquete de agente tiene `__init__.py`
- **todo planificador que existe esta arrancado en main.py** (el de tareas se
  escribio y nunca se enganchó: codigo muerto durante ocho fases)
- ningun agente declara una capacidad que ya declara otro
- `health()` no lanza en ningun agente, aunque su servicio este caido
- ningun agente acepta una capacidad inventada
- la configuracion carga sin variables de entorno

## Entra en `make test-todo`
No es opcional. Es la comprobacion que mas fallos habria pillado y va donde
se decide si un cambio entra.

## La leccion, por fin escrita en codigo
**Verificar que el codigo compila no es verificar que arranca.** Llevaba
cinco fases repitiendolo en prosa y ahora esta en la suite, que es donde
sirve.
