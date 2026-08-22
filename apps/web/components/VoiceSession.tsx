"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Listener } from "@/lib/listen";

type Stage = "off" | "calibrating" | "listening" | "hearing" | "working" | "watching";

/**
 * Sesión de voz manos libres, con interrupción.
 *
 * Un solo interruptor (o Alt+K). Mientras está encendido el micrófono NUNCA
 * se cierra: cuando es tu turno graba, y mientras KAIROS habla vigila el nivel
 * para detectar que le cortas.
 *
 * Interrumpir significa interrumpir: se aborta la generación en curso, se
 * calla la voz, y tu nueva frase entra limpia. Antes se solapaban dos voces
 * porque el sistema seguía hablando de lo anterior.
 *
 * Si Whisper no está seguro de lo que oyó, NO envía: pide que lo repitas.
 * Con la memoria curada, un mensaje enviado puede volverse un hecho permanente.
 */
export function VoiceSession({
  active,
  onToggle,
  onUtterance,
  onSay,
  onInterrupt,
  onHush,
  busy,
}: {
  active: boolean;
  onToggle: (next: boolean) => void;
  onUtterance: (text: string) => void;
  onSay: (message: string) => void;
  onInterrupt: () => void;
  onHush: () => void;
  busy: boolean;
}) {
  const [stage, setStage] = useState<Stage>("off");
  const [level, setLevel] = useState(0);
  const [note, setNote] = useState<string | null>(null);
  const listenerRef = useRef<Listener | null>(null);
  const activeRef = useRef(active);
  activeRef.current = active;

  const transcribe = useCallback(
    async (blob: Blob) => {
      setStage("working");
      try {
        const form = new FormData();
        form.append("audio", blob, "audio.webm");
        const response = await fetch("/api/v1/voice/transcribe", {
          method: "POST",
          credentials: "same-origin",
          body: form,
        });
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { detail?: string } | null;
          throw new Error(body?.detail ?? "No se pudo transcribir");
        }
        const data = (await response.json()) as {
          text: string;
          low_confidence: boolean;
          no_speech: boolean;
        };

        if (data.no_speech || !data.text.trim()) {
          // Silencio, ruido de fondo o un golpe. NO se anuncia nada: decir
          // "no te he entendido" cuando nadie ha hablado es peor que callar,
          // y era lo que hacia KAIROS con el ventilador de fondo.
          return;
        }
        // Solo se pide repetir si de verdad se oyo hablar y no se entendio.
        // Una transcripcion muy corta con confianza baja casi siempre es
        // ruido, no una frase mal entendida.
        if (data.low_confidence) {
          if (data.text.trim().length > 12) {
            onSay("Perdona, no te he entendido bien. ¿Puedes repetirlo?");
          }
          return;
        }
        onUtterance(data.text.trim());
      } catch (err) {
        setNote(err instanceof Error ? err.message : "Fallo al transcribir");
        setStage("listening");
      }
    },
    [onSay, onUtterance],
  );

  const beginTurn = useCallback(() => {
    if (!activeRef.current) return;
    setNote(null);
    setStage("calibrating");
    const listener = new Listener(
      {
        onLevel: setLevel,
        onSpeechStart: () => setStage("hearing"),
        onDone: (blob) => void transcribe(blob),
        onFault: (message) => {
          setNote(message);
          setStage("listening");
        },
      },
      { silenceMs: 1100, maxMs: 30_000 },
    );
    listenerRef.current = listener;
    void listener.start().then(() => {
      setStage((prev) => (prev === "calibrating" ? "listening" : prev));
    });
  }, [transcribe]);

  const beginWatch = useCallback(() => {
    if (!activeRef.current) return;
    setStage("watching");
    const listener = new Listener({
      onLevel: setLevel,
      onSpeechStart: () => undefined,
      onDone: () => undefined,
      onFault: () => undefined,
    });
    listenerRef.current = listener;
    void listener.watch(
      () => {
        onInterrupt();
        // Encadena el turno nuevo: le has cortado para decir algo.
        setTimeout(beginTurn, 100);
      },
      // Silenciado inmediato: en cuanto abres la boca, KAIROS se calla.
      onHush,
    );
  }, [beginTurn, onInterrupt, onHush]);

  useEffect(() => {
    if (!active) {
      listenerRef.current?.abort();
      listenerRef.current = null;
      setStage("off");
      setLevel(0);
      return;
    }
    // Turno de KAIROS: vigilar. Turno del usuario: grabar.
    if (busy && stage !== "watching") {
      listenerRef.current?.abort();
      const id = setTimeout(beginWatch, 150);
      return () => clearTimeout(id);
    }
    if (!busy && (stage === "off" || stage === "working" || stage === "watching")) {
      listenerRef.current?.abort();
      const id = setTimeout(beginTurn, 300);
      return () => clearTimeout(id);
    }
  }, [active, busy, stage, beginTurn, beginWatch]);

  useEffect(() => () => listenerRef.current?.abort(), []);

  const caption: Record<Stage, string> = {
    off: "Voz apagada",
    calibrating: "Calibrando",
    listening: "Escuchando",
    hearing: "Te oigo",
    working: "Procesando",
    watching: "Puedes interrumpir",
  };

  const bars = 18;
  const lit = Math.min(bars, Math.round((level / 0.25) * bars));

  return (
    <div className="voice">
      <button
        type="button"
        onClick={() => onToggle(!active)}
        data-live={active || undefined}
        aria-pressed={active}
        title="Alt+K"
      >
        {active ? "Cortar voz" : "Voz · Alt+K"}
      </button>

      {active && (
        <div className="vu" aria-hidden="true">
          {Array.from({ length: bars }, (_, index) => (
            <i key={index} data-lit={index < lit || undefined} data-hot={index > 14 || undefined} />
          ))}
        </div>
      )}

      <span className="voice-state" data-stage={stage}>
        {note ?? caption[stage]}
      </span>
    </div>
  );
}
