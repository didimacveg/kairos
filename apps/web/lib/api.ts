/**
 * Cliente HTTP del núcleo de KAIROS.
 *
 * Todas las peticiones van al mismo origen: Next.js las reenvía al core por
 * `rewrites`. Eso mantiene la cookie de sesión en SameSite=Strict y evita CORS.
 *
 * Desde la Fase 2A el chat va por SSE. Ya no hay timeout de generación: el
 * primer token llega en milisegundos y el flujo se mantiene abierto mientras
 * el modelo escribe. El timeout se conserva solo para las llamadas cortas,
 * donde no responder rápido sí significa que algo está caído.
 */

export type MemoryHit = {
  id: string;
  content: string;
  kind: string;
  similarity: number;
  created_at: string;
};

export type TraceEntry = {
  agent: string;
  step: string;
  detail: Record<string, unknown>;
  duration_ms: number | null;
};

export type ChatResponse = {
  conversation_id: string;
  reply: string;
  model: string;
  latency_ms: number;
  local: boolean;
  memories: MemoryHit[];
  trace: TraceEntry[];
};

export type Health = {
  status: string;
  instance: string;
  egress_allowed: boolean;
  agents: { agent: string; status: string; [k: string]: unknown }[];
};

export type User = {
  id: string;
  username: string;
  role: string;
};

/** Eventos que emite POST /api/v1/chat/stream. */
export type StreamEvent =
  | { type: "token"; text: string }
  | { type: "trace"; trace?: TraceEntry; data?: Record<string, unknown> }
  | { type: "end"; data: ChatStreamEnd }
  | { type: "error"; error: string };

export type ChatStreamEnd = {
  conversation_id: string;
  model: string | null;
  latency_ms: number | null;
  local: boolean;
  memories: MemoryHit[];
  trace: TraceEntry[];
};

export type StreamHandlers = {
  onToken: (text: string) => void;
  onTrace?: (trace: TraceEntry | undefined, data: Record<string, unknown>) => void;
  onEnd: (summary: ChatStreamEnd) => void;
  onError: (message: string) => void;
};

const TIMEOUT_QUICK_MS = 10_000;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
    readonly kind: "http" | "timeout" | "network",
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs: number = TIMEOUT_QUICK_MS,
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(path, {
      ...init,
      credentials: "same-origin",
      signal: AbortSignal.timeout(timeoutMs),
      headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "TimeoutError") {
      throw new ApiError(
        `El núcleo no respondió en ${Math.round(timeoutMs / 1000)} s.`,
        null,
        "timeout",
      );
    }
    throw new ApiError(
      "No se pudo contactar con el núcleo. Comprueba que el contenedor `core` está arriba.",
      null,
      "network",
    );
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(body?.detail ?? response.statusText, response.status, "http");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

/**
 * Consume el flujo SSE del núcleo.
 *
 * SSE separa eventos con una línea en blanco. El buffer es necesario porque
 * un chunk de red puede partir un evento por la mitad: no hay garantía de que
 * cada lectura contenga eventos completos.
 *
 * Devuelve una función para abortar (la usa el botón de detener).
 */
export function streamChat(
  message: string,
  conversationId: string | null,
  handlers: StreamHandlers,
  attachments: string[] = [],
): () => void {
  const controller = new AbortController();

  void (async () => {
    let ended = false;
    try {
      const response = await fetch("/api/v1/chat/stream", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, conversation_id: conversationId, attachments }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null;
        handlers.onError(body?.detail ?? `El núcleo respondió ${response.status}`);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        let boundary = buffer.indexOf("\n\n");
        while (boundary !== -1) {
          const frame = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          boundary = buffer.indexOf("\n\n");

          const line = frame.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;

          let event: StreamEvent;
          try {
            event = JSON.parse(line.slice(6)) as StreamEvent;
          } catch {
            continue;
          }

          switch (event.type) {
            case "token":
              handlers.onToken(event.text);
              break;
            case "trace":
              handlers.onTrace?.(event.trace, event.data ?? {});
              break;
            case "end":
              ended = true;
              handlers.onEnd(event.data);
              break;
            case "error":
              ended = true;
              handlers.onError(event.error);
              break;
          }
        }
      }

      // El flujo terminó sin evento terminal: la conexión se cortó.
      if (!ended) {
        handlers.onError("El flujo se interrumpió antes de completarse.");
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      handlers.onError(err instanceof Error ? err.message : "Fallo en el flujo");
    }
  })();

  return () => controller.abort();
}

export const api = {
  health: () => request<Health>("/api/v1/health"),

  me: () => request<User>("/api/v1/auth/me"),

  login: (username: string, password: string) =>
    request<User>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  logout: () => request<void>("/api/v1/auth/logout", { method: "POST" }),

  /** Ruta sin streaming. Se conserva para depurar con curl. */
  chat: (message: string, conversationId: string | null) =>
    request<ChatResponse>(
      "/api/v1/chat",
      { method: "POST", body: JSON.stringify({ message, conversation_id: conversationId }) },
      300_000,
    ),

  streamChat,
};
