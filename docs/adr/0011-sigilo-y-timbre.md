# ADR 0011 — Sigilo K.A.I.R.O.S y control de timbre

**Estado:** aceptado · **Fecha:** Fase 2G

## El sigilo
Peticion: un holograma central estilo JARVIS con el nombre K.A.I.R.O.S.

Se implementa como SVG con anillos concentricos. La regla del proyecto se
mantiene: **cada anillo codifica un estado real**.

- exterior: el arco cubre la fraccion de agentes que responden al health check
- medio: gira solo mientras el modelo genera
- interior: pulsa solo cuando el microfono escucha
- nucleo: rojo si hay salida a Internet permitida

Si el sistema esta parado, el sigilo esta quieto. Un adorno que gira siempre no
dice nada; uno que gira cuando la maquina piensa te dice que piensa.

Al empezar la conversacion el sigilo se retira a la cabecera en version
compacta, sustituyendo al diafragma anterior.

## Por que se callaba a mitad de respuesta
Tres fallos encadenados, todos mios:

1. `SpeakIn` validaba `max_length=1200`. Un parrafo sin puntuacion superaba el
   limite y FastAPI devolvia 422 de validacion.
2. FastAPI devuelve `detail` como texto en errores propios pero como ARRAY de
   objetos en los de validacion. El cliente hacia `new Error(array)`, de ahi el
   `[object Object]` en pantalla.
3. El `catch` de la cola hacia `break`. Un fallo en UNA frase enmudecia el
   resto de la respuesta.

Correcciones: el esquema ya no valida longitud (se recorta con criterio en el
servidor), los detalles de error se traducen a texto legible, y un fallo de
frase ya no rompe la cola.

Ademas se trocean los fragmentos de mas de 400 caracteres por comas: Piper no
deberia recibir parrafos enteros, ni por latencia ni por memoria.

## Marcado fuera de la voz
El modelo escribe `**negrita**` y Piper lo pronunciaba. Se limpia el marcado
antes de sintetizar. El texto en pantalla conserva su formato: solo se limpia
lo que va a la voz.

## Timbre mas grave
Piper no expone control de tono. Se baja reescribiendo la frecuencia de
reproduccion del WAV — el truco del vinilo a menos revoluciones. Baja el tono y
alarga el audio a la vez, asi que se compensa con `length_scale`.

Es crudo, pero no necesita librerias de procesado de senal ni GPU, y es
reversible con dos variables de entorno. Voz por defecto: `es_ES-sharvard`,
mas sobria que `davefx`. Ambas quedan en la imagen para poder cambiar sin
reconstruir.
