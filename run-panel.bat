@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" --version >nul 2>nul
if errorlevel 1 (
    echo Python was not found.
    echo Run install-windows.bat first, or install Python 3.12+ and add it to PATH.
    pause
    exit /b 1
)

if not exist "data\recommendations\slay-the-spire-2-manual.json" (
    echo Missing recommendation data:
    echo data\recommendations\slay-the-spire-2-manual.json
    pause
    exit /b 1
)

set "PYTHONPATH=%~dp0src"
"%PYTHON_EXE%" -m sts2defect.cli run-panel "data\recommendations\slay-the-spire-2-manual.json" %*
if errorlevel 1 (
    echo.
    echo STS2DEFECT exited with error code %ERRORLEVEL%.
    echo If this is a dependency error, run install-windows.bat again.
    pause
    exit /b %ERRORLEVEL%
)
