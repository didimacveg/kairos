"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

/**
 * Secuencia de arranque de KAIROS.
 *
 * TRANSICIÓN DESDE NEGRO: el fondo arranca ya en negro opaco y no cambia
 * hasta el 93% de la secuencia. Antes había un fotograma donde el modo negro
 * moría y este nacía, y el fondo asomaba — un parpadeo que rompía la entrada.
 * Ahora las dos capas son del mismo negro y el relevo es invisible.
 *
 * PLANTEAMIENTO (el que funcionaba): el núcleo late ARRIBA, no en el centro.
 * Cuando rompe, la onda desciende y deposita la marca. Nunca se solapan.
 *
 * NUEVO EN ESTA VERSIÓN, para dar más peso sin coste:
 *   - barrido horizontal que cruza en el instante de la rotura
 *   - retícula de fondo que aparece con la onda
 *   - tres anillos con velocidades y sentidos distintos
 *   - trazos radiales cortos alrededor de la marca
 *   - dos destellos secundarios que caen tras el principal
 *
 * Todo son divs y gradientes: cero filtros, solo `scale`, `rotate` y
 * `opacity`, que la GPU compone sin repintar.
 */

const PALABRA = "K.A.I.R.O.S";
const DURACION = 8600;
export const MOMENTO_SALUDO = 2800;

const DATOS_IZQ = [
  "núcleo ............ activo",
  "agentes ........... 17/17",
  "memoria ........... 2.4 GB",
  "enlace ............ cifrado",
];
const DATOS_DER = [
  "voz ............... nominal",
  "puente ............ en línea",
  "vigilancia ........ activa",
  "agenda ............ 3 avisos",
];

const FASES = [
  { t: 3.2, txt: "montando núcleo" },
  { t: 4.1, txt: "registrando agentes" },
  { t: 5.0, txt: "enlace cifrado" },
  { t: 5.9, txt: "sistema operativo" },
];

/** Trazos radiales alrededor de la marca. Se calculan una vez. */
const RADIOS = Array.from({ length: 32 }, (_, i) => ({
  angulo: (360 / 32) * i,
  largo: i % 4 === 0 ? 2.6 : 1.4,
  retardo: 2.6 + (i % 8) * 0.03,
}));

