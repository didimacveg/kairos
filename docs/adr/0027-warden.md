# ADR 0027 — El aplicador, y por que el reinicio lo hace un humano

**Estado:** aceptado · **Fecha:** Fase 24

## Correccion previa: el forge no puede estar sin red
`network_mode: none` le quitaba tambien la red interna de Docker, asi que el
nucleo no podia ni hablarle. El objetivo era impedir la salida a Internet, no
aislarlo del sistema. Se sustituye por una red `internal: true`: los
contenedores se ven entre si, el exterior no existe para ellos.

## El warden
El unico proceso con el repositorio en lectura Y escritura. No puede ser el
nucleo (tiene las claves) ni el forge (ejecuta codigo no verificado).

Cuatro operaciones: ramificar, aplicar, probar, fusionar. Si los tests fallan
sobre el resultado real, borra la rama y no queda rastro.

## Dos cerrojos
La ruta comprueba que la propuesta este aprobada, y el agente lo comprueba
otra vez antes de llamar. Lo unico que escribe merece redundancia.

## El reinicio lo hace Diego
El warden fusiona, pero NO reinicia contenedores. Ese es el momento
irreversible: si un merge correcto en git resulta en un nucleo que no arranca,
tener a un humano delante significa que KAIROS no pasa la noche muerto.

Es un comando: `docker compose up -d --force-recreate core`.

Y deshacer siempre es otro: el warden devuelve el commit anterior en cada
respuesta.

## El arbol tiene que estar limpio
Si hay cambios sin guardar, el warden se niega. Aplicar sobre trabajo a medias
produciria un commit con cosas que nadie reviso.
