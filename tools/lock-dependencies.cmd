@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0lock-dependencies.ps1"
exit /b %errorlevel%
