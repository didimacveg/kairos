"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/**
 * Secuencia de arranque de KAIROS.
 *
 * RENDIMIENTO — por que esta escrita asi:
 *
 * La primera version iba a tirones. Causa: ~110 elementos SVG animandose a la
 * vez, cada uno con su propio `filter: drop-shadow`. Ese filtro se calcula en
 * CPU y se recalcula en CADA fotograma; con cien elementos filtrados el
 * navegador no llega a 60 fps y se ve a saltos.
 *
 * Correcciones aplicadas:
 *  - CERO filtros por elemento. El brillo lo da UNA capa difuminada de fondo
 *    y los propios gradientes.
 *  - Solo se animan `transform` y `opacity`, que la GPU compone sin repintar.
 *  - `will-change` declarado en los grupos que se mueven, para que el
 *    navegador los suba a su propia capa antes de empezar.
 *  - Menos elementos y mas grandes: 28 chispas en vez de 70. A esa velocidad
 *    nadie las cuenta, y el coste baja a la mitad.
 *  - Las chispas van en grupos con `translate` en el grupo, no en el circulo:
 *    mover un grupo es una operacion de composicion; mover cada circulo es
 *    recalcular geometria.
 *
 * Cuatro segundos en cuatro actos: carga, detonacion, identidad, entrega.
 */

const RAYOS = 20;
const CHISPAS = 28;
const PALABRA = "K.A.I.R.O.S";
const DURACION = 4000;

