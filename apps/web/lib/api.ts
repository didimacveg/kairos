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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? "Error desconocido");
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export const api = {
  health: () => request<Health>("/api/v1/health"),
  me: () => request<{ username: string; role: string }>("/api/v1/auth/me"),
  login: (username: string, password: string) =>
    request<{ username: string; role: string }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<void>("/api/v1/auth/logout", { method: "POST" }),
  chat: (message: string, conversationId: string | null) =>
    request<ChatResponse>("/api/v1/chat", {
      method: "POST",
      body: JSON.stringify({ message, conversation_id: conversationId }),
    }),
};
