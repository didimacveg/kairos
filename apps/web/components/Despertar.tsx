"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/**
 * El despertar de KAIROS.
 *
 * Solo con "Kairos, despierta". No con cada orden: una animación a pantalla
 * completa cada vez que le pides algo cuesta rendimiento y deja de significar
 * nada. Un evento que ocurre siempre no es un evento.
 *
 * TRES DECISIONES, todas aprendidas a base de que no se viera:
 *
 * 1. **Portal a document.body.** Estaba dentro del contenedor principal, y
 *    basta que un ancestro tenga `transform` o `filter` para que
 *    `position: fixed` deje de referirse a la ventana.
 *
 * 2. **Lienzo cuadrado centrado.** Con `inset: 0` y un viewBox cuadrado en
 *    una pantalla ancha, el centro (500,500) acababa cerca del borde
 *    inferior. La animación se reproducía entera fuera de la vista.
 *
 * 3. **Estilos propios.** globals.css crece por añadidos automáticos y ya se
 *    ha roto varias veces. Un componente que lleva sus estilos dentro no
 *    puede quedarse sin ellos.
 */

const RAYOS = 24;
const CHISPAS = 40;
const PALABRA = "KAIROS";

const CSS = `
.despertar { position: fixed; inset: 0; z-index: 9999; pointer-events: none;
  display: grid; place-items: center; overflow: hidden; }
.d-lienzo { position: absolute; top: 50%; left: 50%; translate: -50% -50%;
  width: min(100vw, 100vh); height: min(100vw, 100vh); overflow: visible; }
.d-flash { position: absolute; inset: 0;
  background:
    radial-gradient(circle at center, rgba(230,236,242,0.22) 0%, transparent 22%),
    radial-gradient(circle at center, rgba(79,216,255,0.18) 0%, transparent 55%),
    radial-gradient(circle at center, rgba(166,120,255,0.10) 0%, transparent 75%);
  animation: dFlash 2.6s cubic-bezier(0.16,1,0.3,1) forwards; }
@keyframes dFlash { 0%{opacity:0} 4%{opacity:1} 30%{opacity:.5} 100%{opacity:0} }
.d-nucleo { transform-origin: 500px 500px;
  animation: dNucleo 2.6s cubic-bezier(0.16,1,0.3,1) forwards; }
@keyframes dNucleo { 0%{transform:scale(0);opacity:0} 5%{transform:scale(1.6);opacity:1}
  18%{transform:scale(.7);opacity:.9} 60%{transform:scale(1.1);opacity:.5}
  100%{transform:scale(2.6);opacity:0} }
.d-rayos rect { opacity: 0; animation: dRayo 1.5s cubic-bezier(0.16,1,0.3,1) forwards; }
@keyframes dRayo { 0%{opacity:0} 10%{opacity:1} 100%{opacity:0} }
.d-anillo { transform-origin: 500px 500px; opacity: 0;
  animation: dAnillo 2.2s cubic-bezier(0.16,1,0.3,1) forwards;
  filter: drop-shadow(0 0 14px rgba(79,216,255,.55)); }
@keyframes dAnillo { 0%{transform:scale(.15) rotate(0deg);opacity:0} 12%{opacity:1}
  100%{transform:scale(7) rotate(150deg);opacity:0} }
.d-barrido { transform-origin: 500px 500px; opacity: 0;
  animation: dBarrido 2.2s cubic-bezier(0.22,1,0.36,1) forwards;
  filter: drop-shadow(0 0 20px rgba(79,216,255,.55)); }
@keyframes dBarrido { 0%{transform:rotate(0deg) scale(.4);opacity:0} 15%{opacity:1}
  75%{opacity:.7} 100%{transform:rotate(900deg) scale(2.4);opacity:0} }
.d-chispas circle { opacity: 0;
  animation: dChispa 1.9s cubic-bezier(0.12,.9,.25,1) forwards;
  filter: drop-shadow(0 0 8px rgba(79,216,255,.55)); }
@keyframes dChispa { 0%{transform:translate(0,0) scale(.4);opacity:0} 8%{opacity:1}
  70%{opacity:.8} 100%{transform:translate(var(--dx),var(--dy)) scale(.2);opacity:0} }
.d-palabra { position: relative; display: flex; gap: clamp(.5rem,2.2vw,1.6rem); }
.d-palabra span { display: inline-block; font-weight: 200; color: #e6ecf2;
  font-size: clamp(2rem,9vw,6rem);
  text-shadow: 0 0 30px rgba(79,216,255,.55), 0 0 80px rgba(166,120,255,.5);
  opacity: 0; animation: dLetra 2.05s cubic-bezier(0.16,1,0.3,1) forwards; }
@keyframes dLetra { 0%{opacity:0;transform:translateY(26px) scale(.7);filter:blur(10px)}
  22%{opacity:1;transform:translateY(0) scale(1);filter:blur(0)}
  70%{opacity:1} 100%{opacity:0;transform:translateY(-10px) scale(1.06);filter:blur(3px)} }
.d-linea { position: absolute; top: 50%; left: 50%; translate: -50% 3.4rem;
  height: 1px; width: 0;
  background: linear-gradient(90deg, transparent, #4fd8ff, #a678ff, transparent);
  animation: dLinea 2.3s cubic-bezier(0.16,1,0.3,1) .75s forwards; }
@keyframes dLinea { 0%{width:0;opacity:0} 30%{width:min(30rem,70vw);opacity:1}
  75%{opacity:1} 100%{width:min(30rem,70vw);opacity:0} }
.d-pie { position: absolute; top: 50%; left: 50%; translate: -50% 4.6rem;
  font-size: .6rem; letter-spacing: .45em; text-transform: uppercase;
  color: #4fd8ff; opacity: 0; animation: dPie 2.2s ease-out 1s forwards; }
@keyframes dPie { 0%{opacity:0;letter-spacing:.9em} 25%{opacity:.9;letter-spacing:.45em}
  70%{opacity:.9} 100%{opacity:0} }
`;

