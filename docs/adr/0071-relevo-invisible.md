# ADR 0071 — El relevo entre dos negros

**Estado:** aceptado · **Fecha:** Fase 71

## El parpadeo al lanzar desde pantalla negra
El modo negro desaparecia de golpe y la secuencia nacia. Dos capas negras
superpuestas, una muriendo y otra naciendo, producen un parpadeo aunque sean
del mismo color: el navegador recompone ambas y el fondo asoma un fotograma.

**Solucion en dos partes:**
1. El modo negro tiene fase de SALIDA: el texto se apaga y el anillo se
   contrae en 450 ms; solo entonces se lanza la secuencia. El negro nunca se
   interrumpe.
2. La secuencia arranca con `background: #000` —el mismo negro— en vez del
   azulado del tema. Los dos negros son identicos y el relevo es invisible.

## Mas capas, mismo coste
Anadido sin filtros: reticula de fondo, barrido horizontal en la rotura,
cuatro destellos secundarios que caen tras el principal, un tercer anillo muy
lento y 32 trazos radiales alrededor de la marca.

Todo son divs y gradientes animando `scale`, `rotate` y `opacity`. La GPU los
compone sin repintar, asi que treinta elementos mas no cuestan fotogramas.

**Lo que cuesta rendimiento son los filtros y los repintados, no el numero de
elementos que solo se transforman.** Es lo contrario de lo que asumi en las
primeras versiones, donde recorte elementos y el problema seguia.
