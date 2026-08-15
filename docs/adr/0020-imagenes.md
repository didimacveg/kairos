# ADR 0020 — Imagenes: donde viven y cuando salen

**Estado:** aceptado · **Fecha:** Fase 13

## Entrada
Subir fichero y **pegar con Ctrl+V**. La segunda es la que se usa de verdad:
Win+Shift+S, recortas, pegas. Sin pasar por el explorador de archivos.

## Almacenamiento
Volumen local `adjuntos:`, con borrado real (el fichero desaparece del disco,
no se marca y ya).

**Nunca entran en la memoria semantica.** Una foto no es un hecho sobre el
usuario, y meterla en el indice de recuerdos ensuciaria cada busqueda futura
sin aportar nada recuperable. Se guarda el hash para detectar duplicados y
comprobar integridad, no para indexar.

## Privacidad: la parte incomoda
`qwen2.5:7b` no ve imagenes. Analizar una foto implica mandarla al proveedor
remoto — es decir, **sale de la maquina**.

Se respeta el interruptor `KAIROS_ALLOW_EGRESS` como todo lo demas, pero
ademas la interfaz lo DICE: "La imagen saldra de esta maquina para
analizarse". Sin egress, avisa de que el modelo local no puede verlas en vez
de fallar en silencio.

Esto es lo mas cerca que ha estado el proyecto de romper su premisa. La
diferencia es que el usuario lo elige adjunto a adjunto y lo ve escrito.

## Vision local
Requeriria un modelo multimodal (qwen2.5vl:7b, ~6 GB). Cabe en la 4060 Ti pero
desplaza al modelo de razonamiento. Queda para cuando haya mas VRAM.
