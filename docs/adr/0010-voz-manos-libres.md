# ADR 0010 — Voz manos libres y sintesis por frases

**Estado:** aceptado · **Fecha:** Fase 2D

## Sintesis por frases, no por respuesta
Piper sintetiza cada frase en cuanto el modelo la termina, no al final. Sin
esto, cada respuesta hablada arrancaria con varios segundos de silencio
mientras se genera el texto completo.

La cola es estrictamente secuencial: reproducir la frase 3 antes que la 2
porque tardo menos en sintetizarse haria el audio incomprensible. El orden
importa mas que la velocidad.

Piper corre en CPU. En un Ryzen 5800X sintetiza mas rapido que tiempo real y
no compite por VRAM con el modelo de razonamiento.

## Fin de turno por silencio, con umbral calibrado
El turno se cierra tras 1,1 s de silencio sostenido. El umbral NO es fijo: se
calibra con el ruido real de la habitacion durante los primeros 400 ms. Un
umbral fijo funciona en un sitio y falla en otro.

Y no se corta hasta haber detectado voz: si no, cualquier pausa antes de
empezar a hablar cerraria la grabacion vacia.

## Confianza: mejor pedir que repita
faster-whisper devuelve `avg_logprob` por segmento. Por debajo de -0.9 el
sistema NO envia: pide que se repita.

Motivo: con la memoria curada de la Fase 2B, un mensaje enviado puede
convertirse en un hecho permanente. Repetir una frase cuesta segundos; ir a
buscar un recuerdo falso en la memoria cuesta mucho mas.

## El medidor de nivel es funcional
Sin el no hay forma de distinguir "el microfono no capta" de "no me esta
entendiendo". Cada barra es una lectura real de RMS. Es la unica pieza de la
interfaz que se movia y no existia antes; se anade porque informa, no porque
adorne.

## Las respuestas cortas eran culpa del prompt
No era `num_predict` ni un limite de tokens. El prompt del sistema decia
"Se conciso y concreto", y el modelo obedecia. Se sustituye por una
instruccion que escala la longitud a lo que se pide. `num_predict: -1` se fija
explicitamente para que quede claro que no hay tope artificial.

Es un recordatorio util: antes de buscar el parametro, leer lo que le estas
diciendo al modelo.

## Neon: donde esta el limite
La paleta sube de saturacion y se anaden resplandores, a peticion expresa.
La regla que no se cruza: **el brillo marca actividad real**. Un elemento
encendido significa que ese subsistema esta trabajando. No hay ningun
resplandor decorativo, ninguna barra de progreso falsa, ningun grafico de
relleno. Seria mas "futurista" y haria el producto peor.
