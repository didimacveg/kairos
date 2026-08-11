"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Console } from "@/components/Console";

export default function Page() {
  const [username, setUsername] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .me()
      .then((user) => setUsername(user.username))
      .catch(() => setUsername(null))
      .finally(() => setChecking(false));
  }, []);

  async function signIn() {
    setBusy(true);
    setError(null);
    try {
      const user = await api.login(form.username, form.password);
      setUsername(user.username);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesion");
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    await api.logout().catch(() => undefined);
    setUsername(null);
  }

  if (checking) {
    return <main className="gate"><p style={{ color: "var(--muted)" }}>Comprobando sesion…</p></main>;
  }

  if (username) {
    return <Console username={username} onSignOut={() => void signOut()} />;
  }

  return (
    <main className="gate">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void signIn();
        }}
      >
        <h1>KAIROS</h1>
        <p>Acceso local. Esta instancia no esta publicada en Internet.</p>
        <input
          aria-label="Usuario"
          autoComplete="username"
          placeholder="Usuario"
          value={form.username}
          onChange={(event) => setForm({ ...form, username: event.target.value })}
        />
        <input
          aria-label="Contrasena"
          autoComplete="current-password"
          type="password"
          placeholder="Contrasena"
          value={form.password}
          onChange={(event) => setForm({ ...form, password: event.target.value })}
        />
        {error && <div className="error">{error}</div>}
        <button type="submit" disabled={busy || !form.username || !form.password}>
          {busy ? "Verificando…" : "Entrar"}
        </button>
      </form>
    </main>
  );
}
