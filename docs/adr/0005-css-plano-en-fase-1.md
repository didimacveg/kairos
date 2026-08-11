# ADR 0005 — CSS plano en Fase 1; Tailwind aplazado

**Estado:** aceptado · **Fecha:** Fase 1

## Decision
La interfaz usa CSS plano con custom properties y un unico `globals.css`.
Tailwind se introducira cuando existan componentes repetidos que justifiquen
utilidades.

## Motivos
- La superficie de UI de la Fase 1 son dos pantallas. Un sistema de utilidades
  con su cadena de build no se amortiza.
- Sin fuentes remotas ni CDN: la interfaz debe verse identica sin conexion.

## Consecuencias
- Cuando lleguen el panel de vision (Fase 3) y el de operacion (Fase 5), habra
  que migrar. Las custom properties de `:root` son ya los tokens de diseno, asi
  que la migracion es mecanica.
