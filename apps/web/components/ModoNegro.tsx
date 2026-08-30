"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/**
 * Modo negro: la pantalla se apaga y espera.
 *
 * LA TRANSICIÓN, que es lo que fallaba: al lanzar la animación desde aquí,
 * el modo negro desaparecía de golpe y la secuencia empezaba con un salto.
 * Dos capas negras superpuestas, una muriendo y otra naciendo, producen un
 * parpadeo aunque las dos sean del mismo color: el navegador recompone
 * ambas y el fondo asoma un fotograma.
 *
 * Ahora hay una fase de SALIDA: el texto "en espera" se apaga, el anillo se
 * contrae, y solo cuando eso termina (450 ms) se avisa al padre para que
 * lance la secuencia. El negro nunca se interrumpe.
 */
const CSS = `
.modo-negro { position: fixed; inset: 0; z-index: 99998; background: #000;
  display: grid; place-items: center;
  animation: mnEntra .8s ease-out forwards !important; }
@keyframes mnEntra { from{opacity:0} to{opacity:1} }

/* Fase de salida: lo de dentro se apaga, el negro se queda. */
.modo-negro[data-saliendo] .mn-marco {
  animation: mnSale .45s cubic-bezier(.4,0,1,1) forwards !important; }
@keyframes mnSale { to{opacity:0;scale:.9} }
.modo-negro[data-saliendo] .mn-disparo { opacity: 0 !important; }

.modo-negro .mn-marco { position: relative; display: grid; place-items: center;
  padding: 2.4rem 4rem; will-change: opacity, scale; }
.modo-negro .mn-anillo { position: absolute; inset: 0; border: 1px solid #17414f;
  border-radius: 999px; opacity: .45; will-change: transform, opacity;
  animation: mnAnillo 4.5s ease-in-out infinite !important; }
@keyframes mnAnillo { 50%{transform:scale(1.05);opacity:.85} }

.modo-negro span { position: relative; font-size: clamp(.9rem, 2.4vw, 1.6rem);
  letter-spacing: .65em; text-transform: uppercase; white-space: nowrap;
  color: #4fd8ff; will-change: opacity;
  text-shadow: 0 0 24px rgba(79,216,255,.65);
  animation: mnLatido 4.5s ease-in-out infinite !important; }
@keyframes mnLatido { 0%,100%{opacity:.4} 50%{opacity:1} }

.modo-negro .mn-disparo { position: absolute; right: 1.6rem; bottom: 1.6rem;
  width: 2.2rem; height: 2.2rem; border-radius: 50%;
  border: 1px solid #12303a; background: transparent; cursor: pointer;
  color: #1d4d5c; font-size: .6rem; display: grid; place-items: center;
  padding: 0; pointer-events: auto;
  transition: border-color .3s, color .3s, opacity .3s; }
.modo-negro .mn-disparo:hover { border-color: #4fd8ff; color: #4fd8ff; }
`;

export function ModoNegro({
  activo,
  onSalir,
  onDespertar,
}: {
  activo: boolean;
  onSalir: () => void;
  onDespertar?: () => void;
}) {
  const [montado, setMontado] = useState(false);
  const [saliendo, setSaliendo] = useState(false);

  useEffect(() => setMontado(true), []);
  useEffect(() => {
    if (!activo) setSaliendo(false);
  }, [activo]);

  useEffect(() => {
    if (!activo) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onSalir();
      if ((e.key === " " || e.key === "Enter") && onDespertar) {
        e.preventDefault();
        lanzar();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  /** Apaga lo de dentro ANTES de lanzar. El negro nunca se interrumpe. */
  const lanzar = () => {
    if (saliendo || !onDespertar) return;
    setSaliendo(true);
    setTimeout(onDespertar, 450);
  };

  if (!montado || !activo) return null;

  return createPortal(
    <div className="modo-negro" data-saliendo={saliendo || undefined}>
      <style dangerouslySetInnerHTML={{ __html: CSS }} />
      <div className="mn-marco">
        <div className="mn-anillo" />
        <span>en espera</span>
      </div>
      {onDespertar && (
        <button
          type="button"
          className="mn-disparo"
          onClick={lanzar}
          title="Lanzar la secuencia (o pulsa Espacio)"
        >
          ▸
        </button>
      )}
    </div>,
    document.body,
  );
}
