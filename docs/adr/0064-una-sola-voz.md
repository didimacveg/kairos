# ADR 0064 — Una sola voz para todos los agentes

**Estado:** aceptado · **Fecha:** Fase 64

## El problema
Los prompts vivian dentro de cada agente y cada fase anadia reglas al que
tocaba. El resultado eran ocho voces distintas: el informe hablaba de una
forma, el razonamiento de otra, la curiosidad de otra.

Peor: reglas que deberian valer para todos —no usar muletillas, no inventar,
decir cuando no se sabe— estaban en unos y en otros no, segun cuando se
escribieron.

## La estructura
    IDENTIDAD    quien es KAIROS
    HONESTIDAD   que hacer cuando no sabe algo
    REGLAS       como escribe / como habla
    TAREA        lo especifico del agente

**El orden no es casual.** Un modelo aplica peor las reglas que llegan
DESPUES de la tarea concreta: para entonces ya esta pensando en el problema.

## Escrito y hablado son prompts distintos
Lo que se lee en pantalla y lo que se pronuncia no se escriben igual:
- por escrito el formato ayuda; hablado se pronunciaria ("asterisco asterisco")
- al oido no se puede releer, asi que las frases van mas cortas
- una muletilla hablada pesa el doble que escrita

Antes esto se corregia a mano en el agente de voz. Ahora el razonamiento sabe
si su respuesta se va a hablar y elige.

## Las reglas llevan su motivo
"No inventes datos" se sigue peor que "no inventes datos PORQUE quien lo lee
lo dara por bueno". Un modelo aplica mejor una regla cuando entiende que
protege.

## Criterio propio, explicito
La identidad dice que si Diego plantea algo que no cuadra, hay que decirselo.
El lo pidio expresamente, y sin ponerlo por escrito un modelo tiende a
asentir.
