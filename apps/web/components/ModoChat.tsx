"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { Render } from "@/lib/render";

import type { Attached } from "./Attachments";

/**
 * Modo chat: KAIROS sin instrumentos.
 *
 * El panel principal es un panel de control: sigilo, telemetría, trazas. Está
 * bien para operar el sistema y estorba para estudiar. Cuando estás con un
 * ejercicio de física quieres el texto grande, el hilo entero visible y nada
 * más.
 *
 * Es la MISMA conversación: mismo hilo, misma memoria, mismos adjuntos. No es
 * otro KAIROS, es la misma cabeza sin el salpicadero.
 *
 * Se abre con "Kairos, modo chat" o con el botón. Se sale con Escape.
 */

type Entrada = { from: "me" | "kairos"; said: string };

const CSS = `
.chatmodo { position: fixed; inset: 0; z-index: 90; background: var(--void);
  display: grid; grid-template-rows: auto minmax(0,1fr) auto;
  animation: cmEntra .45s cubic-bezier(.16,1,.3,1) !important; }
@keyframes cmEntra { from{opacity:0} to{opacity:1} }

.chatmodo .cm-cab { display: flex; align-items: center; justify-content: space-between;
  padding: .9rem 1.4rem; border-bottom: 1px solid var(--rule);
  font-family: var(--data); font-size: .5625rem; letter-spacing: var(--track-label);
  text-transform: uppercase; color: var(--faint); }

.chatmodo .cm-hilo { overflow-y: auto; padding: 2rem 1.4rem;
  scrollbar-width: thin; scrollbar-color: var(--rule-bright) transparent; }
.chatmodo .cm-centro { max-width: 46rem; margin: 0 auto; }

.chatmodo .cm-turno { margin-bottom: 1.9rem; }
.chatmodo .cm-quien { font-family: var(--data); font-size: .5rem;
  letter-spacing: var(--track-label); text-transform: uppercase;
  color: var(--faint); display: block; margin-bottom: .45rem; }
.chatmodo .cm-turno[data-de="kairos"] .cm-quien { color: var(--ice); }
.chatmodo .cm-turno p { margin: 0; font-size: 1rem; line-height: 1.72;
  color: var(--bone); white-space: pre-wrap; }
.chatmodo .cm-turno[data-de="me"] p { color: #9fb0b6; }

.chatmodo .cm-vacio { color: var(--dim); font-size: .9rem; line-height: 1.7; }

.chatmodo .cm-pie { border-top: 1px solid var(--rule); padding: 1rem 1.4rem 1.4rem; }
.chatmodo .cm-caja { max-width: 46rem; margin: 0 auto; display: flex; gap: .6rem;
  align-items: flex-end; }
.chatmodo .cm-caja textarea { flex: 1; min-height: 3rem; max-height: 12rem;
  resize: vertical; font-size: .95rem; line-height: 1.6; }
.chatmodo .cm-fotos { display: flex; gap: .4rem; margin: 0 auto .6rem;
  max-width: 46rem; flex-wrap: wrap; }
.chatmodo .cm-fotos img { width: 3.4rem; height: 3.4rem; object-fit: cover;
  border: 1px solid var(--rule-bright); }

.chatmodo .cm-turno p { margin: 0 0 .85rem; }
.chatmodo .cm-turno p:last-child { margin-bottom: 0; }

.chatmodo .enc { font-weight: 400; color: #fff; margin: 1.4rem 0 .6rem;
  line-height: 1.35; }
.chatmodo .enc[data-nivel="1"] { font-size: 1.35rem; }
.chatmodo .enc[data-nivel="2"] { font-size: 1.15rem; }
.chatmodo .enc[data-nivel="3"] { font-size: 1rem; color: var(--ice); }
.chatmodo .enc[data-nivel="4"] { font-size: .92rem; color: var(--ice-dim); }
.chatmodo .cm-turno > :first-child.enc { margin-top: 0; }

.chatmodo ul, .chatmodo ol { margin: .3rem 0 .9rem; padding-left: 1.4rem; }
.chatmodo li { margin-bottom: .4rem; line-height: 1.7; }
.chatmodo li::marker { color: var(--ice-dim); }

.chatmodo blockquote { margin: .6rem 0 1rem; padding: .5rem 0 .5rem .9rem;
  border-left: 2px solid var(--brass); color: #b6c3c8; font-style: italic; }

.chatmodo code { font-family: var(--data); font-size: .86em;
  background: rgba(79,216,255,.09); border: 1px solid var(--rule);
  padding: .08em .35em; color: #9fe4f5; }

.chatmodo .bloque-codigo { position: relative; margin: .8rem 0 1.1rem;
  padding: 1rem; background: #060a10; border: 1px solid var(--rule);
  border-left: 2px solid var(--ice-dim); overflow-x: auto; }
.chatmodo .bloque-codigo code { background: none; border: none; padding: 0;
  font-size: .82rem; line-height: 1.65; color: #b8c9cf; white-space: pre; }
.chatmodo .bloque-codigo .lang { position: absolute; top: .4rem; right: .7rem;
  font-family: var(--data); font-size: .5rem; letter-spacing: .18em;
  text-transform: uppercase; color: var(--faint); }

/* Formulas: en linea y en bloque */
.chatmodo .mate { font-family: "Cambria Math", Georgia, serif; font-size: 1.06em;
  color: #d7ecf2; padding: 0 .12em; }
.chatmodo .mate-bloque { font-family: "Cambria Math", Georgia, serif;
  font-size: 1.28rem; color: #e8f6fa; text-align: center;
  margin: 1.1rem 0; padding: .9rem 1rem;
  background: rgba(79,216,255,.045); border-top: 1px solid var(--rule);
  border-bottom: 1px solid var(--rule); overflow-x: auto; }

/* La fraccion se compone de verdad: numerador sobre denominador. */
.chatmodo .frac { display: inline-flex; flex-direction: column;
  vertical-align: middle; text-align: center; margin: 0 .22em;
  font-size: .88em; line-height: 1.18; }
.chatmodo .frac > span:first-child { border-bottom: 1px solid currentColor;
  padding: 0 .3em .06em; }
.chatmodo .frac > span:last-child { padding: .06em .3em 0; }
`;

