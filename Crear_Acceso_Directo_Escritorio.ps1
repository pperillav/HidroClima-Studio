$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "HidroClima Studio.lnk"
$IconPath = Join-Path $Root "hidroclima\static\hidroclima_studio.ico"
$PortableExe = Join-Path $Root "dist\HidroClimaStudio\HidroClimaStudio.exe"
$VbsLauncher = Join-Path $Root "Iniciar_HidroClimaStudio.vbs"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
if (Test-Path $PortableExe) {
    $Shortcut.TargetPath = $PortableExe
} else {
    $Shortcut.TargetPath = "wscript.exe"
    $Shortcut.Arguments = "`"$VbsLauncher`""
}
$Shortcut.WorkingDirectory = $Root
$Shortcut.Description = "HidroClima Studio - Hidrología IDF, Balance Hídrico, Climatología y Pavimentos"
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = $IconPath
}
$Shortcut.Save()
Write-Host "Acceso directo creado en el escritorio: $ShortcutPath"
