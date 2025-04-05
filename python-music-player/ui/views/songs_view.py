# ui/views/songs_view.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QHeaderView, QAbstractItemView, QTableWidgetItem,
    QLabel, QHBoxLayout, QFrame, QLineEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from typing import List
from core.models import Track
from utils.formatters import format_duration_ms # Use the formatter

class SongsView(QWidget):
    """Widget displaying the list of songs in a table."""
    track_selected = Signal(int) # Emits track ID (renamed from track_double_clicked)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("songs_page") # For potential specific styling
        
        # Add gradient background
        self.setStyleSheet("""
            #songs_page {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #121212, stop:0.4 #1a1a1a, stop:1 #121212);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        # Add header section
        header_frame = QFrame()
        header_frame.setObjectName("view_header")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 10)
        
        # Add title label with a music icon
        title_container = QHBoxLayout()
        title_container.setSpacing(15)
        
        music_icon_label = QLabel("♪")
        music_icon_label.setFixedSize(32, 32)
        music_icon_label.setObjectName("view_icon")
        music_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        music_icon_label.setStyleSheet("#view_icon { background-color: #1db954; border-radius: 16px; color: white; font-size: 18px; }")
        title_container.addWidget(music_icon_label)
        
        title_label = QLabel("All Songs")
        title_label.setObjectName("view_title")
        title_container.addWidget(title_label)
        
        header_layout.addLayout(title_container)
        header_layout.addStretch()
        
        # Add song count label with badge styling
        self.count_label = QLabel("0 songs")
        self.count_label.setObjectName("count_label")
        self.count_label.setStyleSheet("#count_label { background-color: rgba(29, 185, 84, 0.15); padding: 5px 12px; border-radius: 12px; color: #1db954; }")
        header_layout.addWidget(self.count_label)
        
        layout.addWidget(header_frame)
        
        # Add search box
        search_frame = QFrame()
        search_frame.setObjectName("search_frame")
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(0, 0, 0, 10)
        
        search_icon_label = QLabel("🔍")
        search_icon_label.setObjectName("search_icon")
        search_layout.addWidget(search_icon_label)
        
        self.search_box = QLineEdit()
        self.search_box.setObjectName("search_box")
        self.search_box.setPlaceholderText("Search songs...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self.filter_songs)
        self.search_box.setStyleSheet("""
            #search_box {
                border: none;
                border-radius: 15px;
                padding: 8px 12px;
                background-color: #333333;
                color: white;
            }
        """)
        search_layout.addWidget(self.search_box)
        
        layout.addWidget(search_frame)
        
        # Add separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setObjectName("separator")
        layout.addWidget(separator)

        self.table = QTableWidget()
        self.table.setObjectName("song_table") # For QSS styling

        # Setup Table Appearance and Behavior
        self.table.setColumnCount(6) # ID (hidden), #, Title, Artist, Album, Duration
        self.table.setHorizontalHeaderLabels(["", "#", "Title", "Artist", "Album", "Duration"]) # Added # column
        self.table.setColumnHidden(0, True) # Hide the ID column (column 0)
        self.table.horizontalHeader().setStretchLastSection(False) # Last col (Time) non-stretching
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents) # Size cols initially
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) # Title stretches
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) # Album stretches
        
        # Set fixed width for track number column
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 40) # Set width for # column
        
        self.table.verticalHeader().setVisible(False) # Hide row numbers
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers) # Don't allow editing
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True) # Use alternate color from QSS
        self.table.setShowGrid(False) # Hide grid lines for cleaner look
        
        # Set row height for better spacing
        self.table.verticalHeader().setDefaultSectionSize(36)
        
        layout.addWidget(self.table)

        # Connect Signals
        # Change from doubleClicked to clicked for single-click activation
        self.table.clicked.connect(self.on_row_clicked)
        
        # Store all tracks for filtering
        self.all_tracks = []

    def load_tracks(self, tracks):
        """Load tracks into the view."""
        print(f"SongsView: Loading {len(tracks)} tracks")
        # Store all tracks for filtering
        self.all_tracks = tracks
        
        # Display all tracks
        self._populate_table(tracks)
        
    def _populate_table(self, tracks):
        """Populate the table with the given tracks."""
        # Clear existing rows
        self.table.setRowCount(0)
        
        # Add new rows
        self.table.setRowCount(len(tracks))
        
        for i, track in enumerate(tracks):
            # ID (hidden)
            id_item = QTableWidgetItem()
            id_item.setData(Qt.ItemDataRole.UserRole, track.id)
            self.table.setItem(i, 0, id_item)
            
            # Track Number (#)
            track_number_item = QTableWidgetItem(str(i + 1))
            track_number_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 1, track_number_item)
            
            # Title
            title_item = QTableWidgetItem(track.display_title())
            self.table.setItem(i, 2, title_item)
            
            # Artist
            artist_item = QTableWidgetItem(track.display_artist())
            self.table.setItem(i, 3, artist_item)
            
            # Album
            album_item = QTableWidgetItem(track.display_album() if hasattr(track, 'display_album') else "Unknown Album")
            self.table.setItem(i, 4, album_item)
            
            # Duration
            duration_item = QTableWidgetItem(track.display_duration() if hasattr(track, 'display_duration') else "")
            duration_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(i, 5, duration_item)
            
        # Update track count
        self.count_label.setText(f"{len(tracks)} songs")

    def filter_songs(self, search_text):
        """Filter the songs based on the search text."""
        if not search_text:
            # If search is empty, show all tracks
            self._populate_table(self.all_tracks)
            return
            
        # Convert search to lowercase for case-insensitive search
        search_text = search_text.lower()
        
        # Filter tracks
        filtered_tracks = []
        for track in self.all_tracks:
            # Search in title, artist and album
            if (search_text in track.display_title().lower() or 
                search_text in track.display_artist().lower() or 
                (hasattr(track, 'display_album') and search_text in track.display_album().lower())):
                filtered_tracks.append(track)
        
        # Update table with filtered tracks
        self._populate_table(filtered_tracks)

    def on_row_clicked(self, index):
        """Emits the track ID when a row is clicked."""
        row = index.row()
        id_item = self.table.item(row, 0)  # Get item from ID column (column 0)
        if id_item:
            track_id = id_item.data(Qt.ItemDataRole.UserRole)  # Retrieve ID
            if track_id is not None:
                self.track_selected.emit(track_id)  # Use the renamed signal

    def get_all_track_ids_in_order(self) -> List[int]:
        """Returns a list of all track IDs currently displayed in the table order."""
        ids = []
        for row in range(self.table.rowCount()):
             id_item = self.table.item(row, 0)
             if id_item:
                track_id = id_item.data(Qt.ItemDataRole.UserRole)
                if track_id is not None:
                    ids.append(track_id)
        return ids