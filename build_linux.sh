#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
RELEASE_DIR="$SCRIPT_DIR/release/linux"

echo "Building WTS GUI for Linux..."

# Setup Virtual Environment to bypass system package limits (PEP 668)
VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Install dependencies inside the venv
echo "Installing dependencies in virtual environment..."
pip install pyinstaller openpyxl

# Clean previous build
rm -rf build dist

# Run PyInstaller
# --onefile: Bundle everything into a single executable
# --windowed: No console window
# --add-data: Include README.md (Linux separator is ':')
# --hidden-import: Force include openpyxl and its dependencies
pyinstaller --name wts_gui --onefile --windowed --add-data "README.md:." --hidden-import=openpyxl --hidden-import=et_xmlfile wts_gui.py

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
