# ADR 0077 — Rutinas por demostracion

**Estado:** aceptado · **Fecha:** Fase 77

## La idea, y de donde viene
De Grok Bot: en vez de programar una automatizacion, haces la tarea una vez y
el sistema la guarda.

## No hace falta grabar la pantalla
KAIROS ya registra en la auditoria cada capacidad que ejecuta. Una rutina es
**esa secuencia con un nombre**.

Grabar el raton y la pantalla seria mas impresionante y mucho peor: lo que
importa no es donde hiciste clic, es QUE le pediste. Un clic en unas
coordenadas se rompe si mueves una ventana; una capacidad no.

## Solo acciones del escritorio
Perfiles, aplicaciones, musica, pestañas, brillo, voz. Buscar y razonar
quedan fuera: eso se pide cada vez, no se repite.

## Lo irreversible pausa
Enviar correo y crear o borrar eventos se guardan en la rutina, pero al
repetirla **paran y piden confirmacion**.

Una rutina es una comodidad, no una via para saltarse las confirmaciones que
el resto del sistema exige. Si repitiendo una rutina se pudiera enviar un
correo sin que nadie mire, todo el diseno de confirmaciones seria decorativo.

## Ventana de diez minutos
Cubre una sesion de trabajo sin arrastrar lo que se hizo hace media hora por
otro motivo. Y no se guardan acciones repetidas consecutivas: encender el
perfil de trabajo tres veces no es una rutina, es ruido en la auditoria.
