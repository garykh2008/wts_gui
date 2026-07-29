#!/bin/bash

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
RELEASE_DIR="$SCRIPT_DIR/release/linux"

echo "Building WTS GUI for Linux (PySide6 Edition)..."

# NOTE: Both the venv and all PyInstaller build/dist output must live on the
# native Linux filesystem, NOT on /mnt/ (Windows NTFS). NTFS does not support
# Unix permissions, causing both ensurepip and chmod to fail under WSL.
VENV_DIR="$HOME/.cache/wts_gui_venv"
BUILD_TMP="$HOME/.cache/wts_gui_build"
DIST_TMP="$HOME/.cache/wts_gui_dist"

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    rm -rf "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

# Verify venv was created successfully
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo ""
    echo "Error: Virtual environment creation failed."
    echo "The 'python3-venv' package is likely missing. Install it with:"
    echo ""
    PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo "    sudo apt install python${PY_VER}-venv"
    echo ""
    exit 1
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Upgrade pip
pip install --upgrade pip

# Install dependencies inside the venv
echo "Installing dependencies (openpyxl, pyinstaller)..."
pip install openpyxl pyinstaller

# Clean previous Linux-side build dirs
rm -rf "$BUILD_TMP" "$DIST_TMP"

# Run PyInstaller
# --onefile:    Bundle everything into a single executable
# --windowed:   No console window (useful for GUI apps)
# --add-data:   Include README files (Linux separator is ':')
# --workpath:   Build intermediates on Linux filesystem (avoids NTFS chmod issues)
# --distpath:   Output binary on Linux filesystem (avoids NTFS chmod issues)
echo "Running PyInstaller..."
pyinstaller --name wts_gui \
            --onefile \
            --windowed \
            --workpath "$BUILD_TMP" \
            --distpath "$DIST_TMP" \
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

    # Copy executable from Linux tmp to the Windows-side release directory
    cp "$DIST_TMP/wts_gui" "$RELEASE_DIR/"

    echo "Executable copied to: $RELEASE_DIR/wts_gui"

    # Clean up Linux-side build artifacts and Windows-side spec file
    rm -rf "$BUILD_TMP" "$DIST_TMP"
    rm -f wts_gui.spec
else
    echo ""
    echo "Build Failed!"
fi

# Deactivate virtual environment
deactivate
