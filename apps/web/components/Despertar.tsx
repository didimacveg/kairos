"use client";

import { useEffect, useState } from "react";

/**
 * El despertar de KAIROS.
 *
 * Se dispara SOLO con la frase exacta "Kairos, despierta". No con cada orden:
 * una animacion a pantalla completa cada vez que le pides algo cuesta
 * rendimiento y deja de significar nada. Un evento que ocurre siempre no es
 * un evento.
 *
 * Dura 2,6 s. Es lo unico de la interfaz que puede ocupar toda la pantalla.
 */

const RAYOS = 24;
const CHISPAS = 40;
const PALABRA = "KAIROS";

export function Despertar({ activo }: { activo: boolean }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!activo) return;
    setVisible(true);
    const id = setTimeout(() => setVisible(false), 2600);
    return () => clearTimeout(id);
  }, [activo]);

  if (!visible) return null;

  return (
    <div className="despertar" aria-hidden="true">
      <div className="d-flash" />

      <svg className="d-lienzo" viewBox="0 0 1000 1000" preserveAspectRatio="xMidYMid slice">
        <defs>
          <radialGradient id="d-nucleo">
            <stop offset="0%" stopColor="var(--bone)" stopOpacity="1" />
            <stop offset="30%" stopColor="var(--ice)" stopOpacity="0.9" />
            <stop offset="70%" stopColor="var(--brass)" stopOpacity="0.3" />
            <stop offset="100%" stopColor="var(--brass)" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="d-rayo" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--ice)" stopOpacity="0" />
            <stop offset="50%" stopColor="var(--ice)" stopOpacity="1" />
            <stop offset="100%" stopColor="var(--brass)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Detonacion central */}
        <circle className="d-nucleo" cx="500" cy="500" r="60" fill="url(#d-nucleo)" />

        {/* Rayos que salen disparados */}
        <g className="d-rayos">
          {Array.from({ length: RAYOS }, (_, i) => (
            <rect
              key={i}
              x="498" y="360" width="4" height="140"
              fill="url(#d-rayo)"
              transform={`rotate(${(360 / RAYOS) * i} 500 500)`}
              style={{ animationDelay: `${i * 0.012}s` }}
            />
          ))}
        </g>

        {/* Anillos concentricos expandiendose y girando */}
        {[0, 1, 2, 3].map((i) => (
          <circle
            key={i}
            className="d-anillo"
            cx="500" cy="500" r="90"
            fill="none"
            stroke={i % 2 === 0 ? "var(--ice)" : "var(--brass)"}
            strokeWidth={4 - i * 0.6}
            strokeDasharray={i === 1 ? "30 18" : i === 3 ? "6 22" : "none"}
            style={{ animationDelay: `${i * 0.11}s` }}
          />
        ))}

        {/* Barrido que gira rapido */}
        <g className="d-barrido">
          <circle
            cx="500" cy="500" r="200" fill="none"
            stroke="var(--ice)" strokeWidth="3"
            strokeDasharray="300 957" strokeLinecap="round" opacity="0.85"
          />
        </g>

        {/* Chispas que salen despedidas */}
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
                fill={i % 3 === 0 ? "var(--brass)" : "var(--ice)"}
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

      {/* La palabra se monta letra a letra */}
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
}
