# ADR 0013 — HUD, interrupcion y prompt limpio

**Estado:** aceptado · **Fecha:** Fase 2I

## Estructura ornamental si; movimiento falso no
El HUD gana muchos anillos, marcas, corchetes y graduaciones. La regla del
proyecto se afina en vez de romperse:

**Estructura fija que siempre se ve igual = la caja del instrumento.** Un
anillo grabado no miente sobre nada.

**Movimiento o longitud variables = telemetria, y tiene que ser real.** Nada
gira, se enciende o cambia de tamano sin un valor detras: agentes vivos,
generacion en curso, recuerdos consultados, microfono abierto, salida de datos.

Si KAIROS esta parado, todo lo que se mueve esta quieto.

La paleta pasa a dominancia cian. El laton se reserva para el anillo de datos,
que solo gira durante la generacion: el color caliente sigue significando "la
maquina esta trabajando".

## Interrupcion
Antes, hablar mientras KAIROS hablaba producia dos voces solapadas: el sistema
seguia con la respuesta anterior.

Ahora el microfono no se cierra nunca durante la sesion. Cambia de modo:
- turno del usuario -> graba
- turno de KAIROS  -> vigila el nivel sin grabar

Detectar voz sostenida durante la respuesta aborta el flujo, calla la cola de
audio y abre turno nuevo. Interrumpir significa interrumpir.

El umbral de interrupcion es 2,2x el normal y exige 260 ms sostenidos. El
altavoz entra por el microfono y la cancelacion de eco del navegador ayuda pero
no es perfecta; sin ese margen, KAIROS se interrumpiria a si mismo.

## El prompt
Dos correcciones:

1. El bloque MEMORIA deja de ser tema de conversacion. Nada de "recupere
   informacion de conversaciones anteriores" ni citas de similitud. El usuario
   ya sabe lo que ha contado.
2. Sin acceso a Internet ni a la hora actual, y con fecha de corte: cuando le
   pregunten por algo de hoy debe decirlo en UNA frase. Antes soltaba parrafos
   explicando lo que no podia hacer, que es peor que un "no lo se".

Esto NO le da la capacidad. Solo hace honesto y breve el fallo. La capacidad
real es una herramienta de busqueda web, y va aparte.
