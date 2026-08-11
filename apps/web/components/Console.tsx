"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, streamChat, type ChatStreamEnd, type Health, type MemoryHit, type TraceEntry } from "@/lib/api";
import { Instruments, type TurnSummary } from "./Instruments";
import { MicButton } from "./MicButton";
import { StatusStrip } from "./StatusStrip";

type Entry = { from: "me" | "kairos"; said: string };

/** Arranques sugeridos. Son ejemplos reales de lo que KAIROS sabe hacer hoy,
 *  no promesas de funciones que aún no existen. */
const OPENERS = [
  "Recuerda que trabajo mejor por las noches",
  "¿Qué sabes de mí?",
  "Explícame cómo funciona un motor de combustión",
];

export function Console({ username, onSignOut }: { username: string; onSignOut: () => void }) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [fault, setFault] = useState<string | null>(null);
  const [summary, setSummary] = useState<TurnSummary | null>(null);
  const [liveTrace, setLiveTrace] = useState<TraceEntry[]>([]);
  const [liveMemories, setLiveMemories] = useState<MemoryHit[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const foot = useRef<HTMLDivElement>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const boxRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const poll = () => api.health().then(setHealth).catch(() => setHealth(null));
    poll();
    const id = setInterval(poll, 20_000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    foot.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries, streaming]);

  useEffect(() => () => abortRef.current?.(), []);

  const send = useCallback(
    (text?: string) => {
      const message = (text ?? draft).trim();
      if (!message || streaming) return;

      setDraft("");
      setFault(null);
      setLiveTrace([]);
      setLiveMemories([]);
      setSummary(null);
      setStreaming(true);
      setEntries((prev) => [...prev, { from: "me", said: message }, { from: "kairos", said: "" }]);

      abortRef.current = streamChat(message, conversationId, {
        onToken: (chunk) => {
          setEntries((prev) => {
            const next = [...prev];
            const target = next[next.length - 1];
            if (target?.from === "kairos") {
              next[next.length - 1] = { ...target, said: target.said + chunk };
            }
            return next;
          });
        },
        onTrace: (trace, data) => {
          if (trace) setLiveTrace((prev) => [...prev, trace]);
          if (Array.isArray(data.memories)) setLiveMemories(data.memories as MemoryHit[]);
          if (typeof data.conversation_id === "string") setConversationId(data.conversation_id);
        },
        onEnd: (done: ChatStreamEnd) => {
          setStreaming(false);
          setConversationId(done.conversation_id);
          setSummary({
            model: done.model ?? "desconocido",
            latency_ms: done.latency_ms ?? 0,
            local: done.local,
            memories: done.memories,
            trace: done.trace,
          });
        },
        onError: (message) => {
          setStreaming(false);
          setFault(message);
          setEntries((prev) => {
            const next = [...prev];
            const target = next[next.length - 1];
            if (target?.from === "kairos" && target.said === "") next.pop();
            return next;
          });
        },
      });
    },
    [draft, streaming, conversationId],
  );

  const halt = useCallback(() => {
    abortRef.current?.();
    setStreaming(false);
  }, []);

  return (
    <div className="deck">
      <StatusStrip
        health={health}
        username={username}
        busy={streaming}
        lastLatency={summary?.latency_ms ?? null}
        lastModel={summary?.model ?? null}
        recalled={summary ? summary.memories.length : null}
        onSignOut={onSignOut}
      />

      <div className="bay">
        <div className="channel">
          <div className="log">
            {entries.length === 0 && (
              <div className="standby">
                <h1>Todo ocurre en esta máquina.</h1>
                <p>
                  KAIROS busca en su memoria antes de responder y te enseña a la derecha
                  exactamente qué consultó. Empieza por donde quieras:
                </p>
                <ul>
                  {OPENERS.map((opener) => (
                    <li key={opener} onClick={() => send(opener)}>
                      {opener}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {entries.map((entry, index) => {
              const pending = streaming && index === entries.length - 1 && entry.from === "kairos";
              return (
                <article className="entry" data-from={entry.from} key={index}>
                  <div className="from">{entry.from === "me" ? username : "kairos"}</div>
                  <div className="said">
                    {entry.said}
                    {pending && entry.said === "" && (
                      <span className="thinking">Consultando memoria…</span>
                    )}
                    {pending && <span className="cursor" aria-hidden="true" />}
                  </div>
                </article>
              );
            })}

            {fault && <div className="fault">{fault}</div>}
            <div ref={foot} />
          </div>

          <div className="console">
            <textarea
              ref={boxRef}
              rows={2}
              value={draft}
              placeholder="Habla o escribe"
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
              onTranscript={(text) => {
                setDraft((prev) => (prev ? `${prev} ${text}` : text));
                boxRef.current?.focus();
              }}
            />
            {streaming ? (
              <button type="button" onClick={halt}>
                Detener
              </button>
            ) : (
              <button type="button" data-primary onClick={() => send()} disabled={!draft.trim()}>
                Enviar
              </button>
            )}
          </div>
        </div>

        <Instruments
          summary={summary}
          liveTrace={liveTrace}
          liveMemories={liveMemories}
          streaming={streaming}
        />
      </div>
    </div>
  );
}
