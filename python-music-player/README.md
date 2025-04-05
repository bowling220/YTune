# YTune

A modern music player built with Python and PySide6, featuring YouTube download functionality.

## Features

- Modern dark UI inspired by popular music players(In Progress)
- Music library management and playback
- YouTube download integration - download songs directly from YouTube
- Album art support(In Progress)
- Playlist management(In Progress)
- Responsive design(In Progress)

## Installation

1. Make sure you have Python 3.6+ installed on your system
2. Install FFmpeg (required for YouTube download functionality):
   - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) or install with Chocolatey: `choco install ffmpeg`
   - **macOS**: Install with Homebrew: `brew install ffmpeg`
   - **Linux**: Install with your package manager (e.g., `sudo apt install ffmpeg`)
   - **IMPORTANT**: After installing FFmpeg, copy the ffmpeg.exe file to the `bin` folder in the YTune directory
3. Run the installation script to install dependencies:

```bash
python install_requirements.py
```


This will install the required packages:
- PySide6 (GUI framework)
- yt-dlp (YouTube downloader)
- mutagen (Music tag handling)

## Running the Application

Start the application by running:

```bash
python main.py
```

On first run, you'll be prompted to select your music directory.

## Using YouTube Download Feature

The application allows you to download music directly from YouTube:

1. Click the "YT" button in the toolbar or select "File > Download from YouTube..."
2. Paste a YouTube URL into the dialog
3. Optionally enter a custom filename or leave it blank to use the video title
4. Click "Download" and wait for the process to complete
5. The downloaded song will be saved to your music library and available for playback


## Distribution

### Creating an Executable

To build a standalone executable that others can run without installing Python:

1. Make sure you have PyInstaller installed:
```bash
pip install pyinstaller
```

2. Run the build script:
```bash
python build_executable.py
```

3. The executable will be available in the `build/dist` directory

### Sharing the Application

#### Method 1: Share the executable
- Upload the executable to a file sharing service like Google Drive, Dropbox, or OneDrive
- Share the download link with others
- Users can simply download and run the executable without installing Python

#### Method 2: Create an installer
1. Install NSIS (Nullsoft Scriptable Install System) from [nsis.sourceforge.io](https://nsis.sourceforge.io/)
2. Use the NSIS script in the `installer` directory:
```bash
makensis installer/installer.nsi
```
3. Share the resulting installer with others

#### Method 3: Share the source code
- Push your code to GitHub or another Git hosting service
- Users can clone the repository and follow the installation instructions
- Note: The ffmpeg.exe file is not included in the repository due to size limitations. Users must download it separately as described in the Installation section.

## Requirements

- Python 3.8 or higher
- FFmpeg (required for audio conversion)
- Internet connection for YouTube downloads
- Audio playback support on your system

## Troubleshooting

- If you encounter the error "The system cannot find the file specified" when downloading:
  1. Make sure FFmpeg is installed and in your system PATH
  2. Make sure you've copied ffmpeg.exe to the bin folder
  3. Run `pip install --upgrade yt-dlp` to ensure you have the latest version
  4. Restart the application

- If the application won't start, try running the installation script again to ensure all dependencies are properly installed.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 