# ADR 0059 — "Cuando me escriba X, avisame"

**Estado:** aceptado · **Fecha:** Fase 59

## Se apoya en la agenda, no es un sistema nuevo
Un aviso de correo es un recordatorio abierto mas: algo cuya fecha no se sabe
y hay que ir comprobando. La agenda ya sabe persistirlos y dispararlos.

Montar un sistema paralelo para lo mismo seria duplicar el problema de
mantener dos.

## Solo lo llegado desde la ultima revision
Cada aviso guarda cuando se comprobo por ultima vez. Sin esa marca, cada ciclo
encontraria los mismos correos y avisaria en bucle.

Y con tope de 24 horas: volver tras un fin de semana no debe soltar veinte
avisos de correos viejos.

## El aviso dice quien y de que, no el cuerpo
"Correo de Laura. Asunto: reunion del martes." Es lo que necesitas para
decidir si merece mirarlo ahora. Leer el cuerpo en alto seria largo y
frecuentemente privado.

## Un nombre busca en remitente Y asunto
"El instituto" puede llegar de varias direcciones distintas. Una direccion
completa si usa `from:` exacto.

## El informe de las 22:00
Ahora incluye lo que hay en las proximas 48 h y el correo sin leer del dia.

Es lo que lo convierte en algo que de verdad quieres oir: saber que tienes
manana ANTES de acostarte, no despues.
