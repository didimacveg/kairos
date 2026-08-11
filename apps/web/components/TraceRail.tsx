"use client";

import type { MemoryHit, TraceEntry } from "@/lib/api";
import type { LastTurn } from "./Console";

/**
 * Rail de traza: el elemento firma de la interfaz.
 *
 * Muestra qué hizo KAIROS para producir la respuesta — qué recuerdos consultó,
 * con qué similitud, qué modelo usó y si salió de la máquina. La auditabilidad
 * es una propiedad del producto, no una página de ajustes.
 *
 * Desde la Fase 2A se rellena en vivo: la recuperación de memoria aparece
 * antes del primer token, así que ves de dónde sale la respuesta mientras se
 * está escribiendo.
 */
export function TraceRail({
  last,
  liveTrace,
  liveMemories,
  streaming,
}: {
  last: LastTurn | null;
  liveTrace: TraceEntry[];
  liveMemories: MemoryHit[];
  streaming: boolean;
}) {
  const trace = last?.trace ?? liveTrace;
  const memories = last?.memories ?? liveMemories;

  if (trace.length === 0 && memories.length === 0) {
    return (
      <aside className="rail">
        <h2>Traza</h2>
        <p>Sin actividad. Cada respuesta dejara aqui los pasos que la produjeron.</p>
      </aside>
    );
  }

  return (
    <aside className="rail" aria-live="polite">
      <h2>{streaming ? "Traza en curso" : "Traza del ultimo turno"}</h2>
      <ol>
        {trace.map((entry, index) => (
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

        {last && (
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
        )}
      </ol>

      {memories.length > 0 && (
        <>
          <h2 style={{ marginTop: "1.5rem" }}>Recuerdos usados</h2>
          <ol>
            {memories.map((memory) => (
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
