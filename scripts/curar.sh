#!/usr/bin/env bash
#
# Autorreparacion de KAIROS.
#
# Diagnostica y ARREGLA lo que puede arreglarse solo. Cada fallo que te
# obliga a abrir una conversacion para resolverlo es un fallo que te aleja de
# usar KAIROS, y la mayoria se arreglan con un reinicio de contenedor.
#
# LO QUE HACE:
#   - reinicia los contenedores caidos o en bucle
#   - si un contenedor esta en bucle, ENSENA su error antes de reintentar
#   - comprueba que el codigo Python compila antes de reiniciar el nucleo
#   - verifica que cada servicio responde de verdad, no solo que "esta up"
#
# LO QUE NO HACE:
#   - tocar codigo. Si algo no compila, lo dice y para.
#   - reintentar en bucle. Dos intentos y se rinde con un diagnostico.
#
# Esa segunda regla importa: un script que reintenta indefinidamente esconde
# el problema en vez de resolverlo.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

VERDE=$'\e[32m'; ROJO=$'\e[31m'; AMBAR=$'\e[33m'; GRIS=$'\e[90m'; FIN=$'\e[0m'
ok()    { echo "  ${VERDE}OK${FIN}    $1"; }
mal()   { echo "  ${ROJO}FALLA${FIN} $1"; }
curo()  { echo "  ${AMBAR}CURADO${FIN} $1"; }
nota()  { echo "        ${GRIS}$1${FIN}"; }

PROBLEMAS=0

echo
echo "=============== CODIGO ==============="

# Primero el codigo: reiniciar un contenedor con codigo roto solo lo pone a
# dar vueltas otra vez.
ROTOS=$(docker compose exec -T core python -c "
import pathlib, py_compile, sys
malos = []
for p in pathlib.Path('/app/kairos').rglob('*.py'):
    try:
        py_compile.compile(str(p), doraise=True)
    except Exception as e:
        malos.append(f'{p.relative_to(\"/app\")}: {e}')
print('\n'.join(malos))
" 2>/dev/null || echo "")

if [ -n "$ROTOS" ]; then
  mal "hay ficheros que no compilan"
  echo "$ROTOS" | head -5 | while read -r l; do nota "$l"; done
  nota "NO se reinicia nada: arregla el codigo primero"
  exit 1
fi
ok "todo el Python compila"

echo
echo "============= CONTENEDORES ============"

ESPERADOS="postgres ollama voice core web forge warden"
for s in $ESPERADOS; do
  ESTADO=$(docker compose ps --format '{{.Service}} {{.State}}' 2>/dev/null \
           | awk -v s="$s" '$1==s {print $2}')

  if [ "$ESTADO" = "running" ]; then
    ok "kairos-$s"
    continue
  fi

  PROBLEMAS=$((PROBLEMAS + 1))

  if [ "$ESTADO" = "restarting" ]; then
    mal "kairos-$s esta en bucle"
    # El error ANTES de reintentar: reiniciar sin mirar es lo que convierte
    # un fallo de cinco minutos en una tarde.
    docker compose logs "$s" --tail 25 --no-log-prefix 2>/dev/null \
      | grep -vE "^\s+File |^\s{4,}" | tail -4 | while read -r l; do nota "$l"; done
    nota "un bucle casi nunca se cura reiniciando; mira el error de arriba"
    continue
  fi

  mal "kairos-$s: ${ESTADO:-ausente}"
  docker compose up -d "$s" >/dev/null 2>&1
  sleep 8
  NUEVO=$(docker compose ps --format '{{.Service}} {{.State}}' | awk -v s="$s" '$1==s {print $2}')
  if [ "$NUEVO" = "running" ]; then
    curo "kairos-$s levantado"
    PROBLEMAS=$((PROBLEMAS - 1))
  else
    nota "sigue en '$NUEVO'"
  fi
done

echo
echo "============== SERVICIOS =============="

# "Up" no significa "responde". Se comprueba de verdad.
comprobar() {
  local nombre="$1" url="$2" servicio="$3"
  if docker compose exec -T core python -c "
import httpx, sys
try:
    r = httpx.get('$url', timeout=8)
    sys.exit(0 if r.status_code == 200 else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
    ok "$nombre"
    return 0
  fi

  mal "$nombre no responde"
  PROBLEMAS=$((PROBLEMAS + 1))
  if [ -n "$servicio" ]; then
    nota "reiniciando..."
    docker compose restart "$servicio" >/dev/null 2>&1
    sleep 12
    if docker compose exec -T core python -c "
import httpx, sys
try:
    sys.exit(0 if httpx.get('$url', timeout=10).status_code == 200 else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
      curo "$nombre recuperado"
      PROBLEMAS=$((PROBLEMAS - 1))
    else
      nota "sigue sin responder tras el reinicio"
    fi
  fi
}

comprobar "voz"     "http://voice:8100/health"  "voice"
comprobar "forge"   "http://forge:8300/health"  "forge"
comprobar "warden"  "http://warden:8400/health" "warden"
comprobar "ollama"  "http://ollama:11434/api/tags" ""

# El nucleo se comprueba desde fuera.
if curl -sf -m 8 http://127.0.0.1:8000/api/v1/health >/dev/null 2>&1; then
  ok "nucleo"
else
  mal "el nucleo no responde"
  PROBLEMAS=$((PROBLEMAS + 1))
  nota "reiniciando..."
  docker compose restart core >/dev/null 2>&1
  sleep 20
  if curl -sf -m 8 http://127.0.0.1:8000/api/v1/health >/dev/null 2>&1; then
    curo "nucleo recuperado"
    PROBLEMAS=$((PROBLEMAS - 1))
  else
    docker compose logs core --tail 20 --no-log-prefix 2>/dev/null \
      | grep -vE "^\s+File |^\s{4,}" | tail -4 | while read -r l; do nota "$l"; done
  fi
fi

echo
echo "=============== PUENTE ==============="

if docker compose exec -T core python -c "
import httpx, sys
try:
    sys.exit(0 if httpx.get('http://host.docker.internal:8200/health', timeout=6).status_code == 200 else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
  ok "el nucleo alcanza el puente"
else
  mal "el puente no responde"
  PROBLEMAS=$((PROBLEMAS + 1))
  nota "En PowerShell:  Start-Service KairosBridge"
  nota "O el acceso directo 'Abrir KAIROS'"
fi

echo
if [ "$PROBLEMAS" -eq 0 ]; then
  echo "  ${VERDE}Todo en pie.${FIN}"
else
  echo "  ${ROJO}Quedan $PROBLEMAS problemas sin resolver.${FIN}"
fi
echo
exit 0
