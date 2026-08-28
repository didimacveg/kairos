"""Smith Agent — KAIROS se escribe a si mismo.

El ciclo completo, con las cuatro piezas ya construidas:

    peticion -> Smith lee su codigo y escribe los ficheros nuevos
             -> difflib calcula el parche
             -> Forge lo ensaya aislado y sin red
             -> si los tests pasan, se crea una PROPUESTA
             -> Diego aprueba o rechaza

Lo que NO hace, y es deliberado:
- No aplica nada. Ni siquiera cuando los tests pasan.
- No escribe en el repositorio. Solo lee; los cambios viven en la propuesta.
- No decide que es importante. La peticion la pone el usuario.

Si los tests fallan, la propuesta se crea igualmente pero marcada, con la
salida del fallo. Un intento fallido tambien es informacion: dice que KAIROS
no supo hacerlo, y por que.
"""
from __future__ import annotations

import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.proposals import store
from kairos.agents.reasoning.providers.base import ChatTurn, LLMProvider
from kairos.agents.registry import AgentRegistry
from kairos.agents.smith import diffs, repo
from kairos.logging import get_logger

log = get_logger("kairos.smith")

MAX_FICHEROS_CONTEXTO = 8

PROMPT = """Eres el ingeniero de KAIROS, un asistente personal. Tu trabajo es
escribir el codigo de un cambio que se te pide sobre TU PROPIO sistema.

Arquitectura, para que sepas donde tocar:
- apps/core/kairos/agents/   agentes; cada uno es un bounded context con
  capacidades nombradas y contrato Agent/AgentRequest/AgentResponse
- apps/core/kairos/core/     orquestador y composicion (bootstrap.py)
- apps/core/kairos/api/v1/   rutas HTTP
- apps/core/tests/           pruebas
- apps/web/                  interfaz Next.js
- apps/bridge/               proceso que corre en Windows y controla el escritorio

Reglas que NO se negocian en este proyecto:
- Todo cambio de comportamiento va SIEMPRE con su test, en un fichero de
  apps/core/tests/. Si anades una capacidad y no anades test, el cambio esta
  incompleto y se rechazara.
- Antes de escribir un test, MIRA uno existente del mismo area y copia su
  forma: como monta los dobles, como llama al agente, que asserts usa. No
  inventes un estilo nuevo.
- NO borres comentarios existentes ni los reescribas. Explican decisiones que
  costaron tiempo. Si un comentario deja de ser cierto por tu cambio,
  actualizalo; si sigue siendo cierto, dejalo intacto.
- Un agente nunca lanza excepciones hacia arriba: devuelve AgentResponse.failure.
- Nada que ejecute acciones acepta comandos libres: solo listas cerradas.
- Todo cambio va acompanado de sus tests.
- Sin `shell=True`, sin interpolar cadenas en comandos, nunca.

FORMATO DE RESPUESTA — texto plano con marcadores. NADA de JSON:

MOTIVO: que hace el cambio y por que, en 2-4 frases
RIESGO: bajo|medio|alto
--- FICHERO: apps/core/kairos/agents/ejemplo.py
<aqui el fichero ENTERO tal y como debe quedar>
<sin escapar nada, sin bloques de codigo, tal cual iria en el editor>
--- FIN FICHERO
--- FICHERO: apps/core/tests/test_ejemplo.py
<otro fichero entero>
--- FIN FICHERO

Repite el par de marcadores por cada fichero. Maximo {max_ficheros}.

SIN TEST NO HAY PROPUESTA. Si tu cambio anade o modifica comportamiento y no
incluyes un fichero en apps/core/tests/, la propuesta esta incompleta. Escribe
el test SIEMPRE, copiando la forma de los TESTS DE REFERENCIA que te doy: los
mismos imports, la misma manera de montar dobles, el mismo estilo de nombres.
Si creas un fichero nuevo, tambien entero.

NO uses JSON bajo ningun concepto: escapar comillas y saltos de linea dentro
de un campo JSON rompe la respuesta y se pierde todo el trabajo. Con estos
marcadores no hay nada que escapar.

Riesgo: bajo si solo anade; medio si modifica logica existente; alto si toca
autenticacion, la base de datos, el puente o el propio Smith."""


