"use client";

import type { Health } from "@/lib/api";

/**
 * Sigilo K.A.I.R.O.S — el núcleo visible del sistema.
 *
 * Es lo primero que ves al entrar y lo que queda cuando no hay conversación.
 * Los anillos no son decoración: cada uno codifica un estado real.
 *
 *   exterior   agentes vivos — el arco cubre la fracción que responde
 *   medio      gira solo mientras el modelo genera
 *   interior   pulsa cuando el micrófono está escuchando
 *   núcleo     rojo si hay salida a Internet permitida
 *
 * Si el sistema está parado, el sigilo está quieto. Un adorno que gira siempre
 * no dice nada; uno que gira cuando la máquina piensa te dice que piensa.
 */
export function Sigil({
  health,
  busy,
  listening,
  compact,
}: {
  health: Health | null;
  busy: boolean;
  listening: boolean;
  compact?: boolean;
}) {
  const total = health?.agents.length ?? 0;
  const up = health?.agents.filter((a) => a.status === "ok").length ?? 0;
  const ratio = total > 0 ? up / total : 0;

  const R_OUT = 92;
  const circumference = 2 * Math.PI * R_OUT;
  const arc = circumference * ratio;

  return (
    <div className="sigil" data-compact={compact || undefined} data-busy={busy || undefined}>
      <svg viewBox="0 0 240 240" role="img" aria-label="Estado de KAIROS">
        <defs>
          <radialGradient id="core-glow">
            <stop offset="0%" stopColor="var(--brass)" stopOpacity="0.5" />
            <stop offset="70%" stopColor="var(--brass)" stopOpacity="0.06" />
            <stop offset="100%" stopColor="var(--brass)" stopOpacity="0" />
          </radialGradient>
        </defs>

        <circle cx="120" cy="120" r="86" fill="url(#core-glow)" />

        {/* Exterior — agentes vivos */}
        <circle
          cx="120" cy="120" r={R_OUT}
          fill="none" stroke="var(--rule-bright)" strokeWidth="1"
        />
        <circle
          className="ring-agents"
          cx="120" cy="120" r={R_OUT}
          fill="none" stroke="var(--ice)" strokeWidth="2" strokeLinecap="butt"
          strokeDasharray={`${arc} ${circumference}`}
          transform="rotate(-90 120 120)"
        />

        {/* Medio — gira mientras genera */}
        <g className="ring-think" data-live={busy || undefined}>
          <circle
            cx="120" cy="120" r="70"
            fill="none" stroke="var(--brass)" strokeWidth="1"
            strokeDasharray="26 14" opacity="0.75"
          />
          <circle
            cx="120" cy="120" r="62"
            fill="none" stroke="var(--brass-dim)" strokeWidth="1"
            strokeDasharray="4 22"
          />
        </g>

        {/* Interior — escucha */}
        <circle
          className="ring-listen"
          cx="120" cy="120" r="48"
          fill="none"
          stroke={listening ? "var(--ember)" : "var(--rule-bright)"}
          strokeWidth="1"
          data-live={listening || undefined}
        />

        {/* Marcas de cuadrante: dan sensación de instrumento calibrado */}
        {[0, 90, 180, 270].map((deg) => (
          <line
            key={deg}
            x1="120" y1="18" x2="120" y2="30"
            stroke="var(--brass)" strokeWidth="1.5" opacity="0.7"
            transform={`rotate(${deg} 120 120)`}
          />
        ))}

        {/* Núcleo — estado de la salida de datos */}
        <circle
          cx="120" cy="120" r="5"
          fill={health?.egress_allowed ? "var(--ember)" : "var(--brass)"}
          className="core-dot"
        />
      </svg>

      <div className="sigil-mark">
        <span>K.A.I.R.O.S</span>
        <small>
          {busy
            ? "procesando"
            : listening
              ? "escuchando"
              : total
                ? `${up} de ${total} agentes en línea`
                : "sin contacto con el núcleo"}
        </small>
      </div>
    </div>
  );
}
