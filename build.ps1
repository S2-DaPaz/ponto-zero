# Gera dist\PontoZero.exe (arquivo único, sem console).
# Uso: powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) {
    python -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install -q -r requirements.txt pyinstaller
.\.venv\Scripts\python.exe tools\make_icon.py | Out-Null

.\.venv\Scripts\pyinstaller.exe --noconfirm --clean --onefile --windowed `
    --name PontoZero `
    --icon assets\icon.ico `
    --add-data "assets\icon.ico;assets" `
    --collect-data customtkinter `
    --hidden-import pystray._win32 `
    --exclude-module numpy --exclude-module unittest --exclude-module pydoc `
    run.py

Write-Host "Pronto: $PSScriptRoot\dist\PontoZero.exe"
