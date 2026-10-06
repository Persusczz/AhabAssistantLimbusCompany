@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>&1
if errorlevel 1 (
    echo uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/
    goto failed
)
echo [1/2] Installing locked dependencies...
call uv sync --locked
if errorlevel 1 goto failed
echo [2/2] Starting AALC development mode...
call uv run --no-sync main_dev.py --no-reload
if errorlevel 1 goto failed
exit /b 0

:failed
echo Startup failed. See the output above.
pause
exit /b 1
