"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/**
 * Modo negro: la pantalla se apaga y espera.
 *
 * Existe para grabar: se apaga, se prepara la cámara, y "despierta" arranca
 * la secuencia desde el negro.
 *
 * El disparador discreto abajo a la derecha es para cuando grabas solo y no
 * puedes hablar: un punto casi invisible que lanza la animación. En cámara no
 * se distingue de un píxel muerto, y evita tener que decir la frase en voz
 * alta si estás narrando otra cosa.
 *
 * Escape siempre saca. Una pantalla en negro sin salida sería un fallo
 * disfrazado de función.
 */
const CSS = `
.modo-negro { position: fixed; inset: 0; z-index: 99998; background: #000;
  display: grid; place-items: center;
  animation: mnEntra .8s ease-out forwards !important; }
@keyframes mnEntra { from{opacity:0} to{opacity:1} }

.modo-negro .mn-marco { position: relative; display: grid; place-items: center;
  padding: 2.4rem 4rem; }
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

/* El disparador: casi invisible, pero ahi. */
.modo-negro .mn-disparo { position: absolute; right: 1.6rem; bottom: 1.6rem;
  width: 2.2rem; height: 2.2rem; border-radius: 50%;
  border: 1px solid #12303a; background: transparent; cursor: pointer;
  color: #1d4d5c; font-size: .5rem; letter-spacing: .1em;
  display: grid; place-items: center; padding: 0;
  transition: border-color .3s, color .3s; }
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
  useEffect(() => setMontado(true), []);

  useEffect(() => {
    if (!activo) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onSalir();
      // Espacio o Enter lanzan la secuencia sin tener que hablar: útil
      // cuando grabas solo y estás narrando otra cosa.
      if ((e.key === " " || e.key === "Enter") && onDespertar) {
        e.preventDefault();
        onDespertar();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activo, onSalir, onDespertar]);

  if (!montado || !activo) return null;

  return createPortal(
    <div className="modo-negro">
      <style dangerouslySetInnerHTML={{ __html: CSS }} />
      <div className="mn-marco">
        <div className="mn-anillo" />
        <span>en espera</span>
      </div>
      {onDespertar && (
        <button
          type="button"
          className="mn-disparo"
          onClick={onDespertar}
          title="Lanzar la secuencia (o pulsa Espacio)"
        >
          ▸
        </button>
      )}
    </div>,
    document.body,
  );
}
