/**
 * Palabra de activación en el navegador.
 *
 * Esto sustituye a la escucha del puente. Un solo micrófono, el de la página,
 * y el mismo comportamiento en el PC y en el móvil.
 *
 * Cómo funciona: el micrófono está siempre abierto pero casi nunca se
 * transcribe. Un detector de energía con umbral autocalibrado decide qué
 * trozos contienen voz; solo esos van a Whisper. En silencio el coste es ~0.
 *
 * Dos fases:
 *   ESPERA   segmentos cortos, transcritos solo para buscar "Kairos". Si no
 *            aparece, se descartan y no se guarda nada.
 *   ORDEN    tras oírlo, graba la frase completa y la envía.
 *
 * Si la orden venía en la misma frase ("Kairos, pon música") no pide nada más.
 */

const RATE = 16000;
const BLOCK = 1600;

const FLOOR_MIN = 0.012;
const FLOOR_MARGIN = 3.0;
const NOISE_WINDOW = 300;

const SILENCE_END_MS = 700;
const MIN_SPEECH_BLOCKS = 6;
const UTTERANCE_MAX_MS = 15_000;
/** Tras ejecutar algo, un minuto sin necesidad de repetir la palabra. */
/**
 * Ventana de seguimiento: cuanto tiempo acepta ordenes sin repetir el nombre.
 *
 * Baja de 60 s a 12 s, y ademas se puede desactivar del todo. Motivo real:
 * con un minuto abierto, una conversacion normal en la habitacion entra
 * entera como ordenes. Que KAIROS conteste mientras hablas con alguien no es
 * un fallo de umbral —una conversacion supera cualquier umbral razonable—
 * sino de ventana demasiado generosa.
 *
 * 12 s cubre el caso util ("kairos, pon musica" ... "sube el volumen") sin
 * dejar la puerta abierta media conversacion.
 */
export const FOLLOW_UP_MS = 12_000;

/**
 * En modo estricto NO hay ventana de seguimiento: cada orden exige el nombre.
 * Es lo que quieres con gente delante.
 */
export const MODO_ESTRICTO_CLAVE = "kairos.escucha.estricta";

function modoEstricto(): boolean {
  try {
    return window.localStorage.getItem(MODO_ESTRICTO_CLAVE) === "si";
  } catch {
    return false;
  }
}

export type WakeHandlers = {
  onLevel: (rms: number) => void;
  onState: (estado: "espera" | "oyendo" | "procesando" | "seguimiento") => void;
  onUtterance: (texto: string) => void;
  onFault: (mensaje: string) => void;
};

function mediana(valores: number[]): number {
  if (!valores.length) return FLOOR_MIN;
  const orden = [...valores].sort((a, b) => a - b);
  return orden[Math.floor(orden.length / 2)];
}

export class WakeListener {
  private stream: MediaStream | null = null;
  private context: AudioContext | null = null;
  private recorder: MediaRecorder | null = null;
  private raf = 0;
  private parado = false;
  private ruido: number[] = [];
  private umbral = FLOOR_MIN;
  private despiertoHasta = 0;

  constructor(
    private readonly handlers: WakeHandlers,
    private readonly palabras: string[],
  ) {}