const CSS = `
.despertar { position: fixed; inset: 0; z-index: 99999; pointer-events: none;
  display: grid; place-items: center; overflow: hidden; background: #05070d;
  animation: dVelo 4s cubic-bezier(.22,1,.36,1) forwards !important; }
@keyframes dVelo { 0%,60%{background:#05070d} 100%{background:rgba(5,7,13,0)} }

.despertar .d-lienzo { position: absolute; top: 50%; left: 50%; translate: -50% -50%;
  width: min(150vw,150vh); height: min(150vw,150vh); overflow: visible;
  will-change: transform; }

/* El brillo global: UNA capa difuminada en vez de un filtro por elemento.
   Esto es lo que devolvio la fluidez. */
.despertar .d-halo { position: absolute; top: 50%; left: 50%; translate: -50% -50%;
  width: min(90vw,90vh); height: min(90vw,90vh); border-radius: 50%;
  background: radial-gradient(circle,
    rgba(255,255,255,.45) 0%, rgba(79,216,255,.32) 22%,
    rgba(166,120,255,.14) 48%, transparent 70%);
  filter: blur(48px); opacity: 0; will-change: transform, opacity;
  animation: dHalo 4s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dHalo { 0%{transform:scale(.05);opacity:0}
  13%{transform:scale(.25);opacity:.7} 17%{transform:scale(1.5);opacity:1}
  35%{transform:scale(1);opacity:.55} 70%{opacity:.3} 100%{transform:scale(1.8);opacity:0} }

/* --- acto 1: carga -------------------------------------------------------- */
.despertar .d-carga { transform-origin: 500px 500px; will-change: transform, opacity;
  animation: dCarga 4s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dCarga {
  0%{transform:scale(0);opacity:0} 4%{transform:scale(.3);opacity:1}
  8%{transform:scale(.18);opacity:.8} 11%{transform:scale(.36);opacity:1}
  14%{transform:scale(.22);opacity:.9}
  17%{transform:scale(3);opacity:1} 28%{transform:scale(1);opacity:.5}
  100%{transform:scale(3.6);opacity:0} }

/* --- acto 2: detonacion --------------------------------------------------- */
.despertar .d-choque { transform-origin: 500px 500px; opacity: 0;
  will-change: transform, opacity;
  animation: dChoque 2.6s cubic-bezier(.08,.92,.18,1) .58s forwards !important; }
@keyframes dChoque { 0%{transform:scale(.05);opacity:0} 5%{opacity:1}
  100%{transform:scale(16);opacity:0} }

.despertar .d-rayos { transform-origin: 500px 500px; opacity: 0;
  will-change: transform, opacity;
  animation: dRayos 2s cubic-bezier(.1,.94,.18,1) .58s forwards !important; }
@keyframes dRayos { 0%{transform:scale(.05) rotate(0deg);opacity:0}
  7%{opacity:1} 50%{opacity:.85} 100%{transform:scale(6) rotate(30deg);opacity:0} }

.despertar .d-anillo { transform-origin: 500px 500px; opacity: 0;
  will-change: transform, opacity;
  animation: dAnillo 3s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dAnillo { 0%{transform:scale(.08) rotate(0deg);opacity:0}
  9%{opacity:1} 65%{opacity:.7} 100%{transform:scale(10) rotate(240deg);opacity:0} }

.despertar .d-barrido { transform-origin: 500px 500px; opacity: 0;
  will-change: transform, opacity;
  animation: dBarrido 3.1s cubic-bezier(.2,1,.34,1) .5s forwards !important; }
@keyframes dBarrido { 0%{transform:rotate(0deg) scale(.15);opacity:0}
  10%{opacity:1} 78%{opacity:.45} 100%{transform:rotate(1620deg) scale(3.6);opacity:0} }

/* Las chispas se mueven POR GRUPO: el navegador lo compone sin recalcular. */
.despertar .d-chispa { opacity: 0; will-change: transform, opacity;
  animation: dChispa 2.8s cubic-bezier(.06,.94,.16,1) forwards !important; }
@keyframes dChispa { 0%{transform:translate(0,0) scale(.2);opacity:0}
  5%{opacity:1} 55%{opacity:.95}
  100%{transform:translate(var(--dx),var(--dy)) scale(.08);opacity:0} }

/* --- acto 3: identidad ---------------------------------------------------- */
.despertar .d-rejilla { opacity: 0; will-change: transform, opacity;
  animation: dRejilla 3.4s cubic-bezier(.16,1,.3,1) 1.05s forwards !important; }
@keyframes dRejilla { 0%{opacity:0;transform:scale(1.3)} 22%{opacity:.32;transform:scale(1)}
  68%{opacity:.22} 100%{opacity:0} }

.despertar .d-palabra { position: relative; display: flex; z-index: 2;
  gap: clamp(.15rem,1vw,.7rem); }
.despertar .d-palabra span { display: inline-block; font-weight: 200; color: #fff;
  font-size: clamp(1.7rem,7.5vw,5.4rem); letter-spacing: .06em;
  will-change: transform, opacity;
  text-shadow: 0 0 30px rgba(79,216,255,.95), 0 0 90px rgba(166,120,255,.65);
  opacity: 0; animation: dLetra 3.1s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dLetra {
  0%{opacity:0;transform:translate3d(0,64px,0) scale(.35)}
  17%{opacity:1;transform:translate3d(0,0,0) scale(1.16)}
  25%{transform:translate3d(0,0,0) scale(1)}
  74%{opacity:1} 100%{opacity:0;transform:translate3d(0,-26px,0) scale(1.12)} }

.despertar .d-linea { position: absolute; top: 50%; left: 50%; z-index: 2;
  translate: -50% 4rem; height: 2px; width: min(40rem,82vw);
  transform-origin: center; transform: scaleX(0); will-change: transform, opacity;
  background: linear-gradient(90deg, transparent, #4fd8ff, #fff, #a678ff, transparent);
  animation: dLinea 3.2s cubic-bezier(.16,1,.3,1) 1.2s forwards !important; }
@keyframes dLinea { 0%{transform:scaleX(0);opacity:0} 22%{transform:scaleX(1);opacity:1}
  70%{opacity:1} 100%{transform:scaleX(1);opacity:0} }

.despertar .d-pie { position: absolute; top: 50%; left: 50%; translate: -50% 5.4rem;
  font-size: clamp(.5rem,1.1vw,.72rem); letter-spacing: .5em; z-index: 2;
  text-transform: uppercase; color: #7ee6ff; white-space: nowrap; opacity: 0;
  will-change: opacity;
  animation: dPie 2.8s ease-out 1.55s forwards !important; }
@keyframes dPie { 0%{opacity:0} 22%{opacity:1} 72%{opacity:1} 100%{opacity:0} }
`;

