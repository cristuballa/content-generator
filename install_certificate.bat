@echo off
title KCT Studio - Install SSL Certificate
cd /d "%~dp0"
echo ============================================================
echo   KCT Studio - Install Local SSL Certificate into Windows
echo ============================================================
echo.
echo This will register the certificate in your personal Windows
echo Trusted Root Certification Authorities store so that Chrome,
echo Edge, and other browsers show a secure HTTPS connection.
echo.
if not exist "certs\cert.crt" (
    echo Generating certificate first...
    python -c "from core.cert_manager import cert_manager; cert_manager.ensure_certificates()"
)
echo.
echo Running certutil to install certificate...
echo Note: When the Windows Security Warning dialog appears, click [Yes].
echo.
certutil -addstore -user Root "certs\cert.crt"
echo.
echo ============================================================
echo Certificate installation complete!
echo You can now open https://localhost:7860 in your browser.
echo ============================================================
pause
