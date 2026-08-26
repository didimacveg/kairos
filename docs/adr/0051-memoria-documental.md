# ADR 0051 — Los apuntes de Diego, indexados

**Estado:** aceptado · **Fecha:** Fase 51

## Que resuelve
KAIROS resolvia fisica en general. Con esto responde con SU temario: los
apuntes de su profesor, el libro de su curso, la notacion de su clase.

## Tabla aparte de la memoria personal
La memoria son cosas sobre Diego; esto son documentos. Mezclarlas haria que un
apunte de historia compitiera con "le gusta el heavy metal" en la misma
busqueda, y las dos cosas saldrian peor.

## Troceado por parrafos, no por caracteres
Cortar cada 500 caracteres parte frases y conceptos por la mitad, y un trozo
que empieza a media explicacion no sirve al recuperarlo.

Se agrupan parrafos hasta el tamano objetivo y se corta en el limite de
parrafo mas cercano. Un parrafo gigante se parte por frases, nunca a media.

## El titulo va en cada trozo
"La energia cinetica es 1/2mv²" recuperado suelto podria venir de cualquier
sitio. Con "[Fisica 1BACH · Tema 3]" delante, KAIROS sabe de que habla.

## Solapamiento
250 caracteres del trozo anterior se arrastran al siguiente: un concepto que
cae en la frontera aparece en los dos vecinos y se recupera venga la pregunta
por donde venga.

## Se consulta siempre, sin palabra clave
Si has subido tus apuntes de fisica, quieres que los use al preguntar de
fisica, no tener que decirselo. Si nada supera el umbral de similitud, no se
anade nada y la respuesta sale como siempre.

## Si contradicen al modelo, se dice
El prompt es explicito: si los apuntes contradicen lo que el modelo sabe, hay
que senalarlo en vez de elegir uno en silencio. Un apunte puede estar mal, y
un modelo tambien.
