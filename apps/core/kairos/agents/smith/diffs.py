"""Generacion de parches a partir de ficheros completos.

DOS DECISIONES, ambas por lo mismo: darle al modelo el formato con menos
oportunidades de equivocarse.

1. **El modelo no escribe diffs unificados.** Escribe el fichero resultante
   entero y el diff lo calcula `difflib`. Los diffs generados por modelos
   fallan mucho: numeros de linea equivocados, contexto que no coincide.

2. **El modelo no responde en JSON.** Responde con marcadores en texto plano.
   Meter un fichero Python dentro de un campo JSON obliga a escapar cada
   comilla, cada barra y cada salto de linea — miles de oportunidades de
   fallar en un fichero de 200 lineas. En la primera prueba real el modelo
   escapo una comilla simple (que en JSON no se escapa) y toda la respuesta
   quedo inservible, con un plan que era correcto.

   Con marcadores no hay nada que escapar. El parser busca las lineas de
   delimitacion y corta.

El formato correcto es el que menos margen de error le deja al modelo, no el
mas elegante.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

MAX_FICHEROS = 6
MAX_LINEAS_FICHERO = 3000

INICIO = "--- FICHERO:"
FIN = "--- FIN FICHERO"


@dataclass(frozen=True)
class Cambio:
    ruta: str
    contenido: str


@dataclass(frozen=True)
class Propuesta:
    cambios: list[Cambio]
    motivo: str
    riesgo: str


def parsear_respuesta(bruto: str) -> tuple[list[Cambio], str]:
    """Compatibilidad con la firma anterior."""
    p = parsear(bruto)
    return p.cambios, p.motivo


def parsear(bruto: str) -> Propuesta:
    """Extrae motivo, riesgo y ficheros. Nunca lanza.

    Tolerante a propósito: si el modelo añade texto antes o después de los
    marcadores, se ignora. Lo unico que importa es lo que hay entre ellos.
    """
    texto = bruto.replace("\r\n", "\n")

    motivo = ""
    riesgo = "medio"
    for linea in texto.split("\n")[:20]:
        limpia = linea.strip()
        if limpia.upper().startswith("MOTIVO:"):
            motivo = limpia.split(":", 1)[1].strip()
        elif limpia.upper().startswith("RIESGO:"):
            valor = limpia.split(":", 1)[1].strip().lower()
            if valor in {"bajo", "medio", "alto"}:
                riesgo = valor

    cambios: list[Cambio] = []
    posicion = 0
    while len(cambios) < MAX_FICHEROS:
        i = texto.find(INICIO, posicion)
        if i == -1:
            break
        fin_cabecera = texto.find("\n", i)
        if fin_cabecera == -1:
            break
        ruta = texto[i + len(INICIO) : fin_cabecera].strip().strip("`").lstrip("/")

        j = texto.find(FIN, fin_cabecera)
        if j == -1:
            break
        contenido = texto[fin_cabecera + 1 : j]
        posicion = j + len(FIN)

        # Rutas que se escapan del repositorio se descartan aqui, antes de
        # llegar al forge.
        if not ruta or ".." in ruta or ruta.startswith("~"):
            continue
        if contenido.count("\n") > MAX_LINEAS_FICHERO:
            continue
        if not contenido.strip():
            continue
        # El modelo a veces envuelve el fichero en un bloque de codigo.
        contenido = _quitar_valla(contenido)
        if not contenido.endswith("\n"):
            contenido += "\n"
        cambios.append(Cambio(ruta=ruta, contenido=contenido))

    return Propuesta(cambios=cambios, motivo=motivo, riesgo=riesgo)


def _quitar_valla(texto: str) -> str:
    """Quita ```python ... ``` si el modelo lo ha metido igualmente."""
    lineas = texto.split("\n")
    while lineas and not lineas[0].strip():
        lineas.pop(0)
    while lineas and not lineas[-1].strip():
        lineas.pop()
    if lineas and lineas[0].lstrip().startswith("```"):
        lineas.pop(0)
        if lineas and lineas[-1].strip().startswith("```"):
            lineas.pop()
    return "\n".join(lineas)


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

    cuerpo = "".join(difflib.unified_diff(antes, despues, fromfile=a, tofile=b, n=3))
    if not cuerpo:
        return ""
    if not cuerpo.endswith("\n"):
        cuerpo += "\n\\ No newline at end of file\n"
    return cabecera + cuerpo


def nombre_rama(peticion: str) -> str:
    """Rama legible y valida para git a partir de la peticion."""
    import unicodedata

    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", peticion.lower())
        if unicodedata.category(c) != "Mn"
    )
    limpio = re.sub(r"[^a-z0-9]+", "-", sin_tildes).strip("-")[:40]
    return f"kairos/{limpio or 'propuesta'}"
