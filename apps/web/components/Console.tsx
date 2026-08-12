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
import { SpeechQueue } from "@/lib/speech";
import { Instruments, type TurnSummary } from "./Instruments";
import { Sigil } from "./Sigil";
import { StatusStrip } from "./StatusStrip";
import { VoiceSession } from "./VoiceSession";

type Entry = { from: "me" | "kairos"; said: string };

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
  const [voiceOn, setVoiceOn] = useState(false);

  const foot = useRef<HTMLDivElement>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const speechRef = useRef<SpeechQueue | null>(null);
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

  useEffect(
    () => () => {
      abortRef.current?.();
      speechRef.current?.stop();
    },
    [],
  );

  const send = useCallback(
    (text?: string, speak = false) => {
      const message = (text ?? draft).trim();
      if (!message || streaming) return;

      setDraft("");
      setFault(null);
      setLiveTrace([]);
      setLiveMemories([]);
      setSummary(null);
      setStreaming(true);
      setEntries((prev) => [...prev, { from: "me", said: message }, { from: "kairos", said: "" }]);

      speechRef.current?.stop();
      const voice = speak ? new SpeechQueue((message) => setFault(message)) : null;
      speechRef.current = voice;

      abortRef.current = streamChat(message, conversationId, {
        onToken: (chunk) => {
          voice?.push(chunk);
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
          voice?.flush();
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
          voice?.stop();
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
    speechRef.current?.stop();
    setStreaming(false);
  }, []);

  /** KAIROS dice algo por su cuenta (p. ej. "no te he entendido") sin
   *  pasar por el modelo: es una respuesta del sistema, no una generación. */
  const say = useCallback(
    (message: string) => {
      setEntries((prev) => [...prev, { from: "kairos", said: message }]);
      if (voiceOn) {
        const queue = new SpeechQueue();
        queue.push(message);
        queue.flush();
      }
    },
    [voiceOn],
  );

  return (
    <div className="deck">
      <StatusStrip
        health={health}
        username={username}
        busy={streaming}
        listening={voiceOn}
        lastLatency={summary?.latency_ms ?? null}
        lastModel={summary?.model ?? null}
        recalled={summary ? summary.memories.length : null}
        onSignOut={onSignOut}
      />

      <div className="bay">
        <div className="channel">
          <div className="log">
            {entries.length === 0 && (
              <div className="core-stage">
                <Sigil health={health} busy={streaming} listening={voiceOn} />
                <p className="hint">
                  Escribe, o enciende la sesión de voz y habla. Todo el procesamiento
                  ocurre en esta máquina.
                </p>
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
            <VoiceSession
              active={voiceOn}
              busy={streaming}
              onToggle={(next) => {
                setVoiceOn(next);
                if (!next) speechRef.current?.stop();
              }}
              onUtterance={(text) => send(text, true)}
              onSay={say}
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
