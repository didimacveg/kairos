#!/usr/bin/env bash
# Estado completo de KAIROS en un comando.
#
# Existe porque diagnosticar "algo no va" costaba media docena de comandos
# repartidos entre dos terminales. Esto los junta y dice QUE hacer, no solo
# que esta roto.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ok()   { printf '  \033[32m OK \033[0m %s\n' "$1"; }
mal()  { printf '  \033[31mFALLA\033[0m %s\n' "$1"; }
avisa(){ printf '  \033[33mAVISO\033[0m %s\n' "$1"; }
pista(){ printf '        → %s\n' "$1"; }

echo
echo "=============== CONTENEDORES ==============="
if ! docker compose ps --format '{{.Name}} {{.State}}' 2>/dev/null | grep -q .; then
  mal "Docker no responde"
  pista "Abre Docker Desktop en Windows y espera a que arranque"
  exit 1
fi
while read -r nombre estado; do
  [ "$estado" = "running" ] && ok "$nombre" || mal "$nombre ($estado)"
done < <(docker compose ps --format '{{.Name}} {{.State}}')

echo
echo "================= NUCLEO =================="
SALUD=$(curl -s --max-time 8 http://127.0.0.1:8000/api/v1/health || echo "")
if [ -z "$SALUD" ]; then
  mal "El nucleo no responde en el puerto 8000"
  pista "docker compose up -d core && docker compose logs core --tail 30"
else
  python3 - "$SALUD" <<'PY'
import json, sys
d = json.loads(sys.argv[1])
verde, rojo, amar, reset = "\033[32m", "\033[31m", "\033[33m", "\033[0m"
print(f"  {verde} OK {reset} instancia {d['instance']}, estado {d['status']}")
for a in d["agents"]:
    e = a.get("status")
    marca = f"{verde} OK {reset}" if e == "ok" else (
        f"{amar}AVISO{reset}" if e == "disabled" else f"{rojo}FALLA{reset}")
    extra = ""
    if a["agent"] == "reasoning":
        extra = f" — {'nube' if not a.get('local') else 'local'}: {a.get('modelo_nube') or a.get('modelo_local')}"
    if a["agent"] == "device" and e != "ok":
        extra = " — el puente no responde"
    print(f"  {marca} agente {a['agent']}{extra}")
if d.get("egress_allowed"):
    print(f"  {amar}AVISO{reset} salida a Internet PERMITIDA")
else:
    print(f"  {verde} OK {reset} sin salida a Internet")
PY
fi

echo
if [ -z "$SALUD" ]; then
  echo
  echo "================= PUENTE =================="
  echo "  (no se comprueba: el nucleo esta caido y es quien pregunta)"
else
echo "================= PUENTE =================="
PUENTE=$(docker compose exec -T core python -c "
import httpx
try:
    r = httpx.get('http://host.docker.internal:8200/health', timeout=6)
    print(r.status_code)
except Exception as e:
    print('X')
" 2>/dev/null | tr -d '\r\n ')
if [ "$PUENTE" = "200" ]; then
  ok "El nucleo alcanza el puente"
else
  mal "El nucleo NO alcanza el puente"
  pista "En PowerShell:  cd C:\\kairos-bridge ; py bridge.py"
  pista "Si ya corre, revisa la regla del cortafuegos para el puerto 8200"
fi

echo
fi

echo "================ CONFIGURACION ============"
falta=0
for clave in KAIROS_BRIDGE_TOKEN ANTHROPIC_API_KEY KAIROS_SESSION_SECRET; do
  valor=$(grep -E "^${clave}=" .env 2>/dev/null | cut -d= -f2-)
  if [ -z "$valor" ]; then
    # La clave de la nube solo hace falta con egress activo.
    if [ "$clave" = "ANTHROPIC_API_KEY" ] && ! grep -q '^KAIROS_ALLOW_EGRESS=true' .env; then
      avisa "$clave vacia (sin salida a Internet, no hace falta)"
    else
      mal "$clave vacia o ausente en .env"
      falta=1
    fi
  else
    ok "$clave definida (${#valor} caracteres)"
  fi
done
[ "$falta" = "1" ] && pista "Recuerda: sed -i no anade la linea si no existe; comprueba que este la clave y el '='"

echo
echo "================== ACCESO ================="
BIND=$(grep -E "^KAIROS_WEB_BIND=" .env 2>/dev/null | cut -d= -f2- || echo "127.0.0.1")
if [ "$BIND" = "0.0.0.0" ]; then
  avisa "La web acepta conexiones de la red privada (movil activado)"
else
  ok "La web solo acepta conexiones de este PC"
fi
curl -s -o /dev/null --max-time 5 -w "        interfaz web: HTTP %{http_code}\n" http://127.0.0.1:3000 || echo "        interfaz web: sin respuesta"
echo
