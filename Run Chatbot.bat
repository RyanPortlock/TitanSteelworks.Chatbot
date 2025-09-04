@echo off
setlocal
REM Launch the Titan Steelworks GUI without a visible console

REM Change to repo root (folder containing this .bat)
pushd "%~dp0"

REM Activate virtual environment (adjust if yours is different)
call .venv\Scripts\activate

REM Run the GUI
python app\gui.py

REM Keep the window open if something crashes
pause
endlocal