const CSS = `
.despertar { position: fixed; inset: 0; z-index: 99999; pointer-events: none;
  overflow: hidden; background: #000;
  animation: dVelo 8.6s linear forwards !important; }
@keyframes dVelo { 0%,93%{background:#000} 100%{background:rgba(5,7,13,0)} }

.despertar .c { position: absolute; left: 50%; will-change: scale, opacity; }

/* ====== retícula de fondo ============================================== */
.despertar .d-malla { position: absolute; inset: 0; opacity: 0;
  background-image:
    linear-gradient(rgba(126,230,255,.055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(126,230,255,.055) 1px, transparent 1px);
  background-size: 5vmin 5vmin;
  animation: dMalla 8.6s ease-out forwards !important; }
@keyframes dMalla { 0%,20%{opacity:0;scale:1.08} 30%{opacity:1;scale:1}
  86%{opacity:1} 100%{opacity:0} }

/* ====== ACTO 1 · el núcleo late arriba ================================= */
.despertar .d-nucleo { top: 31%; translate: -50% -50%;
  width: 1vmin; height: 1vmin; border-radius: 50%; background: #fff;
  box-shadow: 0 0 34px 7px rgba(126,230,255,.95);
  opacity: 0; scale: 0;
  animation: dNucleo 8.6s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dNucleo {
  0%{scale:0;opacity:0}
  3%{scale:1;opacity:1} 5.5%{scale:.42;opacity:.6}
  8%{scale:1.5;opacity:1} 10.5%{scale:.48;opacity:.68}
  13%{scale:2.2;opacity:1} 15.5%{scale:.55;opacity:.75}
  18%{scale:3.2;opacity:1} 20%{scale:.6;opacity:.8}
  22%{scale:4.5;opacity:1}
  26%{scale:.15;opacity:0}
  100%{opacity:0} }

/* Barrido horizontal en el instante de la rotura. */
.despertar .d-barrido { position: absolute; left: 0; right: 0; top: 31%;
  height: 1px; opacity: 0; transform-origin: center;
  background: linear-gradient(90deg, transparent,
    rgba(255,255,255,.9) 45%, rgba(126,230,255,.9) 55%, transparent);
  animation: dBarrido 1.1s cubic-bezier(.2,.9,.3,1) 1.85s forwards !important; }
@keyframes dBarrido { 0%{opacity:0;scale:0 1} 25%{opacity:1;scale:1 1}
  100%{opacity:0;scale:1 1;top:50%} }

/* La onda desciende y deposita la marca. */
.despertar .d-onda { top: 31%; translate: -50% -50%;
  width: 12vmin; height: 12vmin; border-radius: 50%;
  opacity: 0; scale: .1;
  animation: dOnda 1.7s cubic-bezier(.14,.85,.25,1) 1.9s forwards !important; }
@keyframes dOnda { 0%{scale:.1;opacity:0;top:31%} 12%{opacity:1}
  100%{scale:7.5;opacity:0;top:50%} }

/* Destellos secundarios que caen tras el principal. */
.despertar .d-chispa { top: 31%; translate: -50% -50%;
  width: .5vmin; height: .5vmin; border-radius: 50%;
  background: rgba(126,230,255,.95); opacity: 0;
  animation: dChispa 1.5s cubic-bezier(.2,.7,.3,1) forwards !important; }
@keyframes dChispa { 0%{opacity:0;scale:.5} 15%{opacity:1;scale:1}
  100%{opacity:0;scale:.2;top:50%} }

.despertar .d-luz { top: 50%; translate: -50% -50%;
  width: 72vmin; height: 72vmin; border-radius: 50%;
  background: radial-gradient(circle,
    rgba(126,230,255,.10) 0%, rgba(79,216,255,.05) 34%, transparent 64%);
  opacity: 0; scale: .3;
  animation: dLuz 8.6s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dLuz { 0%,21%{scale:.3;opacity:0} 31%{scale:1;opacity:1}
  88%{opacity:1} 100%{scale:1.1;opacity:0} }

/* ====== ACTO 2 · LA MARCA: un bloque, un instante ====================== */
.despertar .d-marca { top: 50%; translate: -50% -50%; z-index: 3;
  display: flex; flex-direction: column; align-items: center; gap: 1.05rem;
  opacity: 0;
  animation: dMarca 8.6s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dMarca {
  0%,29%{opacity:0;scale:1.16;filter:blur(10px)}
  34%{opacity:1;scale:1;filter:blur(0)}
  88%{opacity:1;scale:1;filter:blur(0)}
  100%{opacity:0;scale:1.04;filter:blur(3px)} }

.despertar .d-palabra { display: flex; gap: clamp(.14rem,.9vw,.62rem);
  white-space: nowrap; font-weight: 200; color: #fff;
  font-size: clamp(1.6rem,7vw,5rem); letter-spacing: .08em;
  text-shadow: 0 0 36px rgba(126,230,255,.65), 0 0 100px rgba(185,140,255,.25); }
.despertar .d-linea { height: 1px; width: min(28rem,64vw);
  background: linear-gradient(90deg, transparent,
    rgba(126,230,255,.85), rgba(185,140,255,.6), transparent); }
.despertar .d-sub { font-size: clamp(.42rem,.9vw,.58rem); letter-spacing: .55em;
  text-transform: uppercase; color: rgba(126,230,255,.8); white-space: nowrap; }

/* Trazos radiales alrededor de la marca. */
.despertar .d-radios { top: 50%; translate: -50% -50%;
  width: 26vmin; height: 26vmin; }
.despertar .d-radios i { position: absolute; top: 50%; left: 50%;
  height: 1px; background: rgba(126,230,255,.55);
  transform-origin: 0 50%; opacity: 0;
  animation: dRadio 5.4s ease-out forwards !important; }
@keyframes dRadio { 0%{opacity:0} 8%{opacity:1} 84%{opacity:1} 100%{opacity:0} }

/* ====== ACTO 3 · estructura =========================================== */
.despertar .d-rot { position: absolute; top: 50%; left: 50%;
  translate: -50% -50%; width: 50vmin; height: 50vmin;
  animation: rotA 48s linear infinite !important; }
.despertar .d-rot-b { width: 36vmin; height: 36vmin;
  animation: rotB 34s linear infinite !important; }
.despertar .d-rot-c { width: 62vmin; height: 62vmin;
  animation: rotC 70s linear infinite !important; }
@keyframes rotA { to{rotate:360deg} }
@keyframes rotB { to{rotate:-360deg} }
@keyframes rotC { to{rotate:360deg} }

.despertar .d-orbita { position: absolute; inset: 0; border-radius: 50%;
  opacity: 0; scale: .84;
  animation: dOrbita 8.6s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dOrbita { 0%,27%{scale:.84;opacity:0} 35%{scale:1;opacity:1}
  88%{opacity:1} 100%{scale:1.12;opacity:0} }

.despertar .d-datos { position: absolute; top: 50%; translate: 0 -50%;
  font-size: clamp(.42rem,.88vw,.58rem); letter-spacing: .16em;
  color: rgba(126,230,255,.7); line-height: 2.4; white-space: nowrap; }
.despertar .d-izq { left: 5vw; }
.despertar .d-der { right: 5vw; text-align: right; }
.despertar .d-datos div { opacity: 0;
  animation: dDato 4.8s cubic-bezier(.16,1,.3,1) forwards !important; }
@keyframes dDato { 0%{opacity:0;transform:translate3d(-12px,0,0)}
  12%{opacity:1;transform:none} 82%{opacity:1} 100%{opacity:0} }
.despertar .d-der div { animation-name: dDatoDer !important; }
@keyframes dDatoDer { 0%{opacity:0;transform:translate3d(12px,0,0)}
  12%{opacity:1;transform:none} 82%{opacity:1} 100%{opacity:0} }

/* ====== carga ========================================================= */
.despertar .d-carga { position: absolute; bottom: 16vh; left: 50%;
  translate: -50% 0; width: min(24rem,54vw); opacity: 0;
  animation: dCarga 5s ease-out 2.9s forwards !important; }
@keyframes dCarga { 0%{opacity:0} 9%{opacity:1} 80%{opacity:1} 100%{opacity:0} }
.despertar .d-barra { height: 2px; background: rgba(126,230,255,.13); }
.despertar .d-barra i { display: block; height: 100%; width: 100%;
  transform-origin: left; scale: 0 1;
  background: linear-gradient(90deg, rgba(126,230,255,.8), #fff);
  animation: dBarra 3.3s cubic-bezier(.5,.05,.3,1) 3s forwards !important; }
@keyframes dBarra { to{scale:1 1} }
.despertar .d-fase { margin-top: .5rem; position: relative; height: 1rem;
  font-size: clamp(.4rem,.8vw,.5rem); letter-spacing: .2em;
  text-transform: uppercase; color: rgba(126,230,255,.65); }
.despertar .d-fase span { position: absolute; left: 0; opacity: 0;
  animation: dFase .95s ease-out forwards !important; }
@keyframes dFase { 0%{opacity:0} 22%{opacity:1} 78%{opacity:1} 100%{opacity:0} }

/* ====== marco ========================================================= */
.despertar .d-esq { position: absolute; width: 3vmin; height: 3vmin;
  border: 1px solid rgba(126,230,255,.4); opacity: 0;
  animation: dMarco 5.8s ease-out 2.6s forwards !important; }
@keyframes dMarco { 0%{opacity:0;scale:1.35} 10%{opacity:1;scale:1}
  84%{opacity:1} 100%{opacity:0} }
.despertar .d-escala { position: absolute; top: 50%; translate: 0 -50%;
  display: flex; flex-direction: column; gap: 1.1vh; opacity: 0;
  animation: dMarco 5.8s ease-out 2.9s forwards !important; }
.despertar .d-escala i { display: block; height: 1px;
  background: rgba(126,230,255,.35); }
.despertar .d-nodo { position: absolute; top: 5vh; left: 50%;
  translate: -50% 0; font-size: clamp(.38rem,.76vw,.5rem);
  letter-spacing: .42em; text-transform: uppercase;
  color: rgba(126,230,255,.45); opacity: 0;
  animation: dMarco 5.8s ease-out 2.7s forwards !important; }
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
.deck[data-arrancando] .stage .sigil { animation-delay: 8.6s !important; }
.deck[data-arrancando] .strip        { animation-delay: 8.8s !important; }
.deck[data-arrancando] .log-rail     { animation-delay: 8.95s !important; }
.deck[data-arrancando] .instruments  { animation-delay: 9.05s !important; }
.deck[data-arrancando] .utterance    { animation-delay: 9.15s !important; }
.deck[data-arrancando] .console      { animation-delay: 9.25s !important; }
@keyframes dEntra { from{opacity:0;transform:translate3d(0,12px,0)} to{opacity:1;transform:none} }
`;

