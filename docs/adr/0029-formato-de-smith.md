# ADR 0029 — Marcadores en texto plano, no JSON

**Estado:** aceptado · **Fecha:** Fase 26

## El fallo real
Primera prueba de Smith en produccion. El modelo escribio un plan correcto y
la respuesta quedo inservible porque escapo una comilla simple dentro de un
campo JSON — y en JSON las comillas simples no se escapan.

Un caracter, toda la propuesta perdida.

## Por que era inevitable
Meter un fichero Python dentro de un campo JSON obliga a escapar cada comilla
doble, cada barra invertida y cada salto de linea. Un fichero de 200 lineas
son miles de oportunidades de fallar, y basta una para invalidar la respuesta
entera.

## Decision
Marcadores en texto plano:

    MOTIVO: ...
    RIESGO: bajo|medio|alto
    --- FICHERO: ruta/relativa.py
    <el fichero entero, sin escapar nada>
    --- FIN FICHERO

No hay nada que escapar. El parser busca los delimitadores y corta.

## El principio, generalizado
Es la tercera vez en Smith que un formato elegido por comodidad resulta
fragil: primero los diffs unificados, luego el JSON. **El formato correcto es
el que menos margen de error le deja al modelo, no el mas ordenado de leer.**

## Riesgo: nunca a la baja
El modelo declara un riesgo y las rutas tocadas determinan otro. Se toma el
mayor de los dos. Un modelo que se autoevalua tiende a decir "bajo"; que
pueda subirlo es util, que pueda bajarlo no.

## Propuestas por voz
Se admiten, con preambulo rigido: "proponte...", "hazte capaz de...",
"programate...". Cualquier otra construccion sigue siendo conversacion.

Mas estricto que el resto de ordenes por voz a proposito: una frase mal
transcrita no debe generar una propuesta de codigo, y una cola llena de basura
deja de leerse — que es exactamente perder el control creyendo tenerlo.
