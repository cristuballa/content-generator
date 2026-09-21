@echo off
cd /d "%~dp0"
echo Starting KCT Studio System Tray...
start "" pythonw.exe tray_app.py --restart
echo [OK] KCT Studio Tray App started in background.
echo Check the Windows System Tray (click ^ arrow if hidden).
