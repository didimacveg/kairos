# ADR 0031 — Un solo microfono, y vive en la web

**Estado:** aceptado · **Fecha:** Fase 28

## El problema
KAIROS tenia dos oidos: el del puente (escucha ambiente en Windows) y el de
la web (Alt+K). Funcionalmente distintos, con comportamientos distintos, y
obligaban a saber por cual hablar segun lo que quisieras.

Es una fuga del diseno interno a la experiencia. El usuario no deberia saber
que existe un puente.

## Decision
**La escucha vive en la web. El puente solo actua.**

El navegador tiene el microfono, hace la deteccion de voz y la palabra de
activacion, y manda al nucleo. El puente conserva unicamente lo que solo el
puede hacer: abrir aplicaciones, colocar ventanas, hablar por los altavoces.

## Lo que se gana
- **Un solo sitio donde hablarle.** Se acabo elegir canal.
- **Mismo comportamiento en el movil.** Antes la escucha ambiente era
  exclusiva del PC porque vivia en el puente; ahora funciona igual en el
  telefono con HTTPS.
- **El puente pasa a ser invisible.** Es plomeria, y la plomeria no deberia
  notarse.

## Lo que cuesta
La pestana de KAIROS tiene que estar abierta para que oiga. Se resuelve
abriendola en modo aplicacion al arrancar el PC: ventana propia, sin barra de
direcciones, con el permiso de microfono recordado.

Es un coste menor que el anterior, que era tener que entender la arquitectura
para usar el asistente.

## Donde vive KAIROS
El nucleo se queda en casa, en el servidor. La interfaz se desplaza contigo.
Es la misma idea de siempre llevada hasta el final: KAIROS no es la ventana
ni el puente — es lo que corre en casa, y le hablas desde donde estes.