export function ModoChat({
  abierto,
  onCerrar,
  entradas,
  onEnviar,
  streaming,
  adjuntos,
  onFoto,
}: {
  abierto: boolean;
  onCerrar: () => void;
  entradas: Entrada[];
  onEnviar: (texto: string) => void;
  streaming: boolean;
  adjuntos: Attached[];
  onFoto: (f: File) => void;
}) {
  const [borrador, setBorrador] = useState("");
  const [montado, setMontado] = useState(false);
  const pie = useRef<HTMLDivElement>(null);
  const fichero = useRef<HTMLInputElement>(null);

  useEffect(() => setMontado(true), []);

  useEffect(() => {
    if (!abierto) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCerrar();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [abierto, onCerrar]);

  useEffect(() => {
    if (abierto) pie.current?.scrollIntoView({ behavior: "smooth" });
  }, [entradas, streaming, abierto]);

  if (!montado || !abierto) return null;

  const enviar = () => {
    const texto = borrador.trim();
    if (!texto || streaming) return;
    setBorrador("");
    onEnviar(texto);
  };

  return createPortal(
    <div className="chatmodo">
      <style dangerouslySetInnerHTML={{ __html: CSS }} />

      <div className="cm-cab">
        <span>Modo chat · misma memoria, sin instrumentos</span>
        <button type="button" onClick={onCerrar}>
          Volver al panel
        </button>
      </div>

      <div className="cm-hilo">
        <div className="cm-centro">
          {entradas.length === 0 && (
            <p className="cm-vacio">
              Pregúntale lo que quieras: un ejercicio de física, un problema de
              matemáticas, código que no compila. Puedes pegar una foto con
              <b> Ctrl+V</b> o pulsar Foto.
            </p>
          )}
          {entradas.map((e, i) => (
            <article className="cm-turno" data-de={e.from} key={i}>
              <span className="cm-quien">{e.from === "me" ? "tú" : "kairos"}</span>
              {e.from === "kairos" ? (
                <Render texto={e.said || (streaming && i === entradas.length - 1 ? "…" : "")} />
              ) : (
                <p>{e.said}</p>
              )}
            </article>
          ))}
          <div ref={pie} />
        </div>
      </div>

      <div className="cm-pie">
        {adjuntos.length > 0 && (
          <div className="cm-fotos">
            {adjuntos.map((a) => (
              <img key={a.id} src={a.url} alt={a.name} />
            ))}
          </div>
        )}
        <div className="cm-caja">
          <input
            ref={fichero}
            type="file"
            accept="image/*"
            capture="environment"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onFoto(f);
              e.target.value = "";
            }}
          />
          <button type="button" onClick={() => fichero.current?.click()}>
            Foto
          </button>
          <textarea
            rows={2}
            value={borrador}
            placeholder="Escribe tu pregunta"
            onChange={(e) => setBorrador(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                enviar();
              }
            }}
          />
          <button type="button" data-primary onClick={enviar} disabled={streaming || !borrador.trim()}>
            {streaming ? "Pensando" : "Enviar"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
