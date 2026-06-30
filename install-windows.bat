@echo off
setlocal
cd /d "%~dp0"

echo [STS2DEFECT] Creating local virtual environment...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo Failed to create .venv. Install Python 3.12+ and make sure python is on PATH.
        pause
        exit /b 1
    )
)

echo [STS2DEFECT] Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo.
    echo Failed to upgrade pip. Check your network or Python installation.
    pause
    exit /b 1
)

echo [STS2DEFECT] Installing runtime dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements-windows.txt
if errorlevel 1 (
    echo.
    echo Dependency installation failed. See docs\windows-portable.md for common fixes.
    pause
    exit /b 1
)

echo.
echo Installation complete. Double-click run-panel.bat to start STS2DEFECT.
pause