export function Despertar({ activo }: { activo: boolean }) {
  const [visible, setVisible] = useState(false);
  const [montado, setMontado] = useState(false);

  useEffect(() => setMontado(true), []);

  useEffect(() => {
    if (!activo) return;
    setVisible(true);
    const id = setTimeout(() => setVisible(false), 2600);
    return () => clearTimeout(id);
  }, [activo]);

  if (!montado || !visible) return null;

  const escena = (
    <div className="despertar" aria-hidden="true">
      <style dangerouslySetInnerHTML={{ __html: CSS }} />
      <div className="d-flash" />

      <svg className="d-lienzo" viewBox="0 0 1000 1000" preserveAspectRatio="xMidYMid meet">
        <defs>
          <radialGradient id="d-nucleo-grad">
            <stop offset="0%" stopColor="#e6ecf2" stopOpacity="1" />
            <stop offset="30%" stopColor="#4fd8ff" stopOpacity="0.9" />
            <stop offset="70%" stopColor="#a678ff" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#a678ff" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="d-rayo-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4fd8ff" stopOpacity="0" />
            <stop offset="50%" stopColor="#4fd8ff" stopOpacity="1" />
            <stop offset="100%" stopColor="#a678ff" stopOpacity="0" />
          </linearGradient>
        </defs>

        <circle className="d-nucleo" cx="500" cy="500" r="60" fill="url(#d-nucleo-grad)" />

        <g className="d-rayos">
          {Array.from({ length: RAYOS }, (_, i) => (
            <rect
              key={i}
              x="497" y="300" width="6" height="200"
              fill="url(#d-rayo-grad)"
              transform={`rotate(${(360 / RAYOS) * i} 500 500)`}
              style={{ animationDelay: `${i * 0.012}s` }}
            />
          ))}
        </g>

        {[0, 1, 2, 3].map((i) => (
          <circle
            key={i}
            className="d-anillo"
            cx="500" cy="500" r="90"
            fill="none"
            stroke={i % 2 === 0 ? "#4fd8ff" : "#a678ff"}
            strokeWidth={4 - i * 0.6}
            strokeDasharray={i === 1 ? "30 18" : i === 3 ? "6 22" : undefined}
            style={{ animationDelay: `${i * 0.11}s` }}
          />
        ))}

        <g className="d-barrido">
          <circle
            cx="500" cy="500" r="200" fill="none"
            stroke="#4fd8ff" strokeWidth="3"
            strokeDasharray="300 957" strokeLinecap="round" opacity="0.85"
          />
        </g>

        <g className="d-chispas">
          {Array.from({ length: CHISPAS }, (_, i) => {
            const ang = (360 / CHISPAS) * i + (i % 3) * 4;
            const dist = 260 + (i % 5) * 70;
            const rad = (ang * Math.PI) / 180;
            return (
              <circle
                key={i}
                cx="500" cy="500"
                r={i % 4 === 0 ? 4 : 2.2}
                fill={i % 3 === 0 ? "#a678ff" : "#4fd8ff"}
                style={
                  {
                    "--dx": `${Math.cos(rad) * dist}px`,
                    "--dy": `${Math.sin(rad) * dist}px`,
                    animationDelay: `${0.05 + (i % 7) * 0.03}s`,
                  } as React.CSSProperties
                }
              />
            );
          })}
        </g>
      </svg>

      <div className="d-palabra">
        {PALABRA.split("").map((letra, i) => (
          <span key={i} style={{ animationDelay: `${0.55 + i * 0.07}s` }}>
            {letra}
          </span>
        ))}
      </div>

      <div className="d-linea" />
      <span className="d-pie">sistemas en linea</span>
    </div>
  );

  return createPortal(escena, document.body);
}
