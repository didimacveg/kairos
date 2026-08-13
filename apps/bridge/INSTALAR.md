# Fase 5 — Perfiles, cierre por voz y escucha permanente

## 1. Python en Windows (esto es lo que fallaba)

`py` no existe porque solo tienes Python dentro de WSL. El puente corre en
Windows, así que necesita el suyo. En **PowerShell como administrador**:

```powershell
winget install --id Python.Python.3.12 -e --source winget
```

Cierra y reabre PowerShell. Comprueba:

```powershell
py --version
```

Si `winget` no existe, descarga el instalador de `python.org/downloads` y
**marca "Add python.exe to PATH"** en la primera pantalla.

## 2. Copiar el puente fuera de la ruta de red

Trabajar desde `\\wsl.localhost\...` es lento y da problemas con `pip`. En
PowerShell:

```powershell
mkdir C:\kairos-bridge -Force
copy \\wsl.localhost\Ubuntu\home\diego\kairos-os\apps\bridge\* C:\kairos-bridge\
cd C:\kairos-bridge
py -m pip install -r requirements.txt
```

## 3. Arrancar

```powershell
py bridge.py
```

Imprime un token. Cópialo y en **Ubuntu**:

```bash
cd /home/diego/kairos-os
sed -i 's|^KAIROS_BRIDGE_TOKEN=.*|KAIROS_BRIDGE_TOKEN=EL_TOKEN_QUE_SALIO|' .env
sed -i 's|^KAIROS_BRIDGE_ENABLED=.*|KAIROS_BRIDGE_ENABLED=true|' .env
docker compose up -d --force-recreate core
```

## 4. Las canciones de Spotify

Los `spotify:track:REEMPLAZA_...` del config **no funcionan**: son marcadores.
Para cada canción, en Spotify: clic derecho → Compartir → Copiar enlace.

De `https://open.spotify.com/track/ABC123?si=xxx` te quedas con `ABC123`, y en
`C:\kairos-bridge\bridge-config.json` pones `spotify:track:ABC123`.

Tres canciones que reemplazar:
- `REEMPLAZA_LEGENDS_NEVER_DIE` → perfil estudio
- `REEMPLAZA_BACK_IN_BLACK` → perfiles trabajo y juego
- `REEMPLAZA_SHOULD_I_STAY` → frase "papi está en casa"

Luego, en el menú de la bandeja: **Recargar configuración**.

## 5. Probar

**Por voz, sin tocar nada.** Di en alto:

- *"Kairos, abre el perfil trabajo"*
- *"Kairos, cierra el perfil trabajo y abre el perfil juego"*
- *"Kairos, cierra el perfil juego"*
- *"Kairos, despierta, papi está en casa"* → suena la canción y se abre trabajo

En la consola del puente verás qué oyó y qué hizo.

**Por bandeja**, para probar sin voz: clic en el icono → Abrir / Cerrar perfil.

## 6. Ajustar las ventanas

Si una app no se recoloca, su `window` no coincide con el título real. Para
verlos todos:

```powershell
py -c "import actions; [print(m) for m in actions.list_monitors()]"
```

Y para el título exacto de una ventana abierta, mira la barra de título: basta
con un trozo, no hace falta el título completo.

## 7. Arranque automático (opcional)

```powershell
$s = (New-Object -ComObject WScript.Shell).CreateShortcut(
  "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\KAIROS Bridge.lnk")
$s.TargetPath = "pythonw.exe"
$s.Arguments = "C:\kairos-bridge\bridge.py"
$s.WorkingDirectory = "C:\kairos-bridge"
$s.Save()
```

`pythonw.exe` en vez de `py` para que arranque sin ventana de consola.
