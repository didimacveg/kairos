"use client";

import { useEffect, useState } from "react";
import type { Health } from "@/lib/api";

/**
 * Sigilo K.A.I.R.O.S — interfaz de estado del sistema.
 *
 * NOTA DE IMPLEMENTACIÓN, importante: el movimiento va con `<animateTransform>`
 * (SMIL), no con animaciones CSS.
 *
 * Motivo: las reglas `@media (prefers-reduced-motion: reduce) { * { animation:
 * none !important } }` heredadas de fases anteriores mataban toda animación CSS
 * en máquinas con los efectos de Windows desactivados, y localizarlas en una
 * hoja de estilos que crece por añadidos resultó frágil. SMIL vive dentro del
 * SVG, no pasa por la cascada y no hay `!important` que lo anule.
 *
 * La preferencia del usuario se respeta en React: si el movimiento está
 * apagado, los `<animateTransform>` simplemente no se renderizan.
 *
 * Regla del proyecto, intacta: **estructura fija ornamental sí; movimiento o
 * dato falsos no.** Nada gira si no hay contacto con el núcleo, y la velocidad
 * cambia según el sistema esté en reposo o generando.
 */

const C = 200;
const TAU = Math.PI * 2;

function at(radius: number, deg: number): [number, number] {
  const rad = ((deg - 90) * Math.PI) / 180;
  return [C + radius * Math.cos(rad), C + radius * Math.sin(rad)];
}

function arcPath(radius: number, from: number, to: number): string {
  const [x1, y1] = at(radius, from);
  const [x2, y2] = at(radius, to);
  const large = Math.abs(to - from) > 180 ? 1 : 0;
  return `M ${x1} ${y1} A ${radius} ${radius} 0 ${large} 1 ${x2} ${y2}`;
}

/** Rotación continua alrededor del centro. `dur` en segundos. */
function Spin({ dur, reverse }: { dur: number; reverse?: boolean }) {
  return (
    <animateTransform
      attributeName="transform"
      attributeType="XML"
      type="rotate"
      from={`${reverse ? 360 : 0} ${C} ${C}`}
      to={`${reverse ? 0 : 360} ${C} ${C}`}
      dur={`${dur}s`}
      repeatCount="indefinite"
    />
  );
}

