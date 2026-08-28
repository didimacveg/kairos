"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/**
 * Secuencia de arranque.
 *
 * CUARTA VERSIÓN, esta vez buscando limpieza en vez de espectáculo.
 *
 * Las anteriores acumulaban elementos —chispas, rayos, rejillas, barridos—
 * pensando que más piezas era más impresionante. El resultado era ruido: a
 * esa velocidad no se distinguía nada y todo competía por la atención.
 *
 * Esta tiene SEIS elementos y una idea: un punto que se carga, rompe en un
 * anillo que se expande, y deja la marca. Nada más.
 *
 * Lo que la hace buena ahora es el TIEMPO, no la cantidad:
 *   - la carga late tres veces (tensión antes del suceso)
 *   - la rotura es instantánea (14% de la duración)
 *   - la marca aparece con calma y se queda (el 60% del tiempo total)
 *
 * Una animación de sistema debe leerse como una afirmación, no como fuegos
 * artificiales.
 */

const PALABRA = "K.A.I.R.O.S";
const DURACION = 2600;

const CSS = `
.despertar { position: fixed; inset: 0; z-index: 99999; pointer-events: none;
  display: grid; place-items: center; background: #05070d;
  animation: dVelo 2.6s cubic-bezier(.4,0,.2,1) forwards !important; }
@keyframes dVelo { 0%,62%{background:#05070d} 100%{background:rgba(5,7,13,0)} }

/* Un solo resplandor, muy suave. */
.despertar .d-luz { position: absolute; width: 70vmin; height: 70vmin;
  border-radius: 50%;
  background: radial-gradient(circle,
    rgba(255,255,255,.20) 0%, rgba(126,230,255,.14) 14%,
    rgba(79,216,255,.07) 32%, transparent 62%);
  opacity: 0; will-change: transform, opacity;
  animation: dLuz 2.6s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dLuz {
  0%{transform:scale(.04);opacity:0}
  9%{transform:scale(.09);opacity:.7}
  12%{transform:scale(.05);opacity:.5}
  15%{transform:scale(1);opacity:1}
  45%{transform:scale(.85);opacity:.5}
  100%{transform:scale(1.1);opacity:0} }

/* El punto que se carga y rompe. */
.despertar .d-punto { position: absolute; width: 1.2vmin; height: 1.2vmin;
  border-radius: 50%; background: #fff;
  box-shadow: 0 0 24px 4px rgba(126,230,255,.9);
  opacity: 0; will-change: transform, opacity;
  animation: dPunto 2.6s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dPunto {
  0%{transform:scale(0);opacity:0}
  6%{transform:scale(1);opacity:1}
  9%{transform:scale(.6);opacity:.8}
  12%{transform:scale(1.3);opacity:1}
  15%{transform:scale(28);opacity:0} }

/* Dos anillos finos. Uno rompe, el otro le sigue medio segundo despues. */
.despertar .d-anillo { position: absolute; border-radius: 50%;
  width: 18vmin; height: 18vmin; opacity: 0;
  will-change: transform, opacity;
  animation: dAnillo 2.1s cubic-bezier(.12,.9,.25,1) forwards !important; }
@keyframes dAnillo { 0%{transform:scale(.05);opacity:0} 10%{opacity:1}
  100%{transform:scale(5.5);opacity:0} }

/* La marca: sin rotaciones ni escalas exageradas. Aparece y se queda. */
.despertar .d-palabra { position: relative; display: flex; z-index: 2;
  gap: clamp(.12rem,.8vw,.55rem); }
.despertar .d-palabra span { display: inline-block; font-weight: 200; color: #fff;
  font-size: clamp(1.6rem,7vw,5rem); letter-spacing: .08em;
  will-change: transform, opacity;
  text-shadow: 0 0 32px rgba(126,230,255,.6);
  opacity: 0; animation: dLetra 2.2s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dLetra {
  0%{opacity:0;transform:translate3d(0,14px,0)}
  16%{opacity:1;transform:translate3d(0,0,0)}
  82%{opacity:1;transform:translate3d(0,0,0)}
  100%{opacity:0} }

/* Linea fina bajo la marca. */
.despertar .d-linea { position: absolute; top: 50%; left: 50%; z-index: 2;
  translate: -50% 3.6rem; height: 1px; width: min(26rem,64vw);
  transform-origin: center; transform: scaleX(0); will-change: transform, opacity;
  background: linear-gradient(90deg, transparent, rgba(126,230,255,.85), transparent);
  animation: dLinea 2.2s cubic-bezier(.16,1,.3,1) .55s forwards !important; }
@keyframes dLinea { 0%{transform:scaleX(0);opacity:0} 30%{transform:scaleX(1);opacity:1}
  80%{opacity:1} 100%{opacity:0} }

.despertar .d-pie { position: absolute; top: 50%; left: 50%; translate: -50% 4.7rem;
  font-size: clamp(.46rem,1vw,.64rem); letter-spacing: .55em; z-index: 2;
  text-transform: uppercase; color: rgba(126,230,255,.75); white-space: nowrap;
  opacity: 0; will-change: opacity;
  animation: dPie 2s ease-out .85s forwards !important; }
@keyframes dPie { 0%{opacity:0} 28%{opacity:1} 80%{opacity:1} 100%{opacity:0} }
`;

