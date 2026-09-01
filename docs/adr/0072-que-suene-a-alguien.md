# ADR 0072 — Que suene a alguien, no a un buscador

**Estado:** aceptado · **Fecha:** Fase 72

## El problema
Preguntado por los incendios de Madrid, KAIROS respondio con una lista de
cuentas de Twitter donde mirar. Preguntado dos cosas seguidas, contesto "son
dos preguntas distintas, te respondo" y las enumero.

Eso es lo que hace un asistente generico. Y Diego dijo la frase que resume el
problema: seguiria usando ChatGPT antes que a KAIROS.

## Lo que se prohibe explicitamente
- Enumerar las partes de una pregunta antes de contestarlas
- Ofrecer listas de sitios donde buscar lo que no sabe
- Empezar con "claro", "por supuesto", "excelente pregunta"
- Recordar lo hablado antes si no viene a cuento — el usuario estaba ahi
- Cerrar con "espero que te sirva"
- Mencionar que es una IA o que tiene limitaciones

Prohibirlo por escrito funciona mejor que pedir "se natural". Un modelo sabe
evitar una lista concreta; "natural" no le dice nada.

## No saber es una respuesta completa
"No lo se" y para. Si ha buscado y no hay nada: "he buscado y no encuentro
nada de hoy" — eso es informacion. Una lista de periodicos donde mirar, no.

## Hablado y escrito son prompts distintos
Lo hablado prohibe TODO formato, limita a tres o cuatro frases, y pide que
escriba como se habla: "son y media", no "la hora actual es las nueve y
treinta".

## Lo que NO arregla esto
La latencia. Cuatro de los quince segundos son del modelo generando y eso no
se toca desde aqui. Lo que baja la sensacion de espera es que la voz empiece
con la primera frase en vez de con la respuesta entera — otra fase.
