<#
run.ps1 — simple developer helper to create a venv (if missing), install requirements, and run the GUI.

Usage (PowerShell):
  .\run.ps1           # creates/activates venv, installs deps if needed, runs the GUI
  .\run.ps1 -Rebuild  # force reinstall requirements
#>

param(
    [switch]$Rebuild
)

Set-StrictMode -Version Latest
Push-Location -Path $PSScriptRoot
try {
    $venvPath = Join-Path $PSScriptRoot '.venv'
    $pythonExe = Join-Path $venvPath 'Scripts\python.exe'
    $activate = Join-Path $venvPath 'Scripts\Activate.ps1'

    if (-not (Test-Path $pythonExe)) {
        Write-Host 'Creating virtual environment...' -ForegroundColor Cyan
        py -3.11 -m venv .venv
    }

    Write-Host 'Activating virtual environment...' -ForegroundColor Cyan
    & $activate

    if ($Rebuild -or -not (Get-Command pip -ErrorAction SilentlyContinue)) {
        Write-Host 'Installing requirements...' -ForegroundColor Cyan
        pip install --upgrade pip
        pip install -r requirements.txt
    }

    Write-Host 'Launching GUI... (close the window to exit)' -ForegroundColor Green
    & $pythonExe '.\src\titansteelworks\gui.py'
}
finally {
    Pop-Location
}
