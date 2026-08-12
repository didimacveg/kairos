/**
 * Escucha manos libres.
 *
 * Graba, mide el nivel en tiempo real y cierra el turno por silencio
 * sostenido. Sin botón de enviar: hablas, callas, y se manda solo.
 *
 * Dos decisiones que evitan que esto sea insufrible:
 *
 * 1. El umbral se calibra con el ruido real de la habitación durante los
 *    primeros 400 ms. Un umbral fijo funciona en un sitio y falla en otro.
 * 2. No se corta hasta haber detectado voz. Si no, cualquier pausa antes de
 *    empezar a hablar cerraría la grabación vacía.
 */

export type ListenHandlers = {
  onLevel: (rms: number) => void;
  onSpeechStart: () => void;
  onDone: (audio: Blob) => void;
  onFault: (message: string) => void;
};

export type ListenOptions = {
  /** Silencio sostenido que cierra el turno. */
  silenceMs?: number;
  /** Tope duro por si el micro capta ruido continuo. */
  maxMs?: number;
};

export class Listener {
  private recorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private context: AudioContext | null = null;
  private chunks: Blob[] = [];
  private raf = 0;
  private stopping = false;

  constructor(
    private readonly handlers: ListenHandlers,
    private readonly options: ListenOptions = {},
  ) {}

  async start(): Promise<void> {
    const silenceMs = this.options.silenceMs ?? 1100;
    const maxMs = this.options.maxMs ?? 30_000;

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      });
    } catch {
      this.handlers.onFault(
        "Sin acceso al micrófono. Permítelo en el candado de la barra de direcciones.",
      );
      return;
    }

    this.context = new AudioContext();
    const source = this.context.createMediaStreamSource(this.stream);
    const analyser = this.context.createAnalyser();
    analyser.fftSize = 1024;
    analyser.smoothingTimeConstant = 0.6;
    source.connect(analyser);

    const samples = new Float32Array(analyser.fftSize);
    const started = performance.now();

    let floor = 0.014;
    let calibrating = true;
    let noiseSum = 0;
    let noiseCount = 0;
    let heardSpeech = false;
    let quietSince = 0;

    const tick = () => {
      if (this.stopping) return;
      analyser.getFloatTimeDomainData(samples);

      let sum = 0;
      for (const value of samples) sum += value * value;
      const rms = Math.sqrt(sum / samples.length);
      this.handlers.onLevel(rms);

      const elapsed = performance.now() - started;

      if (calibrating) {
        noiseSum += rms;
        noiseCount += 1;
        if (elapsed > 400) {
          // Margen sobre el ruido ambiente, con suelo mínimo por si el micro
          // está silenciado y la media sale casi cero.
          floor = Math.max(0.014, (noiseSum / noiseCount) * 2.8);
          calibrating = false;
        }
      } else if (rms > floor) {
        if (!heardSpeech) {
          heardSpeech = true;
          this.handlers.onSpeechStart();
        }
        quietSince = 0;
      } else if (heardSpeech) {
        if (quietSince === 0) quietSince = performance.now();
        else if (performance.now() - quietSince > silenceMs) {
          this.stop();
          return;
        }
      }

      if (elapsed > maxMs) {
        this.stop();
        return;
      }

      this.raf = requestAnimationFrame(tick);
    };

    this.chunks = [];
    const recorder = new MediaRecorder(this.stream, { mimeType: "audio/webm" });
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) this.chunks.push(event.data);
    };
    recorder.onstop = () => {
      this.release();
      const blob = new Blob(this.chunks, { type: "audio/webm" });
      if (!heardSpeech || blob.size < 1200) {
        this.handlers.onFault("No he oído nada.");
        return;
      }
      this.handlers.onDone(blob);
    };
    recorder.start();
    this.recorder = recorder;

    this.raf = requestAnimationFrame(tick);
  }

  stop(): void {
    if (this.stopping) return;
    this.stopping = true;
    cancelAnimationFrame(this.raf);
    if (this.recorder && this.recorder.state !== "inactive") this.recorder.stop();
    else this.release();
  }

  /** Corta sin entregar audio: para abortar un turno. */
  abort(): void {
    this.stopping = true;
    cancelAnimationFrame(this.raf);
    if (this.recorder) {
      this.recorder.onstop = null;
      if (this.recorder.state !== "inactive") this.recorder.stop();
    }
    this.release();
  }

  private release(): void {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    void this.context?.close().catch(() => undefined);
    this.context = null;
    this.recorder = null;
  }
}
