# ADR 0002 — Local-first estricto: sin Supabase cloud ni Vercel

**Estado:** aceptado · **Fecha:** Fase 1

## Contexto
La propuesta inicial declaraba "todo el procesamiento sensible en local" y a la
vez listaba Supabase y Vercel como infraestructura base. Son incompatibles: la
memoria del sistema es el dato mas sensible del proyecto.

## Decision
Regla fundacional: **KAIROS nunca depende de Internet para funcionar.**
- Postgres corre en la maquina del usuario.
- La autenticacion es propia, sin proveedor externo.
- No hay despliegue publico.
- Los proveedores cloud de modelos son adaptadores opcionales tras el
  interruptor `KAIROS_ALLOW_EGRESS`, que por defecto esta desactivado.

## Consecuencias
- Se pierde comodidad: no hay panel de Supabase ni previews de Vercel.
- Se gana lo que define al proyecto: un sistema que sigue funcionando con el
  router desenchufado.
- Copias de seguridad y actualizaciones pasan a ser responsabilidad del
  operador. Documentar en Fase 2.
