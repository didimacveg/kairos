"use client";

import { useCallback, useEffect, useState } from "react";

type Propuesta = {
  id: string;
  titulo: string;
  motivo: string;
  rama: string;
  riesgo: "bajo" | "medio" | "alto";
  estado: string;
  lineas_diff: number;
  tests: string;
  created_at: string;
};

/**
 * Panel de auto-mejora: donde KAIROS pide permiso para cambiarse.
 *
 * El ciclo entero es visible aquí: pides un cambio, KAIROS lo escribe, se
 * ensaya aislado, y aparece con su diff y sus tests para que decidas.
 *
 * Tres botones, tres momentos distintos, a propósito:
 *   Aprobar   decisión reversible, no toca nada
 *   Rechazar  la propuesta muere
 *   Aplicar   escribe en el repositorio de verdad
 *
 * Aprobar y aplicar están separados porque son cosas distintas: una es un
 * juicio, la otra una operación que puede fallar.
 */
export function Proposals() {
  const [abierto, setAbierto] = useState(false);
  const [items, setItems] = useState<Propuesta[]>([]);
  const [historial, setHistorial] = useState<Propuesta[]>([]);
  const [diff, setDiff] = useState<{ id: string; texto: string } | null>(null);
  const [peticion, setPeticion] = useState("");
  const [trabajando, setTrabajando] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    try {
      const r = await fetch("/api/v1/proposals", { credentials: "same-origin" });
      if (!r.ok) return;
      const d = (await r.json()) as { pendientes: Propuesta[]; historial: Propuesta[] };
      setItems(d.pendientes ?? []);
      setHistorial((d.historial ?? []).filter((p) => p.estado !== "pendiente"));
    } catch {
      /* el núcleo caído ya se señala en la cabecera */
    }
  }, []);

  useEffect(() => {
    cargar();
    const id = setInterval(cargar, 30_000);
    return () => clearInterval(id);
  }, [cargar]);

  const pedir = async () => {
    const texto = peticion.trim();
    if (texto.length < 8) return;
    setTrabajando("pidiendo");
    setAviso("KAIROS está leyendo su código y ensayando el cambio. Tarda unos minutos.");
    try {
      const r = await fetch("/api/v1/smith/proponer", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ peticion: texto }),
      });
      const cuerpo = await r.json().catch(() => null);
      if (!r.ok) throw new Error(cuerpo?.detail ?? `El núcleo respondió ${r.status}`);
      setPeticion("");
      setAviso(
        cuerpo?.tests_verdes
          ? "Propuesta lista, con los tests en verde."
          : "Propuesta creada, pero los tests fallan. Léela antes de aprobar.",
      );
      await cargar();
    } catch (err) {
      setAviso(err instanceof Error ? err.message : "No se pudo proponer");
    } finally {
      setTrabajando(null);
    }
  };

  const verDiff = async (id: string) => {
    if (diff?.id === id) {
      setDiff(null);
      return;
    }
    const r = await fetch(`/api/v1/proposals/${id}/diff`, { credentials: "same-origin" });
    if (!r.ok) return;
    const d = (await r.json()) as { diff: string };
    setDiff({ id, texto: d.diff });
  };

  const decidir = async (id: string, aprobar: boolean) => {
    setTrabajando(id);
    try {
      await fetch(`/api/v1/proposals/${id}/decidir`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ aprobar, nota: "" }),
      });
      await cargar();
    } finally {
      setTrabajando(null);
    }
  };

  const aplicar = async (id: string) => {
    setTrabajando(id);
    setAviso("Aplicando: rama, parche, tests y merge. Un par de minutos.");
    try {
      const r = await fetch(`/api/v1/proposals/${id}/aplicar`, {
        method: "POST",
        credentials: "same-origin",
      });
      const cuerpo = await r.json().catch(() => null);
      if (!r.ok) throw new Error(cuerpo?.detail ?? `El núcleo respondió ${r.status}`);
      setAviso(
        cuerpo?.ok
          ? `Aplicado en ${cuerpo.commit_actual}. Reinicia el núcleo para que entre: ` +
            `docker compose up -d --force-recreate core`
          : "No se pudo aplicar. El repositorio quedó como estaba.",
      );
      await cargar();
    } catch (err) {
      setAviso(err instanceof Error ? err.message : "Fallo al aplicar");
    } finally {
      setTrabajando(null);
    }
  };

  const pendientes = items.length;

  return (
    <div className="props">
      <button type="button" onClick={() => setAbierto((v) => !v)} data-pending={pendientes || undefined}>
        Propuestas{pendientes > 0 ? ` · ${pendientes}` : ""}
      </button>

      {abierto && (
        <div className="props-panel">
          <div className="props-head">
            <span>Auto-mejora</span>
          </div>

          <div className="props-ask">
            <textarea
              rows={2}
              value={peticion}
              placeholder="Pídele a KAIROS que cambie algo de sí mismo"
              onChange={(e) => setPeticion(e.target.value)}
              disabled={trabajando !== null}
            />
            <button
              type="button"
              onClick={() => void pedir()}
              disabled={trabajando !== null || peticion.trim().length < 8}
            >
              {trabajando === "pidiendo" ? "Escribiendo" : "Proponer"}
            </button>
          </div>

          {aviso && <div className="props-aviso">{aviso}</div>}

          {pendientes === 0 && <p className="quiet">Nada pendiente de decidir.</p>}

          {items.map((p) => (
            <article key={p.id} className="prop" data-riesgo={p.riesgo}>
              <div className="prop-cab">
                <span className="riesgo">riesgo {p.riesgo}</span>
                <span className={p.tests.startsWith("VERDE") ? "verde" : "rojo"}>
                  {p.tests.startsWith("VERDE") ? "tests en verde" : "tests en rojo"}
                </span>
              </div>
              <h3>{p.titulo}</h3>
              <p>{p.motivo}</p>
              <div className="prop-meta">
                {p.rama} · {p.lineas_diff} líneas
              </div>

              <div className="prop-acts">
                <button type="button" onClick={() => void verDiff(p.id)}>
                  {diff?.id === p.id ? "Ocultar cambios" : "Ver cambios"}
                </button>
                <button
                  type="button"
                  data-primary
                  onClick={() => void decidir(p.id, true)}
                  disabled={trabajando !== null}
                >
                  Aprobar
                </button>
                <button
                  type="button"
                  onClick={() => void decidir(p.id, false)}
                  disabled={trabajando !== null}
                >
                  Rechazar
                </button>
              </div>

              {diff?.id === p.id && <pre className="prop-diff">{diff.texto}</pre>}
            </article>
          ))}

          {historial.length > 0 && (
            <>
              <div className="props-head props-sep">
                <span>Decididas</span>
              </div>
              {historial.slice(0, 6).map((p) => (
                <article key={p.id} className="prop" data-estado={p.estado}>
                  <div className="prop-cab">
                    <span className="riesgo">{p.estado}</span>
                  </div>
                  <h3>{p.titulo}</h3>
                  {p.estado === "aprobada" && (
                    <div className="prop-acts">
                      <button
                        type="button"
                        data-primary
                        onClick={() => void aplicar(p.id)}
                        disabled={trabajando !== null}
                      >
                        {trabajando === p.id ? "Aplicando" : "Aplicar al repositorio"}
                      </button>
                    </div>
                  )}
                </article>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
