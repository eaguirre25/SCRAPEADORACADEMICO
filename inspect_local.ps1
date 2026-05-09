$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

Write-Host "Ejecutando healthcheck..." -ForegroundColor Cyan
py -3 dashboard_healthcheck.py

$port = 8082
while (Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue) {
  $port += 1
}

Write-Host ""
Write-Host "Levantando dashboard en http://localhost:$port/" -ForegroundColor Green
Start-Process -FilePath "py.exe" -ArgumentList @("-3", "-m", "http.server", "$port") -WorkingDirectory (Join-Path $repoRoot "docs") -WindowStyle Hidden

Start-Sleep -Seconds 2
Start-Process "http://localhost:$port/"
