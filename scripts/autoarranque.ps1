# Arranque automatico del puente KAIROS.
#
# Version robusta: registra lo que hace en un log, para que si el puente no
# aparece tras encender el PC se pueda ver por que en vez de adivinar.
$ErrorActionPreference = "Continue"
$log = "C:\kairos-bridge\autoarranque.log"

function Registrar($msg, $color = "White") {
    $linea = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Write-Host $msg -ForegroundColor $color
    Add-Content -Path $log -Value $linea -ErrorAction SilentlyContinue
}

Registrar "=== Configurando autoarranque ===" Cyan

# --- Python ---------------------------------------------------------------
$rutas = @()
foreach ($n in @("pythonw.exe")) {
    $c = Get-Command $n -ErrorAction SilentlyContinue
    if ($c) { $rutas += $c.Source }
}
$c = Get-Command python.exe -ErrorAction SilentlyContinue
if ($c) { $rutas += ($c.Source -replace 'python\.exe$','pythonw.exe') }
$rutas += @(
  "C:\Program Files\Python313\pythonw.exe","C:\Program Files\Python312\pythonw.exe",
  "C:\Program Files\Python311\pythonw.exe",
  "$env:LOCALAPPDATA\Programs\Python\Python313\pythonw.exe",
  "$env:LOCALAPPDATA\Programs\Python\Python312\pythonw.exe"
)
$pythonw = $rutas | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $pythonw) { Registrar "No encuentro pythonw.exe" Red; exit 1 }
Registrar "Python: $pythonw" Green

if (-not (Test-Path "C:\kairos-bridge\bridge.py")) {
    Registrar "Falta C:\kairos-bridge\bridge.py — sincroniza desde Ubuntu" Red
    exit 1
}

# --- Lanzador con espera ---------------------------------------------------
# El puente arranca antes que Docker al encender el PC. No es un problema —
# solo llama al nucleo cuando hay que transcribir — pero esperar un poco evita
# una tanda de errores en el log durante el primer minuto.
$lanzador = @"
Start-Sleep -Seconds 25
Set-Location 'C:\kairos-bridge'
Start-Process '$pythonw' -ArgumentList 'C:\kairos-bridge\bridge.py' -WorkingDirectory 'C:\kairos-bridge' -WindowStyle Hidden
"@
Set-Content -Path "C:\kairos-bridge\lanzar.ps1" -Value $lanzador -Encoding UTF8
Registrar "Lanzador escrito" Green

# --- Tarea programada: mas fiable que la carpeta Inicio -------------------
# La carpeta Inicio depende de la sesion grafica y a veces se salta silenciosamente.
# Una tarea programada con reintentos arranca siempre.
$nombre = "KAIROS Bridge"
Unregister-ScheduledTask -TaskName $nombre -Confirm:$false -ErrorAction SilentlyContinue

$accion = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\kairos-bridge\lanzar.ps1"
$disparador = New-ScheduledTaskTrigger -AtLogOn
$ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

try {
    Register-ScheduledTask -TaskName $nombre -Action $accion -Trigger $disparador `
        -Settings $ajustes -Description "Arranca el puente de KAIROS al iniciar sesion" | Out-Null
    Registrar "Tarea programada creada" Green
} catch {
    Registrar "No se pudo crear la tarea (¿ejecutas como administrador?): $_" Yellow
    Registrar "Alternativa: acceso directo en Inicio" Yellow
    $s = (New-Object -ComObject WScript.Shell).CreateShortcut(
        "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\KAIROS Bridge.lnk")
    $s.TargetPath = $pythonw
    $s.Arguments = "C:\kairos-bridge\bridge.py"
    $s.WorkingDirectory = "C:\kairos-bridge"
    $s.Save()
    Registrar "Acceso directo creado" Green
}

# --- Arrancarlo ahora ------------------------------------------------------
Get-Process pythonw -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 2
Start-Process $pythonw -ArgumentList "C:\kairos-bridge\bridge.py" `
    -WorkingDirectory "C:\kairos-bridge" -WindowStyle Hidden
Registrar "Puente lanzado, esperando..." Cyan
Start-Sleep 8

try {
    $r = Invoke-WebRequest "http://127.0.0.1:8200/health" -TimeoutSec 8 -UseBasicParsing
    Registrar "El puente responde: HTTP $($r.StatusCode)" Green
    Registrar "Arrancara solo al iniciar sesion." Green
} catch {
    Registrar "El puente no responde. Lanzalo a mano para ver el error:" Red
    Registrar "  cd C:\kairos-bridge ; py bridge.py" Yellow
}
