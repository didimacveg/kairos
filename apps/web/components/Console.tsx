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
import { WakeListener } from "@/lib/wake";
import { Attachments, type Attached } from "./Attachments";
import { Despertar } from "./Despertar";
import { Instruments, type TurnSummary } from "./Instruments";
import { Sigil } from "./Sigil";
import { StatusStrip } from "./StatusStrip";
import { VoiceSession } from "./VoiceSession";

type Entry = { from: "me" | "kairos"; said: string };

/** Atajos que abren y cierran la sesión de voz. Alt+K y Alt+7. */
function isVoiceHotkey(event: KeyboardEvent): boolean {
  if (!event.altKey || event.ctrlKey || event.metaKey) return false;
  return event.code === "KeyK" || event.code === "Digit7" || event.code === "Numpad7";
}

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
  const [adjuntos, setAdjuntos] = useState<Attached[]>([]);
  const [escuchaAmbiente, setEscuchaAmbiente] = useState(false);
  const [estadoEscucha, setEstadoEscucha] = useState("espera");
  const [despertando, setDespertando] = useState(0);
  const wakeRef = useRef<WakeListener | null>(null);

  const logFoot = useRef<HTMLDivElement>(null);
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
    logFoot.current?.scrollIntoView({ behavior: "smooth" });
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
      const voice = speak ? new SpeechQueue((m) => setFault(m)) : null;
      speechRef.current = voice;

      const idsAdjuntos = adjuntos.map((a) => a.id);
      setAdjuntos([]);
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
      }, idsAdjuntos);
    },
    [draft, streaming, conversationId, adjuntos],
  );

  const halt = useCallback(() => {
    abortRef.current?.();
    speechRef.current?.stop();
    setStreaming(false);
  }, []);

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

  // Escucha ambiente: el ÚNICO micrófono de KAIROS. Vive aquí para que se
  // comporte igual en el PC y en el móvil.
  useEffect(() => {
    if (!escuchaAmbiente) {
      wakeRef.current?.stop();
      wakeRef.current = null;
      setEstadoEscucha("espera");
      return;
    }
    const listener = new WakeListener(
      {
        onLevel: () => undefined,
        onState: (estado) => {
          // El salto a "seguimiento" es el instante en que KAIROS reconoce
          // su nombre. Es el unico evento de la interfaz que viene del mundo
          // real, y por eso es el que dispara la animacion.
          if (estado === "seguimiento") setDespertando((n) => n + 1);
          setEstadoEscucha(estado);
        },
        onUtterance: (texto) => {
          listener.marcarActividad();
          send(texto, true);
        },
        onFault: setFault,
      },
      ["kairos", "cairos", "kairo", "cairo", "chairos", "gairos", "kayros"],
    );
    wakeRef.current = listener;
    void listener.start();
    return () => {
      listener.stop();
      wakeRef.current = null;
    };
  }, [escuchaAmbiente]);

  // Atajo global dentro de la pestaña. Un atajo que funcione con la ventana
  // minimizada necesita el demonio de host: el navegador no puede.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!isVoiceHotkey(event)) return;
      event.preventDefault();
      setVoiceOn((prev) => {
        if (prev) speechRef.current?.stop();
        return !prev;
      });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // La última respuesta de KAIROS, que es la que se muestra grande bajo el
  // sigilo. El historial completo vive en el carril de la izquierda.
  const current = [...entries].reverse().find((e) => e.from === "kairos");

  return (
    <div className="deck">
      <Despertar activo={despertando > 0} key={despertando} />
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
        {/* Carril de registro: la conversación completa, en pequeño */}
        <aside className="log-rail">
          <h2>Registro</h2>
          {entries.length === 0 && <p className="quiet">Sin actividad todavía.</p>}
          {entries.map((entry, index) => (
            <div className="line" data-from={entry.from} key={index}>
              <span className="who">{entry.from === "me" ? username : "kairos"}</span>
              <p>{entry.said || "…"}</p>
            </div>
          ))}
          <div ref={logFoot} />
        </aside>

        {/* Escenario: el sigilo manda siempre */}
        <div className="stage">
          <Sigil
            health={health}
            busy={streaming}
            listening={voiceOn}
            recalled={summary?.memories.length ?? liveMemories.length}
          />

          <div className="utterance" data-streaming={streaming || undefined}>
            {current?.said ? (
              <p>{current.said}</p>
            ) : streaming ? (
              <p className="quiet">Consultando memoria…</p>
            ) : (
              <p className="quiet">
                Pulsa <b>Alt+K</b> para hablar, o escribe abajo. Todo el procesamiento
                ocurre en esta máquina.
              </p>
            )}
          </div>

          {fault && <div className="fault">{fault}</div>}

          <div className="console">
            <textarea
              ref={boxRef}
              rows={1}
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
            <Attachments
              items={adjuntos}
              egress={health?.egress_allowed ?? false}
              onAdd={(item) => setAdjuntos((prev) => [...prev, item].slice(0, 4))}
              onRemove={(id) => setAdjuntos((prev) => prev.filter((a) => a.id !== id))}
            />
            <button
              type="button"
              onClick={() => setEscuchaAmbiente((v) => !v)}
              data-live={escuchaAmbiente || undefined}
              title="KAIROS escucha y responde cuando dices su nombre"
            >
              {escuchaAmbiente ? `Oyendo · ${estadoEscucha}` : "Escucha ambiente"}
            </button>
            <VoiceSession
              active={voiceOn}
              busy={streaming}
              onToggle={(next) => {
                setVoiceOn(next);
                if (!next) speechRef.current?.stop();
              }}
              onInterrupt={halt}
              onHush={() => speechRef.current?.stop()}
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
