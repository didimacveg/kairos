# ADR 0003 — Agentes como bounded contexts en un solo proceso

**Estado:** aceptado · **Fecha:** Fase 1

## Contexto
La propuesta pedia siete agentes coordinados por event bus desde el primer dia,
sin funcionalidad construida todavia.

## Decision
Los agentes existen como modulos con contrato estable (`Agent`,
`AgentRequest`, `AgentResponse`, `AgentRegistry`), pero se ejecutan en el mismo
proceso y se invocan por llamada directa. No hay cola de mensajes.

## Motivos
- El contrato aporta valor de mantenibilidad ya: evita que voz, vision, memoria
  y automatizacion se acoplen.
- El transporte distribuido no aporta nada con un usuario y una maquina, y
  anade fallo parcial, serializacion y depuracion asincrona.

## Cuando revisar
Cuando el primer agente deba correr en otro equipo (Vision en Raspberry, Fase
3). Entonces el registro devolvera proxies de red. El contrato no cambia.
