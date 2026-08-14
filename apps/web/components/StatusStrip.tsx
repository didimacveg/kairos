"use client";

import { useEffect, useState } from "react";

import type { Health } from "@/lib/api";
import { Briefings } from "./Briefings";
import { Sigil } from "./Sigil";

/**
 * Tira de telemetría — el elemento firma de la interfaz.
 *
 * Todo lo que muestra es real: agentes vivos según el health check, modelo
 * cargado, latencia del último turno, recuerdos consultados, y si hay salida
 * a Internet. Nada de indicadores decorativos: si un número aparece aquí es
 * porque KAIROS lo mide.
 *
 * El color codifica estado. Latón = el sistema actuando en local. Hielo =
 * lectura de instrumento. Brasa = datos saliendo de la máquina, que en una
 * instalación bien configurada no debería verse nunca.
 */
export function StatusStrip({
  health,
  username,
  busy,
  listening,
  lastLatency,
  lastModel,
  recalled,
  onSignOut,
}: {
  health: Health | null;
  username: string;
  busy: boolean;
  listening: boolean;
  lastLatency: number | null;
  lastModel: string | null;
  recalled: number | null;
  onSignOut: () => void;
}) {
  const [motion, setMotion] = useState(true);

  // El navegador recuerda la eleccion: es una preferencia del dueno de esta
  // instancia, no algo que decidir en cada arranque.
  useEffect(() => {
    const stored = window.localStorage.getItem("kairos.motion");
    const on = stored === null ? true : stored === "on";
    setMotion(on);
    document.documentElement.dataset.motion = on ? "on" : "off";
  }, []);

  const toggleMotion = () => {
    const next = !motion;
    setMotion(next);
    document.documentElement.dataset.motion = next ? "on" : "off";
    window.localStorage.setItem("kairos.motion", next ? "on" : "off");
  };

  const agentsUp = health?.agents.filter((a) => a.status === "ok").length ?? 0;
  // Los desactivados no salen en la cuenta: no estan rotos, estan apagados.
  const agentsTotal = health?.agents.filter((a) => a.status !== "disabled").length ?? 0;
  const degraded = agentsTotal > 0 && agentsUp < agentsTotal;

  return (
    <header className="strip">
      <div className="wordmark">
        <Sigil health={health} busy={busy} listening={listening} compact />
        K.A.I.R.O.S
      </div>

      <dl className="gauges">
        <div className="gauge">
          <dt>Nodo</dt>
          <dd data-tone="local">{health?.instance ?? "—"}</dd>
        </div>

        <div className="gauge">
          <dt>Agentes</dt>
          <dd data-tone={degraded ? "alert" : "local"}>
            {agentsTotal ? `${agentsUp}/${agentsTotal} activos` : "—"}
          </dd>
        </div>

        <div className="gauge">
          <dt>Modelo</dt>
          <dd>{lastModel ?? "en reposo"}</dd>
        </div>

        <div className="gauge">
          <dt>Última respuesta</dt>
          <dd data-tone={lastLatency === null ? "idle" : undefined}>
            {lastLatency === null ? "—" : `${(lastLatency / 1000).toFixed(2)} s`}
          </dd>
        </div>

        <div className="gauge">
          <dt>Memoria consultada</dt>
          <dd data-tone={recalled === null ? "idle" : undefined}>
            {recalled === null ? "—" : `${recalled} recuerdos`}
          </dd>
        </div>

        <div className="gauge">
          <dt>Micrófono</dt>
          <dd data-tone={listening ? "alert" : "idle"}>
            {listening ? "escuchando" : "apagado"}
          </dd>
        </div>

        <div className="gauge">
          <dt>Salida de datos</dt>
          <dd data-tone={health?.egress_allowed ? "alert" : "local"}>
            {health?.egress_allowed ? "permitida" : "bloqueada"}
          </dd>
        </div>
      </dl>

      <div className="identity">
        <Briefings />
        <button
          type="button"
          className="motion-toggle"
          onClick={toggleMotion}
          title="Animación del sigilo"
        >
          {motion ? "Movimiento" : "Estático"}
        </button>
        <span className="who">{username}</span>
        <button type="button" onClick={onSignOut} style={{ padding: "0.3rem 0.7rem" }}>
          Salir
        </button>
      </div>
    </header>
  );
}
