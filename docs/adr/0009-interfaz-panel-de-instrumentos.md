# ADR 0009 — La interfaz es un panel de instrumentos

**Estado:** aceptado · **Fecha:** Fase 2F

## Contexto
Peticion: una interfaz "mas futurista y avanzada, mas Tony Stark".

## Decision
Se toma la direccion, pero ejecutada como **instrumentacion**, no como
ciencia ficcion decorativa.

La lectura facil de "Stark" es azul neon, hologramas y rejillas que giran. Es
tambien lo que hace cualquier interfaz que quiere parecer futurista, y en dos
dias cansa. Lo que hace JARVIS memorable en las peliculas no es el brillo: es
que la maquina le ensena a Tony sus propias constantes mientras trabaja.

KAIROS ya tiene esos numeros y son reales: agentes vivos, modelo cargado,
latencia medida, recuerdos consultados con su coincidencia, estado de la
salida de datos. La interfaz los pone en primer plano.

Regla que se sigue en todo el diseno: **ningun indicador es decorativo.** Si
un numero aparece en pantalla es porque el sistema lo mide. Una barra de
progreso falsa o un grafico de relleno serian mas "futuristas" y harian el
producto peor.

## Elementos
- **Tira de telemetria** (firma): lectura continua en la cabecera.
- **Diafragma**: unico movimiento continuo, solo gira cuando KAIROS genera.
- **Columna de instrumentos**: responde a "por que ha dicho eso".
- **Barras de coincidencia**: la longitud ES la similitud, no un adorno.
- **Secuencia de arranque**: comprobaciones reales de nucleo y sesion. Si el
  nucleo esta caido lo dice antes de pedir una contrasena inutil.

## Color con significado
- laton `#d9a441` — el sistema actuando en local
- hielo `#74b8cc` — dato medido
- brasa `#d2593f` — datos saliendo de la maquina

El tercero no deberia verse nunca en una instalacion bien configurada. Que la
privacidad tenga color propio es intencionado.

## Restricciones respetadas
- **Sin fuentes remotas ni CDN.** KAIROS debe verse identico con el router
  desenchufado. Toda la tipografia sale de pilas del sistema; la personalidad
  la dan pesos, espaciado y escala.
- **Adaptable a pantalla estrecha** desde ya, pensando en el acceso movil: en
  movil los instrumentos se pliegan bajo la conversacion en vez de
  desaparecer. La auditabilidad no es una funcion de escritorio.
- `prefers-reduced-motion` respetado.

## Nota sobre el orden
Se recomendo hacer la interfaz DESPUES de la voz y las imagenes, para
disenarla una sola vez. Se decidio adelantarla. Consecuencia asumida: cuando
entren la sintesis de voz (2D) y la carga de imagenes (2E) habra que ampliar
la consola. El sistema de tokens de `:root` esta pensado para que ampliar sea
mecanico, no un rediseno.
