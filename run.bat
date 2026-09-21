@echo off
title KCT Studio - AI Video Pipeline
cd /d "%~dp0"

:: Auto-kill any orphaned process holding port 7860
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":7860 " ^| findstr "LISTENING"') do (
    echo Freeing port 7860 (PID %%a)...
    taskkill /F /PID %%a >nul 2>&1
)

echo =======================================================
echo   Starting KCT Studio v2.0 - AI Video Pipeline
echo   URL: https://localhost:7860
echo =======================================================
python app.py
pause
