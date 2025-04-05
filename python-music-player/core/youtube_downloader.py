#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import uuid
import tempfile
import subprocess
from typing import Optional, Tuple, Dict
from PySide6.QtCore import QObject, Signal, QRunnable, Slot
import platform
import zipfile
import shutil
from urllib.request import urlretrieve
import time
import traceback

class DownloaderSignals(QObject):
    """Signals for the YouTube downloader worker."""
    started = Signal(str)  # URL of the video
    progress = Signal(float)  # Progress percentage (0-100)
    finished = Signal(str, str)  # (url, local_file_path)
    error = Signal(str, str)  # (url, error_message)
    status_update = Signal(str)  # Status message for UI

class YouTubeDownloader(QRunnable):
    """Worker to download YouTube videos as MP3 files."""
    
    def __init__(self, url: str, output_dir: str, filename: Optional[str] = None, 
                 ffmpeg_path: Optional[str] = None, is_playlist: bool = False):
        """
        Initialize the downloader
        
        Args:
            url: YouTube URL to download
            output_dir: Directory to save the downloaded audio
            filename: Optional custom filename (without extension)
            ffmpeg_path: Optional path to FFmpeg executable
            is_playlist: Whether to download as a playlist
        """
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self.custom_filename = filename
        self.ffmpeg_path = ffmpeg_path
        self.is_playlist = is_playlist
        self.signals = DownloaderSignals()
        self.is_cancelled = False
        self.playlist_items = None  # Will store info about playlist items if is_playlist=True
        
    def _validate_url(self) -> bool:
        """Check if the URL is a valid YouTube URL."""
        youtube_regex = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
        return bool(re.match(youtube_regex, self.url))
    
    def _get_output_path(self, video_title: str) -> str:
        """Generate a valid output path based on title or custom filename"""
        if self.custom_filename:
            # Use the custom filename if provided
            filename = self.custom_filename
        else:
            # Clean up video title to make a valid filename
            filename = re.sub(r'[\\/*?:"<>|]', '', video_title)
            
            # Format as Artist - Title if we can detect a good pattern
            if " - " not in filename:
                # Try to extract artist from common YouTube patterns
                artist_match = re.search(r'^(.*?)\s*[-–—:]\s*(.*?)$', filename)
                if artist_match:
                    artist, title = artist_match.groups()
                    filename = f"{artist.strip()} - {title.strip()}"
                elif "by" in filename.lower():
                    # Look for "Title by Artist" pattern
                    by_match = re.search(r'(.*)\s+by\s+(.*)', filename, re.IGNORECASE)
                    if by_match:
                        title, artist = by_match.groups()
                        filename = f"{artist.strip()} - {title.strip()}"
            
        # Ensure filename is not too long
        if len(filename) > 100:
            filename = filename[:97] + '...'
        
        return os.path.join(self.output_dir, f"{filename}.%(ext)s")
    
    def _get_ytdlp_command(self):
        """Get the command to run yt-dlp or youtube-dl with proper error checking."""
        # Check for yt-dlp in PATH (preferred)
        ytdlp_path = shutil.which("yt-dlp")
        if ytdlp_path:
            self.signals.status_update.emit(f"Using yt-dlp: {ytdlp_path}")
            return [ytdlp_path]
        
        # Check for youtube-dl in PATH
        youtube_dl_path = shutil.which("youtube-dl")
        if youtube_dl_path:
            self.signals.status_update.emit(f"Using youtube-dl: {youtube_dl_path}")
            return [youtube_dl_path]
        
        # Check for existing yt-dlp in our bin directory
        bin_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
        if sys.platform == 'win32':
            local_ytdlp = os.path.join(bin_path, "yt-dlp.exe")
        else:
            local_ytdlp = os.path.join(bin_path, "yt-dlp")
        
        if os.path.exists(local_ytdlp):
            self.signals.status_update.emit(f"Using local yt-dlp: {local_ytdlp}")
            return [local_ytdlp]
        
        # Check for yt-dlp in common Windows locations
        if sys.platform == 'win32':
            for path in [
                os.path.join(os.environ.get('APPDATA', ''), 'yt-dlp', 'yt-dlp.exe'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'yt-dlp', 'yt-dlp.exe'),
                os.path.join(os.environ.get('PROGRAMFILES', ''), 'yt-dlp', 'yt-dlp.exe'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'yt-dlp', 'yt-dlp.exe')
            ]:
                if os.path.exists(path):
                    self.signals.status_update.emit(f"Found yt-dlp at: {path}")
                    return [path]
        
        # Try to download yt-dlp
        downloaded_path = self._download_ytdlp()
        if downloaded_path:
            return [downloaded_path]
        
        # No executables found, try Python modules
        try:
            # Try importing yt-dlp or youtube_dl modules
            try:
                import yt_dlp
                self.signals.status_update.emit("Using yt-dlp Python module")
                return [sys.executable, "-m", "yt_dlp"]
            except ImportError:
                try:
                    import youtube_dl
                    self.signals.status_update.emit("Using youtube-dl Python module")
                    return [sys.executable, "-m", "youtube_dl"]
                except ImportError:
                    pass
        except Exception as e:
            print(f"Error checking for Python modules: {e}")
        
        # We couldn't find any downloader
        error_msg = "Error: Could not find or download yt-dlp or youtube-dl. Please install yt-dlp manually."
        self.signals.error.emit(self.url, error_msg)
        print(error_msg)
        
        # Return a command that will give a more user-friendly error
        if sys.platform == 'win32':
            return ["cmd", "/c", "echo", error_msg, "&", "pause"]
        else:
            return ["echo", error_msg]

    def _build_command(self):
        """Build the command to run youtube-dl or yt-dlp."""
        # Get the base command (either youtube-dl or yt-dlp)
        ytdlp_cmd = self._get_ytdlp_command()
        
        # Add ffmpeg location if available
        ffmpeg_location = []
        if self.ffmpeg_path:
            ffmpeg_location = [f"--ffmpeg-location={self.ffmpeg_path}"]
        
        # Build different commands for playlist vs single video
        if self.is_playlist:
            # Playlist download command with output template for numbered files
            # Use format "[NN] Title" for better visibility of track numbers
            cmd = [
                *ytdlp_cmd,
                "--ignore-errors",  # Skip errors to continue with playlist
                "-f", "bestaudio",
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "0",  # Best quality
                *ffmpeg_location,
                "--yes-playlist",  # Force playlist processing
                "--no-abort-on-error",  # Don't abort on download errors
                "-o", os.path.join(self.output_dir, "[%(playlist_index)03d] %(title)s.%(ext)s"),  # Use brackets for numbering
                "--restrict-filenames",  # Avoid encoding issues with filenames
                "--verbose",  # Add verbose output for debugging
                self.url
            ]
        else:
            # Single video download command
            # Make sure to handle output path correctly (don't use -o= format)
            output_path = os.path.join(self.output_dir, "%(title)s.%(ext)s")
            if self.custom_filename:
                # Use custom filename if provided
                output_path = os.path.join(self.output_dir, f"{self.custom_filename}.%(ext)s")
            
            cmd = [
                *ytdlp_cmd,
                "-f", "bestaudio",
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                *ffmpeg_location,
                "-o", output_path,  # Use separate args for -o option
                "--restrict-filenames",  # Avoid encoding issues
                "--verbose",  # Add verbose output for debugging
                self.url
            ]
        
        return cmd
    
    def _get_default_ffmpeg_path(self):
        """Try to find FFmpeg in standard locations"""
        # Check if FFmpeg is in our bin directory
        bin_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
        
        if sys.platform == 'win32':
            ffmpeg_path = os.path.join(bin_path, "ffmpeg.exe")
            if os.path.exists(ffmpeg_path):
                return ffmpeg_path
            
            # Check Program Files
            for program_files in [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]:
                if program_files:
                    ffmpeg_path = os.path.join(program_files, "FFmpeg", "bin", "ffmpeg.exe")
                    if os.path.exists(ffmpeg_path):
                        return ffmpeg_path
        else:
            # Mac or Linux
            ffmpeg_path = os.path.join(bin_path, "ffmpeg")
            if os.path.exists(ffmpeg_path):
                return ffmpeg_path
            
            # Check system path
            ffmpeg_path = shutil.which("ffmpeg")
            if ffmpeg_path:
                return ffmpeg_path
                
            # Check common locations on Mac
            if sys.platform == 'darwin':
                for path in ["/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
                    if os.path.exists(path):
                        return path
            
            # Check common locations on Linux
            elif sys.platform.startswith('linux'):
                for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
                    if os.path.exists(path):
                        return path
        
        return None
    
    def _try_download_ffmpeg(self):
        """
        Attempt to download FFmpeg for the current platform
        Returns True if successful, False if failed
        """
        self.signals.status_update.emit("Attempting to download FFmpeg automatically...")
        
        system = platform.system().lower()
        ffmpeg_base_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
        
        # Create bin directory if it doesn't exist
        os.makedirs(ffmpeg_base_path, exist_ok=True)
        
        temp_dir = tempfile.mkdtemp()
        download_path = os.path.join(temp_dir, "ffmpeg.zip")
        
        try:
            if system == "windows":
                # Download Windows binary
                url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
                self.signals.status_update.emit(f"Downloading Windows FFmpeg from {url}...")
                urlretrieve(url, download_path)
                
                # Extract the zip file
                with zipfile.ZipFile(download_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Find the ffmpeg.exe in the extracted folders
                found = False
                for root, dirs, files in os.walk(temp_dir):
                    if "ffmpeg.exe" in files:
                        ffmpeg_src = os.path.join(root, "ffmpeg.exe")
                        ffmpeg_dst = os.path.join(ffmpeg_base_path, "ffmpeg.exe")
                        shutil.copy2(ffmpeg_src, ffmpeg_dst)
                        self.ffmpeg_path = ffmpeg_dst
                        found = True
                        break
                
                if not found:
                    # Try alternative URL if first one failed
                    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
                    self.signals.status_update.emit(f"Trying alternative Windows FFmpeg from {url}...")
                    urlretrieve(url, download_path)
                    
                    # Extract the zip file
                    with zipfile.ZipFile(download_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                    
                    # Find the ffmpeg.exe in the extracted folders
                    for root, dirs, files in os.walk(temp_dir):
                        if "ffmpeg.exe" in files:
                            ffmpeg_src = os.path.join(root, "ffmpeg.exe")
                            ffmpeg_dst = os.path.join(ffmpeg_base_path, "ffmpeg.exe")
                            shutil.copy2(ffmpeg_src, ffmpeg_dst)
                            self.ffmpeg_path = ffmpeg_dst
                            found = True
                            break
            
            elif system == "darwin":  # macOS
                # Download macOS binary
                url = "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip"
                self.signals.status_update.emit(f"Downloading macOS FFmpeg from {url}...")
                urlretrieve(url, download_path)
                
                # Extract the zip file
                with zipfile.ZipFile(download_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Find the ffmpeg binary
                ffmpeg_src = os.path.join(temp_dir, "ffmpeg")
                ffmpeg_dst = os.path.join(ffmpeg_base_path, "ffmpeg")
                shutil.copy2(ffmpeg_src, ffmpeg_dst)
                os.chmod(ffmpeg_dst, 0o755)  # Make executable
                self.ffmpeg_path = ffmpeg_dst
            
            elif system == "linux":
                # Download Linux binary
                url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
                self.signals.status_update.emit(f"Downloading Linux FFmpeg from {url}...")
                urlretrieve(url, download_path)
                
                # Extract the tar.xz file
                shutil.unpack_archive(download_path, temp_dir)
                
                # Find the ffmpeg binary in the extracted folder
                for root, dirs, files in os.walk(temp_dir):
                    if "ffmpeg" in files:
                        ffmpeg_src = os.path.join(root, "ffmpeg")
                        ffmpeg_dst = os.path.join(ffmpeg_base_path, "ffmpeg")
                        shutil.copy2(ffmpeg_src, ffmpeg_dst)
                        os.chmod(ffmpeg_dst, 0o755)  # Make executable
                        self.ffmpeg_path = ffmpeg_dst
                        break
            
            else:
                self.signals.status_update.emit(f"Unsupported platform: {system}")
                return False
            
            # Verify that FFmpeg was downloaded and is executable
            if hasattr(self, 'ffmpeg_path') and os.path.exists(self.ffmpeg_path):
                self.signals.status_update.emit(f"FFmpeg downloaded successfully to: {self.ffmpeg_path}")
                return True
            else:
                self.signals.status_update.emit("Failed to download FFmpeg: File not found after download")
                return False
                
        except Exception as e:
            self.signals.status_update.emit(f"Failed to download FFmpeg: {str(e)}")
            return False
        finally:
            # Clean up temp directory
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"Error cleaning up temp directory: {e}")
    
    def cancel(self):
        """Cancel the download."""
        self.is_cancelled = True
    
    @Slot()
    def run(self):
        """Run the downloader."""
        try:
            self.signals.started.emit(self.url)
            
            # Ensure output directory exists
            os.makedirs(self.output_dir, exist_ok=True)
            
            # Try using Python module directly as a last resort
            def try_python_module_directly():
                self.signals.status_update.emit("Trying direct Python module integration...")
                try:
                    # Try importing yt-dlp module
                    try:
                        import yt_dlp as ytdl
                    except ImportError:
                        try:
                            import youtube_dl as ytdl
                        except ImportError:
                            self.signals.error.emit(self.url, "Could not import yt-dlp or youtube-dl modules")
                            return None
                    
                    # Configure options
                    output_template = os.path.join(self.output_dir, '%(title)s.%(ext)s')
                    if self.is_playlist:
                        output_template = os.path.join(self.output_dir, '[%(playlist_index)03d] %(title)s.%(ext)s')
                    
                    ydl_opts = {
                        'format': 'bestaudio/best',
                        'outtmpl': output_template,
                        'restrictfilenames': True,
                        'ignoreerrors': True,
                        'nooverwrites': True,
                        'noplaylist': not self.is_playlist,
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                        'progress_hooks': [self._ytdl_progress_hook],
                    }
                    
                    # Add FFmpeg location if available
                    if self.ffmpeg_path and os.path.exists(self.ffmpeg_path):
                        ydl_opts['ffmpeg_location'] = self.ffmpeg_path
                    
                    # Print options for debugging
                    print(f"Direct module options: {ydl_opts}")
                    self.signals.status_update.emit("Starting download with direct module integration")
                    
                    # Actually run the download
                    with ytdl.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(self.url, download=True)
                    
                    # Check if we got results
                    if not info:
                        self.signals.error.emit(self.url, "Failed to get video information")
                        return None
                    
                    # Get the output file path
                    if self.is_playlist and 'entries' in info:
                        self.signals.status_update.emit(f"Playlist download complete")
                        self.signals.progress.emit(100)
                        return self.output_dir
                    elif not self.is_playlist:
                        # Try to find the downloaded file
                        filename = ytdl.prepare_filename(info)
                        mp3_path = os.path.splitext(filename)[0] + '.mp3'
                        
                        if os.path.exists(mp3_path):
                            self.signals.status_update.emit(f"Download complete: {os.path.basename(mp3_path)}")
                            self.signals.progress.emit(100)
                            return mp3_path
                        
                    # Look for any MP3 files created in the last minute
                    recent_files = []
                    one_minute_ago = time.time() - 60
                    for filename in os.listdir(self.output_dir):
                        filepath = os.path.join(self.output_dir, filename)
                        if (os.path.isfile(filepath) and 
                            filepath.endswith('.mp3') and 
                            os.path.getmtime(filepath) > one_minute_ago):
                            recent_files.append(filepath)
                    
                    if recent_files:
                        newest_file = max(recent_files, key=os.path.getmtime)
                        self.signals.status_update.emit(f"Download complete: {os.path.basename(newest_file)}")
                        self.signals.progress.emit(100)
                        return newest_file
                    
                    # Still not found but we had info
                    self.signals.status_update.emit("Download completed but file location unknown")
                    self.signals.progress.emit(100)
                    return self.output_dir
                    
                except Exception as e:
                    print(f"Direct module approach failed: {str(e)}")
                    traceback.print_exc()
                    return None
            
            # First try with yt-dlp/youtube-dl
            try:
                # Prepare command
                youtube_dl_cmd = self._build_command()
                
                # Validate the command before running
                if not youtube_dl_cmd or len(youtube_dl_cmd) < 2:
                    self.signals.status_update.emit("YouTube downloader executable not found. Trying alternative method...")
                    raise FileNotFoundError("YouTube downloader executable not found")
                    
                # Log what we're about to execute
                cmd_str = " ".join(youtube_dl_cmd)
                print(f"Executing: {cmd_str}")
                self.signals.status_update.emit(f"Starting download: {self.url}")
                
                # Check if the executable actually exists
                if not os.path.exists(youtube_dl_cmd[0]) and not shutil.which(youtube_dl_cmd[0]):
                    # Special handling for Python module commands
                    if youtube_dl_cmd[0] == sys.executable and len(youtube_dl_cmd) > 1 and youtube_dl_cmd[1] == "-m":
                        print(f"Running as Python module: {' '.join(youtube_dl_cmd)}")
                    else:
                        self.signals.status_update.emit(f"Cannot find executable: {youtube_dl_cmd[0]}. Trying alternative method...")
                        raise FileNotFoundError(f"Cannot find executable: {youtube_dl_cmd[0]}")
                
                # Set environment variables for encoding
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                
                # Try downloading with a simple process call first
                try:
                    # Create a temporary directory for more predictable output paths
                    temp_dir = os.path.join(self.output_dir, f"temp_{uuid.uuid4().hex[:8]}")
                    os.makedirs(temp_dir, exist_ok=True)
                    
                    # Modify the command to use the temp directory
                    modified_cmd = youtube_dl_cmd.copy()
                    for i, arg in enumerate(modified_cmd):
                        if arg.startswith("-o=") or arg.startswith("-o "):
                            # Replace output template
                            modified_cmd[i] = f"-o={os.path.join(temp_dir, '%(title)s.%(ext)s')}"
                        elif i > 0 and modified_cmd[i-1] == "-o":
                            # Replace output path
                            modified_cmd[i] = os.path.join(temp_dir, "%(title)s.%(ext)s")
                    
                    # Run the process directly for better reliability
                    print(f"Running simplified command: {' '.join(modified_cmd)}")
                    process_result = subprocess.run(
                        modified_cmd,
                        capture_output=True,
                        text=True,
                        errors='replace',
                        env=env
                    )
                    
                    # Check for files in the temp directory
                    downloaded_files = []
                    for file in os.listdir(temp_dir):
                        file_path = os.path.join(temp_dir, file)
                        if os.path.isfile(file_path) and file.endswith('.mp3'):
                            downloaded_files.append(file_path)
                    
                    if downloaded_files:
                        # Move the file to the target directory
                        for file_path in downloaded_files:
                            target_path = os.path.join(self.output_dir, os.path.basename(file_path))
                            shutil.move(file_path, target_path)
                            self.signals.status_update.emit(f"Download complete: {os.path.basename(target_path)}")
                            self.signals.finished.emit(self.url, target_path)
                            return
                    
                    # If we get here, the simplified approach didn't work
                    # Check for errors in the output
                    error_output = process_result.stderr
                    if error_output and "ERROR:" in error_output:
                        print(f"yt-dlp error: {error_output}")
                        raise Exception(f"yt-dlp error: {error_output.strip()}")
                    
                    # If no direct error, continue with the more complex approach
                    raise Exception("No files downloaded, trying alternate method")
                    
                except Exception as e:
                    print(f"Simple approach failed: {str(e)}, trying advanced method...")
                    # Continue to the more complex approach with pipe handling
                
                    # Start the process with pipe handling
                    process = subprocess.Popen(
                        youtube_dl_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=False,  # Get byte streams
                        bufsize=0,  # Unbuffered for binary mode
                        env=env
                    )
                    
                    # Process the download and get the output file
                    output_file = self._process_download(process)
                    
                    # If the output file is None, there was an error
                    if not output_file:
                        raise Exception("Failed to download with yt-dlp")
                    
                    # Success with yt-dlp
                    basename = os.path.basename(output_file) if output_file else "Unknown"
                    self.signals.status_update.emit(f"Download complete: {basename}")
                    self.signals.finished.emit(self.url, output_file)
                    return
                
            except (FileNotFoundError, PermissionError, Exception) as e:
                # First attempt failed, try pytube fallback
                print(f"yt-dlp download failed: {str(e)}. Trying pytube fallback...")
                self.signals.status_update.emit("First download method failed. Trying alternative...")
                
                # Try using pytube as a fallback
                output_file = self._download_with_pytube()
                
                if output_file:
                    # Success with pytube
                    if os.path.isdir(output_file):
                        self.signals.status_update.emit("Playlist download complete!")
                    else:
                        basename = os.path.basename(output_file)
                        self.signals.status_update.emit(f"Download complete: {basename}")
                        
                    self.signals.finished.emit(self.url, output_file)
                    return
                else:
                    # Both methods failed
                    self.signals.error.emit(self.url, "All download methods failed. Please try again later.")
                    return
            
            # After all other methods fail, try direct module integration
            self.signals.status_update.emit("All download methods failed. Trying final approach...")
            output_file = try_python_module_directly()
            
            if output_file:
                # Success with direct module integration
                if os.path.isdir(output_file):
                    # Count how many MP3 files were downloaded 
                    mp3_count = 0
                    for filename in os.listdir(output_file):
                        if filename.endswith('.mp3'):
                            mp3_count += 1
                    
                    if mp3_count > 0:
                        self.signals.status_update.emit(f"Playlist download complete! Downloaded {mp3_count} tracks.")
                    else:
                        self.signals.status_update.emit("Playlist download complete!")
                else:
                    basename = os.path.basename(output_file)
                    self.signals.status_update.emit(f"Download complete: {basename}")
                    
                self.signals.finished.emit(self.url, output_file)
                return
            else:
                # All methods failed
                self.signals.error.emit(self.url, "All download methods failed. Please check the URL and try again later.")
                return
            
        except Exception as e:
            print(f"Error in downloader: {str(e)}")
            traceback.print_exc()
            self.signals.error.emit(self.url, str(e))
            return

    def _process_download(self, process):
        """Process the download and emit progress signals."""
        # Initialize variables for tracking playlist download progress
        self.current_video = 0
        self.total_videos = 1  # Default to 1 for single video
        output_file = None
        
        import select
        import time

        # Loop until process completes
        while process.poll() is None and not self.is_cancelled:
            try:
                # Check which file descriptors are ready to read without blocking
                if sys.platform == 'win32':
                    # Windows doesn't support select on pipes, so just read with timeout
                    line = b''
                    error_line = b''
                    
                    # Read from stdout if data available
                    try:
                        line = process.stdout.readline()
                    except (IOError, OSError):
                        pass
                        
                    # Read from stderr if data available    
                    try:
                        error_line = process.stderr.readline()
                    except (IOError, OSError):
                        pass
                        
                    # If no data was read, sleep briefly to avoid CPU spinning
                    if not line and not error_line:
                        time.sleep(0.1)
                        continue
                else:
                    # Unix platforms can use select for non-blocking IO
                    reads = [process.stdout, process.stderr]
                    ret = select.select(reads, [], [], 0.1)
                    
                    if not ret[0]:
                        # No data available, try again
                        continue
                        
                    # Read from available file descriptors
                    line = b''
                    error_line = b''
                    
                    if process.stdout in ret[0]:
                        line = process.stdout.readline()
                        
                    if process.stderr in ret[0]:
                        error_line = process.stderr.readline()
                
                # Decode the byte streams
                line_text = line.decode('utf-8', errors='replace').strip()
                error_text = error_line.decode('utf-8', errors='replace').strip()
                
                if not line_text and not error_text:
                    continue
                    
                # Process stderr for errors
                if error_text:
                    print(f"STDERR: {error_text}")
                    # Check for specific error messages
                    if "ERROR:" in error_text:
                        self.signals.error.emit(self.url, error_text)
                        return None
                
                # Process stdout for progress updates
                if line_text:
                    # Look for destination file path
                    dest_match = re.search(r'\[download\] Destination: (.+)', line_text)
                    if dest_match:
                        output_path = dest_match.group(1)
                        filename = os.path.basename(output_path)
                        if self.is_playlist and self.total_videos > 1:
                            self.signals.status_update.emit(f"Downloading [{self.current_video}/{self.total_videos}]: {filename}")
                        else:
                            self.signals.status_update.emit(f"Downloading: {filename}")
                        output_file = output_path
                    
                    # Look for video count in playlist
                    playlist_match = re.search(r'Downloading (\d+) videos', line_text)
                    if playlist_match:
                        self.total_videos = int(playlist_match.group(1))
                        self.signals.status_update.emit(f"Found {self.total_videos} videos in playlist")
                    
                    # Look for current video in playlist
                    video_index_match = re.search(r'\[download\] Downloading video (\d+) of (\d+)', line_text)
                    if video_index_match:
                        self.current_video = int(video_index_match.group(1))
                        self.total_videos = int(video_index_match.group(2))
                        filename = os.path.basename(output_file or 'video')
                        self.signals.status_update.emit(f"Downloading [{self.current_video}/{self.total_videos}]: {filename}")
                    
                    # Look for overall progress percentage
                    progress_match = re.search(r'\[download\]\s+(\d+\.\d+)%', line_text)
                    if progress_match:
                        individual_progress = float(progress_match.group(1))
                        # If we're downloading a playlist, calculate overall progress
                        if self.total_videos > 1:
                            # Weight the progress: completed videos + current video progress
                            overall_progress = ((self.current_video - 1) + (individual_progress / 100)) / self.total_videos * 100
                            # Cap at 99.9% until completely done
                            overall_progress = min(overall_progress, 99.9)
                            self.signals.progress.emit(overall_progress)
                        else:
                            self.signals.progress.emit(individual_progress)
                    
                    # Look for conversion/processing messages
                    if "[ffmpeg] Destination:" in line_text:
                        output_match = re.search(r'\[ffmpeg\] Destination: (.+)', line_text)
                        if output_match:
                            output_file = output_match.group(1)
                            filename = os.path.basename(output_file)
                            if self.is_playlist and self.total_videos > 1:
                                self.signals.status_update.emit(f"Converting [{self.current_video}/{self.total_videos}]: {filename}")
                            else:
                                self.signals.status_update.emit(f"Converting: {filename}")
                    
                    # Look for completion
                    if "Deleting original file" in line_text:
                        if self.total_videos == 1 or self.current_video == self.total_videos:
                            # Final file is done
                            self.signals.status_update.emit("Download complete, verifying file...")
            
            except Exception as e:
                print(f"Error processing youtube-dl output: {str(e)}")
                # Continue processing despite the error
        
        # Make sure to drain any remaining output
        process.communicate()
        
        # Check if process was cancelled
        if self.is_cancelled:
            return None
        
        # Verify file exists
        if output_file and os.path.exists(output_file):
            # File exists and process completed
            self.signals.progress.emit(100)
            return output_file
        else:
            # Look for any downloaded files in the target directory
            if os.path.isdir(self.output_dir):
                # Check if any files were created in the last minute
                recent_files = []
                one_minute_ago = time.time() - 60
                
                for filename in os.listdir(self.output_dir):
                    filepath = os.path.join(self.output_dir, filename)
                    if os.path.isfile(filepath) and os.path.getmtime(filepath) > one_minute_ago:
                        # File was recently created
                        recent_files.append(filepath)
            
            if recent_files:
                # Return the most recently created file
                newest_file = max(recent_files, key=os.path.getmtime)
                return newest_file
            
            # No file found
            self.signals.error.emit(self.url, "Download completed but no output file was found. The download may have failed silently.")
            return None

    def _download_ytdlp(self):
        """Automatically download yt-dlp to a local folder."""
        try:
            self.signals.status_update.emit("yt-dlp not found. Attempting to download it automatically...")
            
            # Create bin directory in the application folder
            bin_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
            os.makedirs(bin_path, exist_ok=True)
            
            # Download the appropriate executable based on platform
            if sys.platform == 'win32':
                # Windows binary
                ytdlp_url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
                ytdlp_path = os.path.join(bin_path, "yt-dlp.exe")
            else:
                # Unix binary
                ytdlp_url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
                ytdlp_path = os.path.join(bin_path, "yt-dlp")
            
            self.signals.status_update.emit(f"Downloading yt-dlp from {ytdlp_url}...")
            urlretrieve(ytdlp_url, ytdlp_path)
            
            # Make executable on Unix systems
            if sys.platform != 'win32':
                os.chmod(ytdlp_path, 0o755)
            
            if os.path.exists(ytdlp_path):
                self.signals.status_update.emit(f"Successfully downloaded yt-dlp to {ytdlp_path}")
                return ytdlp_path
            
            return None
        except Exception as e:
            self.signals.status_update.emit(f"Failed to download yt-dlp: {str(e)}")
            return None

    def _download_with_pytube(self):
        """Fallback method to download using pytube library."""
        try:
            self.signals.status_update.emit("Falling back to pytube for download...")
            
            # Import pytube library
            try:
                from pytube import YouTube, Playlist
            except ImportError:
                self.signals.error.emit(self.url, "pytube library not found. Please install with: pip install pytube")
                return None
            
            # Ensure output directory exists
            os.makedirs(self.output_dir, exist_ok=True)
            
            # Determine if URL is a playlist
            if self.is_playlist:
                self.signals.status_update.emit("Processing playlist with pytube...")
                try:
                    playlist = Playlist(self.url)
                    self.total_videos = len(playlist.video_urls)
                    self.signals.status_update.emit(f"Found {self.total_videos} videos in playlist")
                    
                    downloaded_files = []
                    for i, video_url in enumerate(playlist.video_urls):
                        if self.is_cancelled:
                            break
                        
                        self.current_video = i + 1
                        self.signals.status_update.emit(f"Downloading: video {self.current_video} of {self.total_videos}")
                        
                        # Download the individual video
                        try:
                            yt = YouTube(video_url)
                            # Calculate progress percentage for the playlist
                            overall_progress = (i / self.total_videos) * 100
                            self.signals.progress.emit(min(overall_progress, 99.9))
                            
                            # Download audio stream
                            audio_stream = yt.streams.filter(only_audio=True).first()
                            # Add numbering to the filename - use bracketed format
                            base_filename = f"[{i+1:03d}] {self._sanitize_filename(yt.title)}"
                            output_file = os.path.join(self.output_dir, base_filename)
                            downloaded_file = audio_stream.download(output_path=self.output_dir, filename=base_filename)
                            
                            # Convert to mp3
                            mp3_file = self._convert_to_mp3(downloaded_file)
                            if mp3_file:
                                downloaded_files.append(mp3_file)
                                
                        except Exception as e:
                            print(f"Error downloading video {video_url}: {str(e)}")
                            # Continue with the next video
                            continue
                    
                    if downloaded_files:
                        self.signals.progress.emit(100)
                        return self.output_dir  # Return the directory for playlists
                    return None
                    
                except Exception as e:
                    self.signals.error.emit(self.url, f"Failed to process playlist: {str(e)}")
                    return None
            else:
                # Single video download
                self.signals.status_update.emit("Downloading single video with pytube...")
                try:
                    yt = YouTube(self.url)
                    # Download audio stream
                    audio_stream = yt.streams.filter(only_audio=True).first()
                    
                    # Use custom filename if provided, otherwise use video title
                    if self.custom_filename:
                        base_filename = self.custom_filename
                    else:
                        base_filename = self._sanitize_filename(yt.title)
                        
                    downloaded_file = audio_stream.download(output_path=self.output_dir, filename=base_filename)
                    
                    # Convert to mp3
                    mp3_file = self._convert_to_mp3(downloaded_file)
                    if mp3_file:
                        self.signals.progress.emit(100)
                        return mp3_file
                        
                    return downloaded_file
                    
                except Exception as e:
                    self.signals.error.emit(self.url, f"Failed to download video: {str(e)}")
                    return None
                
        except Exception as e:
            self.signals.error.emit(self.url, f"Error with pytube downloader: {str(e)}")
            return None
        
    def _sanitize_filename(self, filename):
        """Sanitize filename to be valid on Windows and other platforms."""
        # Remove invalid characters
        filename = re.sub(r'[\\/*?:"<>|]', '', filename)
        # Truncate if too long
        if len(filename) > 100:
            filename = filename[:97] + '...'
        return filename
        
    def _convert_to_mp3(self, file_path):
        """Convert downloaded file to MP3 format using FFmpeg."""
        if not file_path or not os.path.exists(file_path):
            return None
        
        try:
            # Get FFmpeg path
            ffmpeg_path = self.ffmpeg_path
            if not ffmpeg_path:
                ffmpeg_path = self._get_default_ffmpeg_path()
            
            if not ffmpeg_path or not os.path.exists(ffmpeg_path):
                print("FFmpeg not found, can't convert to MP3")
                return file_path  # Return original file if we can't convert
            
            # Create MP3 file path
            mp3_path = os.path.splitext(file_path)[0] + '.mp3'
            
            # Run FFmpeg command
            ffmpeg_cmd = [
                ffmpeg_path,
                '-i', file_path,
                '-vn',  # No video
                '-ar', '44100',  # Audio sampling rate
                '-ac', '2',  # Stereo
                '-b:a', '192k',  # Bitrate
                '-f', 'mp3',  # Format
                mp3_path
            ]
            
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            process.wait()
            
            # Delete original file if conversion successful
            if os.path.exists(mp3_path):
                try:
                    os.remove(file_path)
                except:
                    pass
                return mp3_path
            
            return file_path  # Return original if conversion failed
            
        except Exception as e:
            print(f"Error converting to MP3: {str(e)}")
            return file_path  # Return original file if conversion fails

    def _ytdl_progress_hook(self, d):
        """Progress hook for ytdl module."""
        if d['status'] == 'downloading':
            # Update progress
            total_bytes = d.get('total_bytes')
            downloaded_bytes = d.get('downloaded_bytes')
            
            if total_bytes and downloaded_bytes:
                progress = (downloaded_bytes / total_bytes) * 100
                self.signals.progress.emit(progress)
            
            # Update status message
            eta = d.get('eta')
            if eta:
                speed = d.get('speed', 0)
                speed_str = f"{speed/1024/1024:.2f} MB/s" if speed else "unknown speed"
                self.signals.status_update.emit(f"Downloading: ETA {eta}s at {speed_str}")
            
        elif d['status'] == 'finished':
            self.signals.status_update.emit(f"Download finished, converting to MP3...")
            self.signals.progress.emit(95)  # Almost done, just needs conversion

def download_from_youtube(url: str, output_dir: str, filename: Optional[str] = None, 
                       ffmpeg_path: Optional[str] = None, is_playlist: bool = False) -> YouTubeDownloader:
    """
    Convenience function to create and configure a YouTube downloader worker.
    
    Args:
        url: YouTube URL to download
        output_dir: Directory to save the downloaded audio
        filename: Optional custom filename (without extension)
        ffmpeg_path: Optional path to FFmpeg executable
        is_playlist: Whether the URL is a playlist
        
    Returns:
        Configured YouTubeDownloader instance
    """
    downloader = YouTubeDownloader(url, output_dir, filename, ffmpeg_path, is_playlist)
    return downloader 