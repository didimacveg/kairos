"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Captura de voz con MediaRecorder.
 *
 * El micrófono vive en el navegador (ADR 0008). El audio se graba, se manda
 * al núcleo y vuelve como texto al cuadro de escritura — NO se envía solo.
 * Ver la transcripción antes de mandarla es lo que evita que un error de
 * reconocimiento acabe en la memoria permanente.
 *
 * La pista se detiene explícitamente al terminar: si no, el navegador deja el
 * indicador de micrófono encendido y el usuario no puede saber si sigue
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
  const [error, setError] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const releaseMic = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // Si el componente se desmonta grabando, el micro se libera igualmente.
  useEffect(() => releaseMic, [releaseMic]);

  const send = useCallback(
    async (blob: Blob) => {
      setWorking(true);
      setError(null);
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
        if (data.text.trim()) {
          onTranscript(data.text.trim());
        } else {
          setError("No se entendió nada. Prueba a hablar más cerca del micrófono.");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Fallo al transcribir");
      } finally {
        setWorking(false);
      }
    },
    [onTranscript],
  );

  const start = useCallback(async () => {
    setError(null);
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
        releaseMic();
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        if (blob.size > 1000) void send(blob);
        else setError("Grabación demasiado corta.");
      };

      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
      setSeconds(0);
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch {
      setError("Sin acceso al micrófono. Permítelo en el candado de la barra de direcciones.");
    }
  }, [releaseMic, send]);

  const stop = useCallback(() => {
    recorderRef.current?.stop();
    recorderRef.current = null;
    setRecording(false);
  }, []);

  const label = working ? "Transcribiendo…" : recording ? `Detener ${seconds}s` : "Hablar";

  return (
    <div className="mic">
      <button
        type="button"
        onClick={() => (recording ? stop() : void start())}
        disabled={disabled || working}
        data-recording={recording || undefined}
        aria-label={recording ? "Detener grabación" : "Grabar mensaje de voz"}
      >
        {label}
      </button>
      {error && <span className="mic-error">{error}</span>}
    </div>
  );
}
