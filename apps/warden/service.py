"""KAIROS Warden — el unico proceso que escribe en el repositorio real.

Existe porque alguien tiene que aplicar lo aprobado, y ese alguien no puede
ser ni el nucleo (tiene tus claves) ni el forge (ejecuta codigo no verificado).

QUE HACE, y nada mas:
  1. crea una rama desde el estado actual
  2. aplica el parche aprobado
  3. ejecuta la suite de tests SOBRE EL RESULTADO
  4. si pasa, hace merge a la rama principal
  5. si no pasa, borra la rama y no toca nada

QUE NO HACE:
  - ejecutar comandos arbitrarios: cuatro operaciones, todas escritas aqui
  - reiniciar contenedores: eso lo hace Diego con un comando. El reinicio es
    el momento irreversible, y tener a un humano delante significa que un
    merge malo no deja KAIROS muerto mientras duerme
  - aplicar nada sin `aprobada=true`: el nucleo lo comprueba antes, y aqui se
    exige otra vez. Dos cerrojos para lo unico que escribe.

Guarda SIEMPRE el commit anterior. Deshacer es un comando.
"""
from __future__ import annotations

import os
import secrets
import subprocess
import time
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

REPO = Path(os.getenv("KAIROS_WARDEN_REPO", "/repo"))
SECRETO = os.getenv("KAIROS_WARDEN_TOKEN", "")
RAMA_PRINCIPAL = os.getenv("KAIROS_WARDEN_MAIN", "main")
TIMEOUT_TESTS = int(os.getenv("KAIROS_WARDEN_TIMEOUT", "420"))
ORIGENES = ("127.", "::1", "10.", "172.", "192.168.")

app = FastAPI(title="KAIROS Warden", version="0.1.0")


def autorizar(request: Request, x_warden_token: str = Header(default="")) -> None:
    cliente = request.client.host if request.client else ""
    if not any(cliente.startswith(p) for p in ORIGENES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Origen no permitido")
    if not SECRETO or not secrets.compare_digest(x_warden_token, SECRETO):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalido")


class Aplicacion(BaseModel):
    rama: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9/_.-]+$")
    parche: str = Field(min_length=1)
    titulo: str = Field(min_length=1, max_length=200)
    aprobada: bool = False


def _git(*args: str, timeout: int = 120) -> tuple[int, str]:
    """git con lista de argumentos. Nunca shell, nunca cadena interpolada."""
    try:
        r = subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True,
            timeout=timeout, shell=False,
        )
        return r.returncode, (r.stdout + r.stderr)[-4000:]
    except subprocess.TimeoutExpired:
        return 124, f"tiempo agotado tras {timeout}s"
    except Exception as exc:  # noqa: BLE001
        return 1, f"{type(exc).__name__}: {exc}"


def _tests() -> tuple[int, str]:
    try:
        r = subprocess.run(
            ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
             "--ignore=tests/test_integracion_memoria.py"],
            cwd=REPO / "apps" / "core", capture_output=True, text=True,
            timeout=TIMEOUT_TESTS, shell=False,
        )
        return r.returncode, (r.stdout + r.stderr)[-6000:]
    except Exception as exc:  # noqa: BLE001
        return 1, f"{type(exc).__name__}: {exc}"