REVISION = """Acabas de escribir un cambio de codigo. Ahora releelo como si lo
hubiera escrito otra persona y tuvieras que aprobarlo.

Busca especificamente:

1. ERRORES QUE UN INTERPRETE PILLARIA. Tipos mal usados, variables sin
   definir, imports que faltan, estructuras indexadas que no se pueden
   indexar. Ejemplo real: `frozenset({"a": 1})` se queda solo con las claves,
   asi que `frozenset(...)["a"]` revienta — debia ser un dict.
2. TESTS QUE FALTAN. Si el cambio anade comportamiento y no hay fichero de
   test en apps/core/tests/, escribelo ahora.
3. TESTS QUE NO PASARIAN. Miralos linea a linea imaginando la ejecucion:
   ¿los dobles devuelven lo que el codigo espera? ¿los nombres de campo
   coinciden con los reales?
4. COMENTARIOS BORRADOS. Si has quitado un comentario que seguia siendo
   cierto, devuelvelo.
5. CONTRATOS ROTOS. Un agente nunca lanza hacia arriba: devuelve
   AgentResponse.failure.

Devuelve los ficheros CORREGIDOS en el mismo formato de marcadores:

MOTIVO: que has corregido respecto a tu primera version
RIESGO: bajo|medio|alto
--- FICHERO: ruta/del/fichero.py
<fichero entero corregido>
--- FIN FICHERO

Devuelve TODOS los ficheros, tambien los que no cambian. Si de verdad no hay
nada que corregir, devuelvelos tal cual estaban."""


SOLO_TEST = """Tienes UNA tarea: escribir el fichero de tests del cambio que
te dan. Nada mas. No repitas el codigo, no expliques, no propongas mejoras.

El test tiene que:
- ir en apps/core/tests/test_<algo>.py
- copiar la forma de los TESTS DE REFERENCIA: mismos imports, misma manera de
  montar dobles, mismo estilo de nombres y asserts
- probar el comportamiento NUEVO, no el que ya existia
- pasar sin salir a Internet: si el codigo hace peticiones HTTP, usa un
  transporte falso como hacen los tests de referencia
- cubrir tambien el caso de error, no solo el bueno

FORMATO — texto plano con marcadores, NADA de JSON:

MOTIVO: que cubre el test
--- FICHERO: apps/core/tests/test_ejemplo.py
<el fichero entero>
--- FIN FICHERO"""


CORREGIR = """Los tests de tu cambio han fallado. Arreglalo.

Te doy el codigo que escribiste y la salida REAL de pytest. Lee el error con
atencion: casi siempre dice exactamente que esta mal y en que linea.

REGLAS:
- Arregla la CAUSA, no el sintoma. Si un test falla porque el codigo tiene un
  error, arregla el codigo. Si falla porque el test asume algo que no es
  cierto, arregla el test. Nunca borres un test para que deje de fallar.
- Cambia lo minimo. No reescribas lo que ya funcionaba.
- Si el error es de importacion o de tipos, mira si el nombre que usas existe
  de verdad en el modulo que dices.
- Si no entiendes el fallo, dilo en MOTIVO en vez de adivinar. Una propuesta
  honesta que dice "no se por que falla" es mas util que una que empeora.

Devuelve TODOS los ficheros corregidos en el formato de marcadores:

MOTIVO: que estaba mal y que has cambiado
RIESGO: bajo|medio|alto
--- FICHERO: ruta/del/fichero.py
<fichero entero corregido>
--- FIN FICHERO"""


