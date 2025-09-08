Packaging instructions

1) Activate your project's venv (PowerShell):

& .\.venv\Scripts\Activate.ps1

2) Run the build script:

.\packaging\build_exe.ps1

This script uses PyInstaller to produce a Windows executable in the `dist/` folder. It bundles the `docs/` directory and the `.env` file. If you want a non-bundled folder build (useful for debugging resources), edit the script and remove the `--onefile` flag.
