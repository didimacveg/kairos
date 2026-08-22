"""Generacion de parches a partir de ficheros completos.

DECISION IMPORTANTE: el modelo NO escribe diffs unificados. Escribe el
contenido completo del fichero resultante, y el diff lo calcula `difflib`.

Por que: los modelos de lenguaje producen diffs rotos con mucha frecuencia —
numeros de linea equivocados, contexto que no coincide, cuentas de @@ mal. Un
parche que no aplica es un ensayo perdido y una propuesta inutil.

Pedir el fichero entero elimina esa clase de fallo entera. Cuesta mas tokens,
pero el parche o es valido o no existe; nunca es "casi valido".
"""
from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass

MAX_FICHEROS = 6
MAX_LINEAS_FICHERO = 3000


@dataclass(frozen=True)
class Cambio:
    ruta: str
    contenido: str


def parsear_respuesta(bruto: str) -> tuple[list[Cambio], str]:
    """Extrae los ficheros propuestos y el motivo. Nunca lanza."""
    texto = bruto.strip()
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio == -1 or fin == -1:
        return [], ""
    try:
        datos = json.loads(texto[inicio : fin + 1])
    except json.JSONDecodeError:
        return [], ""
    if not isinstance(datos, dict):
        return [], ""

    motivo = str(datos.get("motivo", "")).strip()
    cambios: list[Cambio] = []
    for entrada in (datos.get("ficheros") or [])[:MAX_FICHEROS]:
        if not isinstance(entrada, dict):
            continue
        ruta = str(entrada.get("ruta", "")).strip().lstrip("/")
        contenido = entrada.get("contenido")
        if not ruta or not isinstance(contenido, str):
            continue
        # Rutas que se escapan del repositorio se descartan aqui, antes de
        # llegar al forge.
        if ".." in ruta or ruta.startswith("~"):
            continue
        if contenido.count("\n") > MAX_LINEAS_FICHERO:
            continue
        cambios.append(Cambio(ruta=ruta, contenido=contenido))
    return cambios, motivo


def construir_diff(original: str | None, nuevo: str, ruta: str) -> str:
    """Diff unificado en el formato que entiende `git apply`."""
    antes = (original or "").splitlines(keepends=True)
    despues = nuevo.splitlines(keepends=True)
    if antes == despues:
        return ""

    a = f"a/{ruta}" if original is not None else "/dev/null"
    b = f"b/{ruta}"
    cabecera = f"diff --git a/{ruta} b/{ruta}\n"
    if original is None:
        cabecera += "new file mode 100644\n"

    cuerpo = "".join(
        difflib.unified_diff(antes, despues, fromfile=a, tofile=b, n=3)
    )
    if not cuerpo:
        return ""
    # `git apply` exige que la ultima linea termine en salto.
    if not cuerpo.endswith("\n"):
        cuerpo += "\n\\ No newline at end of file\n"
    return cabecera + cuerpo


def nombre_rama(peticion: str) -> str:
    """Rama legible y valida para git a partir de la peticion."""
    limpio = re.sub(r"[^a-zA-Z0-9]+", "-", peticion.lower()).strip("-")[:40]
    return f"kairos/{limpio or 'propuesta'}"
