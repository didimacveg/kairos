# ADR 0025 — El banco de pruebas: donde se ejecuta lo que KAIROS escribe

**Estado:** aceptado · **Fecha:** Fase 21

## El problema
Para que KAIROS se proponga cambios hace falta ejecutar codigo que ha escrito
un modelo de lenguaje. Ese es, con diferencia, el mayor riesgo del proyecto.

## Decision
Un servicio aparte, `forge`, con cuatro operaciones y ninguna mas: clonar,
ramificar, parchear, probar. No existe endpoint que acepte una cadena de
shell; `subprocess` se llama siempre con lista de argumentos y `shell=False`.

## Aislamiento
- **Sin red.** `network_mode: none`. Un parche hostil no puede exfiltrar nada
  ni descargar dependencias. Tampoco puede hablar con el nucleo: la
  conversacion va siempre en sentido nucleo -> forge.
- **Repositorio en solo lectura.** Se clona a un temporal; el original no es
  escribible desde dentro.
- **Efimero.** El directorio de trabajo se borra al terminar, con o sin exito.
- **Sin privilegios.** `cap_drop: ALL`, `no-new-privileges`, usuario sin root,
  limite de memoria y de procesos.
- **Sin nada que robar.** No tiene claves, ni base de datos, ni acceso al
  puente. El nucleo si tiene todo eso, y por eso no ejecuta el codigo el.

## Doble opt-in
`KAIROS_FORGE_ENABLED=false` de fabrica y hace falta token. Sin las dos cosas
el agente ni se registra.

## Lo que falta
El agente generador (que escribe el parche) y el aplicador (que hace merge de
lo aprobado). Con el forge en pie, ambos pueden construirse sin que ejecutar
codigo propuesto sea temerario.
