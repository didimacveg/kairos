"use client";

import { useEffect, useRef, useState } from "react";
import { api, type ChatResponse, type Health } from "@/lib/api";
import { TraceRail } from "./TraceRail";

type Turn = { role: "user" | "assistant"; content: string };

export function Console({ username, onSignOut }: { username: string; onSignOut: () => void }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [last, setLast] = useState<ChatResponse | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns.length, busy]);

  async function send() {
    const message = draft.trim();
    if (!message || busy) return;
    setDraft("");
    setError(null);
    setBusy(true);
    setTurns((prev) => [...prev, { role: "user", content: message }]);
    try {
      const response = await api.chat(message, conversationId);
      setConversationId(response.conversation_id);
      setLast(response);
      setTurns((prev) => [...prev, { role: "assistant", content: response.reply }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fallo la peticion");
    } finally {
      setBusy(false);
    }
  }

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
            {turns.map((turn, index) => (
              <article className="turn" data-role={turn.role} key={index}>
                <div className="who">{turn.role === "user" ? username : "kairos"}</div>
                <div className="body">{turn.content}</div>
              </article>
            ))}
            {busy && (
              <article className="turn" data-role="assistant">
                <div className="who">kairos</div>
                <div className="body" style={{ color: "var(--muted)" }}>
                  Recuperando memoria y generando…
                </div>
              </article>
            )}
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
                  void send();
                }
              }}
            />
            <button type="button" onClick={() => void send()} disabled={busy || !draft.trim()}>
              Enviar
            </button>
          </div>
        </div>

        <TraceRail last={last} />
      </div>
    </div>
  );
}
