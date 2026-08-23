# ADR 0040 — Componer formulas y codigo sin dependencias

**Estado:** aceptado · **Fecha:** Fase 39

## El problema
KAIROS ya resolvia fisica y matematicas. Lo que devolvia era texto plano con
asteriscos y barras invertidas de LaTeX sin interpretar — util para leer con
esfuerzo, inutil para estudiar.

## Por que escrito a mano
Dos alternativas descartadas:
- **CDN de KaTeX**: KAIROS funciona sin Internet por diseno. Una fuente
  externa rompe eso.
- **react-markdown + katex como dependencias**: ~400 KB y dos librerias que
  mantener para cubrir un subconjunto que aqui ocupa doscientas lineas.

## Lo que cubre y lo que no
Cubre encabezados, listas, citas, negrita, cursiva, codigo en linea y en
bloque, y formulas con fracciones compuestas de verdad, raices, exponentes,
subindices, letras griegas y simbolos matematicos.

No cubre LaTeX completo: matrices, integrales con limites complejos y
diagramas se muestran en monoespaciada legible. **Es preferible ensenar la
formula cruda que una version mal compuesta**, porque una formula rota se lee
como una formula distinta.

## El formato solo cuando toca
El prompt aprende a distinguir: por escrito puede usar formato porque la
interfaz lo compone; hablando, el formato sobra. Una respuesta de voz llena de
encabezados es ruido.

## Modo estudio
Ante un ejercicio, KAIROS explica el razonamiento y el principio que aplica,
no solo el resultado. Y si el enunciado tiene un error, lo dice.

Es una decision sobre para que sirve: un sistema que da resultados sin
explicacion es una calculadora cara.
