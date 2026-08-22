"use client";

import { useCallback, useEffect, useState } from "react";

type Briefing = {
  id: string;
  content: string;
  created_at: string;
  read: boolean;
};

/**
 * Informes diarios pendientes.
 *
 * KAIROS los cuenta en alto a su hora, pero si no estabas delante el audio se
 * perdió. Aquí siguen esperando: eso es lo que convierte un aviso en un aviso
 * y no en ruido.
 *
 * El botón de escuchar los reproduce con la misma voz, así que puedes oír el
 * informe de las 15:30 a las nueve de la noche.
 */
export function Briefings() {
  const [items, setItems] = useState<Briefing[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [hablando, setHablando] = useState<string | null>(null);
  const [fallo, setFallo] = useState<string | null>(null);
  // La fecha SOLO se formatea despues de montar. `toLocaleString` da un
  // resultado distinto en el servidor (contenedor, UTC, locale C) que en el
  // navegador, y esa diferencia es lo que rompia la hidratacion de React.
  const [montado, setMontado] = useState(false);

  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/v1/briefing/latest", { credentials: "same-origin" });
      if (response.ok) setItems((await response.json()) as Briefing[]);
    } catch {
      /* el núcleo caído ya se señala en la cabecera */
    }
  }, []);

  useEffect(() => {
    setMontado(true);
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, [load]);

  const pendientes = items.filter((b) => !b.read).length;

  const marcar = async (id: string) => {
    await fetch(`/api/v1/briefing/${id}/read`, { method: "POST", credentials: "same-origin" });
    setItems((prev) => prev.map((b) => (b.id === id ? { ...b, read: true } : b)));
  };

  const escuchar = async (id: string, texto: string) => {
    // Piper tarda varios segundos con un informe de cinco frases. Sin
    // indicador parece que el boton no hace nada y se pulsa dos veces.
    setHablando(id);
    setFallo(null);
    try {
      const response = await fetch("/api/v1/voice/speak", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: texto }),
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(body?.detail ?? `El nucleo respondio ${response.status}`);
      }
      const blob = await response.blob();
      if (blob.size < 100) throw new Error("El audio llego vacio");
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => {
        URL.revokeObjectURL(url);
        setHablando(null);
      };
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        setFallo("El navegador no pudo reproducir el audio");
        setHablando(null);
      };
      await audio.play();
    } catch (err) {
      setFallo(err instanceof Error ? err.message : "No se pudo reproducir");
      setHablando(null);
    }
  };

  const generar = async () => {
    setBusy(true);
    try {
      await fetch("/api/v1/briefing/now", { method: "POST", credentials: "same-origin" });
      await load();
      setOpen(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="briefings">
      <button type="button" onClick={() => setOpen((v) => !v)} data-pending={pendientes || undefined}>
        Informes{pendientes > 0 ? ` · ${pendientes}` : ""}
      </button>

      {open && (
        <div className="briefing-panel">
          <div className="briefing-head">
            <span>Informe diario</span>
            <button type="button" onClick={generar} disabled={busy}>
              {busy ? "Generando" : "Generar ahora"}
            </button>
          </div>

          {fallo && <div className="fault">{fallo}</div>}

          {items.length === 0 && (
            <p className="quiet">Aún no hay informes. El primero llegará a su hora.</p>
          )}

          {items.map((b) => (
            <article key={b.id} className="briefing" data-unread={!b.read || undefined}>
              <div className="when">
                {montado
                  ? new Date(b.created_at).toLocaleString("es-ES", {
                      weekday: "short",
                      day: "numeric",
                      month: "short",
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : ""}
              </div>
              <p>{b.content}</p>
              <div className="briefing-acts">
                <button
                  type="button"
                  onClick={() => void escuchar(b.id, b.content)}
                  disabled={hablando !== null}
                >
                  {hablando === b.id ? "Sonando" : "Escuchar"}
                </button>
                {!b.read && (
                  <button type="button" onClick={() => void marcar(b.id)}>
                    Marcar leído
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
