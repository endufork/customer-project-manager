@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0cleanup-test-data.ps1" %*
