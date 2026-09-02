# ADR 0076 — Brillo por DDC/CI

**Estado:** aceptado · **Fecha:** Fase 76

## Por que no vale WMI
`WmiMonitorBrightness` solo existe en portatiles. Los monitores externos —los
dos de Diego, un Acer KG241Y S y un GN02— responden "Not supported".

DDC/CI habla con el monitor por el canal de datos del propio cable de video.
Es la unica via que llega a un monitor de sobremesa.

## La secuencia de la toma
    modo negro   los dos a 0
    al lanzar    los dos a 100, 300 ms antes del destello
    +5 segundos  vuelven a 40 y 85, los niveles de trabajo

El salto de 0 a 100 en el instante de la rotura es lo que hace la toma: la
pantalla pasa de apagada a maximo en el mismo fotograma en que la animacion
detona.

## La restauracion la programa el puente
No la interfaz. Si el navegador se cierra a mitad de la secuencia, el brillo
vuelve igualmente — un temporizador en el proceso que sobrevive.

## Un monitor sin DDC no bloquea al otro
Si uno falla, se anota y se sigue con el resto. Con dos monitores, que uno no
tenga DDC/CI activado no debe impedir que el otro funcione.
