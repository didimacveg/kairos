# ADR 0050 — Smith trabaja en segundo plano, y el test va aparte

**Estado:** aceptado · **Fecha:** Fase 49

## El 500 que no era un 500
Smith tarda minutos: dos llamadas al modelo, el ensayo completo en el forge, y
la relectura. Cualquier navegador corta la peticion mucho antes.

El usuario veia un 500 mientras el servidor seguia trabajando — y cuarenta
segundos despues la propuesta aparecia sola. El error era del cliente
rindiendose, no del servidor fallando.

Ahora la ruta confirma al instante y el trabajo va en segundo plano. El panel
refresca hasta que llega.

## El test, en una llamada dedicada
Cuarto intento con esto. Los tres anteriores:
1. instrucciones mas duras en el prompt
2. tests reales del repositorio en el contexto
3. una relectura que buscaba tests que faltaran

Ninguno funciono de forma fiable, y ahora entiendo por que: **pedir codigo y
test en la misma respuesta reparte la atencion del modelo**, y el test siempre
pierde. No es que no sepa escribirlo; es que ya ha "terminado" mentalmente
cuando llega ahi.

Una llamada con una sola tarea —el codigo ya escrito delante, escribe el
test— si lo produce.

## La leccion, generalizada
Cuando un modelo omite sistematicamente una parte de una respuesta compleja,
la solucion no es insistir en las instrucciones: es **separar esa parte en su
propia llamada**.

Es la tercera vez que este proyecto llega a la misma conclusion por caminos
distintos: dos pasadas para elegir ficheros, una relectura aparte, y ahora el
test. Una tarea por llamada.
