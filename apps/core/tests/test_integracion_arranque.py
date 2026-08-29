"""Tests que verifican que KAIROS ARRANCA, no solo que compila.

POR QUE FALTABAN, y por que son los mas importantes de la suite:

Los 240 tests que ya existen usan dobles. Verifican que cada pieza hace lo que
dice su firma. Ninguno construye el sistema entero.

Y eso es exactamente donde ha fallado KAIROS cinco veces esta semana:
  - `Mapped[Any]` sin importar Any     -> compilaba, no arrancaba
  - `EmbeddingProvider` inexistente    -> compilaba, no arrancaba
  - `routes_tareas` que no existia     -> compilaba, no arrancaba
  - un `yield` en el metodo equivocado -> ni compilaba, y ast.parse lo aprobo
  - el modelo Task que faltaba         -> compilaba, no arrancaba

Los cinco los habria pillado un test que simplemente llame a build_core() e
importe el router. Eso es lo que hay aqui.

**Verificar que el codigo compila no es verificar que arranca.** Es la leccion
mas cara de este proyecto, y hasta ahora no estaba escrita en ningun test.
"""
from __future__ import annotations

import importlib
import pathlib
import re

import pytest


# --- 1. El sistema se construye entero ------------------------------------

def test_el_nucleo_se_construye() -> None:
    """build_core() resuelve todos los imports y registra todos los agentes.

    Si un agente importa algo que no existe, esto revienta aqui en lugar de
    dejar el contenedor en bucle.
    """
    from kairos.core.bootstrap import build_core

    core = build_core()
    assert core is not None
    assert core.registry is not None


def test_el_router_importa_todas_sus_rutas() -> None:
    """Un modulo que el router pide y no existe tumba el arranque.

    Ha pasado tres veces: el router se escribia con la lista de lo que
    DEBERIA haber, no con lo que hay en disco.
    """
    from kairos.api.v1.router import api_router

    assert len(api_router.routes) > 10


def test_la_app_completa_se_importa() -> None:
    """El import que hace uvicorn al arrancar, tal cual."""
    modulo = importlib.import_module("kairos.main")
    assert hasattr(modulo, "app")


# --- 2. Los modelos resuelven sus anotaciones ------------------------------

def test_todos_los_modelos_configuran_su_mapper() -> None:
    """SQLAlchemy resuelve las anotaciones al CONFIGURAR, no al importar.

    `Mapped[Any]` sin importar Any pasa la compilacion y revienta aqui. Es
    literalmente el fallo que tumbo KAIROS durante una hora.
    """
    from sqlalchemy.orm import configure_mappers

    import kairos.db.models  # noqa: F401

    configure_mappers()


def test_cada_tabla_tiene_clave_primaria() -> None:
    from kairos.db.models import Base

    for nombre, tabla in Base.metadata.tables.items():
        assert tabla.primary_key.columns, f"{nombre} sin clave primaria"


# --- 3. Coherencia entre lo que se pide y lo que existe --------------------

def _raiz() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1] / "kairos"


def test_el_router_no_pide_rutas_que_no_existen() -> None:
    """Comprueba el disco, no los imports: si falla, dice CUAL falta."""
    router = (_raiz() / "api/v1/router.py").read_text(encoding="utf-8")
    pedidas = set(re.findall(r"\broutes_\w+", router))
    existen = {p.stem for p in (_raiz() / "api/v1").glob("routes_*.py")}
    faltan = pedidas - existen
    assert not faltan, f"el router pide rutas que no existen: {sorted(faltan)}"


def test_el_bootstrap_no_importa_agentes_que_no_existen() -> None:
    boot = (_raiz() / "core/bootstrap.py").read_text(encoding="utf-8")
    pedidos = set(re.findall(r"from kairos\.agents\.(\w+)\.agent import", boot))
    existen = {p.name for p in (_raiz() / "agents").iterdir() if p.is_dir()}
    faltan = pedidos - existen
    assert not faltan, f"el bootstrap importa agentes inexistentes: {sorted(faltan)}"


def test_todos_los_paquetes_de_agente_tienen_init() -> None:
    """Sin __init__.py el paquete no es importable y el arranque falla."""
    sin_init = [
        d.name for d in (_raiz() / "agents").iterdir()
        if d.is_dir() and d.name != "__pycache__" and not (d / "__init__.py").exists()
    ]
    assert not sin_init, f"agentes sin __init__.py: {sin_init}"


def test_los_planificadores_estan_arrancados_en_main() -> None:
    """Un planificador que existe pero nadie lanza es codigo muerto.

    Ha pasado: el de tareas se escribio y nunca se enganchó en main.py.
    """
    main = (_raiz() / "main.py").read_text(encoding="utf-8")
    planificadores = [
        p.parent.name for p in (_raiz() / "agents").rglob("scheduler.py")
    ]
    sin_arrancar = [
        nombre for nombre in planificadores
        if f"agents.{nombre}.scheduler" not in main
    ]
    assert not sin_arrancar, f"planificadores sin arrancar: {sin_arrancar}"


# --- 4. Los agentes cumplen su contrato ------------------------------------

def test_cada_agente_declara_capacidades_no_vacias() -> None:
    from kairos.core.bootstrap import build_core

    core = build_core()
    for agente in core.registry.all():
        assert agente.capabilities, f"{agente.name} sin capacidades"
        assert agente.name, "agente sin nombre"


def test_no_hay_capacidades_duplicadas_entre_agentes() -> None:
    """Dos agentes con la misma capacidad = comportamiento impredecible."""
    from kairos.core.bootstrap import build_core

    vistas: dict[str, str] = {}
    for agente in build_core().registry.all():
        for cap in agente.capabilities:
            assert cap not in vistas, (
                f"'{cap}' la declaran {vistas.get(cap)} y {agente.name}"
            )
            vistas[cap] = agente.name


@pytest.mark.asyncio
async def test_todos_los_agentes_responden_a_health() -> None:
    """health() no debe lanzar aunque el servicio detras este caido.

    Si lanza, tumba el endpoint entero y KAIROS parece muerto cuando solo
    tenia un agente sin responder.
    """
    from kairos.core.bootstrap import build_core

    for agente in build_core().registry.all():
        salud = await agente.health()
        assert isinstance(salud, dict), f"{agente.name} no devuelve dict"
        assert "status" in salud, f"{agente.name} sin campo status"


@pytest.mark.asyncio
async def test_una_capacidad_inventada_se_rechaza_sin_lanzar() -> None:
    """El contrato: un agente NUNCA lanza hacia arriba, devuelve failure."""
    from kairos.agents.base import AgentRequest
    from kairos.core.bootstrap import build_core

    for agente in build_core().registry.all():
        r = await agente.handle(AgentRequest(capability="inventada.que.no.existe"))
        assert r.ok is False, f"{agente.name} acepto una capacidad inventada"


# --- 5. Configuracion ------------------------------------------------------

def test_la_configuracion_se_carga_sin_variables() -> None:
    """Todo ajuste debe tener un valor por defecto razonable.

    Si algo es obligatorio, KAIROS no arranca en una maquina limpia y el
    error llega en forma de contenedor en bucle.
    """
    from kairos.config import get_settings

    s = get_settings()
    assert s.timezone
    assert s.postgres_host
