# KAIROS en el móvil, con voz

## Lo que estás montando

Tu PC sigue sin un solo puerto abierto a Internet. Tailscale crea una red
cifrada entre **tus** dispositivos: para el móvil, KAIROS aparece como si
estuviera en la misma habitación, y para el resto del mundo no existe.

Y con HTTPS dentro de esa red, el micrófono del móvil funciona — los
navegadores solo lo permiten en orígenes seguros.

## 1. En el PC — Tailscale

Descarga de `tailscale.com/download/windows`, instala, e inicia sesión con
Google o GitHub.

**POWERSHELL**:

```powershell
tailscale status
```

Anota el nombre completo de tu máquina: algo como `mazor.tail1234.ts.net`.

## 2. En el PC — activar HTTPS

**POWERSHELL COMO ADMINISTRADOR**:

```powershell
tailscale cert (tailscale status --json | ConvertFrom-Json).Self.DNSName.TrimEnd('.')
tailscale serve --bg 3000
tailscale serve status
```

El primero pide el certificado (una vez). El segundo pone a Tailscale a
escuchar en HTTPS y reenviar a `localhost:3000`.

Si `tailscale cert` falla, entra en `login.tailscale.com/admin/dns` y activa
**HTTPS Certificates**. Es un interruptor.

## 3. En el PC — configurar KAIROS

**UBUNTU**, con tu dominio:

```bash
cd /home/diego/kairos-os
bash scripts/movil-https.sh mazor.tail1234.ts.net
docker compose up -d --force-recreate core web
make estado
```

## 4. En el móvil

Instala Tailscale, inicia sesión con la misma cuenta, activa la VPN. Abre:

```
https://mazor.tail1234.ts.net
```

Sin puerto: Tailscale sirve en el 443. Entra con tu usuario de siempre.

**Compartir → Añadir a pantalla de inicio.** Se comporta como una app: icono
propio, sin barra del navegador.

## 5. La voz

Pulsa **Voz**. El móvil pedirá permiso de micrófono — acéptalo. A partir de
ahí funciona igual que en el PC: hablas, calla, responde.

Si no aparece el permiso, comprueba que la barra de direcciones muestre el
candado. Sin HTTPS no hay micrófono, y es el navegador quien lo impide.

## Por qué esto es MÁS seguro que antes

- La web sigue atada a `127.0.0.1`. Docker no expone nada a la red.
- Tailscale hace de puerta y solo deja pasar a tus dispositivos autenticados.
- Ya no hace falta regla de cortafuegos: no hay puerto que proteger.
- La cookie de sesión pasa a `Secure`: nunca viaja en claro.
- Sigue habiendo usuario y contraseña, y sesión con caducidad.

## Qué puedes hacer desde el móvil

Todo: hablar, escribir, subir fotos, oír los informes, abrir perfiles y
controlar la música. El puente sigue en tu PC, así que decir "abre el modo
trabajo" desde el autobús **abre las ventanas en tu ordenador de casa**.

Lo único que no: si el PC está apagado, KAIROS no responde. Ese es el problema
que resuelve el mini-PC de la lista de la compra.

## Cerrarlo

```powershell
tailscale serve --bg --https=443 off
```

```bash
cd /home/diego/kairos-os
sed -i 's|^KAIROS_COOKIE_SECURE=.*|KAIROS_COOKIE_SECURE=false|' .env
docker compose up -d --force-recreate core
```
