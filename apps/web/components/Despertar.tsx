"use client";

import { useEffect, useState } from "react";

/**
 * El momento en que KAIROS te oye.
 *
 * Se dispara cuando la escucha ambiente reconoce su nombre. Es el único
 * elemento de la interfaz que responde a algo del mundo físico, y por eso es
 * el único al que se le permite ocupar la pantalla entera.
 *
 * Dura 1,4 s y no se puede encadenar: si vuelves a decir su nombre mientras
 * suena, se ignora. Una animación que se repite sobre sí misma deja de leerse
 * como un evento y pasa a leerse como un fallo.
 */
export function Despertar({ activo }: { activo: boolean }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!activo) return;
    setVisible(true);
    const id = setTimeout(() => setVisible(false), 1400);
    return () => clearTimeout(id);
  }, [activo]);

  if (!visible) return null;

  return (
    <div className="despertar" aria-hidden="true">
      <div className="despertar-flash" />
      <div className="despertar-onda" />
      <div className="despertar-onda" />
      <div className="despertar-onda" />
      <span className="despertar-marca">KAIROS</span>
    </div>
  );
}
