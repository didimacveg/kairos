/**
 * Escucha manos libres con interrupción.
 *
 * Dos modos sobre el mismo micrófono:
 *
 *  - `start()`   graba tu turno y lo cierra por silencio sostenido.
 *  - `watch()`   NO graba: solo vigila el nivel mientras KAIROS habla, para
 *                detectar que le estás interrumpiendo.
 *
 * Decisiones que evitan que esto sea insufrible:
 *
 * 1. El umbral se calibra con el ruido real de la habitación durante los
 *    primeros 400 ms. Un umbral fijo funciona en un sitio y falla en otro.
 * 2. No se corta el turno hasta haber detectado voz: si no, cualquier pausa
 *    antes de empezar a hablar cerraría la grabación vacía.
 * 3. En modo vigilancia el umbral es MÁS ALTO y exige voz sostenida. El
 *    altavoz reproduciendo a KAIROS entra por el micro, y la cancelación de
 *    eco del navegador ayuda pero no es perfecta. Sin ese margen, KAIROS se
 *    interrumpiría a sí mismo.
 */

export type ListenHandlers = {
  onLevel: (rms: number) => void;
  onSpeechStart: () => void;
  onDone: (audio: Blob) => void;
  onFault: (message: string) => void;
};

export type ListenOptions = {
  silenceMs?: number;
  maxMs?: number;
};

const CALIBRATION_MS = 400;
const FLOOR_MIN = 0.014;
const FLOOR_MARGIN = 2.8;
/** Margen extra sobre el umbral normal para dar por buena una interrupción. */
// Margen sobre el ruido ambiente YA CALIBRADO. Se recalibra en cada turno,
// asi que ventiladores y aire acondicionado entran en la medida base. Sube
// este valor si KAIROS se calla solo; bajalo si cuesta interrumpirle.
const BARGE_MARGIN = 2.4;
/** Voz sostenida necesaria para interrumpir. Un golpe seco no basta. */
const BARGE_SUSTAIN_MS = 220;

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

  private async openMic(): Promise<AnalyserNode | null> {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
      });
    } catch {
      this.handlers.onFault(
        "Sin acceso al micrófono. Permítelo en el candado de la barra de direcciones.",
      );
      return null;
    }
    this.context = new AudioContext();
    const source = this.context.createMediaStreamSource(this.stream);
    const analyser = this.context.createAnalyser();
    analyser.fftSize = 1024;
    analyser.smoothingTimeConstant = 0.6;
    source.connect(analyser);
    return analyser;
  }

  /**
   * Vigila el nivel sin grabar, con DOS umbrales:
   *
   *  - `onHush` salta al primer indicio de voz. Calla el altavoz al instante.
   *  - `onBarge` salta si la voz se sostiene. Aborta la generación.
   *
   * Separarlos es lo que arregla el solapamiento: antes había que esperar a
   * confirmar la interrupción y durante ese tiempo se oían dos voces. Ahora
   * el silencio es inmediato y la decisión de cortar viene después. Si era un
   * ruido y no tú, el audio se reanuda solo en la frase siguiente.
   */
  async watch(onBarge: () => void, onHush?: () => void): Promise<void> {
    const analyser = await this.openMic();
    if (!analyser) return;

    const samples = new Float32Array(analyser.fftSize);
    const started = performance.now();
    let floor = FLOOR_MIN;
    let calibrating = true;
    let noiseSum = 0;
    let noiseCount = 0;
    let loudSince = 0;
    let hushed = false;

    const tick = () => {
      if (this.stopping) return;
      analyser.getFloatTimeDomainData(samples);
      let sum = 0;
      for (const v of samples) sum += v * v;
      const rms = Math.sqrt(sum / samples.length);
      this.handlers.onLevel(rms);

      const elapsed = performance.now() - started;
      if (calibrating) {
        noiseSum += rms;
        noiseCount += 1;
        if (elapsed > CALIBRATION_MS) {
          floor = Math.max(FLOOR_MIN, (noiseSum / noiseCount) * FLOOR_MARGIN) * BARGE_MARGIN;
          calibrating = false;
        }
      } else if (rms > floor) {
        if (loudSince === 0) {
          loudSince = performance.now();
          // Callar primero, preguntar después.
          if (!hushed) {
            hushed = true;
            onHush?.();
          }
        } else if (performance.now() - loudSince > BARGE_SUSTAIN_MS) {
          this.abort();
          onBarge();
          return;
        }
      } else {
        loudSince = 0;
        hushed = false;
      }

      this.raf = requestAnimationFrame(tick);
    };

    this.raf = requestAnimationFrame(tick);
  }

  async start(): Promise<void> {
    const silenceMs = this.options.silenceMs ?? 1100;
    const maxMs = this.options.maxMs ?? 30_000;

    const analyser = await this.openMic();
    if (!analyser) return;

    const samples = new Float32Array(analyser.fftSize);
    const started = performance.now();

    let floor = FLOOR_MIN;
    let calibrating = true;
    let noiseSum = 0;
    let noiseCount = 0;
    let heardSpeech = false;
    let quietSince = 0;

    const tick = () => {
      if (this.stopping) return;
      analyser.getFloatTimeDomainData(samples);
      let sum = 0;
      for (const v of samples) sum += v * v;
      const rms = Math.sqrt(sum / samples.length);
      this.handlers.onLevel(rms);

      const elapsed = performance.now() - started;

      if (calibrating) {
        noiseSum += rms;
        noiseCount += 1;
        if (elapsed > CALIBRATION_MS) {
          floor = Math.max(FLOOR_MIN, (noiseSum / noiseCount) * FLOOR_MARGIN);
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
    const recorder = new MediaRecorder(this.stream as MediaStream, { mimeType: "audio/webm" });
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

  /** Corta sin entregar audio. */
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
