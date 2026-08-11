# Modelo de amenazas — Fase 1

Un modelo de amenazas sin activos ni adversarios nombrados no sirve para nada.
Estos son los de esta fase; se revisa al cerrar cada fase.

## Activos

| Activo | Por que importa |
|---|---|
| Memoria semantica (`memory_items`) | Perfil acumulado del propietario: habitos, planes, opiniones |
| Historial de conversaciones | Contenido literal de todo lo dicho al sistema |
| Credencial del propietario | Da acceso a todo lo anterior |
| Secreto de instancia | Permite forjar sesiones si se filtra junto con la BD |
| Auditoria | Es la unica evidencia de que paso algo |

## Adversarios considerados

1. **Alguien con acceso fisico al ordenador desbloqueado.** Realista en una casa
   compartida. Mitigacion parcial: sesion con caducidad, cookie HttpOnly. No
   mitigado: cifrado de disco es responsabilidad del sistema operativo, no de
   KAIROS. **Actua: activa BitLocker o LUKS.**
2. **Otro dispositivo de la misma red WiFi.** Mitigacion: ningun puerto se
   publica fuera de `127.0.0.1`. Exponer a la LAN es una decision explicita que
   exige TLS y repensar esta seccion.
3. **Exfiltracion por dependencia comprometida.** Una libreria maliciosa en el
   backend tendria acceso a la BD. Mitigacion: contenedor sin capacidades
   (`cap_drop: ALL`), sistema de ficheros de solo lectura, usuario no root,
   `KAIROS_ALLOW_EGRESS=false` como interruptor central. No mitigado del todo:
   fija versiones y revisa el lockfile.
4. **Fuga por proveedor remoto.** Mitigacion: bloqueo por configuracion en el
   agente, no solo por ausencia de clave.

## Fuera de alcance en Fase 1

- Adversario con root en la maquina anfitriona. Si tiene root, ha ganado.
- Ataques de canal lateral sobre el modelo local.
- Terceros grabados por camaras: **entra en Fase 3** y se trata en
  `camaras-y-consentimiento.md`. Es el mayor riesgo del proyecto entero.

## Lo que Docker **no** hace aqui

Los contenedores comparten kernel con el anfitrion. Son una herramienta de
reproducibilidad y de contencion de fallos, no una frontera de seguridad frente
a codigo hostil. En particular, el futuro Automation Agent (Fase 4) ejecutara
acciones sobre el sistema real: su seguridad vendra de una lista blanca de
acciones y de confirmacion humana explicita, no de estar en un contenedor.

## Controles activos en Fase 1

- Argon2id (t=3, m=64 MiB, p=4) para contrasenas; minimo 12 caracteres.
- Verificacion de contrasena a tiempo constante aunque el usuario no exista.
- Tokens de sesion de 32 bytes; en la BD solo se guarda su HMAC-SHA256.
- Cookie `HttpOnly` + `SameSite=Strict`; `Secure` configurable.
- `audit_log` append-only, reforzado con trigger en Postgres.
- CSP restrictiva, `X-Frame-Options: DENY`, `nosniff`, `no-referrer`.
- `TrustedHostMiddleware` con lista blanca de hosts.
- Contenedores: `no-new-privileges`, `read_only`, `cap_drop: ALL`, usuario 10001.
