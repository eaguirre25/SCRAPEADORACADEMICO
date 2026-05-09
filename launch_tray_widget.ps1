$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$trayScript = Join-Path $repoRoot "tray_widget.ps1"

Start-Process -FilePath "powershell.exe" -ArgumentList "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$trayScript`"" -WorkingDirectory $repoRoot -WindowStyle Hidden
