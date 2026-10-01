# ============================================================
#  FlowSpeak - create Desktop + Start Menu shortcuts.
#  Right-click this file -> "Run with PowerShell".
# ============================================================
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
$target = Join-Path $root "run.bat"
$icon = Join-Path $root "flowspeak\assets\flowspeak.ico"

function New-FlowSpeakShortcut($path) {
    $shell = New-Object -ComObject WScript.Shell
    $sc = $shell.CreateShortcut($path)
    $sc.TargetPath = $target
    $sc.WorkingDirectory = $root
    $sc.WindowStyle = 7           # minimized; the app itself has no window
    $sc.Description = "FlowSpeak - voice dictation"
    if (Test-Path $icon) { $sc.IconLocation = $icon }
    $sc.Save()
}

$desktop = [Environment]::GetFolderPath("Desktop")
New-FlowSpeakShortcut (Join-Path $desktop "FlowSpeak.lnk")
Write-Host "Created Desktop shortcut." -ForegroundColor Green

$startMenu = Join-Path ([Environment]::GetFolderPath("ApplicationData")) "Microsoft\Windows\Start Menu\Programs"
New-FlowSpeakShortcut (Join-Path $startMenu "FlowSpeak.lnk")
Write-Host "Created Start Menu shortcut (search 'FlowSpeak')." -ForegroundColor Green

Write-Host ""
Write-Host "Done. You can now launch FlowSpeak from the Desktop or Start Menu."
