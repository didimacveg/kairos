#!/usr/bin/env bash
# Copia el puente a C:\kairos-bridge sin salir de Ubuntu.
# Se acabo el copy manual en PowerShell.
set -euo pipefail
DEST="/mnt/c/kairos-bridge"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/apps/bridge"
[ -d "$DEST" ] || { echo "No existe $DEST"; exit 1; }
cp "$SRC"/*.py "$DEST"/
cp "$SRC"/bridge-config.json "$DEST"/
echo "Puente sincronizado. Ahora, en PowerShell: Ctrl+C en la ventana del puente y "py bridge.py"."
