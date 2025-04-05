# ui/main_window.py
import sys
import os
from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSplitter,
    QPushButton, QListWidget, QStackedWidget, QSlider, QFileDialog, QStatusBar,
    QProgressBar, QMenu, QMessageBox
)
from PySide6 import QtCore
from PySide6.QtCore import Qt, QSize, QUrl, QSettings, QThreadPool, Slot, QTimer
from PySide6.QtGui import QIcon, QPixmap, QImageReader, QPainter, QColor, QAction
from PySide6.QtMultimedia import QMediaPlayer

# Project imports
from core import database, playback
from core.scanner import scan_directories, MediaScanner
from core.models import Track
from utils.formatters import format_duration_ms
from .views.songs_view import SongsView
from .dialogs.youtube_downloader_dialog import YouTubeDownloaderDialog
from core.player import Player
from core.database import Database
from ui.views.playlist_view import PlaylistView
from ui.player_controls import PlayerControls

# --- Icon Paths --- (Adjust if your structure differs)
ICON_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'icons')
def get_icon_path(name):
    return os.path.join(ICON_DIR, name)

def safe_load_icon(icon_path, fallback_color=None):
    """Safely load an icon with fallback if the file doesn't exist"""
    pixmap = QPixmap(icon_path)
    if not pixmap.isNull():
        return pixmap
        
    # Create a fallback icon if loading fails
    print(f"Warning: Could not load icon: {icon_path}")
    temp_pixmap = QPixmap(64, 64)
    temp_pixmap.fill(Qt.GlobalColor.transparent)
    
    # Draw a simple shape
    painter = QPainter(temp_pixmap)
    
    if fallback_color:
        painter.setBrush(fallback_color)
    else:
        painter.setBrush(Qt.GlobalColor.gray)
    
    painter.setPen(Qt.GlobalColor.darkGray)
    
    # Draw a circle as default fallback
    painter.drawEllipse(10, 10, 44, 44)
    painter.end()
    
    return temp_pixmap

ICON_PLAY = get_icon_path("play.jpg")
ICON_PAUSE = get_icon_path("pause.png")
ICON_NEXT = get_icon_path("next.png")
ICON_PREV = get_icon_path("next1.png")
ICON_MUSIC_NOTE = get_icon_path("music_note.png")
# Additional icons
ICON_SCAN = get_icon_path("refresh.png")  # For scan library
ICON_SETTINGS = get_icon_path("settings.png")  # For settings
ICON_SONGS = get_icon_path("music.png")  # For songs view
ICON_ALBUMS = get_icon_path("album.png")  # For albums view
ICON_ARTISTS = get_icon_path("artist.png")  # For artists view
ICON_PLAYLIST = get_icon_path("playlist.png")  # For playlist
ICON_VOLUME_HIGH = get_icon_path("volume_high.png")
ICON_VOLUME_MEDIUM = get_icon_path("volume_medium.png")
ICON_VOLUME_LOW = get_icon_path("volume-low.png")  # Note: using dash as in filename
ICON_VOLUME_MUTE = get_icon_path("volume-mute.png")  # Note: using dash as in filename

