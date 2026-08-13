"""Acciones sobre el escritorio de Windows.

TODO lo que este modulo puede hacer esta declarado en un fichero de
configuracion que escribe el usuario. No existe ninguna funcion que ejecute
una cadena arbitraria: no hay `os.system`, no hay `shell=True`, y el nucleo
—y por tanto el modelo— solo puede pedir acciones POR NOMBRE.

Esa es la frontera de seguridad del proyecto. Un modelo de lenguaje con
capacidad de ejecutar comandos arbitrarios en tu maquina es exactamente el
escenario que los propios informes de seguridad de Meta miden con Glimmer:
una de cada cuatro inyecciones de prompt tiene exito. La defensa no puede ser
"que el modelo se porte bien"; tiene que ser que no pueda.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()


@dataclass
class Monitor:
    index: int
    left: int
    top: int
    right: int
    bottom: int
    is_primary: bool = False

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


def list_monitors() -> list[Monitor]:
    """Enumera los monitores fisicos, en orden de posicion horizontal."""
    if not IS_WINDOWS:
        return []

    found: list[Monitor] = []

    MonitorEnumProc = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
        ctypes.POINTER(wintypes.RECT), ctypes.c_double,
    )

    def callback(hmon, hdc, lprect, data):  # type: ignore[no-untyped-def]
        r = lprect.contents
        # El monitor principal es el que tiene su esquina en (0,0). Windows lo
        # define asi, y es mas fiable que adivinar por posicion horizontal.
        primary = r.left == 0 and r.top == 0
        found.append(Monitor(len(found), r.left, r.top, r.right, r.bottom, primary))
        return 1

    user32.EnumDisplayMonitors(0, 0, MonitorEnumProc(callback), 0)
    found.sort(key=lambda m: m.left)
    for i, m in enumerate(found):
        m.index = i
    return found


def find_window(pattern: str) -> int | None:
    """Primera ventana visible cuyo titulo contenga `pattern`."""
    if not IS_WINDOWS:
        return None

    pattern = pattern.lower()
    match: list[int] = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

    def callback(hwnd, _):  # type: ignore[no-untyped-def]
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if pattern in buf.value.lower():
            match.append(hwnd)
            return False
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return match[0] if match else None


SW_MINIMIZE = 6
SW_RESTORE = 9
SW_MAXIMIZE = 3
HWND_TOP = 0
SWP_SHOWWINDOW = 0x0040


def place_window(hwnd: int, monitor: Monitor, slot: str) -> None:
    """Coloca una ventana en un monitor y una posicion.

    slots: full, left, right, top-left, top-right, bottom-left, bottom-right
    """
    if not IS_WINDOWS:
        return

    user32.ShowWindow(hwnd, SW_RESTORE)
    w, h = monitor.width, monitor.height
    x, y = monitor.left, monitor.top

    layout = {
        "full": (x, y, w, h),
        "left": (x, y, w // 2, h),
        "right": (x + w // 2, y, w // 2, h),
        "top-left": (x, y, w // 2, h // 2),
        "top-right": (x + w // 2, y, w // 2, h // 2),
        "bottom-left": (x, y + h // 2, w // 2, h // 2),
        "bottom-right": (x + w // 2, y + h // 2, w // 2, h // 2),
    }
    rect = layout.get(slot, layout["full"])
    user32.SetWindowPos(hwnd, HWND_TOP, *rect, SWP_SHOWWINDOW)


def resolve_monitor(monitors: list[Monitor], value: Any) -> Monitor:
    """Acepta un indice, "principal" o "secundario".

    Por nombre es mas robusto: los indices bailan si cambias los monitores de
    sitio en la configuracion de Windows, y entonces las ventanas aparecen
    donde no toca sin que nada haya cambiado en el fichero.
    """
    if not monitors:
        raise ValueError("sin monitores")
    if isinstance(value, str):
        key = value.strip().lower()
        if key in {"principal", "primary", "main"}:
            return next((m for m in monitors if m.is_primary), monitors[0])
        if key in {"secundario", "secondary", "segundo"}:
            return next((m for m in monitors if not m.is_primary), monitors[-1])
    try:
        return monitors[min(int(value), len(monitors) - 1)]
    except (TypeError, ValueError):
        return monitors[0]


@dataclass
class AppSpec:
    """Una aplicacion declarada en la configuracion.

    `launch` puede ser una ruta a ejecutable, un URI (spotify:, ms-teams:) o
    una URL. NUNCA se interpreta como linea de comandos con shell.
    """
    name: str
    launch: str
    window: str = ""
    monitor: Any = "principal"
    slot: str = "full"
    args: list[str] = field(default_factory=list)
    play: bool = False
    # Aplicaciones que hacen falta corriendo pero no quieres ver.
    background: bool = False


def launch(spec: AppSpec) -> str:
    """Lanza o reposiciona. Si ya esta abierta, no duplica: la recoloca.

    Nunca se usa shell=True. `launch` va como argv[0] o se abre con el
    manejador de protocolo del sistema; no hay interpolacion de cadenas.
    """
    hwnd = find_window(spec.window) if spec.window else None

    if hwnd is None:
        try:
            if spec.launch.startswith(("http://", "https://")) or "://" in spec.launch:
                # URI o URL: lo resuelve el sistema, sin shell.
                if IS_WINDOWS:
                    ctypes.windll.shell32.ShellExecuteW(None, "open", spec.launch, None, None, 1)
                else:
                    subprocess.Popen(["xdg-open", spec.launch])
            else:
                resolved = shutil.which(spec.launch) or spec.launch
                subprocess.Popen([resolved, *spec.args])
        except Exception as exc:  # noqa: BLE001
            return f"no se pudo abrir {spec.name}: {exc}"

        # Margen para que la ventana aparezca antes de recolocarla.
        for _ in range(20):
            time.sleep(0.25)
            if spec.window:
                hwnd = find_window(spec.window)
                if hwnd:
                    break
        action = "abierta"
    else:
        action = "recolocada"

    if hwnd and spec.background:
        if IS_WINDOWS:
            user32.ShowWindow(hwnd, SW_MINIMIZE)
        return f"{spec.name} {action} en segundo plano"

    if hwnd and spec.window:
        monitors = list_monitors()
        if monitors:
            place_window(hwnd, resolve_monitor(monitors, spec.monitor), spec.slot)

    # Con la API de Spotify autorizada, la reproduccion la lleva ella;
    # la tecla multimedia solo es el plan B.
    API_MANAGED = spec.launch.startswith('spotify:track:')
    if spec.play and spec.window and not API_MANAGED:
        return f"{spec.name} {action}, {ensure_playing(spec.window)}"

    return f"{spec.name} {action}"


VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_PREV_TRACK = 0xB1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

# Cuando Spotify reproduce, su titulo de ventana es "Artista - Cancion".
# Parado o recien abierto es solo "Spotify" (o "Spotify Premium"/"Spotify Free").
IDLE_TITLES = {"spotify", "spotify premium", "spotify free", "advertisement"}


def window_title(pattern: str) -> str:
    """Titulo completo de la primera ventana que coincida."""
    if not IS_WINDOWS:
        return ""
    hwnd = find_window(pattern)
    if hwnd is None:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _tap(key: int) -> None:
    if not IS_WINDOWS:
        return
    user32.keybd_event(key, 0, KEYEVENTF_EXTENDEDKEY, 0)
    user32.keybd_event(key, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)


def restart_track() -> None:
    """Vuelve al principio de la cancion actual.

    Spotify reanuda donde lo dejaste, asi que abrir el URI de una cancion ya
    escuchada la retoma a mitad. "Pista anterior" reinicia la actual cuando
    llevas mas de unos segundos, que es exactamente el caso.
    """
    _tap(VK_MEDIA_PREV_TRACK)


def press_play() -> None:
    """Tecla multimedia global de reproduccion/pausa."""
    if not IS_WINDOWS:
        return
    _tap(VK_MEDIA_PLAY_PAUSE)


def ensure_playing(pattern: str, timeout: float = 12.0) -> str:
    """Arranca la reproduccion si esta parada.

    Abrir `spotify:track:ID` navega a la cancion pero NO la reproduce: es
    comportamiento de Spotify, no un fallo. Se resuelve mandando la tecla
    multimedia, pero solo si hace falta — pulsarla a ciegas pausaria algo que
    ya estuviera sonando. El titulo de la ventana dice cual de los dos casos
    es.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        title = window_title(pattern).strip()
        if not title:
            time.sleep(0.5)
            continue
        if title.lower() not in IDLE_TITLES:
            restart_track()
            time.sleep(0.4)
            return f"reproduciendo desde el principio: {title}"
        press_play()
        time.sleep(1.5)
        title = window_title(pattern).strip()
        if title.lower() not in IDLE_TITLES:
            restart_track()
            time.sleep(0.4)
            return f"reproduciendo desde el principio: {title}"
        time.sleep(1.0)
    return "abierto, pero no arranco la reproduccion"


def focus(pattern: str) -> str:
    hwnd = find_window(pattern)
    if hwnd is None:
        return f"no encontrada: {pattern}"
    if IS_WINDOWS:
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
    return f"al frente: {pattern}"


def close_window(pattern: str) -> str:
    """Cierra por mensaje WM_CLOSE: la app puede guardar y preguntar.

    Deliberadamente NO se mata el proceso. Cerrar sin guardar por orden de un
    modelo de lenguaje es exactamente el tipo de dano irreversible que este
    diseno evita.
    """
    hwnd = find_window(pattern)
    if hwnd is None:
        return f"no encontrada: {pattern}"
    if IS_WINDOWS:
        user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
    return f"cerrada: {pattern}"


def describe_desktop() -> dict[str, Any]:
    monitors = list_monitors()
    return {
        "monitores": [
            {"indice": m.index, "ancho": m.width, "alto": m.height,
             "principal": m.is_primary, "x": m.left}
            for m in monitors
        ],
        "plataforma": sys.platform,
    }
