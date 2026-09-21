@echo off
cd /d "%~dp0"
echo ================================================================
echo   Registering KCT Studio System Tray to Run on Windows Boot
echo ================================================================
echo.
python tray_app.py --install-startup
echo.
echo Launching KCT Studio Tray App in background...
start "" pythonw.exe tray_app.py --restart
echo.
echo ================================================================
echo [SUCCESS] KCT Studio is registered to run on Windows boot!
echo The System Tray icon is running in your taskbar notification area.
echo Look for the KCT Studio icon (click the ^ arrow if hidden).
echo ================================================================
echo.
timeout /t 5 >nul
