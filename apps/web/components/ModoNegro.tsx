"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/**
 * Modo negro: la pantalla entera se apaga y espera.
 *
 * Existe para grabar: se dice "Kairos, modo negro", se prepara la cámara, y
 * al decir "Kairos, despierta" todo arranca desde el negro.
 *
 * El "en espera" respira despacio y con anillo alrededor: en una toma a
 * negro, un texto que late es lo que dice al espectador que el sistema está
 * vivo y esperando, no apagado.
 *
 * Escape siempre saca. Una pantalla en negro sin salida sería un fallo
 * disfrazado de función.
 */
const CSS = `
.modo-negro { position: fixed; inset: 0; z-index: 99998; background: #000;
  display: grid; place-items: center;
  animation: mnEntra 1s ease-out forwards !important; }
@keyframes mnEntra { from{opacity:0} to{opacity:1} }

.modo-negro .mn-marco { position: relative; display: grid; place-items: center;
  padding: 2.4rem 4rem; }

.modo-negro .mn-anillo { position: absolute; inset: 0; border: 1px solid #1b4a58;
  border-radius: 999px; opacity: .5; will-change: transform, opacity;
  animation: mnAnillo 4s ease-in-out infinite !important; }
@keyframes mnAnillo { 50%{transform:scale(1.06);opacity:.9} }

.modo-negro span { position: relative; font-size: clamp(.9rem, 2.4vw, 1.6rem);
  letter-spacing: .65em; text-transform: uppercase; white-space: nowrap;
  color: #4fd8ff; will-change: opacity;
  text-shadow: 0 0 24px rgba(79,216,255,.7), 0 0 70px rgba(79,216,255,.35);
  animation: mnLatido 4s ease-in-out infinite !important; }
@keyframes mnLatido { 0%,100%{opacity:.45} 50%{opacity:1} }
`;

export function ModoNegro({ activo, onSalir }: { activo: boolean; onSalir: () => void }) {
  const [montado, setMontado] = useState(false);
  useEffect(() => setMontado(true), []);

  useEffect(() => {
    if (!activo) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onSalir();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activo, onSalir]);

  if (!montado || !activo) return null;

  return createPortal(
    <div className="modo-negro">
      <style dangerouslySetInnerHTML={{ __html: CSS }} />
      <div className="mn-marco">
        <div className="mn-anillo" />
        <span>en espera</span>
      </div>
    </div>,
    document.body,
  );
}