/** Pulso de opacidad. */
function Breathe({ dur, from, to }: { dur: number; from: number; to: number }) {
  return (
    <animate
      attributeName="opacity"
      values={`${from};${to};${from}`}
      dur={`${dur}s`}
      repeatCount="indefinite"
    />
  );
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
  // Un agente "disabled" está apagado a propósito: ni roto ni en el total.
  const agents = (health?.agents ?? []).filter((a) => a.status !== "disabled");
  const total = agents.length;
  const up = agents.filter((a) => a.status === "ok").length;
  const ratio = total > 0 ? up / total : 0;
  const alive = total > 0;

  const [motion, setMotion] = useState(true);

  useEffect(() => {
    const read = () => {
      const stored = window.localStorage.getItem("kairos.motion");
      setMotion(stored === null ? true : stored === "on");
    };
    read();
    // La cabecera cambia localStorage; este evento la mantiene sincronizada.
    window.addEventListener("storage", read);
    const id = setInterval(read, 1500);
    return () => {
      window.removeEventListener("storage", read);
      clearInterval(id);
    };
  }, []);

  // Sin contacto con el núcleo, todo quieto. Es información, no estilo.
  const moving = motion && alive;
  const speed = (idle: number, working: number) => (busy ? working : idle);

  const R_AGENTS = 176;
  const circ = TAU * R_AGENTS;
  const SEGMENTS = 24;
  const litSegments = Math.min(recalled, SEGMENTS);

  return (
    <div className="sigil" data-compact={compact || undefined} data-busy={busy || undefined}>
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

        {/* Corona de bloques */}
        <g opacity="0.5">
          {moving && <Spin dur={speed(46, 9)} />}
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

        <circle cx={C} cy={C} r="192" fill="none" stroke="var(--rule-bright)" strokeWidth="1" opacity="0.5" />
        <circle cx={C} cy={C} r="186" fill="none" stroke="var(--ice-dim)" strokeWidth="0.75"
          strokeDasharray="1 7" opacity="0.85" />

        {/* Corchetes de cuadrante, contrarrotando */}
        <g>
          {moving && <Spin dur={speed(68, 13)} reverse />}
          {[35, 125, 215, 305].map((deg) => (
            <path key={`b${deg}`} d={arcPath(192, deg, deg + 20)}
              fill="none" stroke="var(--ice)" strokeWidth="3" strokeLinecap="round" opacity="0.8" />
          ))}
        </g>

        {/* Agentes vivos */}
        <circle cx={C} cy={C} r={R_AGENTS} fill="none" stroke="var(--rule-bright)" strokeWidth="1" />
        <circle className="ring-agents" cx={C} cy={C} r={R_AGENTS}
          fill="none" stroke="var(--ice)" strokeWidth="3"
          strokeDasharray={`${circ * ratio} ${circ}`} transform={`rotate(-90 ${C} ${C})`}>
          {moving && <Breathe dur={4.2} from={1} to={0.45} />}
        </circle>

        {/* Segmentos: uno por recuerdo consultado */}
        <g className="segments">
          {moving && <Breathe dur={5.5} from={1} to={0.6} />}
          {Array.from({ length: SEGMENTS }, (_, i) => {
            const step = 360 / SEGMENTS;
            const lit = i < litSegments;
            return (
              <path key={i} d={arcPath(163, i * step + 2, i * step + step - 4)}
                fill="none" strokeWidth="7"
                stroke={lit ? "var(--ice)" : "var(--rule-bright)"}
                opacity={lit ? 0.95 : 0.32} data-lit={lit || undefined} />
            );
          })}
        </g>

        {/* Barrido: solo mientras genera */}
        {busy && (
          <g>
            {motion && <Spin dur={1.7} />}
            <circle cx={C} cy={C} r="146" fill="none" stroke="url(#k-sweep)"
              strokeWidth="4" strokeDasharray="230 688" strokeLinecap="round" />
          </g>
        )}

        {/* Graduación fina, deriva lenta */}
        <g opacity="0.55">
          {moving && <Spin dur={speed(92, 18)} />}
          {Array.from({ length: 60 }, (_, i) => {
            const [x1, y1] = at(134, i * 6);
            const [x2, y2] = at(i % 5 === 0 ? 124 : 129, i * 6);
            return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
              stroke="var(--ice)" strokeWidth={i % 5 === 0 ? 1.4 : 0.7} />;
          })}
        </g>
        <circle cx={C} cy={C} r="134" fill="none" stroke="var(--ice-dim)" strokeWidth="1" opacity="0.7" />

        {/* Anillo de datos */}
        <g>
          {moving && <Spin dur={speed(34, 6)} />}
          <circle cx={C} cy={C} r="112" fill="none" stroke="var(--brass)"
            strokeWidth="2" strokeDasharray="40 22" opacity="0.85" />
          {[0, 90, 180, 270].map((deg) => {
            const [x, y] = at(112, deg);
            return <rect key={deg} x={x - 4} y={y - 4} width="8" height="8"
              fill="var(--brass)" opacity="0.9" transform={`rotate(${deg} ${x} ${y})`} />;
          })}
        </g>

        {/* Contra-anillo */}
        <g>
          {moving && <Spin dur={speed(21, 4)} reverse />}
          <circle cx={C} cy={C} r="98" fill="none" stroke="var(--ice)"
            strokeWidth="1" strokeDasharray="3 15" opacity="0.7" />
        </g>

        {/* Arcos interiores */}
        <g>
          {moving && <Spin dur={speed(27, 5)} reverse />}
          {[20, 200].map((deg) => (
            <path key={`i${deg}`} d={arcPath(86, deg, deg + 55)}
              fill="none" stroke="var(--ice)" strokeWidth="2.5" opacity="0.75" strokeLinecap="round" />
          ))}
        </g>
        <circle cx={C} cy={C} r="86" fill="none" stroke="var(--rule-bright)" strokeWidth="1" />

        <circle cx={C} cy={C} r="80" fill="none" stroke="var(--brass-dim)"
          strokeWidth="1" strokeDasharray="2 6" opacity="0.8" />

        {/* Escucha */}
        <circle cx={C} cy={C} r="72" fill="none"
          stroke={listening ? "var(--ember)" : "var(--ice-dim)"} strokeWidth="1.5">
          {listening && motion && <Breathe dur={1.5} from={1} to={0.25} />}
        </circle>

        {/* Disco central con halo */}
        <circle cx={C} cy={C} r="66" fill="none" stroke="var(--ice)" strokeWidth="1.5" opacity="0.7">
          {moving && <Breathe dur={busy ? 1.1 : 3.4} from={0.7} to={0.15} />}
        </circle>
        <circle cx={C} cy={C} r="64" fill="var(--void)" opacity="0.78" />
        <circle cx={C} cy={C} r="64" fill="none" stroke="var(--ice-dim)" strokeWidth="1" />

        <g>
          {moving && <Spin dur={speed(16, 3)} />}
          {[8, 188].map((deg) => (
            <path key={`c${deg}`} d={arcPath(58, deg, deg + 40)}
              fill="none" stroke="var(--brass)" strokeWidth="2" opacity="0.85" strokeLinecap="round" />
          ))}
        </g>

        {!compact && (
          <text x={C} y={C + 5} className="sigil-text" textAnchor="middle"
            textLength="98" lengthAdjust="spacingAndGlyphs">
            K.A.I.R.O.S
          </text>
        )}

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
