# Build the one-folder exe (dist\FLKitsManager\FLKitsManager.exe) and smoke-test it.
# Used by the local post-commit hook (scripts\hooks\post-commit) and by the release workflow.
#   .\scripts\build.ps1                  # with .venv\Scripts\python
#   .\scripts\build.ps1 -Python python   # with the python on PATH (CI)
param([string]$Python = ".venv\Scripts\python.exe")

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$commit = try { git rev-parse --short HEAD } catch { "?" }
Write-Output "build of commit $commit started $(Get-Date -Format s)"

if (Get-Process FLKitsManager -ErrorAction SilentlyContinue) {
    throw "FLKitsManager.exe is running: close it, then run scripts\build.ps1 again"
}

$root = (Get-Location).Path
# kit_zones.png: the texture zones of kits from photos (flkm\photokit\texture.py); flkm.ico: the app icon, of the exe
# and of its windows (flkm\icon.py)
& $Python -m PyInstaller --noconfirm --clean --windowed --onedir --name FLKitsManager --paths $root `
    --add-data "$root\flkm\photokit\kit_zones.png;flkm\photokit" `
    --icon "$root\flkm\flkm.ico" --add-data "$root\flkm\flkm.ico;flkm" `
    --distpath "$root\dist" --workpath "$root\build" --specpath "$root\build" "$root\flkm\__main__.py"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed (exit code $LASTEXITCODE)" }

$env:QT_QPA_PLATFORM = "offscreen"
$p = Start-Process dist\FLKitsManager\FLKitsManager.exe -ArgumentList "--smoke-test" -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "smoke test failed: exit code $($p.ExitCode)" }

Write-Output "build of commit $commit OK $(Get-Date -Format s): dist\FLKitsManager\FLKitsManager.exe"
