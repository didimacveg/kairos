# ADR 0022 — HTTPS dentro de la red privada

**Estado:** aceptado · **Fecha:** Fase 15

## Por que
Los navegadores moviles solo dan acceso al microfono en origenes seguros. Sin
certificado no hay voz en el movil. No es un ajuste que se pueda saltar: es
politica del navegador.

## Como
`tailscale serve` termina el TLS con un certificado real de Let's Encrypt
emitido para el dominio de la red privada, y reenvia a `127.0.0.1:3000`.

## Es mas seguro que la version anterior, no menos
La Fase 14 exponia la web en `0.0.0.0` y confiaba en una regla de cortafuegos
limitada al rango de Tailscale. Esta version:

- Devuelve la web a `127.0.0.1`. Docker no expone nada a la red.
- Elimina la regla de cortafuegos: no hay puerto que proteger.
- Activa `Secure` en la cookie de sesion: nunca viaja en claro.
- Tailscale autentica el dispositivo ANTES de que la peticion llegue al
  nucleo.

Sigue sin abrirse un solo puerto del router. La superficie publica es cero.

## Lo que no resuelve
Si el PC esta apagado, KAIROS no responde. Eso no es un problema de red sino
de donde vive el nucleo, y lo resuelve el nodo permanente de bajo consumo que
esta en la lista de compra.
