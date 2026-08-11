# ADR 0007 — La memoria se cura, no se acumula

**Estado:** aceptado · **Fecha:** Fase 2B

## Contexto
Hasta 2A, el orquestador indexaba literalmente cada mensaje del usuario. En un
solo dia de uso real la memoria contenia: preguntas ("¿cuando trabajo mejor?",
dos copias identicas), peticiones ("escribeme una historia sobre un farero"),
saludos ("Despierta") y dos hechos contradictorios conviviendo con similitud
casi identica (trabaja mejor de noche / por las tardes).

Consecuencia medida: a una pregunta sobre termodinamica, el sistema recupero
seis recuerdos irrelevantes y respondio hablando de los horarios de trabajo del
usuario en lugar de entropia. La memoria degradaba el razonamiento.

Ademas solo se indexaba el lado del usuario. Nunca se guardaba lo que KAIROS
respondio, asi que el sistema recordaba haber recibido una peticion sobre un
farero pero no el farero.

## Decision
La escritura en memoria deja de ser automatica. Un extractor decide, por cada
intercambio completo, si hay algun hecho duradero sobre el usuario. Lo que se
guarda son hechos en tercera persona, no transcripciones.

Antes de escribir, cada candidato se consolida contra lo existente:
- similitud >= 0.95 → duplicado, se descarta
- similitud >= 0.82 → mismo tema con dato nuevo, el anterior pasa a `superseded`
- por debajo → hecho independiente, se guarda

El umbral de recuperacion sube de 0.35 a 0.55.

## Por que el modelo local decide
Un clasificador por reglas no distingue "prefiero trabajar de noche" de
"cuentame que es la noche polar". La extraccion cuesta una llamada extra al
LLM, pero ocurre despues de que el usuario ya tenga su respuesta.

Contrapartida asumida: un modelo de 8B se equivoca. La salida se valida con
dureza y ante la duda se descarta. Preferimos perder un hecho que ensuciar la
memoria: un recuerdo falso contamina todas las busquedas futuras; uno ausente
solo obliga a repetirlo.

## Por que nada se borra
`superseded` y `discarded` son estados, no DELETE. La deteccion de
contradiccion es una heuristica de recencia y falla con hechos parecidos pero
ambos ciertos ("mi hermana estudia derecho" / "mi hermano estudia derecho").
Un estado reversible convierte ese fallo en molestia; un DELETE lo convierte en
perdida de datos.

## Consecuencias
- Latencia: +1 llamada al LLM por turno (~1-2 s), no percibida por el usuario.
- La memoria acumulada hasta hoy sigue sucia. Se limpia con
  `python -m kairos.cli memory-audit`, que propone y solo actua con `--apply`.
- Los umbrales son heuristicas sin validar a escala. Revisar cuando la memoria
  pase de unos cientos de entradas.
