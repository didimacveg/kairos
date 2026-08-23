"use client";

import type { ReactNode } from "react";

/**
 * Renderizado de las respuestas: markdown y fórmulas.
 *
 * POR QUÉ ESCRITO A MANO Y NO CON UNA LIBRERÍA: KAIROS funciona sin Internet
 * por diseño, así que una fuente externa queda descartada. E instalar
 * `react-markdown` + `katex` añade ~400 KB y dos dependencias que mantener
 * para cubrir un subconjunto que aquí ocupa doscientas líneas.
 *
 * LO QUE CUBRE: encabezados, negrita, cursiva, código en bloque y en línea,
 * listas, citas, y fórmulas entre $ o $$ con notación matemática común
 * (fracciones, raíces, exponentes, subíndices, letras griegas).
 *
 * LO QUE NO: LaTeX completo. Integrales con límites complejos, matrices y
 * diagramas se muestran en monoespaciada legible en vez de mal compuestos.
 * Preferible enseñar la fórmula cruda que una versión rota.
 */

const GRIEGAS: Record<string, string> = {
  alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε", zeta: "ζ",
  eta: "η", theta: "θ", iota: "ι", kappa: "κ", lambda: "λ", mu: "μ",
  nu: "ν", xi: "ξ", pi: "π", rho: "ρ", sigma: "σ", tau: "τ",
  upsilon: "υ", phi: "φ", chi: "χ", psi: "ψ", omega: "ω",
  Gamma: "Γ", Delta: "Δ", Theta: "Θ", Lambda: "Λ", Xi: "Ξ", Pi: "Π",
  Sigma: "Σ", Phi: "Φ", Psi: "Ψ", Omega: "Ω",
};

const SIMBOLOS: Record<string, string> = {
  times: "×", cdot: "·", div: "÷", pm: "±", mp: "∓",
  leq: "≤", geq: "≥", neq: "≠", approx: "≈", equiv: "≡",
  infty: "∞", partial: "∂", nabla: "∇", int: "∫", sum: "∑", prod: "∏",
  rightarrow: "→", leftarrow: "←", Rightarrow: "⇒", leftrightarrow: "↔",
  in: "∈", notin: "∉", subset: "⊂", cup: "∪", cap: "∩",
  forall: "∀", exists: "∃", angle: "∠", degree: "°", propto: "∝",
};

const SUPER: Record<string, string> = {
  "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵",
  "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "-": "⁻",
  n: "ⁿ", i: "ⁱ",
};

const SUB: Record<string, string> = {
  "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅",
  "6": "₆", "7": "₇", "8": "₈", "9": "₉", "+": "₊", "-": "₋",
  a: "ₐ", e: "ₑ", i: "ᵢ", o: "ₒ", x: "ₓ", n: "ₙ",
};

function formula(bruto: string): ReactNode {
  let t = bruto;

  // \frac{a}{b} -> (a)/(b) con formato propio
  const fracciones: string[] = [];
  t = t.replace(/\\d?frac\{([^{}]+)\}\{([^{}]+)\}/g, (_, a, b) => {
    fracciones.push(`${a}|${b}`);
    return `\u0001${fracciones.length - 1}\u0001`;
  });

  t = t.replace(/\\sqrt\{([^{}]+)\}/g, "√($1)");
  t = t.replace(/\\text\{([^{}]+)\}/g, "$1");
  t = t.replace(/\\left|\\right/g, "");

  for (const [k, v] of Object.entries(GRIEGAS)) {
    t = t.replace(new RegExp(`\\\\${k}\\b`, "g"), v);
  }
  for (const [k, v] of Object.entries(SIMBOLOS)) {
    t = t.replace(new RegExp(`\\\\${k}\\b`, "g"), v);
  }

  // Exponentes y subíndices simples
  t = t.replace(/\^\{?([0-9n+\-i]+)\}?/g, (_, g: string) =>
    [...g].map((c) => SUPER[c] ?? `^${c}`).join(""));
  t = t.replace(/_\{?([0-9a-z+\-]+)\}?/g, (_, g: string) =>
    [...g].map((c) => SUB[c] ?? `_${c}`).join(""));

  t = t.replace(/[{}]/g, "");

  const partes = t.split(/\u0001(\d+)\u0001/);
  return (
    <>
      {partes.map((p, i) => {
        if (i % 2 === 0) return p;
        const [num, den] = fracciones[Number(p)].split("|");
        return (
          <span className="frac" key={i}>
            <span>{num}</span>
            <span>{den}</span>
          </span>
        );
      })}
    </>
  );
}

