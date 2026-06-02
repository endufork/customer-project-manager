@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-hooks.ps1" %*
