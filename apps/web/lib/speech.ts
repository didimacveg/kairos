/**
 * Cola de habla — KAIROS habla mientras todavía está pensando.
 *
 * Si esperas a que el modelo termine la respuesta entera antes de sintetizar,
 * cada respuesta hablada arranca con varios segundos de silencio y conversar
 * se vuelve insoportable.
 *
 * Solución: trocear el flujo de tokens por frases. En cuanto una frase está
 * completa se manda a sintetizar, y se reproduce mientras el modelo genera las
 * siguientes. La síntesis de la frase N ocurre durante la reproducción de N-1.
 *
 * El orden importa más que la velocidad: reproducir la frase 3 antes que la 2
 * porque tardó menos en sintetizarse haría el audio incomprensible. Por eso la
 * cola es estrictamente secuencial.
 */


/**
 * FastAPI devuelve `detail` como texto en los errores propios, pero como
 * ARRAY de objetos en los de validación. Meter ese array en `new Error()`
 * producía el "[object Object]" que aparecía en pantalla.
 */
function detailToText(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: string } | undefined;
    return first?.msg ?? "El servicio de voz rechazó el texto";
  }
  return "No se pudo sintetizar";
}

function describe(err: unknown): string {
  return err instanceof Error ? err.message : "Fallo al hablar";
}

const SENTENCE_END = /([.!?…]+|\n)/;
const MIN_CHARS = 40;


const MAX_SPOKEN = 700;

/** Trocea un fragmento demasiado largo por comas, sin partir palabras. */
function split(text: string): string[] {
  if (text.length <= MAX_SPOKEN) return [text];
  const out: string[] = [];
  let current = "";
  // Se parte por punto y coma o dos puntos, nunca por comas: una coma no
  // es final de frase y cortar ahi hace que la voz baje el tono a media
  // idea, que es lo que sonaba antinatural.
  for (const part of text.split(/(?<=[;:])\s*/)) {
    if ((current + part).length > MAX_SPOKEN && current) {
      out.push(current.trim());
      current = part;
    } else {
      current += part;
    }
  }
  if (current.trim()) out.push(current.trim());
  return out;
}

/**
 * Cuántas frases se sintetizan por delante de la que suena.
 *
 * Dos y no más: cada frase adelantada es audio que quizás no llegue a sonar
 * si interrumpes, y con la voz de ElevenLabs eso es cuota gastada para nada.
 * Dos cubre el hueco entre frases sin desperdiciar apenas.
 */
const PRECARGA = 2;

export class SpeechQueue {
  private pending: string[] = [];
  private buffer = "";
  private playing = false;
  private stopped = false;
  private current: HTMLAudioElement | null = null;
  private urls: string[] = [];

  constructor(private readonly onFault?: (message: string) => void) {}

  /** Alimenta el buffer con tokens según llegan del stream. */
  push(chunk: string): void {
    if (this.stopped) return;
    this.buffer += chunk;

    for (;;) {
      const match = SENTENCE_END.exec(this.buffer);
      if (!match || match.index === undefined) break;
      const cut = match.index + match[0].length;
      const sentence = this.buffer.slice(0, cut).trim();
      const rest = this.buffer.slice(cut);
      // Fragmentos muy cortos ("Sí.", "Vale.") se acumulan con el siguiente:
      // una petición de síntesis por monosílabo satura el servicio.
      if (sentence.length >= MIN_CHARS) {
        this.buffer = rest;
        // Una "frase" sin puntuación puede ser un párrafo entero. Se trocea
        // por comas para que la síntesis no se atragante ni tarde una
        // eternidad en devolver el primer audio.
        for (const piece of split(sentence)) this.pending.push(piece);
        void this.drain();
      } else {
        break;
      }
    }
  }

  /** Vacía lo que quede en el buffer al terminar el stream. */
  flush(): void {
    if (this.stopped) return;
    const tail = this.buffer.trim();
    this.buffer = "";
    if (tail) {
      this.pending.push(tail);
      void this.drain();
    }
  }

  /** Corta el habla de inmediato y libera los objetos de audio. */
  stop(): void {
    this.stopped = true;
    this.pending = [];
    this.buffer = "";
    if (this.current) {
      this.current.pause();
      this.current = null;
    }
    this.urls.forEach((url) => URL.revokeObjectURL(url));
    this.urls = [];
  }

  get speaking(): boolean {
    return this.playing || this.pending.length > 0;
  }

  /**
   * Reproduce en orden, pero SINTETIZA POR ADELANTADO.
   *
   * Antes esto era estrictamente secuencial: pedir el audio, esperar,
   * reproducir, pedir el siguiente. Entre frase y frase quedaban 300-500 ms
   * de silencio — la ida y vuelta al servicio de voz. En una respuesta de
   * cinco frases, dos segundos de huecos que hacen que KAIROS suene
   * entrecortado aunque cada frase suene bien.
   *
   * Ahora mientras suena la frase 1 ya se están sintetizando la 2 y la 3.
   * El orden de reproducción sigue siendo estricto: reproducir la 3 antes
   * que la 2 porque tardó menos haría el audio incomprensible.
   */
  private async drain(): Promise<void> {
    if (this.playing || this.stopped) return;
    this.playing = true;

    // Peticiones lanzadas, en orden. Cada una es una promesa de audio.
    const enVuelo: Promise<string | null>[] = [];

    const pedir = (frase: string): Promise<string | null> =>
      fetch("/api/v1/voice/speak", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: frase }),
      })
        .then(async (response) => {
          if (!response.ok) {
            const body = (await response.json().catch(() => null)) as
              | { detail?: unknown }
              | null;
            throw new Error(detailToText(body?.detail));
          }
          const url = URL.createObjectURL(await response.blob());
          this.urls.push(url);
          return url;
        })
        .catch((err) => {
          // Un fallo en UNA frase no calla el resto de la respuesta.
          this.onFault?.(describe(err));
          return null;
        });

    while ((this.pending.length > 0 || enVuelo.length > 0) && !this.stopped) {
      // Se rellena el adelanto hasta PRECARGA peticiones simultáneas.
      while (enVuelo.length <= PRECARGA && this.pending.length > 0) {
        enVuelo.push(pedir(this.pending.shift() as string));
      }

      const siguiente = enVuelo.shift();
      if (!siguiente) break;

      const url = await siguiente;
      if (this.stopped) break;
      if (url) await this.play(url);
    }

    this.playing = false;
  }

  private play(url: string): Promise<void> {
    return new Promise((resolve) => {
      const audio = new Audio(url);
      this.current = audio;
      const done = () => {
        this.current = null;
        resolve();
      };
      audio.onended = done;
      audio.onerror = done;
      audio.play().catch(done);
    });
  }
}
