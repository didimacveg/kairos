"use client";

import type { Health } from "@/lib/api";

/**
 * Sigilo K.A.I.R.O.S — interfaz de estado del sistema.
 *
 * Distinción que gobierna todo este componente: **estructura ornamental fija
 * SÍ; movimiento o dato falsos NO.**
 *
 * Un anillo grabado que siempre se ve igual no miente sobre nada — es la caja
 * del instrumento. Lo que no se hace es inventar telemetría: nada gira, se
 * enciende o cambia de longitud si no hay un valor real detrás.
 *
 * Elementos con dato:
 *   arco de agentes   fracción que responde al health check
 *   barrido           gira solo mientras el modelo genera
 *   anillo de datos   ídem, más lento
 *   segmentos vivos   uno encendido por recuerdo consultado
 *   anillo de escucha pulsa solo con el micrófono abierto
 *   núcleo            rojo si hay salida a Internet permitida
 */

const C = 200; // centro
const TAU = Math.PI * 2;

/** Punto en la circunferencia, en grados desde arriba. */
function at(radius: number, deg: number): [number, number] {
  const rad = ((deg - 90) * Math.PI) / 180;
  return [C + radius * Math.cos(rad), C + radius * Math.sin(rad)];
}

/** Arco como comando de path SVG. */
function arcPath(radius: number, from: number, to: number): string {
  const [x1, y1] = at(radius, from);
  const [x2, y2] = at(radius, to);
  const large = Math.abs(to - from) > 180 ? 1 : 0;
  return `M ${x1} ${y1} A ${radius} ${radius} 0 ${large} 1 ${x2} ${y2}`;
}

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
  // Un agente "disabled" esta apagado a proposito (la busqueda sin egress, por
  // ejemplo): no cuenta ni como roto ni en el total. Antes discrepaba de la
  // cabecera y decia "3 de 4" mientras arriba ponia "3/3".
  const agents = (health?.agents ?? []).filter((a) => a.status !== "disabled");
  const total = agents.length;
  const up = agents.filter((a) => a.status === "ok").length;
  const ratio = total > 0 ? up / total : 0;
  const alive = total > 0;

  const R_AGENTS = 176;
  const circ = TAU * R_AGENTS;

  const SEGMENTS = 24;
  const litSegments = Math.min(recalled, SEGMENTS);

  return (
    <div
      className="sigil"
      data-compact={compact || undefined}
      data-busy={busy || undefined}
      data-alive={alive || undefined}
    >
      <svg viewBox="0 0 400 400" role="img" aria-label="Estado de KAIROS">
        <defs>
          <radialGradient id="k-bloom">
            <stop offset="0%" stopColor="var(--ice)" stopOpacity="0.16" />
            <stop offset="60%" stopColor="var(--ice)" stopOpacity="0.05" />
            <stop offset="100%" stopColor="var(--ice)" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="k-sweep" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--ice)" stopOpacity="0" />
            <stop offset="60%" stopColor="var(--ice)" stopOpacity="0.35" />
            <stop offset="100%" stopColor="var(--ice)" stopOpacity="1" />
          </linearGradient>
        </defs>

        <circle cx={C} cy={C} r="180" fill="url(#k-bloom)" />

        {/* Corona de bloques: gira muy despacio mientras hay nucleo */}
        <g className="idle-slow" opacity="0.5">
          {Array.from({ length: 36 }, (_, i) => {
            const [x, y] = at(198, i * 10);
            const wide = i % 3 === 0;
            return (
              <rect key={i} x={x - (wide ? 3 : 1.5)} y={y - 4}
                width={wide ? 6 : 3} height={wide ? 9 : 5}
                fill={i % 6 === 0 ? "var(--brass)" : "var(--ice)"}
                transform={`rotate(${i * 10} ${x} ${y})`} />
            );
          })}
        </g>

        {/* ---- estructura exterior: grabado fijo ---- */}
        <circle cx={C} cy={C} r="192" fill="none" stroke="var(--rule-bright)" strokeWidth="1" opacity="0.5" />
        <circle cx={C} cy={C} r="186" fill="none" stroke="var(--ice-dim)" strokeWidth="0.75"
          strokeDasharray="1 7" opacity="0.85" />

        {/* Corchetes de cuadrante: giran al reves, aun mas despacio */}
        <g className="idle-slower">
        {[35, 125, 215, 305].map((deg) => (
          <path key={`b${deg}`} d={arcPath(192, deg, deg + 20)}
            fill="none" stroke="var(--ice)" strokeWidth="3" strokeLinecap="round" opacity="0.8" />
        ))}
        </g>

        {/* ---- agentes vivos ---- */}
        <circle cx={C} cy={C} r={R_AGENTS} fill="none" stroke="var(--rule-bright)" strokeWidth="1" />
        <circle className="ring-agents" cx={C} cy={C} r={R_AGENTS}
          fill="none" stroke="var(--ice)" strokeWidth="3"
          strokeDasharray={`${circ * ratio} ${circ}`} transform={`rotate(-90 ${C} ${C})`} />

        {/* ---- segmentos de memoria: uno por recuerdo consultado ---- */}
        <g className="segments">
          {Array.from({ length: SEGMENTS }, (_, i) => {
            const step = 360 / SEGMENTS;
            const lit = i < litSegments;
            return (
              <path key={i} d={arcPath(163, i * step + 2, i * step + step - 4)}
                fill="none" strokeWidth="7" strokeLinecap="butt"
                stroke={lit ? "var(--ice)" : "var(--rule-bright)"}
                opacity={lit ? 0.95 : 0.32}
                data-lit={lit || undefined} />
            );
          })}
        </g>

        {/* ---- barrido: solo mientras genera ---- */}
        <g className="ring-sweep" data-live={busy || undefined}>
          <circle cx={C} cy={C} r="146" fill="none" stroke="url(#k-sweep)"
            strokeWidth="4" strokeDasharray="230 688" strokeLinecap="round" />
        </g>

        {/* ---- anillo grabado con marcas finas ---- */}
        <circle cx={C} cy={C} r="134" fill="none" stroke="var(--ice-dim)" strokeWidth="1" opacity="0.7" />
        <g className="idle-drift" opacity="0.55">
          {Array.from({ length: 60 }, (_, i) => {
            const [x1, y1] = at(134, i * 6);
            const [x2, y2] = at(i % 5 === 0 ? 124 : 129, i * 6);
            return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
              stroke="var(--ice)" strokeWidth={i % 5 === 0 ? 1.4 : 0.7} />;
          })}
        </g>

        {/* ---- anillo de datos: gira al generar ---- */}
        <g className="ring-data" data-live={busy || undefined}>
          <circle cx={C} cy={C} r="112" fill="none" stroke="var(--brass)"
            strokeWidth="2" strokeDasharray="40 22" opacity="0.85" />
          {[0, 90, 180, 270].map((deg) => {
            const [x, y] = at(112, deg);
            return <rect key={deg} x={x - 4} y={y - 4} width="8" height="8"
              fill="var(--brass)" opacity="0.9" transform={`rotate(${deg} ${x} ${y})`} />;
          })}
        </g>

        {/* ---- contra-anillo ---- */}
        <g className="ring-counter" data-live={busy || undefined}>
          <circle cx={C} cy={C} r="98" fill="none" stroke="var(--ice)"
            strokeWidth="1" strokeDasharray="3 15" opacity="0.7" />
        </g>

        {/* ---- estructura interior fija ---- */}
        <circle cx={C} cy={C} r="86" fill="none" stroke="var(--rule-bright)" strokeWidth="1" />
        <g className="idle-inner">
        {[20, 200].map((deg) => (
          <path key={`i${deg}`} d={arcPath(86, deg, deg + 55)}
            fill="none" stroke="var(--ice)" strokeWidth="2.5" opacity="0.75" strokeLinecap="round" />
        ))}
        </g>

        {/* ---- escucha ---- */}
        <circle className="ring-listen" cx={C} cy={C} r="72" fill="none"
          stroke={listening ? "var(--ember)" : "var(--ice-dim)"} strokeWidth="1.5"
          data-live={listening || undefined} />

        {/* ---- anillo violeta intermedio: estructura ---- */}
        <circle cx={C} cy={C} r="80" fill="none" stroke="var(--brass-dim)"
          strokeWidth="1" strokeDasharray="2 6" opacity="0.8" />

        {/* ---- disco central con halo ---- */}
        <circle className="core-halo" cx={C} cy={C} r="66" fill="none"
          stroke="var(--ice)" strokeWidth="1.5" opacity="0.7" />
        <circle cx={C} cy={C} r="64" fill="var(--void)" opacity="0.78" />
        <circle cx={C} cy={C} r="64" fill="none" stroke="var(--ice-dim)" strokeWidth="1" />
        {[8, 188].map((deg) => (
          <path key={`c${deg}`} d={arcPath(58, deg, deg + 40)}
            fill="none" stroke="var(--brass)" strokeWidth="2" opacity="0.85" strokeLinecap="round" />
        ))}

        {!compact && (
          <text
            x={C} y={C + 5}
            className="sigil-text"
            textAnchor="middle"
            textLength="98"
            lengthAdjust="spacingAndGlyphs"
          >
            K.A.I.R.O.S
          </text>
        )}

        {/* Núcleo: estado de la salida de datos */}
        {compact && (
          <circle cx={C} cy={C} r="18" className="core-dot"
            fill={health?.egress_allowed ? "var(--ember)" : "var(--ice)"} />
        )}
      </svg>

      {!compact && (
        <div className="sigil-mark">
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
