#!/bin/bash

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
RELEASE_DIR="$SCRIPT_DIR/release/linux"

echo "Building WTS GUI for Linux (PySide6 Edition)..."

# Setup Virtual Environment to bypass system package limits (PEP 668)
VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Upgrade pip
pip install --upgrade pip

# Install dependencies inside the venv
echo "Installing dependencies (openpyxl, pyinstaller)..."
pip install openpyxl pyinstaller

# Clean previous build
rm -rf build dist

# Run PyInstaller
# --onefile: Bundle everything into a single executable
# --windowed: No console window (useful for GUI apps)
# --add-data: Include README files (Linux separator is ':')
echo "Running PyInstaller..."
pyinstaller --name wts_gui \
            --onefile \
            --windowed \
            --add-data "README.md:." \
            --add-data "README_zh-TW.md:." \
            --add-data "web:web" \
            --hidden-import=openpyxl \
            --hidden-import=et_xmlfile \
            wts_gui.py

if [ $? -eq 0 ]; then
    echo ""
    echo "Build Successful!"

    # Create release directory if it doesn't exist
    mkdir -p "$RELEASE_DIR"

    # Move executable to release directory
    mv "dist/wts_gui" "$RELEASE_DIR/"

    echo "Executable moved to: $RELEASE_DIR/wts_gui"

    # Clean up build artifacts
    rm -rf build dist wts_gui.spec
else
    echo ""
    echo "Build Failed!"
fi

# Deactivate virtual environment
deactivate
