"use client";

import type { ChatResponse } from "@/lib/api";

/**
 * Rail de traza: el elemento firma de la interfaz.
 *
 * Muestra que hizo KAIROS para producir la ultima respuesta — que recuerdos
 * consulto, con que similitud, que modelo uso y si salio de la maquina.
 * La auditabilidad es una propiedad del producto, no una pagina de ajustes.
 */
export function TraceRail({ last }: { last: ChatResponse | null }) {
  if (!last) {
    return (
      <aside className="rail">
        <h2>Traza</h2>
        <p>Sin actividad. Cada respuesta dejara aqui los pasos que la produjeron.</p>
      </aside>
    );
  }

  return (
    <aside className="rail" aria-live="polite">
      <h2>Traza del ultimo turno</h2>
      <ol>
        {last.trace.map((entry, index) => (
          <li key={`${entry.agent}-${entry.step}-${index}`}>
            <div className="label">
              {entry.agent}.{entry.step}
            </div>
            {Object.entries(entry.detail).map(([key, value]) => (
              <div className="kv" key={key}>
                <span>{key}</span>
                <span>{value === null ? "—" : String(value)}</span>
              </div>
            ))}
            <div className="kv">
              <span>duracion</span>
              <span>{entry.duration_ms ?? "—"} ms</span>
            </div>
          </li>
        ))}
        <li>
          <div className="label">salida</div>
          <div className="kv">
            <span>modelo</span>
            <span>{last.model}</span>
          </div>
          <div className="kv">
            <span>ejecucion</span>
            <span>{last.local ? "local" : "remota"}</span>
          </div>
        </li>
      </ol>

      {last.memories.length > 0 && (
        <>
          <h2 style={{ marginTop: "1.5rem" }}>Recuerdos usados</h2>
          <ol>
            {last.memories.map((memory) => (
              <li key={memory.id}>
                <div className="kv">
                  <span>similitud</span>
                  <span>{memory.similarity.toFixed(2)}</span>
                </div>
                <p className="memory">{memory.content}</p>
              </li>
            ))}
          </ol>
        </>
      )}
    </aside>
  );
}
