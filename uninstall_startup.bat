@echo off
cd /d "%~dp0"
echo ================================================================
echo   Removing KCT Studio from Windows Boot Startup
echo ================================================================
echo.
python tray_app.py --uninstall-startup
echo.
echo [DONE] Auto-start on boot has been removed.
echo.
pause