  async start(): Promise<void> {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
      });
    } catch {
      this.handlers.onFault(
        "Sin acceso al micrófono. Permítelo en el candado de la barra de direcciones.",
      );
      return;
    }
    this.context = new AudioContext();
    void this.bucle();
  }

  stop(): void {
    this.parado = true;
    cancelAnimationFrame(this.raf);
    if (this.recorder && this.recorder.state !== "inactive") {
      this.recorder.onstop = null;
      this.recorder.stop();
    }
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    void this.context?.close().catch(() => undefined);
    this.context = null;
  }

  /** Abre la ventana de seguimiento tras ejecutar una orden. */
  marcarActividad(): void {
    this.despiertoHasta = Date.now() + FOLLOW_UP_MS;
  }

  private async bucle(): Promise<void> {
    while (!this.parado) {
      const audio = await this.capturar();
      if (audio) console.log("[wake] capturado", audio.size, "bytes");
      if (!audio) continue;

      this.handlers.onState("procesando");
      const texto = (await this.transcribir(audio)).trim();
      console.log("[wake] oido:", JSON.stringify(texto));
      if (!texto) {
        this.handlers.onState("espera");
        continue;
      }

      // Whisper convierte cualquier ruido en la palabra más parecida que
      // conoce. Una sola palabra corta casi nunca es una orden real.
      if (texto.length < 6 && !texto.includes(" ")) {
        this.handlers.onState("espera");
        continue;
      }

      const bajo = texto.toLowerCase();
      const siguiendo = !modoEstricto() && Date.now() < this.despiertoHasta;
      // El nombre tiene que estar al PRINCIPIO de la frase, no en
      // cualquier sitio. "...y entonces le dije a kairos que..." mencionaba
      // el nombre y disparaba una orden con el resto de la frase.
      const idx = this.palabras
        .map((p) => bajo.indexOf(p))
        .filter((i) => i >= 0 && i <= 12)
        .sort((a, b) => a - b)[0];

      if (idx === undefined && !siguiendo) {
        this.handlers.onState("espera");
        continue;
      }

      // En seguimiento, una frase larga casi nunca es una orden: las ordenes
      // son cortas. Una parrafada sin el nombre delante es conversacion con
      // otra persona, y responder a eso es lo mas molesto que puede hacer.
      if (idx === undefined && texto.length > 90) {
        console.log("[wake] descartado por largo sin nombre");
        this.handlers.onState("espera");
        continue;
      }

      // La ventana de seguimiento se consume al usarla: si no, cualquier
      // ruido posterior entraba como orden y el estado se quedaba clavado en
      // "seguimiento" sin llegar a entregar nada.
      this.despiertoHasta = 0;

      let orden = texto;
      if (idx !== undefined) {
        const palabra = this.palabras.find((p) => bajo.indexOf(p) === idx) ?? "";
        orden = texto.slice(idx + palabra.length);
      }
      orden = orden.replace(/^[\s,.;:!?¡¿-]+/, "").trim();

      console.log("[wake] orden:", JSON.stringify(orden), "| siguiendo:", siguiendo);
      if (orden.length < 3) {
        // Solo la palabra: abre la ventana y espera la orden.
        this.despiertoHasta = Date.now() + FOLLOW_UP_MS;
        this.handlers.onState("seguimiento");
        continue;
      }

      console.log("[wake] ENTREGA:", JSON.stringify(orden));
      this.handlers.onUtterance(orden);
      this.handlers.onState("espera");
    }
  }

  private async transcribir(audio: Blob): Promise<string> {
    try {
      const form = new FormData();
      form.append("audio", audio, "audio.webm");
      const r = await fetch("/api/v1/voice/transcribe", {
        method: "POST",
        credentials: "same-origin",
        body: form,
      });
      if (!r.ok) return "";
      const d = (await r.json()) as { text: string; no_speech: boolean };
      return d.no_speech ? "" : d.text;
    } catch {
      return "";
    }
  }

  /** Graba mientras haya voz. El silencio decide cuándo parar. */
  private capturar(): Promise<Blob | null> {
    return new Promise((resolve) => {
      if (!this.stream || !this.context || this.parado) {
        resolve(null);
        return;
      }

      const source = this.context.createMediaStreamSource(this.stream);
      const analyser = this.context.createAnalyser();
      analyser.fftSize = 1024;
      analyser.smoothingTimeConstant = 0.6;
      source.connect(analyser);
      const muestras = new Float32Array(analyser.fftSize);

      const trozos: Blob[] = [];
      const rec = new MediaRecorder(this.stream, { mimeType: "audio/webm" });
      this.recorder = rec;
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) trozos.push(e.data);
      };

      let bloquesVoz = 0;
      let silencioDesde = 0;
      const inicio = performance.now();
      let terminado = false;

      const acabar = (entregar: boolean) => {
        if (terminado) return;
        terminado = true;
        cancelAnimationFrame(this.raf);
        rec.onstop = () => {
          source.disconnect();
          resolve(entregar && bloquesVoz >= MIN_SPEECH_BLOCKS
            ? new Blob(trozos, { type: "audio/webm" })
            : null);
        };
        if (rec.state !== "inactive") rec.stop();
        else resolve(null);
      };

      const tick = () => {
        if (this.parado) {
          acabar(false);
          return;
        }
        analyser.getFloatTimeDomainData(muestras);
        let suma = 0;
        for (const v of muestras) suma += v * v;
        const rms = Math.sqrt(suma / muestras.length);
        this.handlers.onLevel(rms);

        if (rms > this.umbral) {
          bloquesVoz += 1;
          silencioDesde = 0;
          if (bloquesVoz === MIN_SPEECH_BLOCKS) this.handlers.onState("oyendo");
        } else {
          // Ventana móvil del ruido de fondo: mediana, no media, para que un
          // portazo no mueva el umbral. Y móvil porque el ruido cambia.
          this.ruido.push(rms);
          if (this.ruido.length > NOISE_WINDOW) this.ruido.shift();
          if (this.ruido.length % 50 === 0) {
            this.umbral = Math.max(FLOOR_MIN, mediana(this.ruido) * FLOOR_MARGIN);
          }
          if (bloquesVoz) {
            if (silencioDesde === 0) silencioDesde = performance.now();
            else if (performance.now() - silencioDesde > SILENCE_END_MS) {
              acabar(true);
              return;
            }
          } else if (performance.now() - inicio > 2000) {
            acabar(false);
            return;
          }
        }

        if (performance.now() - inicio > UTTERANCE_MAX_MS) {
          acabar(true);
          return;
        }
        this.raf = requestAnimationFrame(tick);
      };

      rec.start();
      this.raf = requestAnimationFrame(tick);
    });
  }
}
