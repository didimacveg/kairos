#!/usr/bin/env bash
# Configura KAIROS para acceso movil por HTTPS dentro de la red privada.
#
# Por que HTTPS: los navegadores moviles solo dan acceso al microfono en
# origenes seguros. Sin certificado no hay voz en el movil, punto.
#
# Tailscale emite certificados reales (Let's Encrypt) para tu dominio de red
# privada, y `tailscale serve` termina el TLS y reenvia a 127.0.0.1. Eso
# significa que la web NO tiene que escuchar en 0.0.0.0 ni hace falta regla de
# cortafuegos: sigue atada a loopback y Tailscale hace de puerta.
#
# Es MAS seguro que la version HTTP anterior, no menos.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

DOMINIO="${1:-}"
if [ -z "$DOMINIO" ]; then
  echo "Uso: bash scripts/movil-https.sh tu-maquina.tu-red.ts.net"
  echo
  echo "El dominio lo da, en PowerShell:  tailscale status --json"
  echo "o se ve en la web de Tailscale, en la columna Machine."
  exit 1
fi

echo "Configurando para $DOMINIO"

# La web vuelve a loopback: Tailscale Serve es quien expone, no Docker.
sed -i 's|^KAIROS_WEB_BIND=.*|KAIROS_WEB_BIND=127.0.0.1|' .env
grep -q '^KAIROS_EXTRA_HOSTS=' .env \
  && sed -i "s|^KAIROS_EXTRA_HOSTS=.*|KAIROS_EXTRA_HOSTS=$DOMINIO|" .env \
  || echo "KAIROS_EXTRA_HOSTS=$DOMINIO" >> .env

# Origen HTTPS permitido para CORS.
sed -i "s|^KAIROS_ALLOWED_ORIGINS=.*|KAIROS_ALLOWED_ORIGINS=http://localhost:3000,https://$DOMINIO|" .env

# Cookie Secure: ahora que hay TLS, la sesion no debe viajar en claro nunca.
grep -q '^KAIROS_COOKIE_SECURE=' .env \
  && sed -i 's|^KAIROS_COOKIE_SECURE=.*|KAIROS_COOKIE_SECURE=true|' .env \
  || echo "KAIROS_COOKIE_SECURE=true" >> .env

echo
grep -E "^KAIROS_(WEB_BIND|EXTRA_HOSTS|ALLOWED_ORIGINS|COOKIE_SECURE)" .env
echo
echo "Ahora, en PowerShell COMO ADMINISTRADOR:"
echo "  tailscale serve --bg 3000"
echo
echo "Y despues, aqui:"
echo "  docker compose up -d --force-recreate core web"
