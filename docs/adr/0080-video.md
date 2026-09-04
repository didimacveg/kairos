# ADR 0080 — El valor no es generar, es comprimir

**Estado:** aceptado · **Fecha:** Fase 80

## La tesis
No se le pide a un modelo que invente un video. Se le pide que lea una
grabacion de veinte minutos y diga que treinta segundos merecen la pena, con
los tiempos exactos.

Eso si es viable, y es lo que de verdad cuesta tiempo al editar.

## Por que funciona sin ver el video
En una grabacion hablada, lo que decide donde cortar es lo que se DICE. La
imagen importa para el montaje fino, no para elegir los momentos.

Por eso basta la transcripcion — y por eso hacen falta marcas de tiempo POR
PALABRA, no por segmento. Deepgram las da; Whisper local solo por segmento.

## KAIROS no corta
Devuelve los comandos. Un corte mal calculado sobre el fichero original es
irrecuperable, y la regla de "avisa, no actua" aplica igual aqui.

El volumen se monta en **solo lectura** para que sea imposible por
construccion, no solo por convencion.

## Los margenes importan
0.3 s antes de la primera palabra, 0.4 s despues de la ultima. Cortar justo
encima suena amputado, y dejar respirar el final es lo que separa un montaje
bueno de uno nervioso.

El margen final es mayor que el inicial a proposito: el oido perdona una
entrada seca mucho mejor que una salida cortada.

## Puede reordenar
El prompt pide explicitamente ordenar los cortes por como cuentan mejor la
historia, no por como aparecen en la grabacion. Un buen montaje no respeta el
orden original.
