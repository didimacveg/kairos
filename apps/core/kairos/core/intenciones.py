"""Reconocimiento de intenciones: que quiere Diego con este mensaje.

POR QUE ESTE FICHERO EXISTE: los seis detectores vivian sueltos dentro del
orquestador, que habia llegado a 937 lineas. Cada fase nueva anadia otro
metodo estatico con su propia expresion regular y sus propias reglas de
normalizacion, todas ligeramente distintas.

Juntos aqui se ve lo que comparten y, sobre todo, **se ve el orden**: cual
gana cuando dos podrian encajar. Eso antes estaba implicito en el orden de
los `if` del orquestador y era invisible.

EL PRINCIPIO QUE LOS GOBIERNA A TODOS: **preambulo explicito, nunca
interpretacion.** Hablar de una funcionalidad no es pedirla; preguntar por los
recordatorios no es crear uno. Si el modelo decidiera que es una orden,
cualquier conversacion sobre diseno acabaria generando propuestas.
"""
from __future__ import annotations

import re
import unicodedata


def normalizar(texto: str) -> str:
    """Minusculas, sin tildes, sin espacios de sobra.

    Una sola funcion para los seis detectores: antes cada uno hacia su propia
    version y se colaban diferencias sutiles.
    """
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    ).strip()


# --- 1. Cambios sobre el propio KAIROS ------------------------------------

_CAMBIO = re.compile(
    r"^\s*(kairos[,:]?\s*)?"
    r"(proponte|propon|hazte capaz de|hazte una|aprende a|programate|"
    r"haz que puedas|modificate para)\s+(?P<que>.{10,900})$",
    re.I | re.S,
)


def peticion_de_cambio(mensaje: str) -> str | None:
    """"Proponte X" -> X. Cualquier otra cosa -> None."""
    m = _CAMBIO.match(normalizar(mensaje))
    return m.group("que").strip() if m else None


# --- 2. Encargos en segundo plano -----------------------------------------

_ENCARGO = re.compile(
    r"^\s*(kairos[,:]?\s*)?"
    r"(hazme|haz|escribeme|escribe|redactame|redacta|preparame|prepara|"
    r"desarrollame|desarrolla|montame|monta)\s+(?P<que>.{20,1800})$",
    re.I | re.S,
)
# Lo que parece encargo pero es una accion del escritorio.
_ES_ESCRITORIO = re.compile(r"\b(perfil|modo trabajo|modo juego|modo estudio)\b", re.I)


def encargo(mensaje: str) -> str | None:
    m = _ENCARGO.match(normalizar(mensaje))
    if not m:
        return None
    que = m.group("que").strip()
    return None if _ES_ESCRITORIO.search(que) else que


# --- 3. El informe del dia -------------------------------------------------

# Preguntas SOBRE el informe, que no son peticiones de informe.
_PREGUNTA_INFORME = re.compile(
    r"\b(que|como|cuando|por que|cual)\b.{0,30}\binforme", re.I
)
_PIDE_INFORME = re.compile(
    r"\b(dame|damelo|ponme|leeme|cuentame|quiero|necesito|generame|"
    r"hazme|lanza|repite)\b.{0,25}\b(informe|resumen|parte)\b"
    r"|\binforme\s+(de[l]?\s+)?(dia|hoy|diario)\b"
    r"|\bresumen\s+(de[l]?\s+)?(dia|hoy)\b"
    r"|\bponme al dia\b"
    r"|\bque tal (va )?(el )?dia\b",
    re.I,
)


def pide_informe(mensaje: str) -> bool:
    limpio = normalizar(mensaje)
    if _PREGUNTA_INFORME.search(limpio):
        return False
    return bool(_PIDE_INFORME.search(limpio))


# --- 4. Recordatorios ------------------------------------------------------

_PREGUNTA_AVISO = re.compile(
    r"^(que|cuantos|cuales|cuando)\b.{0,30}\b(recordatorio|aviso)", re.I
)
_PIDE_AVISO = re.compile(
    r"\b(recuerdame|recuerda que|avisame|avisa cuando|despiertame|"
    r"no me dejes olvidar|apunta que|ponme un recordatorio|"
    r"anotame|programa un aviso)\b",
    re.I,
)


def peticion_de_aviso(mensaje: str) -> bool:
    limpio = normalizar(mensaje)
    if _PREGUNTA_AVISO.match(limpio):
        return False
    return bool(_PIDE_AVISO.search(limpio))


# --- 5. Prefiltro de acciones del escritorio -------------------------------

_ACCIONABLE = re.compile(
    r"\b(perfil|modo|musica|cancion|spotify|volumen|abre|abrir|pon|"
    r"pausa|para|cierra|reproduce|siguiente|anterior|suena|app|"
    r"aplicacion|ventana|pantalla|trabajo|estudio|juego)\b",
    re.I,
)
_INTERROGATIVO = re.compile(
    r"^(que|quien|cuando|donde|cuanto|cuanta|como|cual|por que|"
    r"para que|explicame|dime|cuentame|sabes|puedes decirme)\b",
    re.I,
)


def huele_a_orden(mensaje: str) -> bool:
    """Prefiltro barato antes de gastar una llamada al modelo.

    ANTE LA DUDA, DEVUELVE True: perder medio segundo clasificando es mejor
    que ignorar una orden. Solo se descarta lo que es inequivocamente
    conversacion.
    """
    limpio = normalizar(mensaje).strip(" ?¿!¡.,")
    if _ACCIONABLE.search(limpio):
        return True
    return not _INTERROGATIVO.match(limpio)


# --- El orden importa ------------------------------------------------------
#
# Cuando dos detectores podrian encajar, gana el primero de esta lista. El
# orden no es arbitrario:
#
#   1. encargo          "hazme un trabajo sobre X" — lo mas especifico
#   2. peticion_cambio  "proponte X" — preambulo inconfundible
#   3. peticion_aviso   "recuerdame X"
#   4. pide_informe     "dame el informe"
#   5. huele_a_orden    prefiltro de escritorio
#   6. conversacion     lo demas
#
# De lo mas especifico a lo mas general. Al reves, "hazme un resumen del dia
# sobre la fotosintesis" se tomaria por una peticion de informe.
ORDEN = (
    "encargo",
    "peticion_de_cambio",
    "peticion_de_aviso",
    "pide_informe",
    "huele_a_orden",
)
