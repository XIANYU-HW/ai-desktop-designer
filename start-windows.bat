@echo off
rem Orbit Desktop - double-click to start on Windows.
setlocal
cd /d "%~dp0"
title Orbit Desktop

set "PYEXE="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if not errorlevel 1 set "PYEXE=py -3"
if not defined PYEXE python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if not defined PYEXE if not errorlevel 1 set "PYEXE=python"

if defined PYEXE goto run

echo.
echo  Orbit Desktop needs Python 3.9 or newer, which is not installed yet.
echo.
choice /c YN /m "Install Python 3.12 for this user with winget now"
if errorlevel 2 goto manual
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
echo.
echo  Done. Close this window and double-click start-windows.bat again.
pause
exit /b 0

:manual
echo.
echo  Download Python from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
echo  Then double-click start-windows.bat again.
pause
exit /b 1

:run
%PYEXE% runtime\orbit.py quickstart
if errorlevel 1 pause