const CSS_ENTRADA = `
.deck[data-arrancando] .strip,
.deck[data-arrancando] .log-rail,
.deck[data-arrancando] .stage .sigil,
.deck[data-arrancando] .utterance,
.deck[data-arrancando] .console,
.deck[data-arrancando] .instruments {
  animation: dEntra 1.4s cubic-bezier(.16,1,.3,1) backwards !important;
  will-change: transform, opacity; }
.deck[data-arrancando] .stage .sigil { animation-delay: 2.7s !important; }
.deck[data-arrancando] .strip        { animation-delay: 3.0s !important; }
.deck[data-arrancando] .log-rail     { animation-delay: 3.2s !important; }
.deck[data-arrancando] .instruments  { animation-delay: 3.3s !important; }
.deck[data-arrancando] .utterance    { animation-delay: 3.4s !important; }
.deck[data-arrancando] .console      { animation-delay: 3.5s !important; }
@keyframes dEntra { from{opacity:0;transform:translate3d(0,16px,0) scale(.985)}
  to{opacity:1;transform:none} }
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
    }, DURACION + 1100);
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
            <stop offset="20%" stopColor="#d6f5ff" stopOpacity="0.95" />
            <stop offset="48%" stopColor="#4fd8ff" stopOpacity="0.5" />
            <stop offset="76%" stopColor="#a678ff" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#a678ff" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="dg-choque">
            <stop offset="84%" stopColor="#4fd8ff" stopOpacity="0" />
            <stop offset="94%" stopColor="#ffffff" stopOpacity="0.9" />
            <stop offset="98%" stopColor="#a678ff" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#a678ff" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="dg-rayo" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="1" />
            <stop offset="30%" stopColor="#7ee6ff" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#a678ff" stopOpacity="0" />
          </linearGradient>
        </defs>

        <g className="d-rejilla" stroke="#4fd8ff" strokeWidth="0.7">
          {Array.from({ length: 15 }, (_, i) => (
            <line key={`v${i}`} x1={i * 71.4} y1="0" x2={i * 71.4} y2="1000" />
          ))}
          {Array.from({ length: 15 }, (_, i) => (
            <line key={`h${i}`} x1="0" y1={i * 71.4} x2="1000" y2={i * 71.4} />
          ))}
        </g>

        <circle className="d-choque" cx="500" cy="500" r="70" fill="url(#dg-choque)" />

        {/* Los rayos se animan como UN grupo, no uno a uno. */}
        <g className="d-rayos">
          {Array.from({ length: RAYOS }, (_, i) => (
            <rect
              key={i}
              x="495" y="190" width="10" height="310"
              fill="url(#dg-rayo)"
              transform={`rotate(${(360 / RAYOS) * i} 500 500)`}
            />
          ))}
        </g>

        {[0, 1, 2, 3, 4].map((i) => (
          <circle
            key={i}
            className="d-anillo"
            cx="500" cy="500" r={72 + i * 16}
            fill="none"
            stroke={i % 2 === 0 ? "#7ee6ff" : "#b98cff"}
            strokeWidth={5 - i * 0.7}
            strokeDasharray={i === 1 ? "44 24" : i === 3 ? "9 28" : undefined}
            style={{ animationDelay: `${0.56 + i * 0.09}s` }}
          />
        ))}

        <g className="d-barrido">
          <circle
            cx="500" cy="500" r="235" fill="none"
            stroke="#ffffff" strokeWidth="4.5"
            strokeDasharray="200 1276" strokeLinecap="round"
          />
          <circle
            cx="500" cy="500" r="188" fill="none"
            stroke="#b98cff" strokeWidth="3"
            strokeDasharray="100 1081" strokeLinecap="round"
          />
        </g>

        <circle className="d-carga" cx="500" cy="500" r="95" fill="url(#dg-carga)" />

        {Array.from({ length: CHISPAS }, (_, i) => {
          const ang = (360 / CHISPAS) * i + (i % 4) * 4;
          const dist = 320 + (i % 5) * 110;
          const rad = (ang * Math.PI) / 180;
          return (
            <g
              key={i}
              className="d-chispa"
              style={
                {
                  "--dx": `${Math.cos(rad) * dist}px`,
                  "--dy": `${Math.sin(rad) * dist}px`,
                  animationDelay: `${0.58 + (i % 7) * 0.04}s`,
                } as React.CSSProperties
              }
            >
              <circle
                cx="500" cy="500"
                r={i % 4 === 0 ? 6 : i % 2 === 0 ? 4 : 2.5}
                fill={i % 4 === 0 ? "#ffffff" : i % 3 === 0 ? "#b98cff" : "#7ee6ff"}
              />
            </g>
          );
        })}
      </svg>

      <div className="d-palabra">
        {PALABRA.split("").map((letra, i) => (
          <span key={i} style={{ animationDelay: `${1.32 + i * 0.07}s` }}>
            {letra}
          </span>
        ))}
      </div>

      <div className="d-linea" />
      <span className="d-pie">todos los sistemas en linea</span>
    </div>
  );
}
