"use client";

import type { MemoryHit, TraceEntry } from "@/lib/api";

export type TurnSummary = {
  model: string;
  latency_ms: number;
  local: boolean;
  memories: MemoryHit[];
  trace: TraceEntry[];
};

/** Nombres de agente y paso en el idioma del usuario, no en el del código. */
const OPS: Record<string, string> = {
  "memory.retrieve": "Buscar en memoria",
  "memory.ingest": "Consolidar memoria",
  "memory.store": "Guardar recuerdo",
  "reasoning.complete": "Generar respuesta",
  "reasoning.complete_stream": "Generar respuesta",
  "voice.transcribe": "Transcribir voz",
};

const FIELDS: Record<string, string> = {
  candidates: "candidatos",
  kept: "conservados",
  min_similarity: "umbral",
  top_similarity: "mejor coincidencia",
  candidatos: "candidatos",
  guardados: "guardados",
  descartados: "descartados",
  sustituidos: "sustituidos",
  extraccion_ms: "extracción",
  model: "modelo",
  local: "ejecución",
  turns: "turnos",
  chars: "caracteres",
  kind: "tipo",
};

function label(value: unknown, key: string): string {
  if (value === null || value === undefined) return "—";
  if (key === "local") return value ? "local" : "remota";
  if (typeof value === "number" && !Number.isInteger(value)) return value.toFixed(2);
  return String(value);
}

/**
 * Columna de instrumentos.
 *
 * Responde a una sola pregunta: ¿por qué KAIROS ha dicho lo que ha dicho?
 * Se rellena en vivo durante la generación — los recuerdos aparecen antes que
 * el primer token, así que ves de dónde sale la respuesta mientras se escribe.
 */
export function Instruments({
  summary,
  liveTrace,
  liveMemories,
  streaming,
}: {
  summary: TurnSummary | null;
  liveTrace: TraceEntry[];
  liveMemories: MemoryHit[];
  streaming: boolean;
}) {
  const trace = summary?.trace ?? liveTrace;
  const memories = summary?.memories ?? liveMemories;

  if (trace.length === 0 && memories.length === 0) {
    return (
      <aside className="instruments">
        <h2>Instrumentos</h2>
        <p className="quiet">
          Cada respuesta deja aquí los pasos que la produjeron: qué recuerdos se
          consultaron, con qué coincidencia y cuánto tardó cada agente.
        </p>
      </aside>
    );
  }

  return (
    <aside className="instruments" aria-live="polite">
      <section>
        <h2>{streaming ? "Turno en curso" : "Último turno"}</h2>
        <ol className="steps">
          {trace.map((entry, index) => {
            const key = `${entry.agent}.${entry.step}`;
            return (
              <li className="step" key={`${key}-${index}`}>
                <div className="op">
                  <b>{OPS[key] ?? key}</b>
                </div>
                {Object.entries(entry.detail).map(([field, value]) => (
                  <div className="row" key={field}>
                    <span>{FIELDS[field] ?? field}</span>
                    <span>{label(value, field)}</span>
                  </div>
                ))}
                <div className="row">
                  <span>tiempo</span>
                  <span>{entry.duration_ms ?? "—"} ms</span>
                </div>
              </li>
            );
          })}
        </ol>
      </section>

      {memories.length > 0 && (
        <section>
          <h2>Memoria consultada</h2>
          <ol className="recall">
            {memories.map((memory) => (
              <li key={memory.id}>
                <div className="meter">
                  <span className="bar">
                    <i style={{ width: `${Math.round(memory.similarity * 100)}%` }} />
                  </span>
                  <span className="val">{memory.similarity.toFixed(2)}</span>
                </div>
                <p className="fact">{memory.content}</p>
              </li>
            ))}
          </ol>
        </section>
      )}

      {summary && (
        <section>
          <h2>Procedencia</h2>
          <div className="row">
            <span>modelo</span>
            <span>{summary.model}</span>
          </div>
          <div className="row">
            <span>ejecución</span>
            <span>{summary.local ? "esta máquina" : "remota"}</span>
          </div>
          <div className="row">
            <span>latencia</span>
            <span>{summary.latency_ms} ms</span>
          </div>
        </section>
      )}
    </aside>
  );
}
