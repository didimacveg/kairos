# ADR 0049 — Trabajar mientras hablas con el

**Estado:** aceptado · **Fecha:** Fase 48

## Por que en pasos
Un modelo escribiendo 3000 palabras de un tiron pierde el hilo a la mitad,
repite ideas y anuncia cosas que luego no cumple.

Con un plan delante y ejecutando paso a paso, cada parte sabe donde encaja y
ve lo ya escrito. El repaso final corrige lo que no cuadra entre partes.

Tres llamadas al modelo en vez de una, y el resultado se sostiene.

## Una tarea a la vez
Dos tareas largas en paralelo compiten por el mismo proveedor y las dos tardan
el doble. Ademas el coste se dispara sin que nadie lo vea venir.

Mientras una tarea corre, la conversacion normal sigue: son llamadas distintas
y no se bloquean entre si. Eso es lo que hace util el segundo plano.

## El progreso se guarda en cada paso
No solo al final. Si el proceso muere a mitad, no se pierde media hora.

## La tarea no toca el sistema
Produce un documento y nada mas. Si algo hay que aplicar, ejecutar o enviar,
pasa por los agentes de siempre y por la confirmacion del usuario.

## Material adjunto
Texto plano, PDF y .docx. El .docx se lee extrayendo el XML directamente, sin
anadir una dependencia entera para sacar parrafos.

El texto extraido se DEVUELVE al usuario antes de encargar nada: asi se ve que
ha entendido KAIROS del documento, en vez de descubrirlo en el resultado.
