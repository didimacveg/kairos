"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/**
 * Modo negro: la pantalla se apaga de verdad.
 *
 * SECUENCIA DE BRILLO, pensada para la toma:
 *   modo negro   -> los dos monitores a 0
 *   al lanzar    -> los dos a 100, justo antes del destello
 *   +5 segundos  -> vuelven solos a los niveles de trabajo
 *
 * El salto de 0 a 100 en el instante de la rotura es lo que hace la toma:
 * la pantalla pasa de apagada a máximo en el mismo fotograma en que la
 * animación detona.
 *
 * La restauración la programa el puente, no la interfaz. Si el navegador se
 * cierra a mitad, el brillo vuelve igualmente.
 */
const CSS = `
.modo-negro { position: fixed; inset: 0; z-index: 99998; background: #000;
  display: grid; place-items: center;
  animation: mnEntra 1.2s ease-out forwards !important; }
@keyframes mnEntra { from{opacity:0} to{opacity:1} }

.modo-negro[data-saliendo] .mn-marco {
  animation: mnSale .4s cubic-bezier(.4,0,1,1) forwards !important; }
@keyframes mnSale { to{opacity:0;scale:.9} }
.modo-negro[data-saliendo] .mn-disparo { opacity: 0 !important; }

.modo-negro .mn-marco { position: relative; display: grid; place-items: center;
  padding: 2.4rem 4rem; will-change: opacity, scale; }
.modo-negro .mn-anillo { position: absolute; inset: 0; border: 1px solid #143a45;
  border-radius: 999px; opacity: .45; will-change: transform, opacity;
  animation: mnAnillo 4.5s ease-in-out infinite !important; }
@keyframes mnAnillo { 50%{transform:scale(1.05);opacity:.85} }

.modo-negro span { position: relative; font-size: clamp(.9rem, 2.4vw, 1.6rem);
  letter-spacing: .65em; text-transform: uppercase; white-space: nowrap;
  color: #4fd8ff; will-change: opacity;
  text-shadow: 0 0 24px rgba(79,216,255,.5);
  animation: mnLatido 4.5s ease-in-out infinite !important; }
@keyframes mnLatido { 0%,100%{opacity:.4} 50%{opacity:1} }

.modo-negro .mn-disparo { position: absolute; right: 1.6rem; bottom: 1.6rem;
  width: 2.2rem; height: 2.2rem; border-radius: 50%; z-index: 3;
  border: 1px solid #12303a; background: transparent; cursor: pointer;
  color: #1d4d5c; font-size: .6rem; display: grid; place-items: center;
  padding: 0; pointer-events: auto;
  transition: border-color .3s, color .3s, opacity .3s; }
.modo-negro .mn-disparo:hover { border-color: #4fd8ff; color: #4fd8ff; }
`;

async function brillo(nivel: number | null) {
  try {
    await fetch("/api/v1/device/brillo", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(nivel === null ? {} : { nivel }),
    });
  } catch {
    // Sin puente o sin DDC/CI. La toma se hace igual, con menos contraste.
  }
}

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
    if (!activo) {
      setSaliendo(false);
      return;
    }
    void brillo(0);
    // Salir por cualquier via restaura. Sin esto, cerrar la pestaña dejaría
    // los dos monitores apagados.
    return () => {
      void brillo(null);
    };
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

  const lanzar = () => {
    if (saliendo || !onDespertar) return;
    setSaliendo(true);
    // A 100 justo antes de que arranque la animación: el destello inicial
    // coincide con la pantalla subiendo al máximo. El puente devuelve el
    // brillo a los niveles de trabajo a los 5 segundos, solo.
    setTimeout(() => void brillo(100), 300);
    setTimeout(onDespertar, 420);
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
