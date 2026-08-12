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

const SENTENCE_END = /([.!?…]+|\n)/;
const MIN_CHARS = 12;

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
        this.pending.push(sentence);
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

  private async drain(): Promise<void> {
    if (this.playing || this.stopped) return;
    this.playing = true;

    while (this.pending.length > 0 && !this.stopped) {
      const sentence = this.pending.shift() as string;
      try {
        const response = await fetch("/api/v1/voice/speak", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: sentence }),
        });
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { detail?: string } | null;
          throw new Error(body?.detail ?? "No se pudo sintetizar");
        }
        if (this.stopped) break;
        const url = URL.createObjectURL(await response.blob());
        this.urls.push(url);
        await this.play(url);
      } catch (err) {
        this.onFault?.(err instanceof Error ? err.message : "Fallo al hablar");
        break;
      }
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
