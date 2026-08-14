"""Recorre paso a paso la cadena que va de 'abre el modo trabajo' a la accion."""
import asyncio, json

from kairos.agents.base import AgentRequest
from kairos.core.bootstrap import build_core

FRASES = ["abre el modo trabajo", "pon bohemian rhapsody", "explicame que es la entropia"]


async def main() -> None:
    core = build_core()
    reg = core.registry
    print("agentes registrados:", reg.names)

    print("\n--- 1. ¿estan los agentes que hacen falta? ---")
    for cap in ("intent.classify", "device.profile", "device.music"):
        try:
            print(f"  {cap:18} -> {reg.find(cap).name}")
        except KeyError as exc:
            print(f"  {cap:18} -> NO REGISTRADO ({exc})")

    print("\n--- 2. ¿responde el puente? ---")
    try:
        device = reg.find("device.profile")
    except KeyError:
        print("  sin DeviceAgent: nada mas que probar")
        return
    status = await device.handle(AgentRequest(capability="device.status"))
    print("  ok:", status.ok, "| error:", status.error)
    perfiles = status.data.get("perfiles", [])
    print("  perfiles:", perfiles)

    print("\n--- 3. ¿que clasifica el modelo? ---")
    try:
        intent = reg.find("intent.classify")
    except KeyError:
        print("  sin IntentAgent")
        return
    for frase in FRASES:
        r = await intent.handle(
            AgentRequest(capability="intent.classify",
                         payload={"text": frase, "profiles": perfiles})
        )
        print(f"  {frase!r:36} -> ok={r.ok} {json.dumps(r.data, ensure_ascii=False)}")
        if not r.ok:
            print("     error:", r.error)


asyncio.run(main())
