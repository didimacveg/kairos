"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/**
 * Secuencia de arranque de KAIROS.
 *
 * REESCRITA POR RENDIMIENTO. Lo que la hacía ir a tirones, en orden de coste:
 *
 * 1. `filter: blur(48px)` sobre un elemento de 90vw ANIMADO. Un desenfoque
 *    gaussiano de ese radio sobre esa superficie se recalcula entero en cada
 *    fotograma. Era, con diferencia, lo más caro de toda la escena.
 *    Sustituido por un gradiente radial estático: el degradado ya tiene el
 *    aspecto difuminado y cuesta cero.
 *
 * 2. Demasiados elementos animándose a la vez. 12 rayos y 16 chispas en vez
 *    de 20 y 28. A esta velocidad la diferencia no se ve; el coste sí.
 *
 * 3. `text-shadow` triple en cada letra, recalculado durante la animación.
 *    Reducido a uno.
 *
 * Ahora solo se animan `transform` y `opacity`, que la GPU compone sin
 * repintar nada. Ningún filtro, en ningún elemento.
 */

const RAYOS = 12;
const CHISPAS = 16;
const PALABRA = "K.A.I.R.O.S";
const DURACION = 3200;

const CSS = `
.despertar { position: fixed; inset: 0; z-index: 99999; pointer-events: none;
  display: grid; place-items: center; overflow: hidden; background: #05070d;
  animation: dVelo 3.2s cubic-bezier(.22,1,.36,1) forwards !important; }
@keyframes dVelo { 0%,55%{background:#05070d} 100%{background:rgba(5,7,13,0)} }

.despertar .d-lienzo { position: absolute; top: 50%; left: 50%; translate: -50% -50%;
  width: min(140vw,140vh); height: min(140vw,140vh); overflow: visible;
  contain: layout paint; }

/* El resplandor: gradiente radial ESTATICO, sin blur. El degradado ya se ve
   difuminado y cuesta cero; el filtro costaba mas que el resto junto. */
.despertar .d-halo { position: absolute; top: 50%; left: 50%; translate: -50% -50%;
  width: min(110vw,110vh); height: min(110vw,110vh); border-radius: 50%;
  background: radial-gradient(circle,
    rgba(255,255,255,.30) 0%, rgba(180,240,255,.22) 8%,
    rgba(79,216,255,.16) 20%, rgba(120,150,255,.09) 34%,
    rgba(166,120,255,.05) 50%, transparent 68%);
  opacity: 0; will-change: transform, opacity;
  animation: dHalo 3.2s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dHalo { 0%{transform:scale(.04);opacity:0}
  14%{transform:scale(.2);opacity:.85} 19%{transform:scale(1.35);opacity:1}
  38%{transform:scale(.95);opacity:.6} 70%{opacity:.28}
  100%{transform:scale(1.6);opacity:0} }

.despertar .d-carga { transform-origin: 500px 500px; will-change: transform, opacity;
  animation: dCarga 3.2s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dCarga {
  0%{transform:scale(0);opacity:0} 5%{transform:scale(.32);opacity:1}
  10%{transform:scale(.2);opacity:.8} 14%{transform:scale(.38);opacity:1}
  17%{transform:scale(.24);opacity:.9}
  21%{transform:scale(2.6);opacity:1} 34%{transform:scale(.9);opacity:.45}
  100%{transform:scale(3);opacity:0} }

.despertar .d-choque { transform-origin: 500px 500px; opacity: 0;
  will-change: transform, opacity;
  animation: dChoque 2.2s cubic-bezier(.08,.92,.18,1) .62s forwards !important; }
@keyframes dChoque { 0%{transform:scale(.05);opacity:0} 6%{opacity:1}
  100%{transform:scale(13);opacity:0} }

.despertar .d-rayos { transform-origin: 500px 500px; opacity: 0;
  will-change: transform, opacity;
  animation: dRayos 1.7s cubic-bezier(.1,.94,.18,1) .62s forwards !important; }
@keyframes dRayos { 0%{transform:scale(.06) rotate(0deg);opacity:0}
  8%{opacity:1} 45%{opacity:.8} 100%{transform:scale(5) rotate(26deg);opacity:0} }

.despertar .d-anillo { transform-origin: 500px 500px; opacity: 0;
  will-change: transform, opacity;
  animation: dAnillo 2.5s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dAnillo { 0%{transform:scale(.08) rotate(0deg);opacity:0}
  10%{opacity:1} 62%{opacity:.65} 100%{transform:scale(8) rotate(200deg);opacity:0} }

.despertar .d-barrido { transform-origin: 500px 500px; opacity: 0;
  will-change: transform, opacity;
  animation: dBarrido 2.6s cubic-bezier(.2,1,.34,1) .55s forwards !important; }
@keyframes dBarrido { 0%{transform:rotate(0deg) scale(.15);opacity:0}
  10%{opacity:1} 75%{opacity:.4} 100%{transform:rotate(1080deg) scale(3);opacity:0} }

.despertar .d-chispa { opacity: 0; will-change: transform, opacity;
  animation: dChispa 2.3s cubic-bezier(.06,.94,.16,1) forwards !important; }
@keyframes dChispa { 0%{transform:translate3d(0,0,0) scale(.2);opacity:0}
  6%{opacity:1} 50%{opacity:.9}
  100%{transform:translate3d(var(--dx),var(--dy),0) scale(.1);opacity:0} }

.despertar .d-rejilla { opacity: 0; will-change: transform, opacity;
  animation: dRejilla 2.8s cubic-bezier(.16,1,.3,1) .95s forwards !important; }
@keyframes dRejilla { 0%{opacity:0;transform:scale(1.25)} 22%{opacity:.28;transform:scale(1)}
  66%{opacity:.18} 100%{opacity:0} }

.despertar .d-palabra { position: relative; display: flex; z-index: 2;
  gap: clamp(.15rem,1vw,.7rem); }
.despertar .d-palabra span { display: inline-block; font-weight: 200; color: #fff;
  font-size: clamp(1.7rem,7.5vw,5.4rem); letter-spacing: .06em;
  will-change: transform, opacity;
  text-shadow: 0 0 40px rgba(120,225,255,.85);
  opacity: 0; animation: dLetra 2.5s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dLetra {
  0%{opacity:0;transform:translate3d(0,52px,0) scale(.45)}
  20%{opacity:1;transform:translate3d(0,0,0) scale(1.12)}
  28%{transform:translate3d(0,0,0) scale(1)}
  76%{opacity:1} 100%{opacity:0;transform:translate3d(0,-20px,0) scale(1.08)} }

.despertar .d-linea { position: absolute; top: 50%; left: 50%; z-index: 2;
  translate: -50% 4rem; height: 2px; width: min(40rem,82vw);
  transform-origin: center; transform: scaleX(0); will-change: transform, opacity;
  background: linear-gradient(90deg, transparent, #4fd8ff, #fff, #a678ff, transparent);
  animation: dLinea 2.6s cubic-bezier(.16,1,.3,1) 1.05s forwards !important; }
@keyframes dLinea { 0%{transform:scaleX(0);opacity:0} 24%{transform:scaleX(1);opacity:1}
  72%{opacity:1} 100%{transform:scaleX(1);opacity:0} }

.despertar .d-pie { position: absolute; top: 50%; left: 50%; translate: -50% 5.4rem;
  font-size: clamp(.5rem,1.1vw,.72rem); letter-spacing: .5em; z-index: 2;
  text-transform: uppercase; color: #7ee6ff; white-space: nowrap; opacity: 0;
  will-change: opacity;
  animation: dPie 2.3s ease-out 1.35s forwards !important; }
@keyframes dPie { 0%{opacity:0} 24%{opacity:1} 74%{opacity:1} 100%{opacity:0} }
`;

