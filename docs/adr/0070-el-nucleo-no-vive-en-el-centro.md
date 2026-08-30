# ADR 0070 — El núcleo no vive donde vive la marca

**Estado:** aceptado · **Fecha:** Fase 70

## El fallo de las nueve versiones anteriores
El nucleo latia en el centro exacto donde despues aparecia la palabra. Da
igual cuanto se ajustaran los tiempos: o se veia a traves de las letras, o las
tapaba al expandirse.

**Ajustar el CUANDO no arregla un problema de DONDE.**

## La solucion
El nucleo vive ARRIBA, al 32% de la altura, sobre el espacio donde ira la
marca. Late ahi, y cuando rompe, la onda DESCIENDE hasta el centro y deposita
la palabra.

El movimiento gana direccion: algo llega y deja algo. Antes solo habia una
explosion en el sitio.

## La marca es UN bloque
Palabra, linea y subtitulo comparten la misma animacion, en el mismo elemento
padre. No son tres elementos coordinados con retardos parecidos — son uno solo
con tres partes.

Por eso el subtitulo llevaba cinco versiones llegando tarde: eran animaciones
distintas y bastaba un ajuste para desincronizarlas. Ahora es imposible que
se separen.

## Ocho segundos
    0.0-1.8  el nucleo late arriba, siete pulsos acelerando
    1.8-2.4  rompe y la onda desciende
    2.4      LA MARCA ENTERA, de golpe, con la onda llegando
    2.5-6.5  estructura: orbitas, datos, barra de carga, marco
    6.5-8.0  todo se desvanece sobre negro
    8.0      entran los paneles

## Y el saludo
Suena a los 2,6 s, justo cuando la marca esta en pantalla. El componente lo
dispara; no depende de ningun numero escrito en otro fichero.
