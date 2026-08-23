# ADR 0039 — Modo chat: KAIROS sin instrumentos

**Estado:** aceptado · **Fecha:** Fase 38

## Por que
El panel principal es un salpicadero: sigilo, telemetria, trazas, agentes.
Sirve para operar el sistema y estorba para estudiar. Con un ejercicio de
fisica delante quieres el texto grande, el hilo entero visible y nada mas.

## Es la MISMA conversacion
Mismo hilo, misma memoria, mismos adjuntos, mismo modelo. No es otro KAIROS
ni un modo tonto: es la misma cabeza sin el salpicadero.

Esto importa porque la alternativa —un chat aparte con su propio estado—
partiria la memoria en dos y KAIROS dejaria de recordar lo hablado segun por
donde entraras.

## Foto directa
El boton de foto usa `capture="environment"`: en el movil abre la camara
trasera directamente, sin pasar por la galeria. Es el gesto que quieres
cuando tienes el ejercicio en papel delante.

Y usa el mismo endpoint que los adjuntos del panel: para el nucleo, una foto
del movil y una imagen pegada con Ctrl+V son lo mismo.

## Sobre saber fisica y matematicas
No hizo falta anadir nada. KAIROS razona con Claude Sonnet, que resuelve
bachillerato sin problema. Lo que faltaba era una interfaz donde eso fuera
comodo, no mas capacidad.

Merece la pena anotarlo: no todas las carencias son de capacidad. Algunas son
de presentacion, y confundirlas lleva a construir de mas.
