@echo off
REM run.bat — create venv if missing, install deps, and run the GUI (cmd-friendly)

SET VENV=%~dp0.venv\Scripts
SET PY=%VENV%\python.exe
SET ACT=%VENV%\Activate.bat

IF NOT EXIST "%PY%" (
  echo Creating virtual environment...
  py -3.11 -m venv "%~dp0.venv"
)

echo Activating virtual environment...
call "%ACT%"

echo Installing requirements (if needed)...
%PY% -m pip install --upgrade pip
%PY% -m pip install -r "%~dp0requirements.txt"

echo Launching GUI...
%PY% "%~dp0src\titansteelworks\gui.py"

pause
