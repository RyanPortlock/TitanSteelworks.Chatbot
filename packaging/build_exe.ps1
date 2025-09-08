# PowerShell script to build a single-file Windows EXE using PyInstaller
# Usage: run from project root in an activated venv, e.g.:
# & .\.venv\Scripts\Activate.ps1; .\packaging\build_exe.ps1

param(
    [string]$Entry = "src\\titansteelworks\\gui.py",
    [string]$DistName = "TitanSteelworks.Chatbot",
    [bool]$OneFile = $true
)

Write-Host "Building EXE for $Entry ..."

# Find a Python executable. Prefer the project's venv if present.
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$venvPy = Join-Path $scriptRoot "..\.venv\Scripts\python.exe"
if (Test-Path $venvPy) { $py = $venvPy } else { $py = "python" }

Write-Host "Using Python: $py"

# Ensure PyInstaller is installed in that Python
& $py -m pip install --upgrade pip setuptools
& $py -m pip install pyinstaller --upgrade

# Clean previous builds
Remove-Item -Recurse -Force .\build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\dist -ErrorAction SilentlyContinue
Remove-Item -Force .\${DistName}.spec -ErrorAction SilentlyContinue

# Collect data files: docs folder and .env template
$datas = @(
    "docs;docs",
    ".env;."
)

# Build arguments
$extraArgs = @()
if ($OneFile) { $extraArgs += "--onefile" }
$extraArgs += "--windowed"
$extraArgs += "--name"; $extraArgs += $DistName
foreach ($d in $datas) { $extraArgs += "--add-data"; $extraArgs += $d }

# Run PyInstaller using the chosen Python
& $py -m PyInstaller @extraArgs $Entry

Write-Host "Build finished. See .\dist\$DistName\ or .\dist\$DistName.exe"
