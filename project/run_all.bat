@echo off
REM run_all.bat - wrapper to call PowerShell run_all.ps1
SETLOCAL
SET PS_CMD=powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_all.ps1" %*
%PS_CMD%
ENDLOCAL
