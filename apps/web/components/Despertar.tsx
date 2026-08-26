"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/**
 * Secuencia de arranque.
 *
 * TERCERA REESCRITURA, esta vez priorizando fluidez sobre espectáculo.
 *
 * Las dos anteriores animaban entre 60 y 110 elementos SVG a la vez. Aunque
 * solo se tocaran `transform` y `opacity`, cien capas compuestas por
 * fotograma es demasiado para un navegador que además está sirviendo la
 * aplicación entera.
 *
 * Esta versión anima **once elementos**: cuatro anillos, un núcleo, un
 * destello, la palabra, la línea y el pie. Ni un SVG con decenas de nodos,
 * ni chispas, ni rayos.
 *
 * Lo que hace que siga siendo llamativa no es la cantidad de piezas: es el
 * ritmo. La carga que late antes de romper, la escala que se pasa y vuelve,
 * y los paneles entrando escalonados detrás. Eso cuesta cero y es lo que se
 * nota en cámara.
 */

const PALABRA = "K.A.I.R.O.S";
const DURACION = 2800;

const CSS = `
.despertar { position: fixed; inset: 0; z-index: 99999; pointer-events: none;
  display: grid; place-items: center; background: #05070d;
  animation: dVelo 2.8s cubic-bezier(.22,1,.36,1) forwards !important; }
@keyframes dVelo { 0%,55%{background:#05070d} 100%{background:rgba(5,7,13,0)} }

/* El resplandor: un solo div con gradiente. Sin blur, sin SVG. */
.despertar .d-luz { position: absolute; width: min(120vmin,120vmin);
  height: min(120vmin,120vmin); border-radius: 50%;
  background: radial-gradient(circle,
    rgba(255,255,255,.34) 0%, rgba(150,235,255,.24) 9%,
    rgba(79,216,255,.15) 22%, rgba(140,140,255,.07) 40%,
    rgba(166,120,255,.03) 58%, transparent 72%);
  opacity: 0; will-change: transform, opacity;
  animation: dLuz 2.8s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dLuz {
  0%{transform:scale(.03);opacity:0}
  12%{transform:scale(.14);opacity:.9}
  16%{transform:scale(.09);opacity:.7}
  20%{transform:scale(1.25);opacity:1}
  42%{transform:scale(.9);opacity:.6}
  100%{transform:scale(1.5);opacity:0} }

/* Cuatro anillos. Divs con borde, no SVG. */
.despertar .d-anillo { position: absolute; border-radius: 50%;
  width: 26vmin; height: 26vmin; opacity: 0;
  will-change: transform, opacity;
  animation: dAnillo 2.4s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dAnillo { 0%{transform:scale(.08);opacity:0} 12%{opacity:1}
  60%{opacity:.6} 100%{transform:scale(4.2);opacity:0} }

.despertar .d-palabra { position: relative; display: flex; z-index: 2;
  gap: clamp(.15rem,1vw,.7rem); }
.despertar .d-palabra span { display: inline-block; font-weight: 200; color: #fff;
  font-size: clamp(1.7rem,7.5vw,5.4rem); letter-spacing: .06em;
  will-change: transform, opacity;
  text-shadow: 0 0 40px rgba(120,225,255,.9);
  opacity: 0; animation: dLetra 2.3s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dLetra {
  0%{opacity:0;transform:translate3d(0,44px,0) scale(.5)}
  22%{opacity:1;transform:translate3d(0,0,0) scale(1.1)}
  30%{transform:translate3d(0,0,0) scale(1)}
  78%{opacity:1} 100%{opacity:0;transform:translate3d(0,-16px,0) scale(1.06)} }

.despertar .d-linea { position: absolute; top: 50%; left: 50%; z-index: 2;
  translate: -50% 4rem; height: 2px; width: min(38rem,80vw);
  transform-origin: center; transform: scaleX(0); will-change: transform, opacity;
  background: linear-gradient(90deg, transparent, #4fd8ff, #fff, #a678ff, transparent);
  animation: dLinea 2.4s cubic-bezier(.16,1,.3,1) .9s forwards !important; }
@keyframes dLinea { 0%{transform:scaleX(0);opacity:0} 26%{transform:scaleX(1);opacity:1}
  74%{opacity:1} 100%{transform:scaleX(1);opacity:0} }

.despertar .d-pie { position: absolute; top: 50%; left: 50%; translate: -50% 5.4rem;
  font-size: clamp(.5rem,1.1vw,.72rem); letter-spacing: .5em; z-index: 2;
  text-transform: uppercase; color: #7ee6ff; white-space: nowrap; opacity: 0;
  will-change: opacity;
  animation: dPie 2.1s ease-out 1.2s forwards !important; }
@keyframes dPie { 0%{opacity:0} 26%{opacity:1} 74%{opacity:1} 100%{opacity:0} }
`;

const CSS_ENTRADA = `
.deck[data-arrancando] .strip,
.deck[data-arrancando] .log-rail,
.deck[data-arrancando] .stage .sigil,
.deck[data-arrancando] .utterance,
.deck[data-arrancando] .console,
.deck[data-arrancando] .instruments {
  animation: dEntra 1s cubic-bezier(.16,1,.3,1) backwards !important;
  will-change: transform, opacity; }
.deck[data-arrancando] .stage .sigil { animation-delay: 1.85s !important; }
.deck[data-arrancando] .strip        { animation-delay: 2.05s !important; }
.deck[data-arrancando] .log-rail     { animation-delay: 2.2s !important; }
.deck[data-arrancando] .instruments  { animation-delay: 2.3s !important; }
.deck[data-arrancando] .utterance    { animation-delay: 2.4s !important; }
.deck[data-arrancando] .console      { animation-delay: 2.5s !important; }
@keyframes dEntra { from{opacity:0;transform:translate3d(0,12px,0)} to{opacity:1;transform:none} }
`;

const ANILLOS = [
  { color: "#7ee6ff", grosor: 3, retardo: 0.18 },
  { color: "#b98cff", grosor: 2, retardo: 0.26 },
  { color: "#7ee6ff", grosor: 1.5, retardo: 0.34 },
  { color: "#ffffff", grosor: 1, retardo: 0.42 },
];

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
    }, DURACION + 800);
    return () => clearTimeout(id);
  }, [activo]);

  if (!montado) return null;

  return createPortal(
    <>
      <style dangerouslySetInnerHTML={{ __html: CSS + CSS_ENTRADA }} />
      {visible && (
        <div className="despertar" aria-hidden="true">
          <div className="d-luz" />
          {ANILLOS.map((a, i) => (
            <div
              key={i}
              className="d-anillo"
              style={{
                border: `${a.grosor}px solid ${a.color}`,
                animationDelay: `${a.retardo}s`,
              }}
            />
          ))}
          <div className="d-palabra">
            {PALABRA.split("").map((letra, i) => (
              <span key={i} style={{ animationDelay: `${0.85 + i * 0.055}s` }}>
                {letra}
              </span>
            ))}
          </div>
          <div className="d-linea" />
          <span className="d-pie">todos los sistemas en linea</span>
        </div>
      )}
    </>,
    document.body,
  );
}