@app.get("/health")
async def health(request: Request) -> dict[str, Any]:
    cliente = request.client.host if request.client else ""
    if not any(cliente.startswith(p) for p in ORIGENES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Origen no permitido")
    code, salida = _git("rev-parse", "--short", "HEAD", timeout=15)
    return {
        "status": "ok" if code == 0 else "sin repositorio",
        "commit": salida.strip() if code == 0 else None,
        "rama_principal": RAMA_PRINCIPAL,
    }


@app.post("/aplicar", dependencies=[Depends(autorizar)])
async def aplicar(body: Aplicacion) -> dict[str, Any]:
    """Aplica un parche aprobado. Si los tests fallan, no queda rastro."""
    if not body.aprobada:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Solo se aplican propuestas aprobadas explicitamente",
        )

    pasos: list[dict[str, Any]] = []
    inicio = time.perf_counter()

    def paso(nombre: str, code: int, salida: str) -> bool:
        pasos.append({"paso": nombre, "ok": code == 0, "salida": salida[-1500:]})
        return code == 0

    # El estado al que volver si algo sale mal.
    code, commit_previo = _git("rev-parse", "HEAD", timeout=15)
    if code != 0:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No veo el repositorio")
    commit_previo = commit_previo.strip()

    # El arbol tiene que estar limpio: aplicar sobre cambios sin guardar
    # produciria un commit con cosas que nadie reviso.
    code, salida = _git("status", "--porcelain", timeout=20)
    if salida.strip():
        return {
            "ok": False,
            "error": "El repositorio tiene cambios sin guardar. Haz commit o stash primero.",
            "detalle": salida[:1000],
            "commit_previo": commit_previo,
        }

    rama_destino = f"{body.rama}-{int(time.time())}"
    try:
        if not paso("rama", *_git("checkout", "-b", rama_destino)):
            return _fin(False, pasos, commit_previo, inicio)

        parche = REPO / ".kairos-aplicar.patch"
        parche.write_text(body.parche, encoding="utf-8")
        if not paso("verificar", *_git("apply", "--check", "-v", str(parche))):
            parche.unlink(missing_ok=True)
            _git("checkout", RAMA_PRINCIPAL)
            _git("branch", "-D", rama_destino)
            return _fin(False, pasos, commit_previo, inicio)

        paso("aplicar", *_git("apply", str(parche)))
        parche.unlink(missing_ok=True)

        _git("add", "-A")
        mensaje = f"feat(kairos): {body.titulo}\n\nPropuesto por Smith y aprobado por el usuario."
        if not paso("commit", *_git("commit", "-m", mensaje)):
            _git("checkout", "-f", RAMA_PRINCIPAL)
            _git("branch", "-D", rama_destino)
            return _fin(False, pasos, commit_previo, inicio)

        # La comprobacion que de verdad importa: los tests sobre el resultado
        # real, no sobre el clon del forge.
        if not paso("tests", *_tests()):
            _git("checkout", "-f", RAMA_PRINCIPAL)
            _git("branch", "-D", rama_destino)
            return _fin(False, pasos, commit_previo, inicio)

        if not paso("volver a principal", *_git("checkout", RAMA_PRINCIPAL)):
            return _fin(False, pasos, commit_previo, inicio)

        if not paso("merge", *_git("merge", "--no-ff", rama_destino, "-m",
                                   f"merge: {body.titulo}")):
            _git("merge", "--abort")
            return _fin(False, pasos, commit_previo, inicio)

        return _fin(True, pasos, commit_previo, inicio, rama=rama_destino)
    except Exception as exc:  # noqa: BLE001
        pasos.append({"paso": "excepcion", "ok": False, "salida": str(exc)})
        _git("checkout", "-f", RAMA_PRINCIPAL)
        return _fin(False, pasos, commit_previo, inicio)


def _fin(ok: bool, pasos: list, previo: str, inicio: float, rama: str = "") -> dict:
    _, actual = _git("rev-parse", "--short", "HEAD", timeout=15)
    return {
        "ok": ok,
        "pasos": pasos,
        "commit_previo": previo,
        "commit_actual": actual.strip(),
        "rama": rama,
        "deshacer": f"git reset --hard {previo[:12]}" if ok else "",
        "duracion_ms": int((time.perf_counter() - inicio) * 1000),
    }


if __name__ == "__main__":
    if not SECRETO:
        print("[warden] KAIROS_WARDEN_TOKEN vacio: rechazara todo")
    uvicorn.run(app, host="0.0.0.0", port=8400, log_level="warning")
