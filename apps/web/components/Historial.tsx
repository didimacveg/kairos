"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Conv = {
  id: string;
  titulo: string;
  mensajes: number;
  ultimo: string | null;
};

/**
 * Historial de conversaciones.
 *
 * Los hilos siempre estuvieron en Postgres; faltaba poder volver a ellos. Al
 * recargar, KAIROS empezaba de cero aunque todo siguiera guardado.
 *
 * El título es el primer mensaje que escribiste, no un resumen generado: es
 * lo que de verdad recuerdas haber preguntado, y no cuesta una llamada al
 * modelo por conversación.
 */
const CSS = `
.hist { position: relative; }
.hist-panel { position: absolute; top: calc(100% + .6rem); right: 0; z-index: 30;
  width: min(28rem, 92vw); max-height: 70vh; overflow-y: auto;
  background: var(--panel); border: 1px solid var(--rule-bright);
  padding: .5rem; box-shadow: 0 24px 60px -20px rgba(0,0,0,.92); }
.hist-cab { font-family: var(--data); font-size: .5rem;
  letter-spacing: var(--track-label); text-transform: uppercase;
  color: var(--faint); padding: .5rem .6rem; border-bottom: 1px solid var(--rule);
  margin-bottom: .4rem; }
.hc { display: flex; align-items: center; gap: .5rem; padding: .5rem .6rem;
  border-left: 2px solid transparent; cursor: pointer; }
.hc:hover { background: rgba(79,216,255,.06); border-left-color: var(--ice-dim); }
.hc[data-activa] { border-left-color: var(--ice); background: rgba(79,216,255,.08); }
.hc-txt { flex: 1; min-width: 0; }
.hc-tit { font-size: .78rem; color: var(--bone); line-height: 1.4;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hc-meta { font-family: var(--data); font-size: .47rem; letter-spacing: .1em;
  color: var(--faint); margin-top: .15rem; }
.hc button { padding: .2rem .45rem !important; font-size: .45rem !important;
  opacity: 0; }
.hc:hover button { opacity: 1; }
`;

export function Historial({
  activa,
  onAbrir,
  onNueva,
}: {
  activa: string | null;
  onAbrir: (id: string, mensajes: { from: "me" | "kairos"; said: string }[]) => void;
  onNueva: () => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const [items, setItems] = useState<Conv[]>([]);
  const caja = useRef<HTMLDivElement>(null);

  const cargar = useCallback(async () => {
    try {
      const r = await fetch("/api/v1/conversaciones", { credentials: "same-origin" });
      if (!r.ok) return;
      const d = (await r.json()) as { conversaciones: Conv[] };
      setItems(d.conversaciones ?? []);
    } catch {
      /* núcleo caído, ya se señala arriba */
    }
  }, []);

  useEffect(() => {
    if (abierto) void cargar();
  }, [abierto, cargar]);

  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: MouseEvent) => {
      if (caja.current && !caja.current.contains(e.target as Node)) setAbierto(false);
    };
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, [abierto]);

  const abrir = async (id: string) => {
    const r = await fetch(`/api/v1/conversaciones/${id}`, { credentials: "same-origin" });
    if (!r.ok) return;
    const d = (await r.json()) as { mensajes: { de: string; said: string }[] };
    onAbrir(
      id,
      d.mensajes.map((m) => ({ from: m.de === "me" ? "me" : "kairos", said: m.said })),
    );
    setAbierto(false);
  };

  const borrar = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await fetch(`/api/v1/conversaciones/${id}`, {
      method: "DELETE",
      credentials: "same-origin",
    });
    await cargar();
  };

  const cuando = (iso: string | null) => {
    if (!iso) return "";
    const d = new Date(iso);
    const dias = Math.floor((Date.now() - d.getTime()) / 86_400_000);
    if (dias === 0) return `hoy ${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
    if (dias === 1) return "ayer";
    if (dias < 7) return `hace ${dias} días`;
    return d.toLocaleDateString("es-ES", { day: "numeric", month: "short" });
  };

  return (
    <div className="hist" ref={caja}>
      <style dangerouslySetInnerHTML={{ __html: CSS }} />
      <button type="button" onClick={() => setAbierto((v) => !v)} title="Conversaciones">
        Hilos
      </button>

      {abierto && (
        <div className="hist-panel">
          <div className="hist-cab">Conversaciones</div>

          <div
            className="hc"
            onClick={() => {
              onNueva();
              setAbierto(false);
            }}
          >
            <div className="hc-txt">
              <div className="hc-tit" style={{ color: "var(--ice)" }}>
                Conversación nueva
              </div>
            </div>
          </div>

          {items.map((c) => (
            <div
              key={c.id}
              className="hc"
              data-activa={c.id === activa || undefined}
              onClick={() => void abrir(c.id)}
            >
              <div className="hc-txt">
                <div className="hc-tit">{c.titulo}</div>
                <div className="hc-meta">
                  {cuando(c.ultimo)} · {c.mensajes} mensajes
                </div>
              </div>
              <button type="button" onClick={(e) => void borrar(e, c.id)}>
                Borrar
              </button>
            </div>
          ))}

          {items.length === 0 && (
            <p style={{ fontSize: ".75rem", color: "var(--dim)", padding: ".6rem" }}>
              Todavía no hay conversaciones guardadas.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