export function Despertar({
  activo,
  onMarca,
}: {
  activo: boolean;
  onMarca?: () => void;
}) {
  const [visible, setVisible] = useState(false);
  const [montado, setMontado] = useState(false);

  useEffect(() => setMontado(true), []);

  const onMarcaRef = useRef(onMarca);
  onMarcaRef.current = onMarca;

  useEffect(() => {
    if (!activo) return;
    setVisible(true);
    const deck = document.querySelector(".deck");
    deck?.setAttribute("data-arrancando", "");

    const aviso = setTimeout(() => onMarcaRef.current?.(), MOMENTO_SALUDO);
    const fin = setTimeout(() => {
      setVisible(false);
      deck?.removeAttribute("data-arrancando");
    }, DURACION + 400);

    return () => {
      clearTimeout(aviso);
      clearTimeout(fin);
    };
  }, [activo]);

  if (!montado) return null;

  return createPortal(
    <>
      <style dangerouslySetInnerHTML={{ __html: CSS + CSS_ENTRADA }} />
      {visible && (
        <div className="despertar" aria-hidden="true">
          <div className="d-malla" />
          <div className="c d-luz" />

          <div className="c d-nucleo" />
          <div className="d-barrido" />
          <div className="c d-onda" style={{ border: "2px solid rgba(126,230,255,.9)" }} />
          <div
            className="c d-onda"
            style={{ border: "1px solid rgba(185,140,255,.6)", animationDelay: "2.1s" }}
          />
          <div
            className="c d-onda"
            style={{ border: "1px solid rgba(255,255,255,.3)", animationDelay: "2.3s" }}
          />

          {[-9, -4, 4, 9].map((dx, i) => (
            <div
              key={i}
              className="c d-chispa"
              style={{ marginLeft: `${dx}vmin`, animationDelay: `${2.05 + i * 0.06}s` }}
            />
          ))}

          <div className="d-rot d-rot-c">
            <div className="d-orbita" style={{ border: "1px solid rgba(126,230,255,.18)" }} />
          </div>
          <div className="d-rot">
            <div className="d-orbita" style={{ border: "1px dashed rgba(126,230,255,.4)" }} />
          </div>
          <div className="d-rot d-rot-b">
            <div
              className="d-orbita"
              style={{ border: "1px solid rgba(185,140,255,.28)", animationDelay: ".2s" }}
            />
          </div>

          <div className="c d-radios">
            {RADIOS.map((r, i) => (
              <i
                key={i}
                style={{
                  width: `${r.largo}vmin`,
                  transform: `rotate(${r.angulo}deg) translateX(11vmin)`,
                  animationDelay: `${r.retardo}s`,
                }}
              />
            ))}
          </div>

          <div className="d-esq" style={{ top: "4vh", left: "4vw", borderRight: "none", borderBottom: "none" }} />
          <div className="d-esq" style={{ top: "4vh", right: "4vw", borderLeft: "none", borderBottom: "none" }} />
          <div className="d-esq" style={{ bottom: "4vh", left: "4vw", borderRight: "none", borderTop: "none" }} />
          <div className="d-esq" style={{ bottom: "4vh", right: "4vw", borderLeft: "none", borderTop: "none" }} />

          <span className="d-nodo">nodo kairos-home · 40.4168 n / 3.7038 o</span>

          <div className="d-escala" style={{ left: "2vw" }}>
            {Array.from({ length: 14 }, (_, i) => (
              <i key={i} style={{ width: i % 4 === 0 ? "1.3vw" : ".65vw" }} />
            ))}
          </div>
          <div className="d-escala" style={{ right: "2vw", alignItems: "flex-end" }}>
            {Array.from({ length: 14 }, (_, i) => (
              <i key={i} style={{ width: i % 4 === 0 ? "1.3vw" : ".65vw" }} />
            ))}
          </div>

          <div className="d-datos d-izq">
            {DATOS_IZQ.map((d, i) => (
              <div key={i} style={{ animationDelay: `${3.0 + i * 0.18}s` }}>{d}</div>
            ))}
          </div>
          <div className="d-datos d-der">
            {DATOS_DER.map((d, i) => (
              <div key={i} style={{ animationDelay: `${3.15 + i * 0.18}s` }}>{d}</div>
            ))}
          </div>

          <div className="c d-marca">
            <div className="d-palabra">{PALABRA}</div>
            <div className="d-linea" />
            <span className="d-sub">todos los sistemas en linea</span>
          </div>

          <div className="d-carga">
            <div className="d-barra"><i /></div>
            <div className="d-fase">
              {FASES.map((f, i) => (
                <span key={i} style={{ animationDelay: `${f.t}s` }}>{f.txt}</span>
              ))}
            </div>
          </div>
        </div>
      )}
    </>,
    document.body,
  );
}
