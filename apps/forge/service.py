"""KAIROS Forge — donde se prueban los cambios que KAIROS se propone.

Es el servicio que ejecuta codigo que KAIROS ha escrito. Por eso es el
componente con el modelo de amenazas mas estricto del proyecto.

QUE PUEDE HACER, y nada mas:
  - copiar el repositorio a un directorio temporal
  - crear una rama y aplicar un parche unificado
  - ejecutar la suite de tests
  - devolver el resultado

QUE NO PUEDE HACER, por diseno:
  - ejecutar comandos arbitrarios. No hay endpoint que acepte una cadena de
    shell. Las operaciones son cuatro y estan escritas aqui.
  - tocar el repositorio real. Trabaja SIEMPRE sobre una copia; el original se
    monta en solo lectura.
  - salir a Internet. El contenedor corre sin red (`network_mode: none` en el
    compose), asi que un parche malicioso no puede exfiltrar nada ni
    descargarse dependencias.
  - persistir nada. El temporal se borra al terminar, pase lo que pase.

Por que un servicio aparte y no dentro del nucleo: el nucleo tiene acceso a tu
memoria, tu auditoria y el puente. Ejecutar codigo no verificado en ese proceso
seria darle esas llaves. Aqui esta aislado y sin nada que robar.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
import secrets
import uvicorn

REPO_ORIGEN = Path(os.getenv("KAIROS_FORGE_REPO", "/repo"))
TRABAJO = Path(os.getenv("KAIROS_FORGE_WORK", "/var/lib/kairos/forge"))
SECRETO = os.getenv("KAIROS_FORGE_TOKEN", "")
TIMEOUT_TESTS = int(os.getenv("KAIROS_FORGE_TIMEOUT", "300"))
MAX_PARCHE_BYTES = 512 * 1024

ORIGENES = ("127.", "::1", "10.", "172.", "192.168.")

app = FastAPI(title="KAIROS Forge", version="0.1.0")


def autorizar(request: Request, x_forge_token: str = Header(default="")) -> None:
    cliente = request.client.host if request.client else ""
    if not any(cliente.startswith(p) for p in ORIGENES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Origen no permitido")
    if not SECRETO or not secrets.compare_digest(x_forge_token, SECRETO):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalido")


class Ensayo(BaseModel):
    rama: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9/_.-]+$")
    parche: str = Field(min_length=1)


def _correr(cmd: list[str], cwd: Path, timeout: int = 60) -> tuple[int, str]:
    """Ejecuta un comando de una LISTA. Nunca shell, nunca cadena.

    Los argumentos vienen de constantes de este fichero, no de la peticion,
    salvo el nombre de rama — que el esquema valida contra un patron estricto.
    """
    try:
        r = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, shell=False
        )
        return r.returncode, (r.stdout + r.stderr)[-8000:]
    except subprocess.TimeoutExpired:
        return 124, f"tiempo agotado tras {timeout}s"
    except Exception as exc:  # noqa: BLE001
        return 1, f"{type(exc).__name__}: {exc}"


@app.get("/health")
async def health(request: Request) -> dict[str, Any]:
    cliente = request.client.host if request.client else ""
    if not any(cliente.startswith(p) for p in ORIGENES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Origen no permitido")
    tiene_repo = (REPO_ORIGEN / ".git").exists()
    return {
        "status": "ok" if tiene_repo else "sin repositorio",
        "repo": str(REPO_ORIGEN),
        "sin_red": os.getenv("KAIROS_FORGE_NO_NET", "?"),
    }


@app.post("/ensayar", dependencies=[Depends(autorizar)])
async def ensayar(body: Ensayo) -> dict[str, Any]:
    """Aplica un parche en una copia y ejecuta los tests.

    El repositorio real NUNCA se toca. Se copia, se parchea la copia, se
    prueba, y la copia se destruye. Si el parche es destructivo, lo unico que
    destruye es un directorio temporal.
    """
    if len(body.parche.encode()) > MAX_PARCHE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Parche demasiado grande")
    if not (REPO_ORIGEN / ".git").exists():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No veo el repositorio")

    TRABAJO.mkdir(parents=True, exist_ok=True)
    destino = TRABAJO / f"ensayo-{uuid.uuid4().hex[:10]}"
    pasos: list[dict[str, Any]] = []
    inicio = time.perf_counter()

    def paso(nombre: str, code: int, salida: str) -> bool:
        pasos.append({"paso": nombre, "ok": code == 0, "salida": salida[-2000:]})
        return code == 0

    try:
        # 1. Copia local del repositorio. `git clone` desde el original en
        #    solo lectura: aunque el parche haga cualquier cosa, el origen no
        #    es escribible desde aqui.
        code, out = _correr(
            ["git", "clone", "--local", "--no-hardlinks", str(REPO_ORIGEN), str(destino)],
            cwd=TRABAJO, timeout=120,
        )
        if not paso("clonar", code, out):
            return _resultado(False, pasos, inicio)

        # 2. Rama nueva.
        code, out = _correr(["git", "checkout", "-b", body.rama], cwd=destino)
        if not paso("rama", code, out):
            return _resultado(False, pasos, inicio)

        # 3. Aplicar el parche. `git apply` valida el formato: un parche
        #    malformado se rechaza antes de tocar un solo fichero.
        parche_path = destino / ".kairos-propuesta.patch"
        parche_path.write_text(body.parche, encoding="utf-8")
        code, out = _correr(
            ["git", "apply", "--check", "-v", str(parche_path)], cwd=destino
        )
        if not paso("verificar parche", code, out):
            return _resultado(False, pasos, inicio)

        code, out = _correr(["git", "apply", str(parche_path)], cwd=destino)
        if not paso("aplicar parche", code, out):
            return _resultado(False, pasos, inicio)
        parche_path.unlink(missing_ok=True)

        # 4. Los tests. Sin red, con tope de tiempo, en la copia.
        code, out = _correr(
            ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
             "--ignore=tests/test_integracion_memoria.py"],
            cwd=destino / "apps" / "core", timeout=TIMEOUT_TESTS,
        )
        exito = paso("tests", code, out)

        # 5. Diff efectivo, para que la propuesta muestre lo que cambio de
        #    verdad y no lo que el parche decia que cambiaria.
        _, diff = _correr(["git", "diff", "HEAD"], cwd=destino, timeout=30)

        return _resultado(exito, pasos, inicio, diff=diff[:60000])
    finally:
        # Se borra pase lo que pase. Un ensayo no deja rastro.
        shutil.rmtree(destino, ignore_errors=True)


def _resultado(ok: bool, pasos: list[dict[str, Any]], inicio: float, diff: str = "") -> dict:
    return {
        "ok": ok,
        "pasos": pasos,
        "diff": diff,
        "duracion_ms": int((time.perf_counter() - inicio) * 1000),
    }


if __name__ == "__main__":
    if not SECRETO:
        print("[forge] KAIROS_FORGE_TOKEN vacio: el servicio rechazara todo")
    uvicorn.run(app, host="0.0.0.0", port=8300, log_level="warning")
