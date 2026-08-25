# ADR 0048 — Correo y calendario

**Estado:** aceptado · **Fecha:** Fase 47

## Permisos minimos
`gmail.modify` y `calendar`. Nada mas.

`gmail.modify` permite leer, buscar, marcar y enviar, pero **no borrar de
forma irreversible**: para eso hace falta el scope completo, que no se pide.
Un fallo de KAIROS puede archivar un correo; no puede hacerlo desaparecer.

## Enviar exige confirmacion, siempre
Es la accion mas irreversible de todo el sistema. Un perfil mal abierto se
cierra; un correo enviado no se recoge.

Doble cerrojo: la ruta devuelve 428 sin confirmacion, y la funcion la vuelve a
exigir. Lo que no se puede deshacer merece redundancia.

Y la confirmacion la pone Diego, nunca el modelo. El modelo puede redactar el
correo; no puede decidir mandarlo.

## El cuerpo no entra en la auditoria
Toda accion queda registrada, pero el cuerpo del correo no. La auditoria se
lee entera cuando se audita, y ahi no pinta nada el contenido personal.

## El token no sale de la maquina
Vive en el volumen del nucleo, con permisos 600, y NUNCA entra en el contexto
de un modelo. Da acceso al buzon entero.
