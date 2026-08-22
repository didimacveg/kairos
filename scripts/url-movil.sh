#!/usr/bin/env bash
# Imprime la URL exacta que hay que abrir en el movil.
set -uo pipefail
IP=$(powershell.exe -NoProfile -Command "tailscale ip -4" 2>/dev/null | tr -d '\r\n ')
NOMBRE=$(powershell.exe -NoProfile -Command "(tailscale status --json | ConvertFrom-Json).Self.DNSName" 2>/dev/null | tr -d '\r\n ' | sed 's/\.$//')

echo
if [ -n "$IP" ]; then
  echo "  IP de este PC en la red privada:  $IP"
else
  echo "  No encuentro Tailscale. Instalalo desde tailscale.com/download/windows"
  exit 1
fi
[ -n "$NOMBRE" ] && echo "  Nombre completo:                  $NOMBRE"

BIND=$(grep -E "^KAIROS_WEB_BIND=" .env 2>/dev/null | cut -d= -f2- || echo "127.0.0.1")
echo
echo "  ------------------------------------------------------------"
if [ -n "$NOMBRE" ]; then
  echo "  CON HTTPS (recomendado, permite microfono en el movil):"
  echo
  echo "      https://$NOMBRE"
  echo
  echo "  Requiere haber ejecutado en PowerShell como administrador:"
  echo "      tailscale serve --bg 3000"
  echo
fi
echo "  SIN HTTPS (sin microfono en el movil):"
echo
echo "      http://$IP:3000"
echo
if [ "$BIND" != "0.0.0.0" ]; then
  echo "  Para que esta segunda funcione hace falta:"
  echo "      sed -i 's|^KAIROS_WEB_BIND=.*|KAIROS_WEB_BIND=0.0.0.0|' .env"
  echo "      docker compose up -d --force-recreate web"
fi
echo "  ------------------------------------------------------------"
echo
