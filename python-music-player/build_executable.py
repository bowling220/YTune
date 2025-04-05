#!/usr/bin/env python3
"""
Build script for creating a standalone executable of YTune
using PyInstaller.
"""
import os
import sys
import subprocess
import shutil
import platform

def main():
    print("Building YTune executable...")
    
    # Check for PyInstaller
    try:
        import PyInstaller
        print(f"Using PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Create build directory if it doesn't exist
    if not os.path.exists("build"):
        os.makedirs("build")
    
    # Clean any previous build artifacts
    for folder in ["build/build", "build/dist"]:
        if os.path.exists(folder):
            print(f"Cleaning {folder}...")
            shutil.rmtree(folder)
    
    # Determine icon path based on platform
    icon_path = ""
    if platform.system() == "Windows":
        icon_path = os.path.join("assets", "icons", "music_note.png")
    elif platform.system() == "Darwin":  # macOS
        icon_path = os.path.join("assets", "icons", "music_note.png")
    
    # Build the PyInstaller command
    cmd = [
        "pyinstaller",
        "--name=YTune",
        "--onefile",
        "--windowed",
        "--clean",
    ]
    
    # Add icon if available
    if icon_path and os.path.exists(icon_path):
        cmd.append(f"--icon={icon_path}")
    
    # Add data files
    cmd.extend([
        "--add-data=assets;assets",  # Include all assets
        "--add-data=bin;bin",        # Include binaries
    ])
    
    # Fix for PySide6 on Windows
    if platform.system() == "Windows":
        cmd.append("--hidden-import=PySide6.QtSvg")
    
    # Add the main script
    cmd.append("main.py")
    
    # Run PyInstaller
    print("Running PyInstaller with command:")
    print(" ".join(cmd))
    subprocess.check_call(cmd)
    
    # Copy the executable to the build directory
    if os.path.exists("dist"):
        if not os.path.exists("build/dist"):
            os.makedirs("build/dist")
        
        for file in os.listdir("dist"):
            src = os.path.join("dist", file)
            dst = os.path.join("build", "dist", file)
            print(f"Copying {src} to {dst}")
            if os.path.isfile(src):
                shutil.copy2(src, dst)
            elif os.path.isdir(src):
                shutil.copytree(src, dst)
    
    print("Build complete! Executable is in the build/dist directory.")

if __name__ == "__main__":
    main() 