# ADR 0052 — Limpieza tras cincuenta fases

**Estado:** aceptado · **Fecha:** Fase 52

## El fallo fatal
`Mapped[Any]` sin importar `Any` en el modelo de documentos. SQLAlchemy
resuelve las anotaciones al configurar el mapper, no al importar el modulo:
por eso `ast.parse` lo daba por bueno y el nucleo entraba en bucle al
arrancar.

**Verificar la sintaxis no es verificar que arranca.** Es la primera vez que
un error pasa la comprobacion que anadimos y aun asi tumba el sistema.

## Los detectores, juntos
Seis detectores de intencion vivian sueltos en el orquestador, que habia
llegado a 937 lineas. Cada fase anadia otro metodo estatico con su expresion
regular y su propia normalizacion, todas ligeramente distintas.

Ahora viven en `core/intenciones.py`, comparten una sola funcion de
normalizacion, y —lo que mas importa— **el orden esta escrito**:

    encargo > cambio > aviso > informe > prefiltro > conversacion

De lo mas especifico a lo mas general. Antes ese orden estaba implicito en la
secuencia de `if` del orquestador y era invisible. Al reves, "hazme un resumen
del dia sobre la fotosintesis" se tomaria por una peticion de informe.

## Los metodos viejos delegan
`_es_encargo` y compania siguen existiendo, llamando al modulo. Hay tests que
los invocan por su nombre y romperlos por una reorganizacion seria cambiar
comportamiento donde solo queriamos cambiar estructura.

## Lo que NO se ha tocado
`globals.css` sigue con 1.600 lineas. Se ha roto tres veces por ediciones
automaticas, y esa es exactamente la razon para no reorganizarlo hoy: un
fichero fragil se toca cuando hay un motivo, no por orden.

La solucion real ya esta en marcha por otra via — los componentes nuevos
llevan sus estilos dentro— y el CSS global se ira vaciando solo.
