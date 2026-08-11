/**
 * Cliente HTTP del núcleo de KAIROS.
 *
 * Todas las peticiones van al mismo origen: Next.js las reenvía al core por
 * `rewrites`. Eso mantiene la cookie de sesión en SameSite=Strict y evita CORS.
 *
 * Los timeouts son explícitos y distintos por operación: la generación con un
 * modelo local puede tardar minutos en frío (primera petición tras arrancar,
 * cuando Ollama carga los pesos en VRAM), mientras que un health check que no
 * responde en 10 s está roto de verdad.
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

/** Generación con modelo local: en frío puede superar el minuto. */
const TIMEOUT_CHAT_MS = 300_000;
/** Consultas ligeras: si no responden rápido, algo está caído. */
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
    // AbortSignal.timeout lanza TimeoutError; el resto son fallos de red.
    if (err instanceof DOMException && err.name === "TimeoutError") {
      throw new ApiError(
        `El núcleo no respondió en ${Math.round(timeoutMs / 1000)} s. ` +
          "Si es la primera petición tras arrancar, Ollama está cargando el modelo en VRAM.",
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

export const api = {
  health: () => request<Health>("/api/v1/health"),

  me: () => request<User>("/api/v1/auth/me"),

  login: (username: string, password: string) =>
    request<User>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  logout: () => request<void>("/api/v1/auth/logout", { method: "POST" }),

  chat: (message: string, conversationId: string | null) =>
    request<ChatResponse>(
      "/api/v1/chat",
      { method: "POST", body: JSON.stringify({ message, conversation_id: conversationId }) },
      TIMEOUT_CHAT_MS,
    ),
};