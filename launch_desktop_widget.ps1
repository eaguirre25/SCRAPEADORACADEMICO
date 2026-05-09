$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$widget = Join-Path $repoRoot "desktop_widget.py"
Start-Process -FilePath "py.exe" -ArgumentList "-3 `"$widget`"" -WorkingDirectory $repoRoot
