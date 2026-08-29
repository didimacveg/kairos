"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/**
 * Secuencia de arranque.
 *
 * EL FALLO DE CENTRADO, por fin entendido: el contenedor usaba
 * `display: grid; place-items: center`, pero los hijos con
 * `position: absolute` NO los coloca el grid — los coloca el bloque
 * contenedor, desde la esquina superior izquierda. Por eso todo se iba
 * arriba a la izquierda y crecía en diagonal.
 *
 * Solución: cada elemento absoluto se centra él mismo con
 * `top:50%; left:50%; translate:-50% -50%`, y las animaciones de escala usan
 * `scale()` en la propiedad `scale`, que se compone con el `translate` sin
 * anularlo. Mezclar `transform: translate(...) scale(...)` con keyframes que
 * solo tocan `transform` era lo que borraba el centrado a mitad de animación.
 *
 * DURACIÓN: 5,2 s. Cinco actos con tiempo para respirar entre ellos. Las
 * versiones cortas se sentían apresuradas: una secuencia de arranque necesita
 * pausas para leerse como algo que ocurre, no como un parpadeo.
 *
 * RENDIMIENTO: nueve elementos, cero filtros, solo `scale`, `rotate` y
 * `opacity` — todo compuesto por GPU.
 */

const PALABRA = "K.A.I.R.O.S";
const DURACION = 5200;

const CSS = `
.despertar { position: fixed; inset: 0; z-index: 99999; pointer-events: none;
  overflow: hidden; background: #05070d;
  animation: dVelo 5.2s cubic-bezier(.4,0,.2,1) forwards !important; }
@keyframes dVelo { 0%,78%{background:#05070d} 100%{background:rgba(5,7,13,0)} }

/* TODO elemento absoluto se centra a si mismo. El grid no lo hace. */
.despertar .c { position: absolute; top: 50%; left: 50%;
  translate: -50% -50%; will-change: scale, opacity; }

/* --- acto 1 (0-1.1s): la carga --------------------------------------- */
.despertar .d-punto { width: 1vmin; height: 1vmin; border-radius: 50%;
  background: #fff; box-shadow: 0 0 20px 3px rgba(126,230,255,.85);
  opacity: 0; scale: 0;
  animation: dPunto 5.2s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dPunto {
  0%{scale:0;opacity:0}
  4%{scale:1;opacity:1}
  7%{scale:.55;opacity:.75}
  10%{scale:1.25;opacity:1}
  13%{scale:.6;opacity:.8}
  16%{scale:1.5;opacity:1}
  19%{scale:.7;opacity:.85}
  /* la rotura */
  23%{scale:34;opacity:0} }

/* --- acto 2 (1.1-2.2s): la onda -------------------------------------- */
.despertar .d-luz { width: 72vmin; height: 72vmin; border-radius: 50%;
  background: radial-gradient(circle,
    rgba(255,255,255,.22) 0%, rgba(126,230,255,.15) 15%,
    rgba(79,216,255,.08) 34%, rgba(185,140,255,.03) 52%, transparent 66%);
  opacity: 0; scale: .04;
  animation: dLuz 5.2s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dLuz {
  0%{scale:.04;opacity:0}
  16%{scale:.1;opacity:.5}
  22%{scale:1;opacity:1}
  40%{scale:.85;opacity:.55}
  78%{opacity:.28}
  100%{scale:1.15;opacity:0} }

.despertar .d-anillo { width: 16vmin; height: 16vmin; border-radius: 50%;
  opacity: 0; scale: .05;
  animation: dAnillo 3.6s cubic-bezier(.1,.9,.22,1) forwards !important; }
@keyframes dAnillo { 0%{scale:.05;opacity:0} 8%{opacity:1}
  55%{opacity:.55} 100%{scale:7;opacity:0} }

/* --- acto 3 (2.2-3s): el disco que gira ------------------------------- */
.despertar .d-arco { width: 40vmin; height: 40vmin; border-radius: 50%;
  border: 1px solid transparent;
  border-top-color: rgba(126,230,255,.9);
  border-right-color: rgba(185,140,255,.45);
  opacity: 0; scale: .5;
  animation: dArco 3.4s cubic-bezier(.22,1,.36,1) 1.15s forwards !important; }
@keyframes dArco {
  0%{scale:.5;rotate:0deg;opacity:0}
  14%{opacity:1}
  70%{opacity:.5}
  100%{scale:1.25;rotate:540deg;opacity:0} }

/* --- acto 4 (2.4-4.4s): la marca -------------------------------------- */
.despertar .d-palabra { display: flex; gap: clamp(.12rem,.8vw,.55rem);
  z-index: 2; white-space: nowrap; }
.despertar .d-palabra span { display: inline-block; font-weight: 200; color: #fff;
  font-size: clamp(1.6rem,7vw,5rem); letter-spacing: .08em;
  will-change: transform, opacity;
  text-shadow: 0 0 34px rgba(126,230,255,.65), 0 0 90px rgba(185,140,255,.3);
  opacity: 0; animation: dLetra 3.4s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dLetra {
  0%{opacity:0;transform:translate3d(0,18px,0)}
  14%{opacity:1;transform:translate3d(0,0,0)}
  84%{opacity:1;transform:translate3d(0,0,0)}
  100%{opacity:0;transform:translate3d(0,-8px,0)} }

.despertar .d-linea { z-index: 2; height: 1px; width: min(28rem,66vw);
  translate: -50% calc(-50% + 3.8rem); scale: 0 1;
  transform-origin: center;
  background: linear-gradient(90deg, transparent,
    rgba(126,230,255,.9), rgba(185,140,255,.7), transparent);
  animation: dLinea 3.2s cubic-bezier(.16,1,.3,1) 2.5s forwards !important; }
@keyframes dLinea { 0%{scale:0 1;opacity:0} 22%{scale:1 1;opacity:1}
  82%{opacity:1} 100%{scale:1 1;opacity:0} }

/* --- acto 5 (4-5.2s): la confirmacion --------------------------------- */
.despertar .d-pie { z-index: 2; translate: -50% calc(-50% + 5rem);
  font-size: clamp(.46rem,1vw,.64rem); letter-spacing: .55em;
  text-transform: uppercase; color: rgba(126,230,255,.8); white-space: nowrap;
  opacity: 0; will-change: opacity;
  animation: dPie 2.6s ease-out 2.9s forwards !important; }
@keyframes dPie { 0%{opacity:0} 22%{opacity:1} 78%{opacity:1} 100%{opacity:0} }
`;

