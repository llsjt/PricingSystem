@echo off
chcp 65001 >nul
echo ========================================
echo   Python Pricing Agent Server
echo ========================================
echo.

REM Check whether Python is available.
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [Error] Python was not found. Please install Python and add it to PATH.
    pause
    exit /b 1
)

echo [Info] Starting service...
echo [Info] Listening at: http://0.0.0.0:8000
echo [Info] API docs: http://localhost:8000/docs
echo.

REM Prefer the project virtual environment when present.
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe -m app.main
) else (
    python -m app.main
)

pause