const CSS_ENTRADA = `
.deck[data-arrancando] .strip,
.deck[data-arrancando] .log-rail,
.deck[data-arrancando] .stage .sigil,
.deck[data-arrancando] .utterance,
.deck[data-arrancando] .console,
.deck[data-arrancando] .instruments {
  animation: dEntra .9s cubic-bezier(.16,1,.3,1) backwards !important;
  will-change: transform, opacity; }
.deck[data-arrancando] .stage .sigil { animation-delay: 1.7s !important; }
.deck[data-arrancando] .strip        { animation-delay: 1.9s !important; }
.deck[data-arrancando] .log-rail     { animation-delay: 2.0s !important; }
.deck[data-arrancando] .instruments  { animation-delay: 2.1s !important; }
.deck[data-arrancando] .utterance    { animation-delay: 2.2s !important; }
.deck[data-arrancando] .console      { animation-delay: 2.3s !important; }
@keyframes dEntra { from{opacity:0;transform:translate3d(0,10px,0)} to{opacity:1;transform:none} }
`;

export function Despertar({ activo }: { activo: boolean }) {
  const [visible, setVisible] = useState(false);
  const [montado, setMontado] = useState(false);

  useEffect(() => setMontado(true), []);

  useEffect(() => {
    if (!activo) return;
    setVisible(true);
    const deck = document.querySelector(".deck");
    deck?.setAttribute("data-arrancando", "");
    const id = setTimeout(() => {
      setVisible(false);
      deck?.removeAttribute("data-arrancando");
    }, DURACION + 700);
    return () => clearTimeout(id);
  }, [activo]);

  if (!montado) return null;

  return createPortal(
    <>
      <style dangerouslySetInnerHTML={{ __html: CSS + CSS_ENTRADA }} />
      {visible && (
        <div className="despertar" aria-hidden="true">
          <div className="d-luz" />
          <div
            className="d-anillo"
            style={{ border: "1.5px solid rgba(126,230,255,.9)", animationDelay: ".15s" }}
          />
          <div
            className="d-anillo"
            style={{ border: "1px solid rgba(185,140,255,.7)", animationDelay: ".32s" }}
          />
          <div className="d-punto" />
          <div className="d-palabra">
            {PALABRA.split("").map((letra, i) => (
              <span key={i} style={{ animationDelay: `${0.5 + i * 0.045}s` }}>
                {letra}
              </span>
            ))}
          </div>
          <div className="d-linea" />
          <span className="d-pie">sistemas en linea</span>
        </div>
      )}
    </>,
    document.body,
  );
}