const CSS_ENTRADA = `
.deck[data-arrancando] .strip,
.deck[data-arrancando] .log-rail,
.deck[data-arrancando] .stage .sigil,
.deck[data-arrancando] .utterance,
.deck[data-arrancando] .console,
.deck[data-arrancando] .instruments {
  animation: dEntra 1.1s cubic-bezier(.16,1,.3,1) backwards !important;
  will-change: transform, opacity; }
.deck[data-arrancando] .stage .sigil { animation-delay: 2.1s !important; }
.deck[data-arrancando] .strip        { animation-delay: 2.35s !important; }
.deck[data-arrancando] .log-rail     { animation-delay: 2.5s !important; }
.deck[data-arrancando] .instruments  { animation-delay: 2.6s !important; }
.deck[data-arrancando] .utterance    { animation-delay: 2.7s !important; }
.deck[data-arrancando] .console      { animation-delay: 2.8s !important; }
@keyframes dEntra { from{opacity:0;transform:translate3d(0,14px,0)} to{opacity:1;transform:none} }
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
    }, DURACION + 900);
    return () => clearTimeout(id);
  }, [activo]);

  if (!montado) return null;

  return createPortal(
    <>
      <style dangerouslySetInnerHTML={{ __html: CSS + CSS_ENTRADA }} />
      {visible && <Escena />}
    </>,
    document.body,
  );
}

function Escena() {
  return (
    <div className="despertar" aria-hidden="true">
      <div className="d-halo" />

      <svg className="d-lienzo" viewBox="0 0 1000 1000" preserveAspectRatio="xMidYMid meet">
        <defs>
          <radialGradient id="dg-carga">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="1" />
            <stop offset="22%" stopColor="#d6f5ff" stopOpacity="0.9" />
            <stop offset="52%" stopColor="#4fd8ff" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#a678ff" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="dg-choque">
            <stop offset="86%" stopColor="#4fd8ff" stopOpacity="0" />
            <stop offset="95%" stopColor="#ffffff" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#a678ff" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="dg-rayo" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="1" />
            <stop offset="35%" stopColor="#7ee6ff" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#a678ff" stopOpacity="0" />
          </linearGradient>
        </defs>

        <g className="d-rejilla" stroke="#4fd8ff" strokeWidth="0.8">
          {Array.from({ length: 11 }, (_, i) => (
            <line key={`v${i}`} x1={i * 100} y1="0" x2={i * 100} y2="1000" />
          ))}
          {Array.from({ length: 11 }, (_, i) => (
            <line key={`h${i}`} x1="0" y1={i * 100} x2="1000" y2={i * 100} />
          ))}
        </g>

        <circle className="d-choque" cx="500" cy="500" r="70" fill="url(#dg-choque)" />

        <g className="d-rayos">
          {Array.from({ length: RAYOS }, (_, i) => (
            <rect
              key={i}
              x="493" y="180" width="14" height="320"
              fill="url(#dg-rayo)"
              transform={`rotate(${(360 / RAYOS) * i} 500 500)`}
            />
          ))}
        </g>

        {[0, 1, 2, 3].map((i) => (
          <circle
            key={i}
            className="d-anillo"
            cx="500" cy="500" r={76 + i * 22}
            fill="none"
            stroke={i % 2 === 0 ? "#7ee6ff" : "#b98cff"}
            strokeWidth={5 - i * 0.8}
            strokeDasharray={i === 1 ? "48 26" : i === 3 ? "10 30" : undefined}
            style={{ animationDelay: `${0.6 + i * 0.1}s` }}
          />
        ))}

        <g className="d-barrido">
          <circle
            cx="500" cy="500" r="230" fill="none"
            stroke="#ffffff" strokeWidth="5"
            strokeDasharray="210 1235" strokeLinecap="round"
          />
        </g>

        <circle className="d-carga" cx="500" cy="500" r="95" fill="url(#dg-carga)" />

        {Array.from({ length: CHISPAS }, (_, i) => {
          const ang = (360 / CHISPAS) * i + (i % 3) * 6;
          const dist = 330 + (i % 4) * 120;
          const rad = (ang * Math.PI) / 180;
          return (
            <g
              key={i}
              className="d-chispa"
              style={
                {
                  "--dx": `${Math.cos(rad) * dist}px`,
                  "--dy": `${Math.sin(rad) * dist}px`,
                  animationDelay: `${0.62 + (i % 5) * 0.045}s`,
                } as React.CSSProperties
              }
            >
              <circle
                cx="500" cy="500"
                r={i % 3 === 0 ? 7 : 4.5}
                fill={i % 3 === 0 ? "#ffffff" : i % 2 === 0 ? "#b98cff" : "#7ee6ff"}
              />
            </g>
          );
        })}
      </svg>

      <div className="d-palabra">
        {PALABRA.split("").map((letra, i) => (
          <span key={i} style={{ animationDelay: `${1.15 + i * 0.06}s` }}>
            {letra}
          </span>
        ))}
      </div>

      <div className="d-linea" />
      <span className="d-pie">todos los sistemas en linea</span>
    </div>
  );
}
