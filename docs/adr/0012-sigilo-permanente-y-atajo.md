# ADR 0012 — El sigilo es la interfaz, no la pantalla de espera

**Estado:** aceptado · **Fecha:** Fase 2H

## Decision
El sigilo K.A.I.R.O.S ocupa el centro de forma permanente, tambien mientras
KAIROS responde. La conversacion se reparte en dos:

- **Carril izquierdo**: el registro completo, en pequeno y recortado a seis
  lineas por entrada. Sirve para localizar, no para leer entero.
- **Bajo el sigilo**: la ultima respuesta a tamano legible.

## El problema que esto crea, y como se resuelve
Una respuesta larga centrada bajo un grafico es peor para leer que una
columna de texto alineada a la izquierda. Es un coste real de la decision.

Se mitiga limitando el ancho a 44rem y dejando el area con scroll propio: el
sigilo no se mueve aunque la respuesta sea larga. Si con el uso resulta
incomodo leer respuestas de varios parrafos ahi, la salida es un modo
"lectura" que expanda el texto sobre el escenario — no volver al layout
anterior.

## Anillos nuevos
Se anaden dos elementos, ambos con dato detras:
- **barrido**: arco de gradiente que gira rapido solo durante la generacion
- **marcas de memoria**: una por recuerdo consultado en el ultimo turno

Sigue sin haber un solo elemento decorativo. Si KAIROS esta parado, el sigilo
esta quieto.

## Atajo de teclado
`Alt+K` o `Alt+7` abren y cierran la sesion de voz. Es un atajo **de la
pestana**: solo funciona con la ventana enfocada.

Un atajo global de Windows —que responda con KAIROS minimizado, o que lo abra
si esta cerrado— necesita un proceso en el host. El navegador no puede
registrar hotkeys del sistema ni abrir aplicaciones, por diseno del sandbox.
Eso es la Fase 2E.

## Limite del timbre
`pitch` baja a 0.84 y `length_scale` sube a 1.16 para compensar. Por debajo de
~0.80 la voz empieza a sonar submarina: el metodo baja tono y formantes a la
vez, y la voz humana no funciona asi.

Una voz realmente tipo JARVIS —grave, resonante, con presencia— necesitaria un
motor con clonacion de voz (XTTS-v2, F5-TTS) corriendo en GPU, ~2 GB de VRAM
que hoy no sobran. Queda anotado para cuando se resuelva el presupuesto de
memoria grafica.
