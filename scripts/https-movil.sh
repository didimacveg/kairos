#!/usr/bin/env bash
# Deja el .env listo para HTTPS por red privada. Detecta el dominio solo.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

DOMINIO=$(powershell.exe -NoProfile -Command \
  "(tailscale status --json | ConvertFrom-Json).Self.DNSName" 2>/dev/null \
  | tr -d '\r\n ' | sed 's/\.$//')

if [ -z "$DOMINIO" ]; then
  echo "No detecto Tailscale. Instalalo o pasa el dominio a mano."
  exit 1
fi
echo "Dominio: $DOMINIO"

poner() {
  grep -q "^$1=" .env && sed -i "s|^$1=.*|$1=$2|" .env || echo "$1=$2" >> .env
}

# Con `tailscale serve`, quien expone es Tailscale: la web vuelve a loopback.
poner KAIROS_WEB_BIND 127.0.0.1
poner KAIROS_EXTRA_HOSTS "$DOMINIO"
poner KAIROS_ALLOWED_ORIGINS "http://localhost:3000,https://$DOMINIO"
# Con TLS de por medio, la cookie de sesion no debe viajar nunca en claro.
poner KAIROS_COOKIE_SECURE true

echo
grep -E "^KAIROS_(WEB_BIND|EXTRA_HOSTS|ALLOWED_ORIGINS|COOKIE_SECURE)" .env
echo
echo "Ahora, en PowerShell COMO ADMINISTRADOR:"
echo "    tailscale serve --bg 3000"
echo
echo "Y aqui:"
echo "    docker compose up -d --force-recreate core web"
echo
echo "Luego en el movil:  https://$DOMINIO"
