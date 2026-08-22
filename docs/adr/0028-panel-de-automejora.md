# ADR 0028 — El ciclo de auto-mejora, usable

**Estado:** aceptado · **Fecha:** Fase 25

## Por que
Las fases 19 a 24 construyeron el ciclo completo — proponer, ensayar,
aprobar, aplicar — pero solo accesible por `curl`. Una capacidad que no se
puede usar comodamente no se usa, y una que no se usa no se depura.

## Tres botones, tres momentos
- **Aprobar**: decision reversible. No toca el repositorio.
- **Rechazar**: la propuesta muere.
- **Aplicar**: escribe de verdad. Solo aparece en las ya aprobadas.

Separados a proposito. Aprobar es un juicio; aplicar es una operacion que
puede fallar. Juntarlos en un boton haria que un fallo al aplicar dejara una
propuesta marcada como si hubiera funcionado.

## El riesgo se ve antes de leer
El borde izquierdo de cada propuesta lo codifica: rojo alto, violeta medio,
azul apagado bajo. Y los tests se declaran en verde o rojo en la cabecera.

Una propuesta con tests en rojo se muestra igual, no se esconde: que KAIROS
no supiera hacer algo es informacion util.

## El reinicio sigue siendo manual
Tras aplicar, el panel dice el comando exacto. Es deliberado: el reinicio es
el momento irreversible y tener a un humano delante impide que un merge malo
deje KAIROS muerto durante la noche.
