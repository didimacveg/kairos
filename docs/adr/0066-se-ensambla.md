# ADR 0066 — Se ensambla, no explota

**Estado:** aceptado · **Fecha:** Fase 66

## La referencia
La interfaz de EDITH en Lejos de casa. Lo que la hace funcionar no es el
destello: es que **el sistema se construye a la vista**, capa por capa, desde
el centro hacia fuera.

## Por que las cinco versiones anteriores fallaban
Todas eran una explosion: los elementos salian disparados y desaparecian. Eso
se lee como un SUCESO, no como algo poniendose en marcha.

Aqui cada pieza aparece, **SE QUEDA**, y encima aparece la siguiente. Al
final hay una interfaz completa girando, no un vacio.

## El trazo se recorre, no se escala
Los anillos usan `stroke-dashoffset` animado: el circulo se DIBUJA de un
extremo al otro. Escalar un circulo desde cero parece que aparece; dibujarlo
parece que se construye.

Es la diferencia entera entre las dos lecturas.

## Siete segundos, en capas
    0.0  el nucleo late
    0.4  reticula de fondo
    0.8  anillo interior + 24 tics
    1.4  anillo medio, girando al reves
    2.0  anillo exterior en cuatro sectores + 48 tics
    2.4  lineas de sistema, tipo terminal
    3.2  la marca se ensambla letra a letra
    4.4  el diagnostico
    5.9  los paneles entran escalonados

## Sigue siendo ligera
Un solo SVG, cero filtros. Las rotaciones van en GRUPOS, no en elementos
sueltos: rotar un grupo es una operacion de composicion, rotar cuarenta lineas
es cuarenta operaciones.

Los tics se calculan una vez al montar, no por fotograma.
