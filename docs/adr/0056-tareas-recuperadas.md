# ADR 0056 — Recuperar las tareas en segundo plano

**Estado:** aceptado · **Fecha:** Fase 56

## Que paso
La Fase 48 construyo la cola de tareas. El panel llego a la interfaz en la
Fase 50, pero `agents/tareas/` nunca se copio: el `apply.sh` fallo a medias y
nadie lo comprobo.

Resultado: un panel completo sin nada detras durante ocho fases.

## El cambio de metodo
Este parche termina comprobando que **todos** los ficheros del nucleo
compilan, no solo los que toca. Si algo queda roto, lo dice antes de que
Diego reinicie el contenedor.

Es lo que ha faltado en cada uno de los tres parches que dejaron KAIROS sin
arrancar: verificar el resultado, no confiar en que las sustituciones
aplicaron.

## Y el router
Se genera leyendo el disco. Un modulo que no existe no puede importarse, y
que el router lo pida es como se cayo el nucleo tres veces.
