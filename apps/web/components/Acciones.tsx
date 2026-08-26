"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Menú de acciones secundarias.
 *
 * Siete botones en fila era el resultado de que cada fase añadiera el suyo
 * sin mirar los anteriores. Lo que se usa a diario —hablar, imagen, enviar—
 * se queda fuera; lo demás vive aquí.
 *
 * El criterio para decidir qué sale y qué entra: si lo usas varias veces al
 * día, fuera. Si lo usas al empezar o para grabar, dentro.
 */
export function Acciones({
  onNegro,
  onDespertar,
  onChat,
  escuchaAmbiente,
  onEscucha,
  escuchaEstricta,
  onEstricta,
}: {
  onNegro: () => void;
  onDespertar: () => void;
  onChat: () => void;
  escuchaAmbiente: boolean;
  onEscucha: () => void;
  escuchaEstricta: boolean;
  onEstricta: () => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const caja = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: MouseEvent) => {
      if (caja.current && !caja.current.contains(e.target as Node)) setAbierto(false);
    };
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, [abierto]);

  const pulsar = (fn: () => void) => () => {
    fn();
    setAbierto(false);
  };

  return (
    <div className="acciones" ref={caja}>
      <style
        dangerouslySetInnerHTML={{
          __html: `
        .acciones { position: relative; }
        .acciones > button[data-abierto] { color: var(--ice); border-color: var(--ice); }
        .acc-menu { position: absolute; bottom: calc(100% + .5rem); left: 0; z-index: 40;
          min-width: 13rem; background: var(--panel);
          border: 1px solid var(--rule-bright); padding: .35rem;
          box-shadow: 0 -14px 40px -16px rgba(0,0,0,.9); }
        .acc-menu button { display: block; width: 100%; text-align: left;
          border: none !important; padding: .5rem .7rem !important;
          background: none; }
        .acc-menu button:hover { background: rgba(79,216,255,.08); color: var(--ice); }
        .acc-menu button[data-on] { color: var(--ice); }
        .acc-menu hr { border: none; border-top: 1px solid var(--rule); margin: .3rem 0; }
        .acc-tit { font-family: var(--data); font-size: .48rem;
          letter-spacing: var(--track-label); text-transform: uppercase;
          color: var(--faint); padding: .45rem .7rem .25rem; }
      `,
        }}
      />

      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        data-abierto={abierto || undefined}
        title="Más acciones"
      >
        Más
      </button>

      {abierto && (
        <div className="acc-menu">
          <div className="acc-tit">Escucha</div>
          <button type="button" onClick={pulsar(onEscucha)} data-on={escuchaAmbiente || undefined}>
            {escuchaAmbiente ? "Desactivar escucha ambiente" : "Activar escucha ambiente"}
          </button>
          {escuchaAmbiente && (
            <button type="button" onClick={pulsar(onEstricta)} data-on={escuchaEstricta || undefined}>
              {escuchaEstricta ? "Modo relajado" : "Modo estricto (exige el nombre)"}
            </button>
          )}

          <hr />
          <div className="acc-tit">Vista</div>
          <button type="button" onClick={pulsar(onChat)}>
            Modo chat
          </button>

          <hr />
          <div className="acc-tit">Grabar</div>
          <button type="button" onClick={pulsar(onNegro)}>
            Pantalla en negro
          </button>
          <button type="button" onClick={pulsar(onDespertar)}>
            Lanzar secuencia de arranque
          </button>
        </div>
      )}
    </div>
  );
}