const CSS_ENTRADA = `
.deck[data-arrancando] .strip,
.deck[data-arrancando] .log-rail,
.deck[data-arrancando] .stage .sigil,
.deck[data-arrancando] .utterance,
.deck[data-arrancando] .console,
.deck[data-arrancando] .instruments {
  animation: dEntra 1.2s cubic-bezier(.16,1,.3,1) backwards !important;
  will-change: transform, opacity; }
.deck[data-arrancando] .stage .sigil { animation-delay: 4.1s !important; }
.deck[data-arrancando] .strip        { animation-delay: 4.35s !important; }
.deck[data-arrancando] .log-rail     { animation-delay: 4.5s !important; }
.deck[data-arrancando] .instruments  { animation-delay: 4.6s !important; }
.deck[data-arrancando] .utterance    { animation-delay: 4.7s !important; }
.deck[data-arrancando] .console      { animation-delay: 4.8s !important; }
@keyframes dEntra { from{opacity:0;transform:translate3d(0,12px,0)} to{opacity:1;transform:none} }
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
      {visible && (
        <div className="despertar" aria-hidden="true">
          <div className="c d-luz" />
          <div
            className="c d-anillo"
            style={{ border: "1.5px solid rgba(126,230,255,.9)", animationDelay: "1.1s" }}
          />
          <div
            className="c d-anillo"
            style={{ border: "1px solid rgba(185,140,255,.65)", animationDelay: "1.35s" }}
          />
          <div
            className="c d-anillo"
            style={{ border: "1px solid rgba(255,255,255,.35)", animationDelay: "1.6s" }}
          />
          <div className="c d-arco" />
          <div className="c d-punto" />
          <div className="c d-palabra">
            {PALABRA.split("").map((letra, i) => (
              <span key={i} style={{ animationDelay: `${2.35 + i * 0.06}s` }}>
                {letra}
              </span>
            ))}
          </div>
          <div className="c d-linea" />
          <span className="c d-pie">todos los sistemas en linea</span>
        </div>
      )}
    </>,
    document.body,
  );
}
