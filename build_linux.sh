#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
RELEASE_DIR="$SCRIPT_DIR/release/linux"

echo "Building WTS GUI for Linux..."

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null
then
    echo "PyInstaller not found. Installing..."
    pip install pyinstaller
fi

# Clean previous build
rm -rf build dist

# Run PyInstaller
# --onefile: Bundle everything into a single executable
# --windowed: No console window
# --add-data: Include README.md (Linux separator is ':')
pyinstaller --name wts_gui --onefile --windowed --add-data "README.md:." wts_gui.py

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
