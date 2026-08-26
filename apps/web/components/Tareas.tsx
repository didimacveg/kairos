"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Tarea = {
  id: string;
  encargo: string;
  titulo: string;
  estado: "pendiente" | "planificando" | "trabajando" | "lista" | "fallida";
  paso: number;
  pasos: number;
  created_at: string;
};

/**
 * Panel de encargos.
 *
 * KAIROS trabaja en segundo plano; esto es donde ves qué está haciendo y
 * recoges el resultado. Sin esto la cola existe pero no se usa.
 *
 * Refresca cada 10 s solo si hay algo en marcha: sondear cada diez segundos
 * una lista quieta es gasto sin motivo.
 */

const CSS = `
.tareas { position: relative; }
.tareas > button[data-trabajando] { color: var(--ice); border-color: var(--ice);
  box-shadow: 0 0 14px -4px var(--ice-glow); }

.tp { position: absolute; top: calc(100% + .6rem); right: 0; z-index: 30;
  width: min(46rem, 94vw); max-height: 78vh; overflow-y: auto;
  background: var(--panel); border: 1px solid var(--rule-bright);
  padding: 1rem; box-shadow: 0 24px 60px -20px rgba(0,0,0,.92); }

.tp-cab { font-family: var(--data); font-size: .5625rem;
  letter-spacing: var(--track-label); text-transform: uppercase;
  color: var(--faint); padding-bottom: .5rem; border-bottom: 1px solid var(--rule);
  margin-bottom: .9rem; }

.tp-nueva { display: flex; flex-direction: column; gap: .5rem; margin-bottom: 1rem; }
.tp-nueva textarea { resize: vertical; min-height: 3.4rem; font-size: .85rem; }
.tp-fila { display: flex; gap: .5rem; align-items: center; }
.tp-fila span { font-size: .7rem; color: var(--dim); flex: 1; }

.t { border: 1px solid var(--rule); border-left-width: 2px; padding: .8rem;
  margin-bottom: .7rem; }
.t[data-estado="trabajando"], .t[data-estado="planificando"] { border-left-color: var(--ice); }
.t[data-estado="lista"] { border-left-color: var(--brass); }
.t[data-estado="fallida"] { border-left-color: var(--ember); }
.t[data-estado="pendiente"] { border-left-color: var(--rule-bright); }

.t-cab { display: flex; justify-content: space-between; gap: 1rem;
  font-family: var(--data); font-size: .5rem; letter-spacing: var(--track-label);
  text-transform: uppercase; color: var(--faint); margin-bottom: .45rem; }
.t h3 { margin: 0 0 .35rem; font-size: .88rem; font-weight: 400; color: var(--bone);
  line-height: 1.4; }
.t p { margin: 0 0 .6rem; font-size: .74rem; line-height: 1.5; color: #9fb0b6; }

.t-barra { height: 2px; background: var(--rule); margin-bottom: .6rem; }
.t-barra i { display: block; height: 100%; background: var(--ice);
  transition: width .6s ease; }

.t-acts { display: flex; gap: .4rem; flex-wrap: wrap; }
.t-acts button { padding: .35rem .7rem !important; font-size: .5rem !important; }

.t-res { margin-top: .8rem; padding: .9rem; max-height: 30rem; overflow-y: auto;
  background: var(--void); border: 1px solid var(--rule);
  font-size: .82rem; line-height: 1.7; color: #c3d2d7; white-space: pre-wrap; }

@media (max-width: 700px) { .tp { width: 94vw; right: -1rem; } }
`;

const ETIQUETA: Record<string, string> = {
  pendiente: "en cola",
  planificando: "planificando",
  trabajando: "trabajando",
  lista: "lista",
  fallida: "fallo",
};

