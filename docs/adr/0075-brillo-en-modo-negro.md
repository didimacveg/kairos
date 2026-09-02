# ADR 0075 — Apagar la pantalla de verdad

**Estado:** aceptado · **Fecha:** Fase 75

## Por que
Un panel encendido mostrando negro sigue emitiendo luz. En camara se ve gris,
y la transicion a la animacion pierde todo el contraste.

## Dos capas, porque una no basta
**El brillo real**, por el puente y WMI. Solo funciona en portatiles y algunos
monitores: los externos por HDMI o DisplayPort casi nunca exponen el control.

**Un velo visual** al 55%, que funciona siempre. Baja la luminancia percibida
aunque el panel siga al maximo.

Se aplican las dos. Si el brillo real responde, negro profundo; si no, el velo
lo compensa en parte.

## El brillo vuelve pase lo que pase
Se restaura al salir del modo negro, al pulsar Escape, y en la limpieza del
efecto si se cierra la pestana. Dejar la pantalla apagada porque el navegador
se cerro seria un fallo desagradable de diagnosticar.

## La transicion tiene tiempos distintos
Bajar: 1,2 s. De golpe se nota como un fallo del monitor; despacio parece
intencionado.

Subir: a los 250 ms de empezar la salida, ANTES de lanzar la secuencia. Asi
la animacion arranca con la pantalla ya a nivel normal y el destello inicial
se ve como debe.
