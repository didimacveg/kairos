"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Listener } from "@/lib/listen";

type Stage = "off" | "calibrating" | "listening" | "hearing" | "working";

/**
 * Sesión de voz manos libres.
 *
 * Un solo interruptor. Mientras está encendido: escucha, detecta cuándo
 * terminas de hablar, transcribe y envía. Sin pulsar tres botones por turno.
 *
 * Si Whisper no está seguro de lo que oyó, NO envía: pide que lo repitas.
 * Con la memoria curada, un mensaje enviado puede convertirse en un hecho
 * permanente — repetir una frase cuesta mucho menos que ir a borrarlo.
 *
 * El medidor de nivel es funcional, no decorativo: sin él no hay forma de
 * distinguir "el micro no capta" de "no me estás entendiendo".
 */
export function VoiceSession({
  active,
  onToggle,
  onUtterance,
  onSay,
  busy,
}: {
  active: boolean;
  onToggle: (next: boolean) => void;
  onUtterance: (text: string) => void;
  onSay: (message: string) => void;
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
          onSay("No he entendido nada. ¿Puedes repetirlo?");
          return;
        }
        if (data.low_confidence) {
          onSay("Perdona, no te he entendido bien. ¿Puedes repetirlo?");
          return;
        }
        onUtterance(data.text.trim());
      } catch (err) {
        setNote(err instanceof Error ? err.message : "Fallo al transcribir");
      }
    },
    [onSay, onUtterance],
  );

  const cycle = useCallback(() => {
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

  // Reabre la escucha cuando KAIROS termina de responder: así la conversación
  // continúa sin volver a tocar nada.
  useEffect(() => {
    if (!active) {
      listenerRef.current?.abort();
      listenerRef.current = null;
      setStage("off");
      setLevel(0);
      return;
    }
    if (!busy && (stage === "off" || stage === "working")) {
      const id = setTimeout(cycle, 350);
      return () => clearTimeout(id);
    }
  }, [active, busy, stage, cycle]);

  useEffect(() => () => listenerRef.current?.abort(), []);

  const caption: Record<Stage, string> = {
    off: "Sesión de voz",
    calibrating: "Calibrando ruido",
    listening: "Escuchando",
    hearing: "Te oigo",
    working: "Procesando",
  };

  // 0.25 de RMS es un grito a un palmo del micro: normaliza bien el rango útil.
  const bars = 16;
  const lit = Math.min(bars, Math.round((level / 0.25) * bars));

  return (
    <div className="voice">
      <button
        type="button"
        onClick={() => onToggle(!active)}
        data-live={active || undefined}
        aria-pressed={active}
      >
        {active ? "Cortar voz" : "Voz"}
      </button>

      {active && (
        <div className="vu" aria-hidden="true">
          {Array.from({ length: bars }, (_, index) => (
            <i key={index} data-lit={index < lit || undefined} data-hot={index > 12 || undefined} />
          ))}
        </div>
      )}

      <span className="voice-state" data-stage={stage}>
        {note ?? caption[stage]}
      </span>
    </div>
  );
}