# Settings Keys
SETTINGS_MUSIC_DIR = "musicDirectory"
SETTINGS_VOLUME = "volume"
SETTINGS_WINDOW_GEOMETRY = "windowGeometry"
SETTINGS_SPLITTER_SIZES = "splitterSizes"


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("YTuneTeam", "YTune") # For storing settings
        self.playback_manager = playback.PlaybackManager()
        self.scanner_worker = None
        self.scanner_thread = None # Using QThreadPool now
        self.thread_pool = QThreadPool()
        print(f"Max Threads: {self.thread_pool.maxThreadCount()}")

        self.is_playing = False
        
        # Create placeholder pixmap for album art
        self.placeholder_pixmap = safe_load_icon(ICON_MUSIC_NOTE, Qt.GlobalColor.darkGray)
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Create player
        self.player = Player()
        self.player.signals.position_changed.connect(self._on_position_changed)
        self.player.signals.duration_changed.connect(self._on_duration_changed)
        self.player.signals.state_changed.connect(self._on_state_changed)
        self.player.signals.media_changed.connect(self._on_media_changed)
        self.player.signals.audio_device_changed.connect(self._on_audio_device_changed)
        
        # Create database
        self.db = Database()
        
        # Initialize UI (this sets up all components)
        self._setup_components()
        
        # Setup menu (only once)
        self._setup_menu()
        
        # Connect signals after UI is set up
        self.connect_signals()
        
        # Load settings
        self.load_settings()

        # Load initial data
        self.reload_song_list()

        # Check if music directory is set, if not prompt user
        if not self.settings.value(SETTINGS_MUSIC_DIR):
            QTimer.singleShot(100, self.select_music_directory) # Delay prompt slightly

        # Initialize track info
        self.current_track_id = None
        self.track_duration = 0
        self.update_track_display(None)
        self.update_play_pause_button(playback.PlaybackState.STOPPED)
        
        # Auto-detect Bluetooth audio devices on startup
        QTimer.singleShot(1000, self._startup_audio_detection)

    def _setup_components(self):
        """Set up all UI components."""
        if hasattr(self, 'central_widget'):
            # Prevent duplicate setup
            return

        # Create main layout containers
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.central_layout = QVBoxLayout(self.central_widget)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)
        
        self.setWindowTitle("YTune")
        self.resize(1200, 800)
        
        self.top_splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Sidebar ---
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(280)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(12)

        # Top button row (Scan, YT, Settings)
        top_button_layout = QHBoxLayout()
        top_button_layout.setSpacing(10)
        
        self.scan_button = QPushButton("Scan")
        self.scan_button.setIcon(QIcon(ICON_SCAN))
        self.scan_button.setIconSize(QSize(16, 16))
        self.scan_button.setToolTip("Scan Library")
        self.scan_button.setObjectName("action_button")
        
        self.youtube_button = QPushButton("YT")
        self.youtube_button.setToolTip("Download from YouTube")
        self.youtube_button.setObjectName("action_button")
        self.youtube_button.clicked.connect(self.show_youtube_downloader)
        
        self.settings_button = QPushButton("Settings")
        self.settings_button.setIcon(QIcon(ICON_SETTINGS))
        self.settings_button.setIconSize(QSize(16, 16))
        self.settings_button.setToolTip("Settings")
        self.settings_button.setObjectName("action_button")
        self.settings_button.clicked.connect(self.select_music_directory)
        
        top_button_layout.addWidget(self.scan_button)
        top_button_layout.addWidget(self.youtube_button)
        top_button_layout.addWidget(self.settings_button)
        top_button_layout.addStretch()
        sidebar_layout.addLayout(top_button_layout)
        
        # Navigation Buttons
        self.nav_buttons = {}
        nav_items = {
            "Songs": ICON_SONGS,
            "Playlists": ICON_PLAYLIST,
            "Albums": ICON_ALBUMS,
            "Artists": ICON_ARTISTS
        }
        
        for item, icon_path in nav_items.items():
            button = QPushButton(item)
            button.setIcon(QIcon(icon_path))
            button.setIconSize(QSize(20, 20))
            button.setObjectName("nav_button")
            button.setCheckable(True)
            # Use both icon and text
            button.setStyleSheet("text-align: left; padding-left: 10px;")
            sidebar_layout.addWidget(button)
            self.nav_buttons[item] = button
        
        # Set Songs as initially checked
        self.nav_buttons["Songs"].setChecked(True)
        
        sidebar_layout.addStretch(1)
        
        # --- Main Content Area ---
        main_content_frame = QFrame()
        main_content_frame.setFrameShape(QFrame.Shape.NoFrame)
        main_content_frame.setObjectName("main_content_area")
        main_content_layout = QVBoxLayout(main_content_frame)
        main_content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create stacked widget BEFORE adding views
        self.stacked_widget = QStackedWidget()
        main_content_layout.addWidget(self.stacked_widget)
        
        if not hasattr(self, 'songs_view'):
            from ui.views.songs_view import SongsView
            self.songs_view = SongsView()
            self.songs_view.track_selected.connect(self.on_track_selected)
        
        if not hasattr(self, 'playlist_view'):
            from ui.views.playlist_view import PlaylistView
            self.playlist_view = PlaylistView()
            self.playlist_view.playlist_selected.connect(self.load_playlist_tracks)
            self.playlist_view.track_selected.connect(self.on_track_selected)

        # Add views to stacked widget
        self.stacked_widget.addWidget(self.songs_view)
        self.stacked_widget.addWidget(self.playlist_view)
        # Will add these later:
        # self.stacked_widget.addWidget(self.albums_view)
        # self.stacked_widget.addWidget(self.artists_view)

        self.top_splitter.addWidget(sidebar)
        self.top_splitter.addWidget(main_content_frame)

        # --- Playback Bar ---
        playback_bar = QFrame()
        playback_bar.setFrameShape(QFrame.Shape.NoFrame)
        playback_bar.setFixedHeight(110)  # Slightly taller for better spacing
        playback_bar.setObjectName("playback_bar")
        
        # Add styling with border instead of shadow
        playback_bar.setStyleSheet("#playback_bar { border-top: 1px solid #333333; }")

        playback_layout = QHBoxLayout(playback_bar)
        playback_layout.setContentsMargins(25, 15, 25, 15)  # More padding
        playback_layout.setSpacing(20)  # More spacing between elements

        # Left: Art + Info
        pb_left_layout = QHBoxLayout()
        pb_left_layout.setSpacing(20)  # More spacing between art and info
        
        if not hasattr(self, 'album_art_label'):
            self.album_art_label = QLabel()
            self.album_art_label.setObjectName("album_art")
            self.album_art_label.setFixedSize(85, 85)
            self.album_art_label.setScaledContents(False)
            self.album_art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.album_art_label.setStyleSheet("#album_art { border-radius: 8px; }")
            default_art = safe_load_icon(ICON_MUSIC_NOTE, Qt.GlobalColor.darkGray)
            self.album_art_label.setPixmap(default_art.scaled(85, 85, Qt.AspectRatioMode.KeepAspectRatio))
            
        pb_left_layout.addWidget(self.album_art_label)

        track_info_layout = QVBoxLayout()
        track_info_layout.setSpacing(6)  # More spacing between title and artist
        track_info_layout.setContentsMargins(0, 10, 0, 10)  # Vertical padding
        
        if not hasattr(self, 'track_title_label'):
            self.track_title_label = QLabel("No Track Playing")
            self.track_title_label.setObjectName("track_title")
            self.track_title_label.setWordWrap(True)
            self.track_title_label.setMaximumWidth(250)
            
        if not hasattr(self, 'track_artist_label'):
            self.track_artist_label = QLabel("")
            self.track_artist_label.setObjectName("track_artist")
            self.track_artist_label.setWordWrap(True)
            
        track_info_layout.addWidget(self.track_title_label)
        track_info_layout.addWidget(self.track_artist_label)
        track_info_layout.addStretch()
        pb_left_layout.addLayout(track_info_layout)
        pb_left_layout.addStretch(1)

        # Center: Controls + Progress
        pb_center_layout = QVBoxLayout()
        pb_center_layout.setSpacing(10)  # More spacing between controls and progress
        pb_center_buttons_layout = QHBoxLayout()
        pb_center_buttons_layout.setSpacing(24)  # More spacing between buttons
        pb_center_buttons_layout.addStretch()
        
        if not hasattr(self, 'prev_button'):
            self.prev_button = QPushButton()
            self.prev_button.setIcon(QIcon(safe_load_icon(ICON_PREV)))
            self.prev_button.setObjectName("playback_button")
            self.prev_button.setIconSize(QSize(28, 28))
            self.prev_button.setFixedSize(44, 44)
            
        if not hasattr(self, 'play_pause_button'):
            self.play_pause_button = QPushButton()
            self.play_pause_button.setIcon(QIcon(safe_load_icon(ICON_PLAY))) # Start with play icon
            self.play_pause_button.setObjectName("play_button")
            self.play_pause_button.setIconSize(QSize(36, 36))  # Larger play button
            self.play_pause_button.setFixedSize(60, 60)
            
        if not hasattr(self, 'next_button'):
            self.next_button = QPushButton()
            self.next_button.setIcon(QIcon(safe_load_icon(ICON_NEXT)))
            self.next_button.setObjectName("playback_button")
            self.next_button.setIconSize(QSize(28, 28))
            self.next_button.setFixedSize(44, 44)
            
        pb_center_buttons_layout.addWidget(self.prev_button)
        pb_center_buttons_layout.addWidget(self.play_pause_button)
        pb_center_buttons_layout.addWidget(self.next_button)
        pb_center_buttons_layout.addStretch()

        pb_center_progress_layout = QHBoxLayout()
        pb_center_progress_layout.setSpacing(10)
        
        if not hasattr(self, 'current_time_label'):
            self.current_time_label = QLabel("0:00")
            self.current_time_label.setObjectName("current_time_label")
            self.current_time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
        if not hasattr(self, 'progress_slider'):
            self.progress_slider = QSlider(Qt.Orientation.Horizontal)
            self.progress_slider.setObjectName("progress_slider")
            self.progress_slider.setCursor(Qt.CursorShape.PointingHandCursor)
            
        if not hasattr(self, 'total_time_label'):
            self.total_time_label = QLabel("0:00")
            self.total_time_label.setObjectName("total_time_label")
            self.total_time_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            
        pb_center_progress_layout.addWidget(self.current_time_label)
        pb_center_progress_layout.addWidget(self.progress_slider, 1)
        pb_center_progress_layout.addWidget(self.total_time_label)

        pb_center_layout.addLayout(pb_center_buttons_layout)
        pb_center_layout.addLayout(pb_center_progress_layout)

        # Right: Volume + Queue
        pb_right_layout = QHBoxLayout()
        pb_right_layout.setSpacing(12)
        pb_right_layout.addStretch()
        
        # Volume controls
        volume_container = QFrame()
        volume_container.setObjectName("volume_container")
        volume_layout = QHBoxLayout(volume_container)
        volume_layout.setContentsMargins(0, 0, 0, 0)
        volume_layout.setSpacing(8)
        
        if not hasattr(self, 'volume_icon_label'):
            self.volume_icon_label = QLabel() # Will hold volume icon
            self.volume_icon_label.setFixedSize(24, 24)
            
        volume_layout.addWidget(self.volume_icon_label)
        
        if not hasattr(self, 'volume_slider'):
            self.volume_slider = QSlider(Qt.Orientation.Horizontal)
            self.volume_slider.setObjectName("volume_slider")
            self.volume_slider.setFixedWidth(100)
            self.volume_slider.setCursor(Qt.CursorShape.PointingHandCursor)
            self.volume_slider.setRange(0, 100)
            
        volume_layout.addWidget(self.volume_slider)
        
        pb_right_layout.addWidget(volume_container)

        # Assemble playback bar layout
        playback_layout.addLayout(pb_left_layout, 3) # Art/Info take more space
        playback_layout.addLayout(pb_center_layout, 4) # Controls/Progress take most space
        playback_layout.addLayout(pb_right_layout, 2) # Volume takes less

        # --- Status Bar ---
        if not hasattr(self, 'scan_progress_bar'):
            self.scan_progress_bar = QProgressBar()
            self.scan_progress_bar.setMaximumHeight(15)
            self.scan_progress_bar.setVisible(False)
            self.status_bar.addPermanentWidget(self.scan_progress_bar)
            
        if not hasattr(self, 'status_label'):
            self.status_label = QLabel("Ready")
            self.status_bar.addWidget(self.status_label) # Temporary messages go here

        # --- Assemble Main Layout ---
        main_container = QVBoxLayout()
        main_container.addWidget(self.top_splitter)
        main_container.addWidget(playback_bar)
        
        # Add to central layout and clear any existing content first
        self.central_layout.addLayout(main_container)

        # Set initial focus to prevent odd focus on start
        if hasattr(self, 'songs_view') and hasattr(self.songs_view, 'table'):
            self.songs_view.table.setFocus()

    def connect_signals(self):
        """Connect all signals and slots."""
        # Connect scan button
        self.scan_button.clicked.connect(self.start_scan)
        
        # Connect navigation buttons
        self.nav_buttons["Songs"].clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.songs_view))
        self.nav_buttons["Playlists"].clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.playlist_view))
        # self.nav_buttons["Albums"].clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.albums_view))
        # self.nav_buttons["Artists"].clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.artists_view))
        
        # Connect playback buttons
        self.play_pause_button.clicked.connect(self.toggle_playback)
        self.next_button.clicked.connect(self.on_next_button_clicked)
        self.prev_button.clicked.connect(self.on_prev_button_clicked)
        
        # Connect playlist-related signals
        self.playlist_view.playlist_selected.connect(self.load_playlist_tracks)
        self.playlist_view.track_selected.connect(self.on_track_selected)
        
        # Connect volume slider
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        
        # Connect progress slider
        self.progress_slider.sliderMoved.connect(self.on_progress_slider_moved)
        self.progress_slider.sliderReleased.connect(self.on_progress_slider_released)
        
        # Connect signals from SongsView
        self.songs_view.track_selected.connect(self.on_track_selected)
        
        # Connect signals from PlaybackManager
        self.playback_manager.state_changed.connect(self.on_playback_state_changed)
        self.playback_manager.track_changed.connect(self.on_track_changed)
        self.playback_manager.position_changed.connect(self.update_playback_position)
        self.playback_manager.duration_changed.connect(self.update_playback_duration)
        self.playback_manager.volume_changed.connect(self.update_volume_display)
        self.playback_manager.playback_error.connect(lambda msg: self.status_bar.showMessage(f"Error: {msg}", 5000))
        
        # Initial volume setup
        self.update_volume_display(self.playback_manager.volume)

    # --- UI Update Slots (Connected to PlaybackManager Signals) ---

    def update_play_pause_button(self, state):
        if state == playback.PlaybackState.PLAYING:
            self.play_pause_button.setIcon(QIcon(safe_load_icon(ICON_PAUSE)))
            self.play_pause_button.setToolTip("Pause")
        else: # Paused or Stopped
            self.play_pause_button.setIcon(QIcon(safe_load_icon(ICON_PLAY)))
            self.play_pause_button.setToolTip("Play")

    def update_track_display(self, track: Optional[Track]):
        if track:
            self.track_title_label.setText(track.display_title())
            self.track_artist_label.setText(track.display_artist())
            # Update album art
            if track.album_art:
                pixmap = QPixmap()
                if pixmap.loadFromData(track.album_art):
                     # Scale pixmap maintaining aspect ratio
                     scaled_pixmap = pixmap.scaled(self.album_art_label.size(),
                                                  Qt.AspectRatioMode.KeepAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation)
                     self.album_art_label.setPixmap(scaled_pixmap)
                else:
                    print(f"Warning: Could not load album art data for {track.filepath}")
                    self.album_art_label.setPixmap(self.placeholder_pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

            else:
                 self.album_art_label.setPixmap(self.placeholder_pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        else: # No track playing
            self.track_title_label.setText("No Track Playing")
            self.track_artist_label.setText("")
            self.album_art_label.setPixmap(self.placeholder_pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.progress_slider.setValue(0)
            self.progress_slider.setEnabled(False)
            self.current_time_label.setText("0:00")
            self.total_time_label.setText("0:00")

    def update_duration_display(self, duration_ms: int):
        if duration_ms > 0:
            self.progress_slider.setMaximum(duration_ms)
            self.total_time_label.setText(format_duration_ms(duration_ms))
            self.progress_slider.setEnabled(True)
        else:
            self.progress_slider.setMaximum(0)
            self.total_time_label.setText("0:00")
            self.progress_slider.setEnabled(False)


    def update_position_display(self, position_ms: int):
        # Only update slider if user isn't dragging it
        if not self.progress_slider.isSliderDown():
            self.progress_slider.setValue(position_ms)
        self.current_time_label.setText(format_duration_ms(position_ms))

    def update_volume_display(self, volume=None):
        """Updates volume display based on current volume."""
        if volume is None:
            volume = self.playback_manager.volume
        
        # Set the volume icon based on level
        if volume <= 0:
            self.volume_icon_label.setPixmap(QPixmap(safe_load_icon(ICON_VOLUME_MUTE)).scaled(
                24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        elif volume < 30:
            self.volume_icon_label.setPixmap(QPixmap(safe_load_icon(ICON_VOLUME_LOW)).scaled(
                24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        elif volume < 70:
            self.volume_icon_label.setPixmap(QPixmap(safe_load_icon(ICON_VOLUME_MEDIUM)).scaled(
                24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.volume_icon_label.setPixmap(QPixmap(safe_load_icon(ICON_VOLUME_HIGH)).scaled(
                24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        
        # Update slider position if it's not the source of the change
        if self.volume_slider.value() != volume:
            self.volume_slider.setValue(volume)


    # --- UI Action Slots ---

    def on_track_selected(self, track_id):
        """Handle track selection from the songs view."""
        print(f"Track selected: {track_id}")
        if hasattr(self, 'db'):
            # Get current widget to determine the context
            current_widget = self.stacked_widget.currentWidget()
            all_track_ids = []
            
            # Get track IDs based on which view is active
            if current_widget == self.songs_view:
                all_track_ids = self.songs_view.get_all_track_ids_in_order()
            elif current_widget == self.playlist_view:
                # Get track IDs from current playlist
                for i in range(self.playlist_view.tracks_model.rowCount()):
                    track_id_data = self.playlist_view.tracks_model.data(
                        self.playlist_view.tracks_model.index(i, 0), Qt.ItemDataRole.UserRole)
                    if track_id_data is not None:
                        all_track_ids.append(track_id_data)
                    
            if all_track_ids:
                # Set up the playlist and immediately start playing
                self.playback_manager.set_playlist(all_track_ids, start_track_id=track_id)
                # Force play in case set_playlist doesn't automatically start playback
                self.playback_manager.play()
                
                # Update UI with the track that should be playing
                track = self.db.get_track_by_id(track_id)
                if track:
                    self.update_track_display(track)
                    self.status_bar.showMessage(f"Playing: {track.display_title()} by {track.display_artist()}", 3000)
                    # Update play/pause button to show pause icon since we're playing
                    self.update_play_pause_button(playback.PlaybackState.PLAYING)
            else:
                print("No track IDs found to play")
                self.status_bar.showMessage("No tracks to play", 3000)

    def on_volume_changed(self, volume: int):
        """Handle volume slider changes"""
        self.playback_manager.set_volume(volume)
        # Volume display update is handled by connecting to playback_manager.volume_changed

    def on_progress_slider_moved(self, position: int):
        """Handle progress slider movement while dragging"""
        # Only update the time display during dragging
        self.current_time_label.setText(format_duration_ms(position))
        
    def on_progress_slider_released(self):
        """Handle progress slider release (actually seek when user releases)"""
        position = self.progress_slider.value()
        self.playback_manager.seek(position)
        
    def on_playback_state_changed(self, state):
        """Handle playback state changes"""
        self.update_play_pause_button(state)
        
    def on_track_changed(self, track: Optional[Track]):
        """Handle track changes"""
        self.update_track_display(track)
        
    def update_playback_position(self, position_ms: int):
        """Handle position updates during playback"""
        self.update_position_display(position_ms)
        
    def update_playback_duration(self, duration_ms: int):
        """Handle duration updates when a new track is loaded"""
        self.update_duration_display(duration_ms)

    def select_music_directory(self):
        """Opens a dialog to select the music library directory."""
        current_dir = self.settings.value(SETTINGS_MUSIC_DIR, "")
        music_dir = QFileDialog.getExistingDirectory(
            self, "Select Music Library Folder", current_dir
        )
        if music_dir:
            self.settings.setValue(SETTINGS_MUSIC_DIR, music_dir)
            print(f"Music directory set to: {music_dir}")
            self.status_bar.showMessage(f"Music directory set. Starting scan...", 3000)
            # Automatically start scan when directory is selected
            QTimer.singleShot(500, self.start_scan)  # Start scan after a short delay

    def start_scan(self):
        """Initiates the library scan in a background thread."""
        music_dir = self.settings.value(SETTINGS_MUSIC_DIR)
        if not music_dir or not os.path.isdir(music_dir):
            print(f"Invalid music directory: {music_dir}")
            self.status_bar.showMessage("Please select a valid music directory first.", 4000)
            self.select_music_directory() # Prompt user again
            return

        if self.scanner_worker:
             print("Scan already in progress.")
             self.status_bar.showMessage("Scan already in progress.", 3000)
             return

        print(f"Starting library scan in directory: {music_dir}")
        print(f"Directory exists: {os.path.exists(music_dir)}")
        print(f"Directory is readable: {os.access(music_dir, os.R_OK)}")
        
        self.scan_button.setEnabled(False)
        self.status_label.setText("Scanning...")
        self.scan_progress_bar.setValue(0)
        self.scan_progress_bar.setMaximum(100) # Initial max, will be updated
        self.scan_progress_bar.setVisible(True)

        # Use QThreadPool
        self.scanner_worker = scan_directories([music_dir])
        self.scanner_worker.signals.progress.connect(self.update_scan_progress)
        self.scanner_worker.signals.scan_finished.connect(self.on_scan_finished)
        self.scanner_worker.signals.error_occurred.connect(self.on_scan_error)

        self.thread_pool.start(self.scanner_worker)


    @Slot(int, int)
    def update_scan_progress(self, current, total):
        """Updates the progress bar during scanning."""
        if total > 0:
            self.scan_progress_bar.setMaximum(total)
            self.scan_progress_bar.setValue(current)
            self.status_label.setText(f"Scanning... ({current}/{total})")
        else:
            self.scan_progress_bar.setMaximum(100)
            self.scan_progress_bar.setValue(0) # Indeterminate state if total is 0

    @Slot(str)
    def on_scan_error(self, message):
         """Handles errors reported by the scanner."""
         self.status_bar.showMessage(f"Scan Error: {message}", 5000)
         # Optionally log the error more permanently

    @Slot(int)
    def on_scan_finished(self, count):
        """Called when the scanner thread finishes."""
        print(f"Scan finished. Processed {count} files.")
        self.status_label.setText("Scan Finished.")
        self.scan_progress_bar.setVisible(False)
        self.scan_button.setEnabled(True)
        self.scanner_worker = None # Allow starting a new scan

        # Reload the song list in the UI
        self.reload_song_list()
        self.status_bar.showMessage(f"Library scan complete. Found/Updated {count} tracks.", 5000)


    def reload_song_list(self):
        """Fetches all tracks from DB and loads them into the songs view."""
        print("Reloading song list from database...")
        if hasattr(self, 'db'):
            all_tracks = self.db.get_all_tracks()
            if hasattr(self, 'songs_view') and hasattr(self.songs_view, 'load_tracks'):
                self.songs_view.load_tracks(all_tracks)
                
                # Also reload playlists
                self.load_playlists()
            else:
                print("Warning: songs_view not available or missing load_tracks method")
        else:
            print("Warning: Database not initialized")


    # --- Settings and Window State ---

    def load_settings(self):
        """Load persistent settings."""
        geometry = self.settings.value(SETTINGS_WINDOW_GEOMETRY)
        if geometry:
            self.restoreGeometry(geometry)
        else:
             self.setGeometry(100, 100, 1100, 750) # Default size

        splitter_sizes = self.settings.value(SETTINGS_SPLITTER_SIZES)
        if splitter_sizes:
            self.top_splitter.restoreState(splitter_sizes)
        else:
            self.top_splitter.setSizes([220, 880]) # Default sizes

        volume = self.settings.value(SETTINGS_VOLUME, playback.DEFAULT_VOLUME, type=int)
        self.playback_manager.set_volume(volume) # Set initial volume
        self.volume_slider.setValue(volume) # Ensure slider matches


    def save_settings(self):
        """Save persistent settings."""
        self.settings.setValue(SETTINGS_WINDOW_GEOMETRY, self.saveGeometry())
        self.settings.setValue(SETTINGS_SPLITTER_SIZES, self.top_splitter.saveState())
        self.settings.setValue(SETTINGS_VOLUME, self.playback_manager.volume)
        print("Settings saved.")

    @Slot()
    def save_splitter_sizes(self):
        """Slot specifically for saving splitter sizes immediately when moved."""
        self.settings.setValue(SETTINGS_SPLITTER_SIZES, self.top_splitter.saveState())


    def closeEvent(self, event):
        """Override close event to save settings."""
        # Stop scanner if running
        if self.scanner_worker:
             print("Attempting to cancel scan on close...")
             self.scanner_worker.cancel()
             # Need to wait? QThreadPool might handle this somewhat gracefully.
             # For simplicity, we won't wait here, but a robust app might.

        self.save_settings()
        print("Closing application.")
        # Ensure playback stops?
        self.playback_manager.stop()
        # Clean up thread pool? Usually not strictly necessary for app exit.
        # self.thread_pool.clear() # Removes queued tasks
        # self.thread_pool.waitForDone() # Waits for active tasks

        event.accept()

    def _setup_menu(self):
        """Set up the main window menu."""
        menu_bar = self.menuBar()
        
        # File Menu
        file_menu = menu_bar.addMenu("&File")
        
        # Add music action
        scan_action = QAction("&Scan Music Library", self)
        scan_action.triggered.connect(self.start_scan)
        file_menu.addAction(scan_action)
        
        # Change music dir action
        music_dir_action = QAction("&Set Music Directory", self)
        music_dir_action.triggered.connect(self.select_music_directory)
        file_menu.addAction(music_dir_action)
        
        # YouTube download action
        youtube_action = QAction("&Download from YouTube", self)
        youtube_action.triggered.connect(self.show_youtube_downloader)
        file_menu.addAction(youtube_action)
        
        # Exit action
        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View Menu
        view_menu = menu_bar.addMenu("&View")
        
        # Songs view action
        songs_action = QAction("&Songs", self)
        songs_action.triggered.connect(lambda: self.stacked_widget.setCurrentWidget(self.songs_view))
        view_menu.addAction(songs_action)
        
        # Playlists view action
        playlists_action = QAction("&Playlists", self)
        playlists_action.triggered.connect(lambda: self.stacked_widget.setCurrentWidget(self.playlist_view))
        view_menu.addAction(playlists_action)
        
        # Audio Menu
        audio_menu = menu_bar.addMenu("&Audio")
        
        # Multi-output action
        multi_output_action = QAction("Enable &Multi-Output (Speakers + AirPods)", self)
        multi_output_action.triggered.connect(self.enable_multi_output)
        audio_menu.addAction(multi_output_action)
        
        # Connect to AirPods action
        airpods_action = QAction("Connect to &AirPods", self)
        airpods_action.triggered.connect(self._connect_to_airpods)
        audio_menu.addAction(airpods_action)
        
        # Auto-select Bluetooth action
        bluetooth_action = QAction("Auto-select &Bluetooth Device", self)
        bluetooth_action.triggered.connect(self._auto_select_bluetooth)
        audio_menu.addAction(bluetooth_action)
        
        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _on_audio_device_changed(self, device_id):
        """Handle audio device changes."""
        self.status_bar.showMessage(f"Audio device changed", 3000)

    def _connect_to_airpods(self):
        """Try to find and connect to AirPods."""
        if self.player.find_and_select_airpods():
            self.status_bar.showMessage("Connected to AirPods", 3000)
        else:
            self.status_bar.showMessage("No AirPods found. Make sure they are connected to your computer.", 5000)
            
    def _auto_select_bluetooth(self):
        """Try to automatically detect and select a Bluetooth audio device."""
        if self.player.auto_select_bluetooth():
            self.status_bar.showMessage("Connected to Bluetooth audio device", 3000)
        else:
            self.status_bar.showMessage("No Bluetooth audio devices found. Make sure your device is connected to your computer.", 5000)

    def _startup_audio_detection(self):
        """Automatically detect and select audio devices on startup."""
        # First try AirPods specifically
        if self.player.find_and_select_airpods():
            self.status_bar.showMessage("Connected to AirPods", 3000)
        # Then try any Bluetooth device
        elif self.player.auto_select_bluetooth():
            self.status_bar.showMessage("Connected to Bluetooth audio device", 3000)
        # Otherwise just show available devices
        else:
            devices = self.player.get_audio_devices()
            if devices:
                device_count = len(devices)
                self.status_bar.showMessage(f"Found {device_count} audio devices. Select one from Settings menu.", 5000)

    def _on_position_changed(self, position):
        """Handle position change from player."""
        if hasattr(self, 'player_controls'):
            self.player_controls.set_position(position)
            
    def _on_duration_changed(self, duration):
        """Handle duration change from player."""
        if hasattr(self, 'player_controls'):
            self.player_controls.set_duration(duration)
            
    def _on_state_changed(self, state):
        """Handle playback state change from player."""
        from PySide6.QtMultimedia import QMediaPlayer
        if state == QMediaPlayer.PlaybackState.PlayingState:
            if hasattr(self, 'player_controls'):
                self.player_controls.set_playing(True)
        else:
            if hasattr(self, 'player_controls'):
                self.player_controls.set_playing(False)
                
    def _on_media_changed(self, file_path):
        """Handle media change from player."""
        self.status_bar.showMessage(f"Playing: {os.path.basename(file_path)}", 3000)

    def toggle_playback(self):
        """Toggle between play and pause."""
        if self.playback_manager.current_track:  # If playing through manager
            if self.playback_manager.player.playbackState() == playback.PlaybackState.PLAYING:
                self.playback_manager.pause()
            else:
                self.playback_manager.play()
        elif hasattr(self, 'player'):  # If playing through direct player
            if self.player.player.playbackState() == playback.PlaybackState.PLAYING:
                self.player.pause()
            else:
                self.player.play()
        self.update_play_pause_button(self.player.player.playbackState() if hasattr(self, 'player') else playback.PlaybackState.STOPPED)
    
    def stop_playback(self):
        """Stop playback."""
        if hasattr(self, 'player'):
            self.player.stop()
            
    def open_file(self):
        """Open a media file."""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("Audio Files (*.mp3 *.wav *.ogg *.flac *.m4a)")
        
        if file_dialog.exec():
            file_path = file_dialog.selectedFiles()[0]
            if file_path:
                self.player.load(file_path)
                self.player.play()
                
    def open_folder(self):
        """Open a folder with media files."""
        folder_path = QFileDialog.getExistingDirectory(self, "Open Music Folder")
        if folder_path:
            # Make sure directory exists in settings
            self.settings.setValue(SETTINGS_MUSIC_DIR, folder_path)
            # Start a scan of this directory
            self.start_scan()
            
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About YTune",
            "YTune\n\n"
            "A modern music player built with Python, PySide6, and Qt.\n\n"
            "Features:\n"
            "- Play local music files\n"
            "- Create and manage playlists\n"
            "- Download music from YouTube\n"
            "- Visualize album art\n"
            "- Multi-output audio support\n\n"
            "© 2024 YTune Team"
        )

    def _setup_models(self):
        """Setup database models."""
        # This would typically involve setting up models for the views
        # For simplicity, we're just loading all tracks directly
        self.reload_song_list()

    def show_youtube_downloader(self):
        """Show the YouTube downloader dialog."""
        try:
            from ui.dialogs.youtube_downloader_dialog import show_youtube_downloader_dialog
            show_youtube_downloader_dialog(self)
        except Exception as e:
            print(f"Error showing YouTube downloader: {e}")
            QMessageBox.warning(
                self,
                "Error",
                f"Could not open YouTube downloader: {str(e)}"
            )

    def on_next_button_clicked(self):
        """Handle next button click."""
        # Use playback manager if playing from a list, otherwise use direct player
        if self.playback_manager.current_track:
            self.playback_manager.play_next()
        else:
            self.player.play_next()

    def on_prev_button_clicked(self):
        """Handle previous button click."""
        # Use playback manager if playing from a list, otherwise use direct player
        if self.playback_manager.current_track:
            self.playback_manager.play_previous()
        else:
            self.player.play_previous()

    def load_playlist_tracks(self, playlist_id):
        """Load tracks for the selected playlist."""
        print(f"Loading tracks for playlist {playlist_id}")
        
        if hasattr(self, 'db'):
            # Get tracks for the playlist
            from core.database import get_playlist_tracks
            tracks = get_playlist_tracks(playlist_id)
            
            # Update the playlist view with the tracks
            if hasattr(self, 'playlist_view') and hasattr(self.playlist_view, 'set_tracks'):
                self.playlist_view.set_tracks(tracks)
                
                # Make the playlist view visible
                self.stacked_widget.setCurrentWidget(self.playlist_view)
                
                # Update status
                self.status_bar.showMessage(f"Loaded playlist with {len(tracks)} tracks", 3000)
            else:
                print("Warning: playlist_view not available or missing set_tracks method")
        else:
            print("Warning: Database not initialized")

    def load_playlists(self):
        """Load all playlists from the database."""
        if hasattr(self, 'db'):
            # Get all playlists
            from core.database import get_all_playlists
            playlists = get_all_playlists()
            
            # Update the playlist view
            if hasattr(self, 'playlist_view') and hasattr(self.playlist_view, 'set_playlists'):
                self.playlist_view.set_playlists(playlists)
                self.status_bar.showMessage(f"Loaded {len(playlists)} playlists", 3000)
            else:
                print("Warning: playlist_view not available or missing set_playlists method")
        else:
            print("Warning: Database not initialized")

    def enable_multi_output(self):
        """Enable multi-output (speakers + AirPods)."""
        if hasattr(self, 'player') and hasattr(self.player, 'enable_multi_output'):
            if self.player.enable_multi_output():
                self.status_bar.showMessage("Opening Sound settings for multi-output setup...", 5000)
            else:
                self.status_bar.showMessage("Failed to enable multi-output", 3000)
        else:
            self.status_bar.showMessage("Multi-output functionality not available", 3000)