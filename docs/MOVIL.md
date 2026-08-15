# KAIROS en el móvil

## Por qué una VPN privada y no abrir el router

Abrir un puerto en el router expone KAIROS a Internet entero: cualquiera que
escanee tu IP encuentra el login. Y ahí dentro está tu memoria, tus
conversaciones y el control de tu PC.

Tailscale crea una red cifrada solo entre TUS dispositivos. Ningún puerto se
abre al exterior, no hace falta IP fija, y para el móvil KAIROS aparece como
si estuviera en la misma habitación.

Es gratis para uso personal (hasta 100 dispositivos).

## 1. En el PC — instalar Tailscale

Descarga de `tailscale.com/download/windows`. Al abrirlo pide iniciar sesión:
usa Google o GitHub, no hace falta crear contraseña nueva.

Cuando termine, **POWERSHELL**:

```powershell
tailscale ip -4
tailscale status
```

El primero da tu dirección en la red privada, algo como `100.x.y.z`. Apúntala.

## 2. En el PC — dejar que la web escuche

**UBUNTU**:

```bash
cd /home/diego/kairos-os
IP=$(powershell.exe -NoProfile -Command "tailscale ip -4" 2>/dev/null | tr -d '\r\n ')
echo "IP en la red privada: $IP"
sed -i 's|^KAIROS_WEB_BIND=.*|KAIROS_WEB_BIND=0.0.0.0|' .env
sed -i "s|^KAIROS_EXTRA_HOSTS=.*|KAIROS_EXTRA_HOSTS=$IP|" .env
sed -i "s|^KAIROS_ALLOWED_ORIGINS=.*|KAIROS_ALLOWED_ORIGINS=http://localhost:3000,http://$IP:3000|" .env
grep -E "^KAIROS_(WEB_BIND|EXTRA_HOSTS|ALLOWED_ORIGINS)" .env
docker compose up -d --force-recreate core web
```

## 3. En el PC — cortafuegos SOLO para la red privada

**POWERSHELL COMO ADMINISTRADOR**:

```powershell
New-NetFirewallRule -DisplayName "KAIROS Web (Tailscale)" `
  -Direction Inbound -Protocol TCP -LocalPort 3000 `
  -RemoteAddress 100.64.0.0/10 -Action Allow -Profile Any
```

`100.64.0.0/10` es el rango que usa Tailscale. Un dispositivo de tu WiFi que
no esté en tu red privada NO puede conectarse: la regla solo abre para ese
rango, no para toda la red local.

## 4. En el móvil

Instala Tailscale (App Store / Play Store), inicia sesión con la misma cuenta,
y activa la VPN. Luego abre en el navegador:

```
http://100.x.y.z:3000
```

Con la IP que apuntaste. Entra con tu usuario y contraseña de siempre.

Añádelo a la pantalla de inicio (Compartir → Añadir a inicio) y se comporta
como una app.

## Qué funciona desde el móvil

Todo lo que no dependa del hardware del PC: chat, memoria, búsqueda web,
informes diarios, abrir perfiles y controlar la música. El puente sigue
corriendo en tu PC, así que "abre el modo trabajo" desde el móvil **abre las
ventanas en tu ordenador de casa**.

Lo que NO funciona: la voz por micrófono. El navegador móvil exige HTTPS para
`getUserMedia`, y de momento vamos por HTTP dentro de la VPN. Se resuelve con
un certificado de Tailscale más adelante.

## Volver a cerrar

```bash
sed -i 's|^KAIROS_WEB_BIND=.*|KAIROS_WEB_BIND=127.0.0.1|' .env
docker compose up -d --force-recreate web
```

Un comando y KAIROS vuelve a ser inalcanzable desde fuera de este PC.

## Lo que sigue estando protegido

- El puerto no se abre a Internet, solo a tu red privada cifrada.
- Sigue haciendo falta usuario y contraseña.
- El cortafuegos limita al rango de Tailscale.
- La sesión caduca a las 72 horas.
- Toda acción queda en la auditoría, venga del PC o del móvil.