function enLinea(texto: string, clave: string): ReactNode {
  // Orden: código primero (no se toca lo de dentro), luego fórmulas, luego
  // negrita y cursiva. Al revés, el markdown dentro del código se procesaría.
  const trozos: ReactNode[] = [];
  const patron = /(`[^`]+`)|(\$[^$\n]+\$)|(\*\*[^*]+\*\*)|(\*[^*\n]+\*)/g;
  let ultimo = 0;
  let m: RegExpExecArray | null;
  let n = 0;

  while ((m = patron.exec(texto)) !== null) {
    if (m.index > ultimo) trozos.push(texto.slice(ultimo, m.index));
    const t = m[0];
    const k = `${clave}-${n++}`;
    if (t.startsWith("`")) {
      trozos.push(<code key={k}>{t.slice(1, -1)}</code>);
    } else if (t.startsWith("$")) {
      trozos.push(
        <span className="mate" key={k}>
          {formula(t.slice(1, -1))}
        </span>,
      );
    } else if (t.startsWith("**")) {
      trozos.push(<strong key={k}>{t.slice(2, -2)}</strong>);
    } else {
      trozos.push(<em key={k}>{t.slice(1, -1)}</em>);
    }
    ultimo = m.index + t.length;
  }
  if (ultimo < texto.length) trozos.push(texto.slice(ultimo));
  return <>{trozos}</>;
}

export function Render({ texto }: { texto: string }) {
  const bloques: ReactNode[] = [];
  const lineas = texto.split("\n");
  let i = 0;
  let n = 0;

  while (i < lineas.length) {
    const linea = lineas[i];

    // Bloque de código
    if (linea.trimStart().startsWith("```")) {
      const lenguaje = linea.trim().slice(3).trim();
      const cuerpo: string[] = [];
      i += 1;
      while (i < lineas.length && !lineas[i].trimStart().startsWith("```")) {
        cuerpo.push(lineas[i]);
        i += 1;
      }
      i += 1;
      bloques.push(
        <pre className="bloque-codigo" key={n++}>
          {lenguaje && <span className="lang">{lenguaje}</span>}
          <code>{cuerpo.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    // Fórmula centrada
    if (linea.trim().startsWith("$$")) {
      const cuerpo: string[] = [];
      const misma = linea.trim().slice(2);
      if (misma.endsWith("$$")) {
        cuerpo.push(misma.slice(0, -2));
        i += 1;
      } else {
        if (misma) cuerpo.push(misma);
        i += 1;
        while (i < lineas.length && !lineas[i].trim().endsWith("$$")) {
          cuerpo.push(lineas[i]);
          i += 1;
        }
        if (i < lineas.length) cuerpo.push(lineas[i].trim().replace(/\$\$$/, ""));
        i += 1;
      }
      bloques.push(
        <div className="mate-bloque" key={n++}>
          {formula(cuerpo.join(" "))}
        </div>,
      );
      continue;
    }

    // Encabezado
    const enc = /^(#{1,4})\s+(.*)$/.exec(linea);
    if (enc) {
      const nivel = enc[1].length;
      bloques.push(
        <p className="enc" data-nivel={nivel} key={n++}>
          {enLinea(enc[2], `e${n}`)}
        </p>,
      );
      i += 1;
      continue;
    }

    // Cita
    if (linea.trimStart().startsWith("> ")) {
      const cuerpo: string[] = [];
      while (i < lineas.length && lineas[i].trimStart().startsWith("> ")) {
        cuerpo.push(lineas[i].trimStart().slice(2));
        i += 1;
      }
      bloques.push(
        <blockquote key={n++}>{enLinea(cuerpo.join(" "), `c${n}`)}</blockquote>,
      );
      continue;
    }

    // Lista
    if (/^\s*([-*+]|\d+\.)\s+/.test(linea)) {
      const puntos: string[] = [];
      const numerada = /^\s*\d+\./.test(linea);
      while (i < lineas.length && /^\s*([-*+]|\d+\.)\s+/.test(lineas[i])) {
        puntos.push(lineas[i].replace(/^\s*([-*+]|\d+\.)\s+/, ""));
        i += 1;
      }
      const items = puntos.map((p, j) => <li key={j}>{enLinea(p, `l${n}-${j}`)}</li>);
      bloques.push(numerada ? <ol key={n++}>{items}</ol> : <ul key={n++}>{items}</ul>);
      continue;
    }

    if (!linea.trim()) {
      i += 1;
      continue;
    }

    // Párrafo: se juntan las líneas seguidas
    const parrafo: string[] = [];
    while (
      i < lineas.length &&
      lineas[i].trim() &&
      !lineas[i].trimStart().startsWith("```") &&
      !lineas[i].trim().startsWith("$$") &&
      !/^\s*([-*+]|\d+\.)\s+/.test(lineas[i]) &&
      !/^#{1,4}\s/.test(lineas[i]) &&
      !lineas[i].trimStart().startsWith("> ")
    ) {
      parrafo.push(lineas[i]);
      i += 1;
    }
    bloques.push(<p key={n++}>{enLinea(parrafo.join(" "), `p${n}`)}</p>);
  }

  return <>{bloques}</>;
}
