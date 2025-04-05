#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QProgressBar, QMessageBox, QFileDialog,
    QCheckBox
)
from PySide6.QtCore import Qt, QThreadPool, QSettings
from PySide6.QtWidgets import QApplication
import re

from core.youtube_downloader import download_from_youtube


class YouTubeDownloaderDialog(QDialog):
    """Dialog for downloading music from YouTube."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.settings = QSettings("MyCompany", "PythonMusicPlayer")
        self.music_dir = self.settings.value("musicDirectory", "")
        self.ffmpeg_path = self.settings.value("ffmpegLocation", "")
        
        self.setWindowTitle("Download from YouTube")
        self.setMinimumWidth(500)
        self.setup_ui()
        
        self.downloader = None
        self.thread_pool = QThreadPool()
        
    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Dialog title bar with minimize option
        title_bar = QHBoxLayout()
        title_label = QLabel("Download from YouTube")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.minimize_btn = QPushButton("Minimize")
        self.minimize_btn.setToolTip("Minimize to a small floating window")
        self.minimize_btn.clicked.connect(self.toggle_minimize)
        title_bar.addWidget(title_label)
        title_bar.addStretch()
        title_bar.addWidget(self.minimize_btn)
        layout.addLayout(title_bar)
        
        # Store original size
        self.is_minimized = False
        self.original_size = None
        self.original_flags = None
        
        # URL Input
        url_layout = QVBoxLayout()
        url_label = QLabel("Enter YouTube URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=... or https://www.youtube.com/playlist?list=...")
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        layout.addLayout(url_layout)
        
        # Playlist mode
        playlist_layout = QHBoxLayout()
        self.playlist_checkbox = QCheckBox("Download as playlist")
        self.playlist_checkbox.setToolTip("If checked, the URL will be treated as a playlist and all songs will be downloaded")
        playlist_layout.addWidget(self.playlist_checkbox)
        
        # Auto-detect playlist
        auto_detect_btn = QPushButton("Auto-detect")
        auto_detect_btn.setToolTip("Automatically detect if the URL is a playlist")
        auto_detect_btn.clicked.connect(self.auto_detect_playlist)
        playlist_layout.addWidget(auto_detect_btn)
        
        playlist_layout.addStretch()
        layout.addLayout(playlist_layout)
        
        # Custom filename (optional)
        filename_layout = QVBoxLayout()
        filename_label = QLabel("Custom filename (optional):")
        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("Leave empty to use the video title")
        filename_layout.addWidget(filename_label)
        filename_layout.addWidget(self.filename_input)
        layout.addLayout(filename_layout)
        
        # Output directory
        dir_layout = QHBoxLayout()
        dir_label = QLabel("Save to:")
        self.dir_input = QLineEdit()
        self.dir_input.setText(self.music_dir)
        self.dir_input.setReadOnly(True)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_directory)
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.dir_input, 1)
        dir_layout.addWidget(browse_btn)
        layout.addLayout(dir_layout)
        
        # FFmpeg location (optional)
        ffmpeg_layout = QHBoxLayout()
        ffmpeg_label = QLabel("FFmpeg location:")
        self.ffmpeg_input = QLineEdit()
        self.ffmpeg_input.setText(self.ffmpeg_path)
        self.ffmpeg_input.setPlaceholderText("Leave empty to use system PATH: NOT REQUIRED")
        ffmpeg_browse_btn = QPushButton("Browse...")
        ffmpeg_browse_btn.clicked.connect(self.browse_ffmpeg)
        ffmpeg_layout.addWidget(ffmpeg_label)
        ffmpeg_layout.addWidget(self.ffmpeg_input, 1)
        ffmpeg_layout.addWidget(ffmpeg_browse_btn)
        layout.addLayout(ffmpeg_layout)
        
        # Save FFmpeg path checkbox
        save_ffmpeg_layout = QHBoxLayout()
        self.save_ffmpeg_cb = QCheckBox("Remember FFmpeg location")
        self.save_ffmpeg_cb.setChecked(bool(self.ffmpeg_path))
        save_ffmpeg_layout.addWidget(self.save_ffmpeg_cb)
        save_ffmpeg_layout.addStretch()
        layout.addLayout(save_ffmpeg_layout)
        
        # Progress
        progress_layout = QVBoxLayout()
        self.status_label = QLabel("Ready to download")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        # Add track counter for playlists
        track_counter_layout = QHBoxLayout()
        self.track_counter_label = QLabel("")
        self.track_counter_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        track_counter_layout.addStretch()
        track_counter_layout.addWidget(self.track_counter_label)
        
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addLayout(track_counter_layout)
        layout.addLayout(progress_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setDefault(True)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_download)
        self.cancel_btn.setEnabled(False)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        
        button_layout.addWidget(self.download_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def browse_directory(self):
        """Open a directory browser dialog."""
        dir_path = QFileDialog.getExistingDirectory(
            self, 
            "Select Save Directory", 
            self.dir_input.text() or self.music_dir
        )
        if dir_path:
            self.dir_input.setText(dir_path)
    
    def browse_ffmpeg(self):
        """Open a file browser dialog to select FFmpeg executable."""
        if os.name == 'nt':  # Windows
            file_filter = "Executable files (*.exe)"
            executable = "ffmpeg.exe"
        else:  # macOS, Linux
            file_filter = "All files (*)"
            executable = "ffmpeg"
            
        ffmpeg_path = QFileDialog.getOpenFileName(
            self,
            "Select FFmpeg Executable",
            self.ffmpeg_input.text() or os.path.expanduser("~"),
            file_filter
        )[0]
        
        if ffmpeg_path:
            # Check if they selected the directory instead of the executable
            if os.path.isdir(ffmpeg_path):
                ffmpeg_path = os.path.join(ffmpeg_path, executable)
            
            # Check if the selected path is valid
            if not os.path.isfile(ffmpeg_path):
                QMessageBox.warning(
                    self,
                    "Invalid Selection",
                    f"The selected path does not point to a valid FFmpeg executable."
                )
                return
                
            self.ffmpeg_input.setText(ffmpeg_path)
    
    def auto_detect_playlist(self):
        """Auto-detect if the URL is a playlist and set the checkbox accordingly."""
        url = self.url_input.text().strip()
        if not url:
            return
        
        # Simple detection based on URL patterns
        if "playlist" in url or "list=" in url:
            self.playlist_checkbox.setChecked(True)
            self.status_label.setText("Detected as a playlist")
            self.filename_input.setEnabled(False)
            self.filename_input.setPlaceholderText("Filenames will be based on video titles")
        else:
            self.playlist_checkbox.setChecked(False)
            self.status_label.setText("Detected as a single video")
            self.filename_input.setEnabled(True)
            self.filename_input.setPlaceholderText("Leave empty to use the video title")
    
    def start_download(self):
        """Start the download process."""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a YouTube URL.")
            return
        
        output_dir = self.dir_input.text()
        if not output_dir:
            QMessageBox.warning(self, "Error", "Please select a save directory.")
            return
        
        if not os.path.isdir(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create directory: {str(e)}")
                return
        
        # Get FFmpeg path
        ffmpeg_path = self.ffmpeg_input.text().strip() or None
        
        # Save FFmpeg path if checkbox is checked
        if self.save_ffmpeg_cb.isChecked() and ffmpeg_path:
            self.settings.setValue("ffmpegLocation", ffmpeg_path)
        elif not self.save_ffmpeg_cb.isChecked():
            self.settings.remove("ffmpegLocation")
        
        filename = self.filename_input.text().strip() or None
        is_playlist = self.playlist_checkbox.isChecked()
        
        # Create and start the downloader
        self.downloader = download_from_youtube(
            url, 
            output_dir, 
            filename, 
            ffmpeg_path,
            is_playlist=is_playlist
        )
        
        # Connect signals
        self.downloader.signals.started.connect(self.on_download_started)
        self.downloader.signals.progress.connect(self.on_download_progress)
        self.downloader.signals.status_update.connect(self.on_status_update)
        self.downloader.signals.finished.connect(self.on_download_finished)
        self.downloader.signals.error.connect(self.on_download_error)
        
        # Start the download
        self.thread_pool.start(self.downloader)
        
        # Update UI
        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.url_input.setEnabled(False)
        self.filename_input.setEnabled(False)
        self.ffmpeg_input.setEnabled(False)
        self.playlist_checkbox.setEnabled(False)
    
    def cancel_download(self):
        """Cancel the ongoing download."""
        if self.downloader:
            self.downloader.cancel()
            self.status_label.setText("Cancelling download...")
            self.cancel_btn.setEnabled(False)
    
    def on_download_started(self, url):
        """Handle download start."""
        self.status_label.setText(f"Download started: {url}")
        self.progress_bar.setValue(0)
    
    def on_download_progress(self, progress):
        """Update progress bar."""
        self.progress_bar.setValue(int(progress))
    
    def on_status_update(self, status):
        """Update status label."""
        # Look for track number information and enhance the status display
        track_info_match = re.search(r'Downloading: (.*?) \((\d+)/(\d+)\)', status)
        
        if track_info_match:
            # We have track numbering information, make it more visible
            filename = track_info_match.group(1)
            current_track = int(track_info_match.group(2))
            total_tracks = int(track_info_match.group(3))
            
            # Format status to prominently show the track numbers
            enhanced_status = f"Track {current_track} of {total_tracks}: {filename}"
            self.status_label.setText(enhanced_status)
            
            # Update the track counter with percentage
            completion_pct = round((current_track / total_tracks) * 100)
            self.track_counter_label.setText(f"Track {current_track}/{total_tracks} ({completion_pct}% complete)")
        else:
            # Regular status update
            self.status_label.setText(status)
            self.track_counter_label.setText("")
        
        # Update title if minimized
        if self.is_minimized:
            self.update_minimized_title()
    
    def update_minimized_title(self):
        """Update the title of the minimized window to show current status."""
        if not self.is_minimized:
            return
        
        try:
            # Safely get the title label
            title_layout = self.layout().itemAt(0)
            if not title_layout or not title_layout.layout():
                return
            
            title_item = title_layout.layout().itemAt(0)
            if not title_item or not title_item.widget():
                return
            
            title_label = title_item.widget()
            
            # Get status text safely
            if not hasattr(self, 'status_label') or not self.status_label:
                return
            
            status_text = self.status_label.text()
            
            # Look for track numbering in the status text
            track_info_match = re.search(r'Track (\d+) of (\d+)', status_text)
            if track_info_match:
                current_track = track_info_match.group(1)
                total_tracks = track_info_match.group(2)
                # Create a more compact title with just the track numbers
                title_label.setText(f"YouTube Downloader - Track {current_track}/{total_tracks}")
                return
            
            # Truncate if too long
            if len(status_text) > 40:
                status_text = status_text[:37] + "..."
            
            title_label.setText("YouTube Downloader - " + status_text)
        except Exception as e:
            print(f"Error updating minimized title: {e}")
            # Don't let title update errors crash the application
    
    def on_download_finished(self, url, file_path):
        """Handle download completion."""
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.url_input.setEnabled(True)
        self.filename_input.setEnabled(True)
        self.ffmpeg_input.setEnabled(True)
        self.playlist_checkbox.setEnabled(True)
        self.url_input.clear()
        self.filename_input.clear()
        self.progress_bar.setValue(100)
        self.track_counter_label.setText("")
        
        QMessageBox.information(
            self,
            "Download Complete",
            f"Downloaded to:\n{file_path}"
        )
        
        # Trigger a scan in the parent app if possible
        main_window = self.parent()
        if main_window and hasattr(main_window, 'start_scan'):
            main_window.start_scan()
    
    def on_download_error(self, url, error_message):
        """Handle download errors."""
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.url_input.setEnabled(True)
        self.filename_input.setEnabled(True)
        self.ffmpeg_input.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Error: {error_message}")
        
        QMessageBox.warning(
            self,
            "Download Error",
            f"Failed to download from {url}:\n{error_message}"
        ) 

    def toggle_minimize(self):
        """Toggle the minimized state of the dialog."""
        if self.is_minimized:
            self.restore_from_minimized()
        else:
            self.minimize_to_compact_view()

    def minimize_to_compact_view(self):
        """Convert the dialog to a compact floating view."""
        if not self.is_minimized:
            try:
                # Store original state
                self.is_minimized = True
                self.original_size = self.size()
                self.original_pos = self.pos()
                
                # Make a backup of the original window flags
                self.original_flags = self.windowFlags()
                
                # Create a list of elements to keep visible
                keep_visible = [self.status_label, self.progress_bar, self.track_counter_label]
                
                # Store which widgets to hide in a safe way
                self.hidden_widgets = []
                for i in range(self.layout().count()):
                    item = self.layout().itemAt(i)
                    if not item:
                        continue
                        
                    widget = item.widget()
                    layout = item.layout()
                    
                    # Skip the title bar layout
                    if i == 0:
                        continue
                    
                    # If it's a widget, hide it
                    if widget and widget not in keep_visible:
                        if widget.isVisible():
                            self.hidden_widgets.append(widget)
                            widget.setVisible(False)
                            
                    # If it's a layout, check each widget in it
                    elif layout:
                        # Check if this layout contains elements we want to keep
                        contains_important = False
                        for j in range(layout.count()):
                            sub_item = layout.itemAt(j)
                            if not sub_item:
                                continue
                                
                            w = sub_item.widget()
                            if w in keep_visible:
                                contains_important = True
                                break
                        
                        if contains_important:
                            continue
                            
                        # Hide all widgets in this layout
                        for j in range(layout.count()):
                            sub_item = layout.itemAt(j)
                            if not sub_item:
                                continue
                                
                            w = sub_item.widget()
                            if w and w.isVisible():
                                self.hidden_widgets.append(w)
                                w.setVisible(False)
                
                # Change the button text
                self.minimize_btn.setText("Expand")
                
                # Update the title with download info
                self.update_minimized_title()
                    
                # Resize to minimum size
                self.adjustSize()
                
                # Move to bottom right corner of screen, but safely
                try:
                    screen_rect = QApplication.primaryScreen().availableGeometry()
                    self.move(screen_rect.width() - self.width() - 20, 
                              screen_rect.height() - self.height() - 20)
                except Exception as e:
                    print(f"Error positioning window: {e}")
                
                # Set window flags safely
                try:
                    new_flags = self.windowFlags() | Qt.WindowStaysOnTopHint
                    self.setWindowFlags(new_flags)
                    self.show()
                except Exception as e:
                    print(f"Error setting window flags: {e}")
                    # Fallback - just show the window
                    self.show()
                    
            except Exception as e:
                print(f"Error in minimize_to_compact_view: {e}")
                # Reset minimized state if there was an error
                self.is_minimized = False
                self.show()

    def restore_from_minimized(self):
        """Restore the dialog from the compact view."""
        if self.is_minimized:
            try:
                # Restore hidden widgets safely
                for widget in self.hidden_widgets:
                    try:
                        if widget and not widget.isVisible():
                            widget.setVisible(True)
                    except Exception as e:
                        print(f"Error restoring widget: {e}")
                        
                self.hidden_widgets = []
                
                # Change the button text back
                self.minimize_btn.setText("Minimize")
                
                # Restore title
                if hasattr(self, 'original_title'):
                    title_label = self.layout().itemAt(0).layout().itemAt(0).widget()
                    title_label.setText("Download from YouTube")
                
                # Restore window flags safely
                try:
                    if hasattr(self, 'original_flags'):
                        self.setWindowFlags(self.original_flags)
                    else:
                        # Fallback - remove StaysOnTop hint
                        self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
                    self.show()
                except Exception as e:
                    print(f"Error restoring window flags: {e}")
                    self.show()
                
                # Restore size
                if hasattr(self, 'original_size') and self.original_size:
                    try:
                        self.resize(self.original_size)
                    except Exception as e:
                        print(f"Error restoring size: {e}")
                    
                # Restore position
                if hasattr(self, 'original_pos') and self.original_pos:
                    try:
                        self.move(self.original_pos)
                    except Exception as e:
                        print(f"Error restoring position: {e}")
                    
                self.is_minimized = False
                
            except Exception as e:
                print(f"Error in restore_from_minimized: {e}")
                # Ensure window is visible
                self.show()

    def closeEvent(self, event):
        """Handle close event for the dialog."""
        # Clean up any resources if needed
        if hasattr(self, 'downloader') and self.downloader:
            self.downloader.cancel()
        
        # Accept the close event to close the dialog
        event.accept()

def show_youtube_downloader_dialog(parent=None):
    """Create and show a YouTube downloader dialog that's safe from crashes."""
    try:
        dialog = YouTubeDownloaderDialog(parent)
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)  # Ensure dialog is deleted when closed
        dialog.setWindowModality(Qt.NonModal)  # Non-modal to allow music player to work
        dialog.show()
        return dialog
    except Exception as e:
        print(f"Error showing YouTube downloader: {e}")
        if parent:
            QMessageBox.warning(parent, "Error", f"Could not open YouTube downloader: {str(e)}")
        return None 