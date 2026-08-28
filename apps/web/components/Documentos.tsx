"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Doc = {
  id: string;
  titulo: string;
  materia: string;
  trozos: number;
  caracteres: number;
  created_at: string;
};

/**
 * Los apuntes de Diego.
 *
 * La memoria documental existe desde la Fase 51 pero solo se podía alimentar
 * por API. Sin panel no se usa — es lo que pasó con los encargos, que
 * estuvieron ocho fases en la interfaz sin nada detrás.
 *
 * Acepta arrastrar y soltar: subir apuntes es algo que haces con varios
 * ficheros de golpe al empezar el curso, no de uno en uno.
 */

const CSS = `
.docs { position: relative; }
.docs > button[data-lleno] { color: var(--brass); border-color: var(--brass); }

.dp { position: absolute; top: calc(100% + .6rem); right: 0; z-index: 30;
  width: min(34rem, 94vw); max-height: 74vh; overflow-y: auto;
  background: var(--panel); border: 1px solid var(--rule-bright);
  padding: 1rem; box-shadow: 0 24px 60px -20px rgba(0,0,0,.92); }

.dp-cab { font-family: var(--data); font-size: .5625rem;
  letter-spacing: var(--track-label); text-transform: uppercase;
  color: var(--faint); padding-bottom: .5rem; border-bottom: 1px solid var(--rule);
  margin-bottom: .9rem; }

.dp-soltar { border: 1px dashed var(--rule-bright); padding: 1.3rem 1rem;
  text-align: center; margin-bottom: .9rem; cursor: pointer;
  transition: border-color .2s, background .2s; }
.dp-soltar:hover, .dp-soltar[data-encima] {
  border-color: var(--ice); background: rgba(79,216,255,.06); }
.dp-soltar p { margin: 0; font-size: .8rem; color: var(--bone); line-height: 1.5; }
.dp-soltar small { display: block; margin-top: .3rem; font-size: .68rem;
  color: var(--faint); }

.dp-materia { width: 100%; margin-bottom: .8rem; font-size: .8rem; }

.d { display: flex; align-items: center; gap: .6rem; padding: .55rem .6rem;
  border-left: 2px solid var(--rule-bright); margin-bottom: .35rem; }
.d:hover { background: rgba(79,216,255,.05); }
.d-txt { flex: 1; min-width: 0; }
.d-tit { font-size: .8rem; color: var(--bone); overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; }
.d-meta { font-family: var(--data); font-size: .47rem; letter-spacing: .1em;
  color: var(--faint); margin-top: .15rem; }
.d button { padding: .2rem .45rem !important; font-size: .45rem !important;
  opacity: 0; }
.d:hover button { opacity: 1; }
`;

export function Documentos() {
  const [abierto, setAbierto] = useState(false);
  const [items, setItems] = useState<Doc[]>([]);
  const [materia, setMateria] = useState("");
  const [encima, setEncima] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const fichero = useRef<HTMLInputElement>(null);
  const caja = useRef<HTMLDivElement>(null);

  const cargar = useCallback(async () => {
    try {
      const r = await fetch("/api/v1/documentos", { credentials: "same-origin" });
      if (!r.ok) return;
      const d = (await r.json()) as { documentos: Doc[] };
      setItems(d.documentos ?? []);
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

  const subir = async (ficheros: FileList | File[]) => {
    setSubiendo(true);
    const lista = Array.from(ficheros);
    let subidos = 0;

    for (const f of lista) {
      setAviso(`Indexando ${f.name}…`);
      try {
        const form = new FormData();
        form.append("file", f, f.name);
        form.append("materia", materia);
        const r = await fetch("/api/v1/documentos/subir", {
          method: "POST",
          credentials: "same-origin",
          body: form,
        });
        const d = await r.json().catch(() => null);
        if (!r.ok) throw new Error(d?.detail ?? "No se pudo leer");
        subidos += 1;
      } catch (err) {
        setAviso(`${f.name}: ${err instanceof Error ? err.message : "fallo"}`);
        setSubiendo(false);
        await cargar();
        return;
      }
    }

    setAviso(
      subidos === lista.length
        ? `${subidos} documento${subidos === 1 ? "" : "s"} indexado${subidos === 1 ? "" : "s"}.`
        : `${subidos} de ${lista.length} indexados.`,
    );
    setSubiendo(false);
    await cargar();
  };

  const borrar = async (id: string) => {
    await fetch(`/api/v1/documentos/${id}`, {
      method: "DELETE",
      credentials: "same-origin",
    });
    await cargar();
  };

  return (
    <div className="docs" ref={caja}>
      <style dangerouslySetInnerHTML={{ __html: CSS }} />
      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        data-lleno={items.length > 0 || undefined}
        title="Apuntes que KAIROS ha indexado"
      >
        Apuntes{items.length > 0 ? ` · ${items.length}` : ""}
      </button>

      {abierto && (
        <div className="dp">
          <div className="dp-cab">Apuntes · KAIROS responde con tu temario</div>

          <input
            className="dp-materia"
            value={materia}
            placeholder="Asignatura (opcional): Física, Historia…"
            onChange={(e) => setMateria(e.target.value)}
          />

          <input
            ref={fichero}
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.md,.csv"
            hidden
            onChange={(e) => {
              if (e.target.files?.length) void subir(e.target.files);
              e.target.value = "";
            }}
          />

          <div
            className="dp-soltar"
            data-encima={encima || undefined}
            onClick={() => !subiendo && fichero.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setEncima(true);
            }}
            onDragLeave={() => setEncima(false)}
            onDrop={(e) => {
              e.preventDefault();
              setEncima(false);
              if (e.dataTransfer.files?.length) void subir(e.dataTransfer.files);
            }}
          >
            <p>{subiendo ? "Indexando…" : "Arrastra tus apuntes aquí"}</p>
            <small>PDF, Word, texto · varios a la vez</small>
          </div>

          {aviso && (
            <p style={{ fontSize: ".75rem", color: "var(--ice)", marginBottom: ".8rem" }}>
              {aviso}
            </p>
          )}

          {items.length === 0 && !subiendo && (
            <p style={{ fontSize: ".78rem", color: "var(--dim)", lineHeight: 1.6 }}>
              Sin apuntes todavía. Sube los de una asignatura y pregúntale de
              ese tema: responderá con tu temario en vez de con teoría general.
            </p>
          )}

          {items.map((d) => (
            <div className="d" key={d.id}>
              <div className="d-txt">
                <div className="d-tit">{d.titulo}</div>
                <div className="d-meta">
                  {d.materia ? `${d.materia} · ` : ""}
                  {d.trozos} fragmentos · {(d.caracteres / 1000).toFixed(0)}k caracteres
                </div>
              </div>
              <button type="button" onClick={() => void borrar(d.id)}>
                Borrar
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
