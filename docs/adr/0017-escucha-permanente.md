# ADR 0017 — Escucha permanente y ordenes de perfil

**Estado:** aceptado · **Fecha:** Fase 5

## Escucha sin pulsar nada
El microfono esta siempre abierto, pero **casi nunca se transcribe**. Un
detector de energia con umbral autocalibrado decide que trozos contienen voz;
solo esos van a Whisper. En una habitacion en silencio el coste en reposo es
practicamente cero.

Dos fases:
1. **Espera** — segmentos de hasta 3 s, transcritos solo para buscar la
   palabra de activacion. Si no aparece, se descartan.
2. **Escucha** — tras oir "kairos", graba la orden completa (hasta 12 s).

Si la orden venia en la misma frase ("kairos, abre el perfil trabajo") no se
pide nada mas: se ejecuta directamente.

## Por que no openWakeWord
openWakeWord es mas eficiente, pero sus modelos preentrenados no incluyen
"kairos" y entrenar uno propio son horas de trabajo y datos. Reutilizar el
Whisper que ya corre en la maquina da una palabra de activacion configurable
—se puede cambiar editando una linea— a cambio de algo mas de CPU. Con VAD
delante, ese coste solo aparece cuando alguien habla.

Variantes fonéticas incluidas ("cairos", "kairo", "cairo") porque Whisper
transcribe nombres propios de forma inconsistente.

## Privacidad
En fase de espera el audio vive en memoria unos segundos y se descarta. No se
escribe a disco, no se guarda en la memoria semantica, y no sale de la maquina:
Whisper corre en local aunque el razonamiento este en la nube.

## Las ordenes NO pasan por el modelo
"Abre el perfil trabajo" se interpreta con cuatro expresiones regulares, no
con el LLM. Es deliberado: un modelo puede alucinar "cierra el perfil trabajo"
a partir de una conversacion cualquiera; un patron fijo sobre tu voz, no.

Todo lo que no encaja con esos patrones no toca el escritorio.

## Cierre de perfiles
`close_profile` solo cierra las ventanas que ese perfil declara, y por
WM_CLOSE: cada aplicacion decide si guardar o preguntar. Nunca se mata un
proceso. Cerrar sin guardar por orden de un sistema automatico es exactamente
el dano irreversible que este diseno evita.

## Cadenas
Una frase puede encadenar: "papi esta en casa" pone la cancion y despues abre
el perfil trabajo. Se declara con `then` en la configuracion, no en codigo.
