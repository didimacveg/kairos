"""Lectura del repositorio: lo que KAIROS puede ver de si mismo.

Acceso de SOLO LECTURA y acotado. El agente puede leer su codigo para
proponerse cambios, pero:

- No sale del arbol del repositorio. Cualquier ruta que se escape tras
  resolver enlaces simbolicos y `..` se rechaza.
- No ve secretos. `.env`, tokens y credenciales estan excluidos por patron,
  no por confianza: el agente manda su propuesta a un modelo remoto, y una
  clave dentro del contexto es una clave filtrada.
- No ve binarios ni dependencias: `node_modules`, `.git`, modelos, imagenes.
  No aportan nada a un parche y llenarian la ventana de contexto.
"""
from __future__ import annotations

from pathlib import Path

RAIZ = Path("/repo")

EXTENSIONES = {".py", ".ts", ".tsx", ".css", ".yml", ".yaml", ".md", ".json", ".sh", ".toml"}

EXCLUIDOS = {
    ".git", "node_modules", ".next", "__pycache__", ".pytest_cache",
    ".ruff_cache", ".venv", "dist", "build", "data", "models", "voices",
}

# Ficheros que NUNCA se leen, aunque encajen por extension.
SECRETOS = {".env", ".bridge-secret", ".spotify-auth.json", "bridge-config.json"}

MAX_BYTES_FICHERO = 120_000


def _seguro(ruta: Path) -> bool:
    """La ruta resuelta tiene que seguir dentro del repositorio."""
    try:
        resuelta = ruta.resolve()
        return resuelta.is_relative_to(RAIZ.resolve())
    except (OSError, ValueError):
        return False


def listar() -> list[str]:
    """Indice de ficheros de codigo, relativos a la raiz."""
    if not RAIZ.exists():
        return []
    salida: list[str] = []
    for ruta in RAIZ.rglob("*"):
        if not ruta.is_file():
            continue
        if any(parte in EXCLUIDOS for parte in ruta.parts):
            continue
        if ruta.name in SECRETOS or ruta.name.startswith(".env"):
            continue
        if ruta.suffix not in EXTENSIONES:
            continue
        if not _seguro(ruta):
            continue
        salida.append(str(ruta.relative_to(RAIZ)))
    return sorted(salida)


def leer(relativa: str) -> str | None:
    """Contenido de un fichero, o None si no se puede o no se debe leer."""
    ruta = RAIZ / relativa
    if not _seguro(ruta) or not ruta.is_file():
        return None
    if ruta.name in SECRETOS or ruta.name.startswith(".env"):
        return None
    if any(parte in EXCLUIDOS for parte in ruta.parts):
        return None
    if ruta.suffix not in EXTENSIONES:
        return None
    try:
        datos = ruta.read_bytes()[:MAX_BYTES_FICHERO]
        return datos.decode("utf-8", errors="replace")
    except OSError:
        return None


def arbol_resumido(limite: int = 400) -> str:
    """Indice compacto para que el modelo sepa que existe antes de pedir."""
    ficheros = listar()[:limite]
    return "\n".join(ficheros)
