$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$widgetScript = Join-Path $repoRoot "desktop_widget.py"
$dashboard = Join-Path $repoRoot "docs\index.html"
$actionsUrl = "https://github.com/eaguirre25/SCRAPEADORACADEMICO/actions"

function New-TechIcon {
  $bitmap = New-Object System.Drawing.Bitmap 64, 64
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

  $bg = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
    [System.Drawing.Rectangle]::new(0, 0, 64, 64),
    [System.Drawing.Color]::FromArgb(255, 8, 12, 18),
    [System.Drawing.Color]::FromArgb(255, 14, 32, 46),
    45
  )
  $graphics.FillEllipse($bg, 3, 3, 58, 58)

  $cyan = [System.Drawing.Color]::FromArgb(255, 88, 246, 255)
  $green = [System.Drawing.Color]::FromArgb(255, 57, 255, 142)
  $blue = [System.Drawing.Color]::FromArgb(255, 88, 166, 255)

  $outerPen = New-Object System.Drawing.Pen($cyan, 3)
  $midPen = New-Object System.Drawing.Pen($blue, 2)
  $linePen = New-Object System.Drawing.Pen($green, 3)
  $thinPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(210, 88, 246, 255), 1.4)

  $graphics.DrawEllipse($outerPen, 5, 5, 54, 54)
  $graphics.DrawArc($midPen, 12, 12, 40, 40, 210, 250)
  $graphics.DrawLine($linePen, 18, 42, 30, 25)
  $graphics.DrawLine($linePen, 30, 25, 44, 39)
  $graphics.DrawLine($thinPen, 17, 18, 47, 18)
  $graphics.DrawLine($thinPen, 17, 49, 47, 49)

  foreach ($p in @(@(18,42), @(30,25), @(44,39))) {
    $brush = New-Object System.Drawing.SolidBrush($cyan)
    $graphics.FillEllipse($brush, $p[0] - 4, $p[1] - 4, 8, 8)
    $brush.Dispose()
  }

  $font = New-Object System.Drawing.Font("Segoe UI", 13, [System.Drawing.FontStyle]::Bold)
  $textBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
  $graphics.DrawString("A", $font, $textBrush, 26, 38)

  $hicon = $bitmap.GetHicon()
  $icon = [System.Drawing.Icon]::FromHandle($hicon)
  $graphics.Dispose()
  $bitmap.Dispose()
  return $icon
}

function Get-WidgetProcesses {
  Get-CimInstance Win32_Process |
    Where-Object {
      ($_.Name -in @("py.exe", "python.exe", "pythonw.exe")) -and
      ($_.CommandLine -like "*desktop_widget.py*")
    }
}

function Start-Widget {
  $existing = Get-WidgetProcesses
  if ($existing) {
    return
  }
  Start-Process -FilePath "py.exe" -ArgumentList "-3 `"$widgetScript`"" -WorkingDirectory $repoRoot
}

function Stop-Widget {
  Get-WidgetProcesses | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
}

function Toggle-Widget {
  if (Get-WidgetProcesses) {
    Stop-Widget
  } else {
    Start-Widget
  }
}

function Git-Pull {
  Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit -Command `"cd '$repoRoot'; git pull --ff-only`""
}

$notifyIcon = New-Object System.Windows.Forms.NotifyIcon
$notifyIcon.Icon = New-TechIcon
$notifyIcon.Text = "SCRAPEADORACADEMICO"
$notifyIcon.Visible = $true

$menu = New-Object System.Windows.Forms.ContextMenuStrip

$openItem = $menu.Items.Add("Abrir / ocultar widget")
$openItem.Add_Click({ Toggle-Widget })

$dashboardItem = $menu.Items.Add("Abrir dashboard")
$dashboardItem.Add_Click({ Start-Process $dashboard })

$actionsItem = $menu.Items.Add("Ver GitHub Actions")
$actionsItem.Add_Click({ Start-Process $actionsUrl })

$pullItem = $menu.Items.Add("Actualizar repo local")
$pullItem.Add_Click({ Git-Pull })

[void]$menu.Items.Add("-")

$exitItem = $menu.Items.Add("Salir")
$exitItem.Add_Click({
  Stop-Widget
  $notifyIcon.Visible = $false
  $notifyIcon.Dispose()
  [System.Windows.Forms.Application]::Exit()
})

$notifyIcon.ContextMenuStrip = $menu
$notifyIcon.Add_MouseClick({
  param($sender, $eventArgs)
  if ($eventArgs.Button -eq [System.Windows.Forms.MouseButtons]::Left) {
    Toggle-Widget
  }
})
$notifyIcon.Add_DoubleClick({ Start-Widget })

$notifyIcon.ShowBalloonTip(
  2500,
  "SCRAPEADORACADEMICO",
  "Icono residente activo. Clic izquierdo abre/oculta el panel.",
  [System.Windows.Forms.ToolTipIcon]::Info
)

[System.Windows.Forms.Application]::Run()
