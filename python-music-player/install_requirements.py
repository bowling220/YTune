#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import os
import platform

def check_python_version():
    """Check if Python version is compatible"""
    required_version = (3, 6)
    current_version = sys.version_info[:2]
    
    if current_version < required_version:
        print(f"Error: Python {required_version[0]}.{required_version[1]} or higher is required.")
        print(f"Current version: {current_version[0]}.{current_version[1]}")
        return False
    return True

def install_package(package):
    """Install a package using pip"""
    print(f"Installing {package}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        return True
    except subprocess.CalledProcessError:
        print(f"Failed to install {package}")
        return False

def install_yt_dlp():
    """Install yt-dlp for YouTube downloading"""
    return install_package("yt-dlp")

def install_pyside6():
    """Install PySide6 for the GUI"""
    return install_package("PySide6")

def install_mutagen():
    """Install mutagen for media tag handling"""
    return install_package("mutagen")

def check_ffmpeg():
    """Check if FFmpeg is installed"""
    print("Checking for FFmpeg...")
    try:
        # Try to run ffmpeg -version to see if it's installed
        result = subprocess.run(
            ["ffmpeg", "-version"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            print("FFmpeg is installed.")
            return True
        else:
            print("FFmpeg command failed.")
            return False
    except FileNotFoundError:
        print("FFmpeg is not installed or not in PATH.")
        return False

def install_ffmpeg_instructions():
    """Provide instructions for installing FFmpeg"""
    system = platform.system()
    print("\nFFmpeg is required for audio conversion. Please install it:")
    
    if system == "Windows":
        print("""
Windows Installation Options:
1. Download from https://ffmpeg.org/download.html
2. Extract the files and add the bin folder to your PATH
3. OR use a package manager like Chocolatey:
   choco install ffmpeg
        """)
    elif system == "Darwin":  # macOS
        print("""
macOS Installation Options:
1. Using Homebrew:
   brew install ffmpeg
2. Using MacPorts:
   port install ffmpeg
        """)
    elif system == "Linux":
        print("""
Linux Installation Options:
1. Debian/Ubuntu:
   sudo apt update && sudo apt install ffmpeg
2. Fedora:
   sudo dnf install ffmpeg
3. Arch Linux:
   sudo pacman -S ffmpeg
        """)
    else:
        print("Please download FFmpeg from https://ffmpeg.org/download.html")
    
    print("After installing FFmpeg, restart your terminal/command prompt.")

def main():
    """Main installation function"""
    print("=== Python Music Player - Dependencies Installer ===\n")
    
    if not check_python_version():
        return False
    
    # Make sure pip is available
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "--version"], 
                              stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("Error: pip is not available. Please install pip first.")
        return False
    
    print("Installing required packages...\n")
    
    # Install dependencies
    success = True
    success = install_pyside6() and success
    success = install_mutagen() and success
    success = install_yt_dlp() and success
    
    # Check for FFmpeg
    ffmpeg_installed = check_ffmpeg()
    if not ffmpeg_installed:
        install_ffmpeg_instructions()
        print("\nWARNING: FFmpeg is required for YouTube download functionality.")
        success = False
    
    if success:
        print("\nAll dependencies installed successfully!")
        print("\nYou can now run the music player with:")
        print("   python main.py")
    else:
        print("\nSome dependencies could not be installed.")
        print("Please check the error messages above and try to install them manually.")
    
    return success

if __name__ == "__main__":
    sys.exit(0 if main() else 1) 