export function Tareas() {
  const [abierto, setAbierto] = useState(false);
  const [items, setItems] = useState<Tarea[]>([]);
  const [encargo, setEncargo] = useState("");
  const [material, setMaterial] = useState<{ nombre: string; texto: string } | null>(null);
  const [abierta, setAbierta] = useState<{ id: string; texto: string } | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const fichero = useRef<HTMLInputElement>(null);

  const cargar = useCallback(async () => {
    try {
      const r = await fetch("/api/v1/tareas", { credentials: "same-origin" });
      if (!r.ok) return;
      const d = (await r.json()) as { tareas: Tarea[] };
      setItems(d.tareas ?? []);
    } catch {
      /* el núcleo caído ya se señala arriba */
    }
  }, []);

  const enMarcha = items.some(
    (t) => t.estado === "trabajando" || t.estado === "planificando" || t.estado === "pendiente",
  );

  useEffect(() => {
    cargar();
    // Solo se sondea si hay algo en marcha. Refrescar una lista quieta cada
    // diez segundos es gasto sin motivo.
    if (!enMarcha) return;
    const id = setInterval(cargar, 10_000);
    return () => clearInterval(id);
  }, [cargar, enMarcha]);

  const subir = async (f: File) => {
    setOcupado(true);
    setAviso(null);
    try {
      const form = new FormData();
      form.append("file", f, f.name);
      const r = await fetch("/api/v1/tareas/material", {
        method: "POST",
        credentials: "same-origin",
        body: form,
      });
      const d = await r.json().catch(() => null);
      if (!r.ok) throw new Error(d?.detail ?? "No se pudo leer el fichero");
      setMaterial({ nombre: d.nombre, texto: d.texto });
      setAviso(`${d.nombre}: ${d.caracteres.toLocaleString("es-ES")} caracteres leídos.`);
    } catch (err) {
      setAviso(err instanceof Error ? err.message : "Fallo al subir");
    } finally {
      setOcupado(false);
    }
  };

  const encargar = async () => {
    const texto = encargo.trim();
    if (texto.length < 10) return;
    setOcupado(true);
    try {
      const r = await fetch("/api/v1/tareas", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ encargo: texto, material: material?.texto ?? "" }),
      });
      const d = await r.json().catch(() => null);
      if (!r.ok) throw new Error(d?.detail ?? "No se pudo encargar");
      setEncargo("");
      setMaterial(null);
      setAviso(d.confirmacion ?? "Encargado.");
      await cargar();
    } catch (err) {
      setAviso(err instanceof Error ? err.message : "Fallo");
    } finally {
      setOcupado(false);
    }
  };

  const ver = async (id: string) => {
    if (abierta?.id === id) {
      setAbierta(null);
      return;
    }
    const r = await fetch(`/api/v1/tareas/${id}`, { credentials: "same-origin" });
    if (!r.ok) return;
    const d = (await r.json()) as { resultado: string };
    setAbierta({ id, texto: d.resultado || "(vacío)" });
  };

  const borrar = async (id: string) => {
    await fetch(`/api/v1/tareas/${id}`, { method: "DELETE", credentials: "same-origin" });
    if (abierta?.id === id) setAbierta(null);
    await cargar();
  };

  const listas = items.filter((t) => t.estado === "lista").length;

  return (
    <div className="tareas">
      <style dangerouslySetInnerHTML={{ __html: CSS }} />
      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        data-trabajando={enMarcha || undefined}
      >
        Encargos{listas > 0 ? ` · ${listas}` : enMarcha ? " · …" : ""}
      </button>

      {abierto && (
        <div className="tp">
          <div className="tp-cab">Encargos · KAIROS trabaja mientras hablas con él</div>

          <div className="tp-nueva">
            <textarea
              rows={3}
              value={encargo}
              placeholder="Qué quieres que haga. Cuanto más concreto, mejor sale."
              onChange={(e) => setEncargo(e.target.value)}
              disabled={ocupado}
            />
            <div className="tp-fila">
              <input
                ref={fichero}
                type="file"
                accept=".txt,.md,.csv,.json,.pdf,.docx,.py,.js,.ts,.html,.css"
                hidden
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void subir(f);
                  e.target.value = "";
                }}
              />
              <button type="button" onClick={() => fichero.current?.click()} disabled={ocupado}>
                {material ? "Cambiar material" : "Adjuntar"}
              </button>
              <span>{material ? material.nombre : "PDF, Word, texto o código"}</span>
              <button
                type="button"
                data-primary
                onClick={() => void encargar()}
                disabled={ocupado || encargo.trim().length < 10}
              >
                Encargar
              </button>
            </div>
          </div>

          {aviso && <p style={{ fontSize: ".75rem", color: "var(--ice)" }}>{aviso}</p>}

          {items.length === 0 && (
            <p style={{ fontSize: ".8rem", color: "var(--dim)", lineHeight: 1.6 }}>
              Nada encargado. Prueba con algo largo: un trabajo, un informe, una
              redacción. KAIROS lo planifica, lo escribe por partes y lo repasa.
            </p>
          )}

          {items.map((t) => (
            <article className="t" data-estado={t.estado} key={t.id}>
              <div className="t-cab">
                <span>{ETIQUETA[t.estado] ?? t.estado}</span>
                {t.pasos > 0 && (
                  <span>
                    {t.paso} de {t.pasos}
                  </span>
                )}
              </div>
              <h3>{t.titulo || t.encargo.slice(0, 90)}</h3>
              {t.titulo && <p>{t.encargo.slice(0, 150)}</p>}

              {t.pasos > 0 && t.estado !== "lista" && (
                <div className="t-barra">
                  <i style={{ width: `${Math.round((t.paso / t.pasos) * 100)}%` }} />
                </div>
              )}

              <div className="t-acts">
                {(t.estado === "lista" || t.estado === "fallida") && (
                  <button type="button" onClick={() => void ver(t.id)}>
                    {abierta?.id === t.id ? "Ocultar" : "Ver resultado"}
                  </button>
                )}
                {abierta?.id === t.id && (
                  <button
                    type="button"
                    onClick={() => void navigator.clipboard.writeText(abierta.texto)}
                  >
                    Copiar
                  </button>
                )}
                <button type="button" onClick={() => void borrar(t.id)}>
                  Borrar
                </button>
              </div>

              {abierta?.id === t.id && <div className="t-res">{abierta.texto}</div>}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
