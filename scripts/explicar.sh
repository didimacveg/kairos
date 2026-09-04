#!/usr/bin/env bash
#
# Introspeccion: por que fallo algo, sin abrir cinco terminales.
#
# Reune en una pantalla lo que hasta ahora habia que buscar en sitios
# distintos: el error del contenedor, las ultimas acciones auditadas, el
# estado de cada agente y las trazas de la ultima conversacion.
#
#   make explicar          todo
#   make explicar voice    solo un servicio
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

FILTRO="${1:-}"
V=$'\e[32m'; R=$'\e[31m'; A=$'\e[33m'; G=$'\e[90m'; F=$'\e[0m'

echo
echo "${A}=== AGENTES QUE NO RESPONDEN ===${F}"
curl -s -m 8 http://127.0.0.1:8000/api/v1/health 2>/dev/null | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print('  el nucleo no responde'); sys.exit()
malos = [a for a in d.get('agents', []) if a.get('status') != 'ok']
print('  todos en linea' if not malos else '\n'.join(f\"  {a['agent']}: {a.get('status')}\" for a in malos))
"

echo
echo "${A}=== ULTIMO ERROR DE CADA SERVICIO ===${F}"
for s in core voice forge warden web; do
  [ -n "$FILTRO" ] && [ "$s" != "$FILTRO" ] && continue
  linea=$(docker compose logs "$s" --tail 120 --no-log-prefix 2>/dev/null \
    | grep -vE "^\s+File |^\s{4,}|INFO:|HTTP Request" \
    | grep -iE "error|exception|traceback|failed|critical" | tail -1)
  if [ -n "$linea" ]; then
    echo "  ${R}$s${F}  ${linea:0:150}"
  else
    echo "  ${V}$s${F}  sin errores recientes"
  fi
done

echo
echo "${A}=== ULTIMAS ACCIONES AUDITADAS ===${F}"
docker compose exec -T core python -c "
import asyncio
from sqlalchemy import select
from kairos.db.models import AuditLog
from kairos.db.session import get_session_factory

async def m():
    async with get_session_factory()() as db:
        filas = (await db.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(12)
        )).scalars().all()
        for f in filas:
            marca = 'OK ' if f.outcome == 'success' else 'FALLO'
            detalle = str(f.detail)[:70] if f.detail else ''
            print(f\"  {f.created_at:%H:%M}  {marca:5}  {f.action:26}  {detalle}\")
asyncio.run(m())
" 2>/dev/null || echo "  (el nucleo no responde)"

echo
echo "${A}=== ULTIMA CONVERSACION: QUE AGENTES ACTUARON ===${F}"
docker compose exec -T core python -c "
import asyncio
from sqlalchemy import select
from kairos.db.models import Message
from kairos.db.session import get_session_factory

async def m():
    async with get_session_factory()() as db:
        filas = (await db.execute(
            select(Message).order_by(Message.created_at.desc()).limit(4)
        )).scalars().all()
        for f in reversed(filas):
            quien = 'tu   ' if f.role == 'user' else 'kairos'
            print(f\"  {quien}  {f.content[:100]}\")
asyncio.run(m())
" 2>/dev/null || echo "  (sin datos)"

echo
echo "${G}  make curar       arregla lo que se pueda${F}"
echo "${G}  make explicar X  solo el servicio X${F}"
echo
