# ADR 0021 — Acceso movil por red privada, no por el router

**Estado:** aceptado · **Fecha:** Fase 14

## Decision
El acceso desde fuera del PC va por Tailscale (WireGuard), no abriendo puertos
en el router.

## Por que
Abrir un puerto expone KAIROS a Internet entero. Dentro hay memoria personal,
historial de conversaciones y control del escritorio. Un login con contrasena
no es defensa suficiente contra escaneo masivo.

Una red privada cifrada entre dispositivos propios elimina la superficie
publica por completo: no hay puerto que escanear.

## Defensa en capas
1. Ningun puerto abierto al exterior.
2. El enlace de la web es configurable y por defecto sigue en 127.0.0.1.
3. Regla de cortafuegos limitada al rango 100.64.0.0/10 — un dispositivo de la
   misma WiFi que no este en la red privada tampoco entra.
4. Usuario y contrasena, sesion con caducidad.
5. Auditoria de toda accion, venga de donde venga.

## Limitacion asumida
El microfono no funciona desde el movil: los navegadores exigen HTTPS para
`getUserMedia` y dentro de la VPN vamos por HTTP. Tailscale puede emitir
certificados; se hara cuando la voz movil sea prioritaria.

## Reversible en un comando
`KAIROS_WEB_BIND=127.0.0.1` y recrear el contenedor. KAIROS vuelve a ser
inalcanzable desde cualquier otro dispositivo.
