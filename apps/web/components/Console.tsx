"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  streamChat,
  type ChatStreamEnd,
  type Health,
  type MemoryHit,
  type TraceEntry,
} from "@/lib/api";
import { MicButton } from "./MicButton";
import { TraceRail } from "./TraceRail";

type Turn = { role: "user" | "assistant"; content: string };

/** Resumen del último turno, tal y como lo consume el rail. */
export type LastTurn = {
  model: string;
  latency_ms: number;
  local: boolean;
  memories: MemoryHit[];
  trace: TraceEntry[];
};

export function Console({ username, onSignOut }: { username: string; onSignOut: () => void }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [last, setLast] = useState<LastTurn | null>(null);
  const [liveTrace, setLiveTrace] = useState<TraceEntry[]>([]);
  const [liveMemories, setLiveMemories] = useState<MemoryHit[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const bottom = useRef<HTMLDivElement>(null);
  const abortRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, streaming]);

  // Si el componente se desmonta a media generación, cortamos el flujo para
  // no dejar la petición viva contra el núcleo.
  useEffect(() => () => abortRef.current?.(), []);

  const send = useCallback(() => {
    const message = draft.trim();
    if (!message || streaming) return;

    setDraft("");
    setError(null);
    setLiveTrace([]);
    setLiveMemories([]);
    setLast(null);
    setStreaming(true);

    // Turno del usuario + hueco vacío del asistente que iremos rellenando.
    setTurns((prev) => [...prev, { role: "user", content: message }, { role: "assistant", content: "" }]);

    abortRef.current = streamChat(message, conversationId, {
      onToken: (text) => {
        setTurns((prev) => {
          const next = [...prev];
          const target = next[next.length - 1];
          if (target?.role === "assistant") {
            next[next.length - 1] = { ...target, content: target.content + text };
          }
          return next;
        });
      },
      onTrace: (trace, data) => {
        if (trace) setLiveTrace((prev) => [...prev, trace]);
        if (Array.isArray(data.memories)) setLiveMemories(data.memories as MemoryHit[]);
        if (typeof data.conversation_id === "string") setConversationId(data.conversation_id);
      },
      onEnd: (summary: ChatStreamEnd) => {
        setStreaming(false);
        setConversationId(summary.conversation_id);
        setLast({
          model: summary.model ?? "desconocido",
          latency_ms: summary.latency_ms ?? 0,
          local: summary.local,
          memories: summary.memories,
          trace: summary.trace,
        });
      },
      onError: (message) => {
        setStreaming(false);
        setError(message);
        // Retiramos el turno vacío para no dejar una burbuja en blanco.
        setTurns((prev) => {
          const next = [...prev];
          const target = next[next.length - 1];
          if (target?.role === "assistant" && target.content === "") next.pop();
          return next;
        });
      },
    });
  }, [draft, streaming, conversationId]);

  const stop = useCallback(() => {
    abortRef.current?.();
    setStreaming(false);
  }, []);

  const egressState = health?.egress_allowed ? "warn" : "offline";

  return (
    <div className="shell">
      <header className="statusbar">
        <span className="mark">KAIROS</span>
        <span>{health?.instance ?? "…"}</span>
        <span className="pill" data-state={health?.status === "ok" ? undefined : "warn"}>
          {health?.status ?? "comprobando"}
        </span>
        <span className="pill" data-state={egressState}>
          {health?.egress_allowed ? "salida a internet permitida" : "sin salida a internet"}
        </span>
        <span className="spacer" />
        <span>{username}</span>
        <button type="button" onClick={onSignOut} style={{ padding: "0.25rem 0.6rem" }}>
          Cerrar sesion
        </button>
      </header>

      <div className="workspace">
        <div style={{ display: "grid", gridTemplateRows: "1fr auto", minHeight: 0 }}>
          <div className="transcript">
            {turns.length === 0 && (
              <p className="empty">
                <strong>Todo ocurre en esta maquina.</strong> Escribe algo. KAIROS buscara en su
                memoria antes de responder y te mostrara a la derecha exactamente que consulto.
              </p>
            )}

            {turns.map((turn, index) => {
              const isLast = index === turns.length - 1;
              const pending = streaming && isLast && turn.role === "assistant";
              return (
                <article className="turn" data-role={turn.role} key={index}>
                  <div className="who">{turn.role === "user" ? username : "kairos"}</div>
                  <div className="body">
                    {turn.content}
                    {pending && <span className="caret" aria-hidden="true" />}
                    {pending && turn.content === "" && (
                      <span style={{ color: "var(--muted)" }}>Recuperando memoria…</span>
                    )}
                  </div>
                </article>
              );
            })}

            {error && <div className="error">{error}</div>}
            <div ref={bottom} />
          </div>

          <div className="composer">
            <textarea
              rows={2}
              value={draft}
              placeholder="Escribe un mensaje"
              aria-label="Mensaje"
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  send();
                }
              }}
            />
            <MicButton
              disabled={streaming}
              onTranscript={(text) =>
                setDraft((prev) => (prev ? `${prev} ${text}` : text))
              }
            />
            {streaming ? (
              <button type="button" onClick={stop}>
                Detener
              </button>
            ) : (
              <button type="button" onClick={send} disabled={!draft.trim()}>
                Enviar
              </button>
            )}
          </div>
        </div>

        <TraceRail
          last={last}
          liveTrace={liveTrace}
          liveMemories={liveMemories}
          streaming={streaming}
        />
      </div>
    </div>
  );
}
