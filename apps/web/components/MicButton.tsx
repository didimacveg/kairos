"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Captura de voz con MediaRecorder.
 *
 * El texto vuelve al cuadro de escritura; no se envía solo. Whisper se
 * equivoca con nombres propios y con ruido, y con la memoria curada un
 * mensaje enviado puede convertirse en un hecho permanente.
 *
 * La pista se detiene explícitamente al terminar: si no, el navegador deja el
 * indicador de micrófono encendido y no hay forma de saber si sigue
 * escuchando. En un sistema cuya premisa es la privacidad, eso importa.
 */
export function MicButton({
  onTranscript,
  disabled,
}: {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}) {
  const [recording, setRecording] = useState(false);
  const [working, setWorking] = useState(false);
  const [fault, setFault] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const release = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => release, [release]);

  const upload = useCallback(
    async (blob: Blob) => {
      setWorking(true);
      setFault(null);
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
          throw new Error(body?.detail ?? `El núcleo respondió ${response.status}`);
        }
        const data = (await response.json()) as { text: string };
        if (data.text.trim()) onTranscript(data.text.trim());
        else setFault("No se entendió nada. Acércate al micrófono.");
      } catch (err) {
        setFault(err instanceof Error ? err.message : "Fallo al transcribir");
      } finally {
        setWorking(false);
      }
    },
    [onTranscript],
  );

  const start = useCallback(async () => {
    setFault(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      });
      streamRef.current = stream;
      chunksRef.current = [];

      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        release();
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        if (blob.size > 1000) void upload(blob);
        else setFault("Grabación demasiado corta.");
      };

      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
      setSeconds(0);
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch {
      setFault("Sin acceso al micrófono. Permítelo en el candado de la barra de direcciones.");
    }
  }, [release, upload]);

  const stop = useCallback(() => {
    recorderRef.current?.stop();
    recorderRef.current = null;
    setRecording(false);
  }, []);

  return (
    <div className="mic">
      <button
        type="button"
        onClick={() => (recording ? stop() : void start())}
        disabled={disabled || working}
        data-recording={recording || undefined}
        aria-label={recording ? "Detener grabación" : "Grabar mensaje de voz"}
      >
        {working ? "Transcribiendo" : recording ? `Detener · ${seconds}s` : "Hablar"}
      </button>
      {fault && <span className="mic-error">{fault}</span>}
    </div>
  );
}
