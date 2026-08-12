"use client";

import type { Health } from "@/lib/api";

/**
 * Sigilo K.A.I.R.O.S — el núcleo visible del sistema.
 *
 * Es la pieza central de la interfaz y lo sigue siendo mientras KAIROS
 * responde. La regla del proyecto no cambia: **cada elemento codifica un
 * estado real**.
 *
 *   arco exterior   fracción de agentes que responden al health check
 *   anillo de datos gira solo mientras el modelo genera
 *   contra-anillo   gira al revés; da profundidad y marca la misma actividad
 *   marcas de memoria  una por recuerdo consultado en el último turno
 *   anillo interior pulsa solo cuando el micrófono escucha
 *   núcleo          rojo si hay salida a Internet permitida
 *
 * Si el sistema está parado, el sigilo está quieto. Un adorno que gira siempre
 * no dice nada; uno que gira cuando la máquina piensa te dice que piensa.
 */
export function Sigil({
  health,
  busy,
  listening,
  recalled = 0,
  compact,
}: {
  health: Health | null;
  busy: boolean;
  listening: boolean;
  recalled?: number;
  compact?: boolean;
}) {
  const total = health?.agents.length ?? 0;
  const up = health?.agents.filter((a) => a.status === "ok").length ?? 0;
  const ratio = total > 0 ? up / total : 0;

  const R_AGENTS = 148;
  const circumference = 2 * Math.PI * R_AGENTS;
  const arc = circumference * ratio;

  // Una marca por recuerdo consultado, repartidas por el anillo exterior.
  const ticks = Math.min(recalled, 12);

  return (
    <div className="sigil" data-compact={compact || undefined} data-busy={busy || undefined}>
      <svg viewBox="0 0 360 360" role="img" aria-label="Estado de KAIROS">
        <defs>
          <radialGradient id="k-core">
            <stop offset="0%" stopColor="var(--brass)" stopOpacity="0.42" />
            <stop offset="55%" stopColor="var(--brass)" stopOpacity="0.07" />
            <stop offset="100%" stopColor="var(--brass)" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="k-sweep" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--ice)" stopOpacity="0" />
            <stop offset="100%" stopColor="var(--ice)" stopOpacity="0.9" />
          </linearGradient>
        </defs>

        <circle cx="180" cy="180" r="140" fill="url(#k-core)" />

        {/* Marcas de memoria consultada */}
        <g className="ticks">
          {Array.from({ length: ticks }, (_, i) => (
            <line
              key={i}
              x1="180" y1="14" x2="180" y2="26"
              stroke="var(--ice)" strokeWidth="2" opacity="0.85"
              transform={`rotate(${(360 / 12) * i} 180 180)`}
            />
          ))}
        </g>

        {/* Agentes vivos */}
        <circle cx="180" cy="180" r={R_AGENTS} fill="none" stroke="var(--rule-bright)" strokeWidth="1" />
        <circle
          className="ring-agents"
          cx="180" cy="180" r={R_AGENTS}
          fill="none" stroke="var(--ice)" strokeWidth="2.5"
          strokeDasharray={`${arc} ${circumference}`}
          transform="rotate(-90 180 180)"
        />

        {/* Barrido: solo mientras genera */}
        <g className="ring-sweep" data-live={busy || undefined}>
          <circle
            cx="180" cy="180" r="126"
            fill="none" stroke="url(#k-sweep)" strokeWidth="3"
            strokeDasharray="180 612" strokeLinecap="round"
          />
        </g>

        {/* Anillo de datos y contra-anillo */}
        <g className="ring-data" data-live={busy || undefined}>
          <circle
            cx="180" cy="180" r="112"
            fill="none" stroke="var(--brass)" strokeWidth="1.5"
            strokeDasharray="34 18" opacity="0.8"
          />
        </g>
        <g className="ring-counter" data-live={busy || undefined}>
          <circle
            cx="180" cy="180" r="98"
            fill="none" stroke="var(--brass-dim)" strokeWidth="1"
            strokeDasharray="5 27"
          />
        </g>

        {/* Estructura fija: da sensación de instrumento calibrado */}
        {[0, 45, 90, 135, 180, 225, 270, 315].map((deg) => (
          <line
            key={deg}
            x1="180" y1="40" x2="180" y2="54"
            stroke="var(--brass)" strokeWidth={deg % 90 === 0 ? 2 : 1}
            opacity={deg % 90 === 0 ? 0.85 : 0.4}
            transform={`rotate(${deg} 180 180)`}
          />
        ))}

        <circle cx="180" cy="180" r="84" fill="none" stroke="var(--rule-bright)" strokeWidth="1" opacity="0.7" />

        {/* Escucha */}
        <circle
          className="ring-listen"
          cx="180" cy="180" r="70"
          fill="none"
          stroke={listening ? "var(--ember)" : "var(--rule-bright)"}
          strokeWidth="1.5"
          data-live={listening || undefined}
        />

        {/* Núcleo: estado de la salida de datos */}
        <circle cx="180" cy="180" r="7" className="core-dot"
          fill={health?.egress_allowed ? "var(--ember)" : "var(--brass)"} />
      </svg>

      {!compact && (
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
      )}
    </div>
  );
}
