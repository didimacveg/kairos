# ADR 0026 — Smith: KAIROS escribe sus propios parches

**Estado:** aceptado · **Fecha:** Fase 22

## El ciclo completo
    peticion -> Smith lee su codigo y escribe los ficheros resultantes
             -> difflib calcula el parche
             -> Forge lo ensaya aislado y sin red
             -> se crea una PROPUESTA con diff, tests y riesgo
             -> Diego aprueba o rechaza

## Ficheros completos, no diffs
El modelo NO escribe diffs unificados. Escribe el contenido completo del
fichero resultante y el diff lo calcula `difflib`.

Motivo: los modelos producen diffs rotos con mucha frecuencia — numeros de
linea equivocados, contexto que no coincide, cuentas de @@ mal. Un parche que
no aplica es un ensayo perdido. Pedir el fichero entero elimina esa clase de
fallo: el parche o es valido o no existe, nunca "casi valido". Cuesta mas
tokens y sale a cuenta.

## Dos pasadas al modelo
Primera: "que ficheros necesitas ver". Segunda: "escribe el cambio".

Meter el repositorio entero en contexto es caro y da peores resultados — el
modelo se pierde. Dos pasadas producen mejores parches y salen mas baratas.

## El riesgo lo decide la ruta, no el modelo
Un modelo que se autoevalua el riesgo tiende a decir "bajo". Las rutas
sensibles (auth, modelos de datos, el propio Smith, el Forge, el puente, el
compose) fuerzan riesgo alto desde codigo.

## Lo que Smith no puede hacer
- Aplicar nada, ni con los tests en verde.
- Escribir en el repositorio: lo tiene montado en solo lectura.
- Leer secretos: `.env`, tokens y credenciales estan excluidos por patron. El
  contenido va a un modelo remoto, y una clave en el contexto es una clave
  filtrada.
- Salir del arbol del repositorio: las rutas se resuelven y se comprueban.
- Crear propuestas sin ensayar: sin Forge activo, Smith ni se registra.

## Los ensayos fallidos tambien se guardan
Si los tests fallan, la propuesta se crea igualmente, marcada en rojo y con la
salida del fallo. Un intento fallido es informacion: dice que KAIROS no supo
hacerlo y por que.

## Lo que falta
El aplicador: merge de la rama aprobada y reinicio con rollback automatico si
el arranque falla. Es la unica pieza que escribe en el repositorio real, y por
eso va aparte y con su propia revision.
