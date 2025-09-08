# Remove build artifacts produced by PyInstaller and Python bytecode caches
Write-Host "Cleaning build artifacts..."
$paths = @(
    "build",
    "dist",
    "*.spec",
    "**\__pycache__",
    "**\*.pyc",
    "**\*.pyo"
)

foreach ($p in $paths) {
    Get-ChildItem -Path $p -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue
}

Write-Host "Cleanup complete."
