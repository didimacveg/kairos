# ADR 0067 — Sustituir por linea, no por patron

**Estado:** aceptado · **Fecha:** Fase 67

## El disparador que nunca se escribio
Tres parches dijeron "+ Console: disparador conectado" y **ninguno lo
escribio**. El patron de texto no coincidia —espaciado distinto— y el parche
lo daba por hecho sin comprobar.

Ahora se busca la LINEA que contiene `<ModoNegro`, se sustituye entera, y
despues se relee el fichero del DISCO para confirmar que la prop esta.

**Un parche que informa de lo que intento en vez de lo que consiguio es peor
que uno que falla ruidosamente.**

## La animacion, septima version
Vuelve al planteamiento que si funcionaba —carga, rotura, marca— y anade lo
que faltaba: datos flotando a los lados y orbitas que se quedan girando.

La version EDITH fallo porque todo se DIBUJABA despacio: quedaba estatica y
lenta. El suceso central tiene que tener fuerza; los datos van alrededor de
el, no en su lugar.

## Diez segundos
    0.0-2.0  el punto late siete veces, acelerando
    2.0-3.5  rotura: onda y tres anillos
    2.6      las esquinas del marco
    3.4-9.0  los datos entran uno a uno por los dos lados
    3.0-9.0  dos orbitas girando en sentidos opuestos
    4.5-9.5  la marca letra a letra
    8.7      los paneles entran escalonados
