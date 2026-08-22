# Arranque automatico del puente KAIROS, sin ventana de consola.
$ErrorActionPreference = "Continue"

Write-Host "Buscando Python..." -ForegroundColor Cyan
$rutas = @()
$cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if ($cmd) { $rutas += $cmd.Source }
$cmd = Get-Command python.exe -ErrorAction SilentlyContinue
if ($cmd) { $rutas += ($cmd.Source -replace 'python\.exe$','pythonw.exe') }
$rutas += @(
  "C:\Program Files\Python313\pythonw.exe",
  "C:\Program Files\Python312\pythonw.exe",
  "C:\Program Files\Python311\pythonw.exe",
  "$env:LOCALAPPDATA\Programs\Python\Python313\pythonw.exe",
  "$env:LOCALAPPDATA\Programs\Python\Python312\pythonw.exe"
)
$pythonw = $rutas | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $pythonw) {
  Write-Host "No encuentro pythonw.exe. Ejecuta:  where.exe python" -ForegroundColor Red
  exit 1
}
Write-Host "  $pythonw" -ForegroundColor Green

if (-not (Test-Path "C:\kairos-bridge\bridge.py")) {
  Write-Host "Falta C:\kairos-bridge\bridge.py" -ForegroundColor Red
  Write-Host "Sincroniza desde Ubuntu:  bash scripts/sincronizar-puente.sh" -ForegroundColor Yellow
  exit 1
}

$destino = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\KAIROS Bridge.lnk"
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($destino)
$s.TargetPath = $pythonw
$s.Arguments = "C:\kairos-bridge\bridge.py"
$s.WorkingDirectory = "C:\kairos-bridge"
$s.Save()
Write-Host "Acceso directo creado en Inicio" -ForegroundColor Green

Get-Process pythonw,python -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like "*bridge.py*" -or $_.Path -like "*python*" } |
  Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 2
Start-Process $pythonw -ArgumentList "C:\kairos-bridge\bridge.py" -WorkingDirectory "C:\kairos-bridge"
Write-Host "Puente arrancado, esperando..." -ForegroundColor Cyan
Start-Sleep 8

try {
  $r = Invoke-WebRequest "http://127.0.0.1:8200/health" -TimeoutSec 8 -UseBasicParsing
  Write-Host "El puente responde: HTTP $($r.StatusCode)" -ForegroundColor Green
  Write-Host "Vive en el icono de la bandeja y arrancara solo al iniciar sesion." -ForegroundColor Green
} catch {
  Write-Host "El puente no responde. Lanzalo a mano para ver el error:" -ForegroundColor Red
  Write-Host "  cd C:\kairos-bridge ; py bridge.py" -ForegroundColor Yellow
}