class SmithAgent(Agent):
    name = "smith"
    capabilities = frozenset({"smith.proponer"})

    def __init__(self, provider: LLMProvider, registry: AgentRegistry) -> None:
        self._provider = provider
        self._registry = registry

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        if request.capability != "smith.proponer":
            return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

        db: AsyncSession | None = context.get("db")
        if db is None:
            return AgentResponse.failure("Se necesita sesion de base de datos")

        peticion = (request.payload.get("peticion") or "").strip()
        if not peticion:
            return AgentResponse.failure("Falta la peticion")

        started = time.perf_counter()
        traza: list[TraceEvent] = []

        # --- 1. Elegir que ficheros mirar ---------------------------------
        indice = repo.arbol_resumido()
        if not indice:
            return AgentResponse.failure(
                "No veo el repositorio. ¿Esta montado /repo en el nucleo?"
            )

        relevantes = await self._elegir_ficheros(peticion, indice)
        traza.append(TraceEvent(
            agent=self.name, step="explorar",
            detail={"ficheros_indice": len(indice.splitlines()),
                    "elegidos": ", ".join(relevantes[:6])},
        ))

        contexto = []
        for ruta in relevantes[:MAX_FICHEROS_CONTEXTO]:
            contenido = repo.leer(ruta)
            if contenido is not None:
                contexto.append(f"=== {ruta} ===\n{contenido}")

        # Tests reales del repositorio, siempre. No es opcional: sin ver uno,
        # el modelo no puede imitar el estilo de la casa.
        referencias = []
        for ruta in self._tests_de_ejemplo(relevantes):
            contenido = repo.leer(ruta)
            if contenido is not None:
                referencias.append(f"=== {ruta} ===\n{contenido}")

        # --- 2. Escribir el cambio ----------------------------------------
        sistema = PROMPT.format(max_ficheros=diffs.MAX_FICHEROS)
        usuario = (
            f"PETICION: {peticion}\n\n"
            f"INDICE DEL REPOSITORIO:\n{indice}\n\n"
            f"FICHEROS RELEVANTES:\n\n" + "\n\n".join(contexto)
            + (
                "\n\nTESTS DE REFERENCIA — copia esta forma de escribir tests "
                "(imports, dobles, nombres, asserts):\n\n" + "\n\n".join(referencias)
                if referencias else ""
            )
        )
        t0 = time.perf_counter()
        try:
            completion = await self._provider.complete([
                ChatTurn(role="system", content=sistema),
                ChatTurn(role="user", content=usuario),
            ])
        except Exception as exc:  # noqa: BLE001
            log.warning('smith.fallo', paso='generar', error=str(exc)[:400])
            return AgentResponse.failure(f"{type(exc).__name__}: {exc}")

        propuesta = diffs.parsear(completion.text)
        cambios, motivo = propuesta.cambios, propuesta.motivo
        if cambios:
            cambios = await self._revisar(peticion, cambios, traza)
            cambios = await self._forzar_test(peticion, cambios, traza)
        if not cambios:
            log.warning('smith.fallo', paso='parsear',
                        respuesta=completion.text[:600])
        traza.append(TraceEvent(
            agent=self.name, step="escribir",
            detail={"ficheros": len(cambios), "modelo": completion.model},
            duration_ms=int((time.perf_counter() - t0) * 1000),
        ))
        if not cambios:
            return AgentResponse.failure("No consegui escribir un cambio valido")

        # --- 3. Construir el parche ---------------------------------------
        partes = []
        for cambio in cambios:
            original = repo.leer(cambio.ruta)
            trozo = diffs.construir_diff(original, cambio.contenido, cambio.ruta)
            if trozo:
                partes.append(trozo)
        parche = "".join(partes)
        if not parche.strip():
            log.warning('smith.fallo', paso='diff',
                        rutas=', '.join(c.ruta for c in cambios))
            return AgentResponse.failure("El cambio propuesto no modifica nada")

        # Si falta el test, se avisa en la traza y sube el riesgo. No se
        # bloquea: un cambio sin test puede seguir siendo util, pero Diego
        # tiene que verlo escrito antes de aprobar.
        toca_comportamiento = any(
            not c.ruta.startswith("apps/core/tests/") for c in cambios
        )
        sin_test = toca_comportamiento and not any(
            c.ruta.startswith("apps/core/tests/") for c in cambios
        )
        if sin_test:
            traza.append(TraceEvent(
                agent=self.name, step="aviso",
                detail={"falta": "ningun fichero de test en la propuesta"},
            ))

        rama = diffs.nombre_rama(peticion)

        # --- 4. Ensayarlo aislado -----------------------------------------
        try:
            forge = self._registry.find("forge.ensayar")
        except KeyError:
            return AgentResponse.failure(
                "El banco de pruebas no esta activo. Sin ensayar no se crean propuestas."
            )

        ensayo = await forge.handle(AgentRequest(
            capability="forge.ensayar",
            actor_id=request.actor_id,
            payload={"rama": rama, "parche": parche},
        ))
        traza += ensayo.trace
        if not ensayo.ok:
            return AgentResponse.failure(f"El ensayo no pudo ejecutarse: {ensayo.error}")

        verde = bool(ensayo.data.get("ok"))
        intentos = 1

        # CICLO CERRADO: si los tests fallan, se lee el error, se corrige y se
        # vuelve a ensayar. UNA sola vez: si el segundo intento tampoco pasa,
        # el problema no es un descuido y hace falta que lo mire una persona.
        # Reintentar en bucle gastaria llamadas sin converger.
        if not verde:
            salida_fallo = "\n\n".join(
                f"[{p['paso']}]\n{p['salida']}"
                for p in ensayo.data.get("pasos", []) if not p["ok"]
            )
            corregidos = await self._corregir(peticion, cambios, salida_fallo, traza)
            if corregidos:
                partes2 = []
                for cambio in corregidos:
                    original = repo.leer(cambio.ruta)
                    trozo = diffs.construir_diff(original, cambio.contenido, cambio.ruta)
                    if trozo:
                        partes2.append(trozo)
                parche2 = "".join(partes2)

                if parche2.strip():
                    ensayo2 = await forge.handle(AgentRequest(
                        capability="forge.ensayar",
                        actor_id=request.actor_id,
                        payload={"rama": rama, "parche": parche2},
                    ))
                    if ensayo2.ok:
                        traza += ensayo2.trace
                        # Se queda con el segundo intento solo si MEJORA. Si
                        # tampoco pasa, se conserva el primero: al menos su
                        # error ya esta diagnosticado.
                        if ensayo2.data.get("ok"):
                            ensayo = ensayo2
                            cambios = corregidos
                            parche = parche2
                            verde = True
                            intentos = 2
        salida = "\n\n".join(
            f"[{p['paso']}] {'OK' if p['ok'] else 'FALLA'}\n{p['salida']}"
            for p in ensayo.data.get("pasos", [])
        )

        # --- 5. Dejar la propuesta ----------------------------------------
        # El riesgo lo decide la ruta. Si el modelo declara uno MAYOR se
        # respeta el suyo: nunca a la baja, si al alza.
        por_ruta = self._riesgo_por_rutas(cambios)
        orden = {"bajo": 0, "medio": 1, "alto": 2}
        riesgo = "alto" if not verde else (
            propuesta.riesgo if orden[propuesta.riesgo] > orden[por_ruta] else por_ruta
        )
        if sin_test and riesgo != "alto":
            riesgo = "alto"
        propuesta = await store.crear(
            db,
            owner_id=request.actor_id,
            titulo=peticion[:200],
            motivo=((motivo or "Sin motivo declarado por el modelo.")
                    + ("\n\nAVISO: esta propuesta NO trae tests."
                       if sin_test else "")),
            diff=ensayo.data.get("diff") or parche,
            rama=rama,
            riesgo=riesgo,
            tests=("VERDE" + (" (corregido al segundo intento)" if intentos > 1 else "")
                   + "\n\n" + salida) if verde else "ROJO\n\n" + salida,
        )

        log.info("smith.propuesta", rama=rama, verde=verde, ficheros=len(cambios))
        return AgentResponse(
            ok=True,
            data={
                "propuesta_id": str(propuesta.id),
                "rama": rama,
                "tests_verdes": verde,
                "ficheros": [c.ruta for c in cambios],
                "riesgo": riesgo,
            },
            trace=traza + [TraceEvent(
                agent=self.name, step="proponer",
                detail={"rama": rama, "tests": "verde" if verde else "rojo", "riesgo": riesgo},
                duration_ms=int((time.perf_counter() - started) * 1000),
            )],
        )

    @staticmethod
    def _tests_de_ejemplo(elegidos: list[str]) -> list[str]:
        """Devuelve tests reales del repositorio para que Smith copie su forma.

        Se le pedia "mira un test existente y copia su estilo" sin ensenarle
        ninguno. Un modelo no puede imitar lo que no ve: por eso escribia
        codigo correcto y se dejaba el test, o lo inventaba con un estilo que
        no cuadraba con la casa.

        Si el modelo ya eligio ficheros de test, se respetan. Si no, se meten
        dos de referencia igualmente — no es opcional.
        """
        ya = [r for r in elegidos if "/tests/" in r or r.startswith("apps/core/tests/")]
        if ya:
            return ya[:2]

        candidatos = [
            r for r in repo.listar()
            if r.startswith("apps/core/tests/test_") and r.endswith(".py")
        ]
        # Los mas representativos primero: uno de agente con dobles, uno puro.
        preferidos = [
            "apps/core/tests/test_device_agent.py",
            "apps/core/tests/test_cloud_and_search.py",
            "apps/core/tests/test_intent.py",
        ]
        elegidos_ref = [c for c in preferidos if c in candidatos]
        return (elegidos_ref or candidatos)[:2]

    async def _forzar_test(
        self, peticion: str, cambios: list[diffs.Cambio], traza: list[TraceEvent]
    ) -> list[diffs.Cambio]:
        """Si el cambio no trae test, se pide APARTE.

        Pedir codigo y test en la misma respuesta no funciona: el modelo gasta
        su atencion en el codigo y el test se queda fuera. Han hecho falta
        tres intentos —instrucciones mas duras, tests de referencia en el
        contexto, una relectura— para confirmarlo.

        Una llamada dedicada, con el codigo ya escrito delante y una sola
        tarea, si lo produce.
        """
        import time as _t

        toca_codigo = [c for c in cambios if not c.ruta.startswith("apps/core/tests/")]
        if not toca_codigo or any(c.ruta.startswith("apps/core/tests/") for c in cambios):
            return cambios

        t0 = _t.perf_counter()
        cuerpo = "\n\n".join(f"=== {c.ruta} ===\n{c.contenido}" for c in toca_codigo)
        referencias = []
        for ruta in self._tests_de_ejemplo([]):
            contenido = repo.leer(ruta)
            if contenido is not None:
                referencias.append(f"=== {ruta} ===\n{contenido}")

        try:
            respuesta = await self._provider.complete([
                ChatTurn(role="system", content=SOLO_TEST),
                ChatTurn(role="user", content=(
                    f"CAMBIO PEDIDO: {peticion}\n\n"
                    f"CODIGO ESCRITO:\n\n{cuerpo}\n\n"
                    f"TESTS DE REFERENCIA — copia su forma:\n\n"
                    + "\n\n".join(referencias)
                )),
            ])
        except Exception:  # noqa: BLE001
            return cambios

        nuevos = diffs.parsear(respuesta.text).cambios
        tests = [c for c in nuevos if c.ruta.startswith("apps/core/tests/")]
        traza.append(TraceEvent(
            agent=self.name, step="test",
            detail={"generado": tests[0].ruta if tests else "no consegui escribirlo"},
            duration_ms=int((_t.perf_counter() - t0) * 1000)))
        return cambios + tests[:1]

    async def _corregir(
        self, peticion: str, cambios: list[diffs.Cambio], salida: str,
        traza: list[TraceEvent],
    ) -> list[diffs.Cambio] | None:
        """Lee el fallo de los tests y arregla el codigo.

        Es lo que cierra el ciclo: hasta ahora una propuesta con los tests en
        rojo se quedaba en rojo y esperaba a que Diego la leyera. Pero el
        error de pytest casi siempre dice exactamente que esta mal, y leerlo
        es justo lo que un modelo sabe hacer.

        Devuelve None si no consigue mejorar nada, para conservar la version
        original: una correccion que empeora es peor que ninguna.
        """
        import time as _t

        t0 = _t.perf_counter()
        cuerpo = "\n\n".join(f"=== {c.ruta} ===\n{c.contenido}" for c in cambios)

        try:
            respuesta = await self._provider.complete([
                ChatTurn(role="system", content=CORREGIR),
                ChatTurn(role="user", content=(
                    f"CAMBIO PEDIDO: {peticion}\n\n"
                    f"CODIGO QUE ESCRIBISTE:\n\n{cuerpo}\n\n"
                    f"SALIDA DE PYTEST:\n{salida[-6000:]}"
                )),
            ])
        except Exception:  # noqa: BLE001
            return None

        corregidos = diffs.parsear(respuesta.text).cambios
        if not corregidos:
            traza.append(TraceEvent(
                agent=self.name, step="corregir",
                detail={"resultado": "no consegui corregirlo"},
                duration_ms=int((_t.perf_counter() - t0) * 1000)))
            return None

        traza.append(TraceEvent(
            agent=self.name, step="corregir",
            detail={"ficheros": ", ".join(c.ruta for c in corregidos)},
            duration_ms=int((_t.perf_counter() - t0) * 1000)))
        return corregidos

    async def _revisar(
        self, peticion: str, cambios: list[diffs.Cambio], traza: list[TraceEvent]
    ) -> list[diffs.Cambio]:
        """Segunda lectura del propio codigo antes de entregarlo.

        Por que hace falta: un modelo escribe de un tiron y no ejecuta nada
        mientras escribe. Los fallos que comete son los de alguien que no ha
        releido — en la primera propuesta real construyo un `frozenset` a
        partir de un diccionario y luego lo indexo, que es un error que se ve
        a simple vista en una segunda pasada.

        Los tests del forge tambien lo detectarian, pero un ciclo del forge
        cuesta minutos y una relectura cuesta segundos. Y hay fallos que los
        tests no cubren: comentarios borrados, tests que faltan.

        Si la revision no devuelve nada util, se conserva la version original:
        una revision que empeora el resultado es peor que ninguna.
        """
        import time as _t

        t0 = _t.perf_counter()
        cuerpo = "\n\n".join(
            f"=== {c.ruta} ===\n{c.contenido}" for c in cambios
        )
        try:
            revision = await self._provider.complete([
                ChatTurn(role="system", content=REVISION),
                ChatTurn(role="user", content=(
                    f"PETICION ORIGINAL: {peticion}\n\n"
                    f"CODIGO QUE HAS ESCRITO:\n\n{cuerpo}"
                )),
            ])
        except Exception:  # noqa: BLE001
            return cambios

        corregida = diffs.parsear(revision.text)
        if not corregida.cambios:
            traza.append(TraceEvent(
                agent=self.name, step="revisar",
                detail={"resultado": "sin cambios tras revisar"},
                duration_ms=int((_t.perf_counter() - t0) * 1000),
            ))
            return cambios

        antes = {c.ruta for c in cambios}
        ahora = {c.ruta for c in corregida.cambios}
        traza.append(TraceEvent(
            agent=self.name, step="revisar",
            detail={
                "ficheros_revisados": len(corregida.cambios),
                "anadidos": ", ".join(sorted(ahora - antes)) or "ninguno",
            },
            duration_ms=int((_t.perf_counter() - t0) * 1000),
        ))
        return corregida.cambios

    async def _elegir_ficheros(self, peticion: str, indice: str) -> list[str]:
        """Pregunta al modelo que ficheros necesita ver.

        Meter el repositorio entero en el contexto es caro y empeora el
        resultado: el modelo se pierde. Dos pasadas —una para elegir, otra
        para escribir— dan mejores parches y salen mas baratas.
        """
        try:
            respuesta = await self._provider.complete([
                ChatTurn(role="system", content=(
                    "Te dan un indice de ficheros y una peticion de cambio. "
                    "Devuelve SOLO un array JSON con las rutas que hay que leer "
                    "para escribir ese cambio, maximo 8, las mas relevantes "
                    "primero. Incluye siempre el fichero de tests que "
                    "correspondera al cambio. Nada de texto alrededor."
                )),
                ChatTurn(role="user", content=f"PETICION: {peticion}\n\nINDICE:\n{indice}"),
            ])
        except Exception:  # noqa: BLE001
            return []

        import json
        texto = respuesta.text
        i, j = texto.find("["), texto.rfind("]")
        if i == -1 or j == -1:
            return []
        try:
            rutas = json.loads(texto[i : j + 1])
        except json.JSONDecodeError:
            return []
        return [str(r).strip().lstrip("/") for r in rutas if isinstance(r, str)][:8]

    @staticmethod
    def _riesgo_por_rutas(cambios: list[diffs.Cambio]) -> str:
        """El riesgo lo decide la ruta, no el modelo.

        Un modelo que se autoevalua el riesgo tiende a decir "bajo". Las rutas
        sensibles estan aqui, en codigo, y no se negocian.
        """
        sensibles = ("auth/", "db/models.py", "agents/smith/", "agents/forge/",
                     "bridge.py", "docker-compose.yml")
        for cambio in cambios:
            if any(s in cambio.ruta for s in sensibles):
                return "alto"
        if any(not c.ruta.startswith("apps/core/tests/") for c in cambios):
            return "medio"
        return "bajo"

    async def health(self) -> dict[str, Any]:
        ficheros = len(repo.listar())
        return {
            "agent": self.name,
            "status": "ok" if ficheros else "sin repositorio",
            "ficheros_visibles": ficheros,
        }
