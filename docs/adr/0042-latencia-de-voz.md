# ADR 0042 — Dos modelos de voz, y ningun filtro en la animacion

**Estado:** aceptado · **Fecha:** Fase 41

## La latencia
Reconocer "modo negro" tardaba segundos. La cadena era: esperar 700 ms de
silencio, subir el audio, y transcribir con Whisper **medium** en CPU.

Usar el modelo grande para reconocer dos palabras conocidas es como leer un
diccionario para comprobar una firma.

**Solucion**: un segundo modelo, `base`, cargado solo para segmentos cortos.
Los de menos de 60 KB —que son siempre ordenes, no frases— van por el rapido.
El resto sigue con `medium`, donde la precision importa.

Y el corte por silencio baja de 700 a 520 ms. Por debajo de ~450 corta a media
pausa.

## La animacion
El culpable era `filter: blur(48px)` sobre un elemento de 90vw **animado**. Un
desenfoque gaussiano de ese radio sobre esa superficie se recalcula entero en
cada fotograma, y ningun navegador lo hace a 60 fps.

Sustituido por un gradiente radial estatico con muchas paradas: el degradado
ya tiene aspecto difuminado y cuesta cero.

Ademas: 12 rayos en vez de 20, 16 chispas en vez de 28, un `text-shadow` por
letra en vez de tres, y `contain: layout paint` en el lienzo.

Resultado: **ningun filtro en ningun elemento**. Solo `transform` y `opacity`,
que la GPU compone sin repintar.

## La leccion
Las dos causas eran la misma: **usar la herramienta pesada para el trabajo
ligero**. El modelo grande para dos palabras; el desenfoque real para simular
un resplandor que un gradiente ya daba.
