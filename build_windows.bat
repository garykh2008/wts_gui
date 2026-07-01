@echo off
set "SCRIPT_DIR=%~dp0"
set "RELEASE_DIR=%SCRIPT_DIR%release\windows"

echo Building WTS GUI for Windows...

:: Check if PyInstaller is installed
where pyinstaller >nul 2>nul
if %errorlevel% neq 0 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

:: Clean previous build
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

:: Run PyInstaller
:: --onefile: Bundle everything into a single executable
:: --windowed: No console window
:: --add-data: Include README.md (Windows separator is ';')
pyinstaller --name wts_gui --onefile --windowed --add-data "README.md;." --add-data "web;web" wts_gui.py

if %errorlevel% equ 0 (
    echo.
    echo Build Successful!
    
    :: Create release directory if it doesn't exist
    if not exist "%RELEASE_DIR%" mkdir "%RELEASE_DIR%"
    
    :: Move executable to release directory
    move /Y "dist\wts_gui.exe" "%RELEASE_DIR%\"
    
    echo Executable moved to: %RELEASE_DIR%\wts_gui.exe
    
    :: Clean up build artifacts
    rmdir /s /q build
    rmdir /s /q dist
    del wts_gui.spec
) else (
    echo.
    echo Build Failed!
)

pause
