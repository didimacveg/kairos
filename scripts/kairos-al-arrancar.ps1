# KAIROS se abre solo al encender el PC, como una aplicacion.
#
# Chrome en modo aplicacion: sin barra de direcciones, sin pestanas, icono
# propio. Es la ventana que tiene el microfono, asi que tenerla abierta es lo
# que hace que KAIROS te oiga.

$ErrorActionPreference = "Continue"

$chrome = @(
  "C:\Program Files\Google\Chrome\Application\chrome.exe",
  "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
  "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $chrome) {
  Write-Host "No encuentro Chrome ni Edge." -ForegroundColor Red
  exit 1
}

$vbs = @"
Set s = CreateObject("WScript.Shell")
WScript.Sleep 45000
s.Run """$chrome"" --app=http://localhost:3000 --start-maximized", 1, False
"@
Set-Content -Path "C:\kairos-bridge\abrir-kairos.vbs" -Encoding ASCII -Value $vbs
Copy-Item "C:\kairos-bridge\abrir-kairos.vbs" `
  "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\KAIROS.vbs" -Force

Write-Host "Hecho. Al encender el PC, KAIROS se abrira solo pasados 45 s." -ForegroundColor Green
Write-Host "La primera vez, acepta el permiso de microfono y marca 'recordar'." -ForegroundColor Yellow

Start-Process $chrome -ArgumentList "--app=http://localhost:3000","--start-maximized"
