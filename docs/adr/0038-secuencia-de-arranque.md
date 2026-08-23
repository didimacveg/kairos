# ADR 0038 — La secuencia de arranque

**Estado:** aceptado · **Fecha:** Fase 36

## Cuatro segundos, cuatro actos
- **0.0-0.6 carga** — el nucleo late tres veces antes de romper. Sin esa
  tension previa la explosion no significa nada: aparece y ya.
- **0.6-1.6 detonacion** — onda de choque, 36 rayos, 70 chispas, 6 anillos,
  doble barrido girando 4 vueltas.
- **1.6-2.8 identidad** — la palabra se monta letra a letra desde abajo, con
  rotacion y desenfoque que se disipa. Rejilla de fondo dibujandose.
- **2.8-4.0 entrega** — el velo negro se disuelve y los paneles entran
  escalonados: sigilo, cabecera, registro, instrumentos, texto, consola.

Ese ultimo acto es lo que separa una animacion de una secuencia de arranque.
Si los paneles aparecen de golpe al terminar, el efecto se rompe justo en el
momento en que deberia rematar.

## Modo negro
"Kairos, modo negro" apaga la pantalla entera y deja un "en espera" latiendo
muy tenue. Existe para grabar: se apaga, se prepara la camara, y "despierta"
arranca desde el negro.

Sin el, el despertar ocurre sobre una interfaz ya visible y pierde el efecto.

Escape siempre saca del negro. Una pantalla en negro sin salida seria un fallo
disfrazado de funcion.

## La leccion que costo cuatro rondas
Todas las reglas van anidadas bajo `.despertar` y con `!important`, porque la
regla global de la Fase 1

    html:not([data-motion="on"]) * { animation: none !important }

tiene especificidad (0,1,1) y gana a cualquier regla propia sin anidar. Los
elementos arrancan en `opacity: 0` y aparecen MEDIANTE la animacion: sin
animacion, un contenedor perfecto lleno de elementos invisibles.

Diagnostico correcto solo tras instrumentar el DOM. Cuatro hipotesis previas,
todas dichas con seguridad, todas equivocadas.

## El boton de movimiento
Decia el estado ("Movimiento" cuando se movia). Ahora dice la accion
("Estatico" cuando se mueve, para pararlo). Un boton describe lo que hace al
pulsarlo, no como estan las cosas.
