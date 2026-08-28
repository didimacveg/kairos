# ADR 0054 — Que se arregle solo lo que pueda arreglarse solo

**Estado:** aceptado · **Fecha:** Fase 54

## Por que esto antes que funciones nuevas
Diego dijo que sigue prefiriendo ChatGPT porque es comodo y nunca esta caido.
Cada fallo de KAIROS que le obliga a abrir una conversacion para resolverlo es
un fallo que le aleja de usarlo.

La mayoria se arreglan con un reinicio de contenedor. Eso no deberia costar
una conversacion.

## El orden importa
Primero el codigo, luego los contenedores, luego los servicios.

Reiniciar un contenedor con codigo roto solo lo pone a dar vueltas otra vez.
Si algo no compila, `curar` lo dice y PARA sin tocar nada.

## Un bucle no se cura reiniciando
Si un contenedor esta en `restarting`, se ensena su error y NO se reintenta.
Reiniciar sin mirar es lo que convierte un fallo de cinco minutos en una
tarde — nos ha pasado varias veces.

## "Up" no es "responde"
`docker compose ps` dice que un contenedor esta arriba mucho antes de que su
proceso conteste. Se comprueba llamando de verdad a cada `/health`.

## Dos intentos y se rinde
Un script que reintenta indefinidamente esconde el problema. Dos intentos y un
diagnostico claro es mas util que diez intentos silenciosos.

## Lo que NO hace
Tocar codigo. Arreglar automaticamente un fichero fuente es exactamente el
tipo de autonomia que decidimos no darle a KAIROS: propone, no aplica.
