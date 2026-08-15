"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type Attached = { id: string; url: string; name: string };

/**
 * Imágenes adjuntas al mensaje.
 *
 * Dos vías de entrada, y la segunda es la que de verdad se usa: soltar un
 * fichero, o **pegar con Ctrl+V**. Haces Win+Shift+S, recortas lo que sea, y
 * lo pegas directamente en la conversación sin pasar por el explorador.
 *
 * Aviso deliberado sobre privacidad: el modelo local no ve imágenes, así que
 * analizarlas implica que salgan de la máquina. La interfaz lo dice en vez de
 * darlo por sabido.
 */
export function Attachments({
  items,
  onAdd,
  onRemove,
  egress,
}: {
  items: Attached[];
  onAdd: (item: Attached) => void;
  onRemove: (id: string) => void;
  egress: boolean;
}) {
  const [subiendo, setSubiendo] = useState(false);
  const [fallo, setFallo] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const subir = useCallback(
    async (file: File) => {
      setSubiendo(true);
      setFallo(null);
      try {
        const form = new FormData();
        form.append("file", file, file.name || "imagen.png");
        const response = await fetch("/api/v1/files", {
          method: "POST",
          credentials: "same-origin",
          body: form,
        });
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { detail?: string } | null;
          throw new Error(body?.detail ?? `El núcleo respondió ${response.status}`);
        }
        const data = (await response.json()) as { id: string };
        onAdd({ id: data.id, url: URL.createObjectURL(file), name: file.name || "captura" });
      } catch (err) {
        setFallo(err instanceof Error ? err.message : "No se pudo subir");
      } finally {
        setSubiendo(false);
      }
    },
    [onAdd],
  );

  // Pegar desde el portapapeles en cualquier parte de la página.
  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      const files = Array.from(event.clipboardData?.files ?? []);
      const imagenes = files.filter((f) => f.type.startsWith("image/"));
      if (imagenes.length === 0) return;
      event.preventDefault();
      imagenes.slice(0, 4).forEach((f) => void subir(f));
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [subir]);

  const quitar = async (id: string) => {
    // Borrado real en el servidor, no solo quitarlo de la lista.
    await fetch(`/api/v1/files/${id}`, { method: "DELETE", credentials: "same-origin" }).catch(
      () => undefined,
    );
    onRemove(id);
  };

  return (
    <div className="attach">
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        multiple
        hidden
        onChange={(event) => {
          Array.from(event.target.files ?? []).slice(0, 4).forEach((f) => void subir(f));
          event.target.value = "";
        }}
      />

      {items.length > 0 && (
        <div className="attach-list">
          {items.map((item) => (
            <figure key={item.id}>
              <img src={item.url} alt={item.name} />
              <button type="button" onClick={() => void quitar(item.id)} aria-label="Quitar">
                ×
              </button>
            </figure>
          ))}
        </div>
      )}

      <button type="button" onClick={() => inputRef.current?.click()} disabled={subiendo}>
        {subiendo ? "Subiendo" : "Imagen"}
      </button>

      {items.length > 0 && !egress && (
        <span className="attach-warn">
          Sin salida a Internet, el modelo local no puede ver imágenes.
        </span>
      )}
      {items.length > 0 && egress && (
        <span className="attach-note">La imagen saldrá de esta máquina para analizarse.</span>
      )}
      {fallo && <span className="attach-warn">{fallo}</span>}
    </div>
  );
}
