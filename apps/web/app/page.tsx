"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Console } from "@/components/Console";

/**
 * Puerta de acceso.
 *
 * La secuencia de arranque no es teatro: son las comprobaciones que el cliente
 * hace de verdad al cargar — sesión y estado del núcleo. Si el núcleo está
 * caído, lo dice antes de que escribas una contraseña que no va a servir.
 */
const CHECKS = ["Contactando con el núcleo", "Comprobando agentes", "Verificando sesión"];

export default function Page() {
  const [username, setUsername] = useState<string | null>(null);
  const [phase, setPhase] = useState(0);
  const [booting, setBooting] = useState(true);
  const [coreDown, setCoreDown] = useState(false);
  const [form, setForm] = useState({ username: "", password: "" });
  const [fault, setFault] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      setPhase(0);
      const alive = await api
        .health()
        .then(() => true)
        .catch(() => false);
      if (cancelled) return;
      if (!alive) {
        setCoreDown(true);
        setBooting(false);
        return;
      }

      setPhase(1);
      await new Promise((r) => setTimeout(r, 180));
      if (cancelled) return;

      setPhase(2);
      const me = await api.me().catch(() => null);
      if (cancelled) return;
      if (me) setUsername(me.username);
      setBooting(false);
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async () => {
    setBusy(true);
    setFault(null);
    try {
      const user = await api.login(form.username, form.password);
      setUsername(user.username);
    } catch (err) {
      setFault(err instanceof Error ? err.message : "No se pudo iniciar sesión");
    } finally {
      setBusy(false);
    }
  }, [form]);

  const signOut = useCallback(async () => {
    await api.logout().catch(() => undefined);
    setUsername(null);
  }, []);

  if (username) {
    return <Console username={username} onSignOut={() => void signOut()} />;
  }

  return (
    <main className="airlock">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void signIn();
        }}
      >
        <h1 className="mark">KAIROS</h1>
        <p className="sub">Sistema local · sin acceso remoto</p>

        <p className="boot">
          {booting ? (
            <>
              <b>·</b> {CHECKS[phase]}…
            </>
          ) : coreDown ? (
            ""
          ) : (
            <>
              <b>·</b> Núcleo en línea. Identifícate.
            </>
          )}
        </p>

        {coreDown && (
          <div className="fault">
            El núcleo no responde. Arráncalo con <b>docker compose up -d</b> y recarga.
          </div>
        )}

        <input
          aria-label="Usuario"
          autoComplete="username"
          placeholder="Usuario"
          value={form.username}
          disabled={booting || coreDown}
          onChange={(event) => setForm({ ...form, username: event.target.value })}
        />
        <input
          aria-label="Contraseña"
          autoComplete="current-password"
          type="password"
          placeholder="Contraseña"
          value={form.password}
          disabled={booting || coreDown}
          onChange={(event) => setForm({ ...form, password: event.target.value })}
        />

        {fault && <div className="fault">{fault}</div>}

        <button
          type="submit"
          data-primary
          disabled={busy || booting || coreDown || !form.username || !form.password}
        >
          {busy ? "Verificando" : "Entrar"}
        </button>
      </form>
    </main>
  );
}
