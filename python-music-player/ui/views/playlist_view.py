from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, 
    QListWidgetItem, QPushButton, QTableView, QHeaderView, QLineEdit, QFrame
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QAbstractTableModel, QModelIndex, QSortFilterProxyModel
from PySide6.QtGui import QIcon, QFont
from typing import List
from core.models import Track

class PlaylistTracksModel(QAbstractTableModel):
    """Custom model for displaying playlist tracks with numbering."""
    
    def __init__(self, tracks=None):
        super().__init__()
        self.tracks = tracks or []
        self.headers = ["#", "Title", "Artist", "Duration"]
        
    def rowCount(self, parent=None):
        return len(self.tracks)
        
    def columnCount(self, parent=None):
        return len(self.headers)
        
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.tracks)):
            return None
            
        track = self.tracks[index.row()]
        col = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                # Track number
                return str(index.row() + 1)
            elif col == 1:
                # Title
                return track.display_title()
            elif col == 2:
                # Artist
                return track.display_artist() 
            elif col == 3:
                # Duration
                return track.display_duration() if hasattr(track, 'display_duration') else ""
                
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col == 0:
                # Center-align track numbers
                return Qt.AlignmentFlag.AlignCenter
            elif col == 3:
                # Right-align duration
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                
        elif role == Qt.ItemDataRole.UserRole:
            # Store track ID for all columns
            return track.id
            
        return None
        
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None
        
    def setTracks(self, tracks):
        self.beginResetModel()
        self.tracks = tracks
        self.endResetModel()

class PlaylistFilterProxyModel(QSortFilterProxyModel):
    """Proxy model to filter tracks in a playlist."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_text = ""
        
    def setSearchText(self, text):
        """Set the search text to filter by."""
        self.search_text = text.lower()
        self.invalidateFilter()
        
    def filterAcceptsRow(self, source_row, source_parent):
        """Determine if a row should be shown based on the filter."""
        if not self.search_text:
            return True
            
        model = self.sourceModel()
        
        # Check if the track title, artist contains the search text
        title = model.data(model.index(source_row, 1, source_parent), Qt.ItemDataRole.DisplayRole)
        artist = model.data(model.index(source_row, 2, source_parent), Qt.ItemDataRole.DisplayRole)
        
        if title and self.search_text in title.lower():
            return True
            
        if artist and self.search_text in artist.lower():
            return True
            
        return False

class PlaylistView(QWidget):
    """View for displaying and interacting with playlists."""
    
    playlist_selected = Signal(int)  # Playlist ID
    track_selected = Signal(int)  # Track ID (renamed from track_double_clicked)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        
    def _init_ui(self):
        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Left side: Playlist list
        left_layout = QVBoxLayout()
        
        # Header
        playlists_header = QLabel("Playlists")
        playlists_header.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        left_layout.addWidget(playlists_header)
        
        # Playlist list
        self.playlist_list = QListWidget()
        self.playlist_list.setMaximumWidth(200)
        self.playlist_list.currentRowChanged.connect(self._on_playlist_selected)
        left_layout.addWidget(self.playlist_list)
        
        # Add playlist button
        self.add_playlist_button = QPushButton("New Playlist")
        self.add_playlist_button.setIcon(QIcon("assets/icons/add.png"))
        left_layout.addWidget(self.add_playlist_button)
        
        main_layout.addLayout(left_layout, 1)
        
        # Right side: Playlist tracks
        right_layout = QVBoxLayout()
        
        # Header
        self.playlist_name_label = QLabel("Select a Playlist")
        self.playlist_name_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        right_layout.addWidget(self.playlist_name_label)
        
        # Count label
        self.count_label = QLabel("0 songs")
        self.count_label.setObjectName("count_label")
        self.count_label.setStyleSheet("#count_label { color: #888; }")
        right_layout.addWidget(self.count_label)
        
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
        self.search_box.setPlaceholderText("Search in playlist...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._filter_tracks)
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
        
        right_layout.addWidget(search_frame)
        
        # Tracks table
        self.tracks_table = QTableView()
        self.tracks_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.tracks_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.tracks_table.setShowGrid(False)
        
        # Change from doubleClicked to clicked for single-click activation
        self.tracks_table.clicked.connect(self._on_track_clicked)
        
        # Set up the custom model
        self.tracks_model = PlaylistTracksModel()
        
        # Set up filter proxy model for search
        self.filter_model = PlaylistFilterProxyModel()
        self.filter_model.setSourceModel(self.tracks_model)
        
        # Set the proxy model on the table view
        self.tracks_table.setModel(self.filter_model)
        
        # Configure the header
        header = self.tracks_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setDefaultSectionSize(40)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        # Remove vertical header (row numbers)
        self.tracks_table.verticalHeader().setVisible(False)
        
        right_layout.addWidget(self.tracks_table)
        
        main_layout.addLayout(right_layout, 3)
        
    def _on_playlist_selected(self, row):
        """Handle playlist selection."""
        if row >= 0 and row < self.playlist_list.count():
            item = self.playlist_list.item(row)
            playlist_id = item.data(Qt.ItemDataRole.UserRole)
            self.playlist_name_label.setText(item.text())
            self.playlist_selected.emit(playlist_id)
    
    def _on_track_clicked(self, index):
        """Handle track click."""
        # Get track ID from model
        source_index = self.filter_model.mapToSource(index)
        track_id = self.tracks_model.data(source_index, Qt.ItemDataRole.UserRole)
        if track_id is not None:
            self.track_selected.emit(track_id)  # Use the renamed signal
    
    def _filter_tracks(self, text):
        """Filter tracks in the playlist based on search text."""
        self.filter_model.setSearchText(text)
        # Update count label to show filtered count
        filtered_count = self.filter_model.rowCount()
        total_count = self.tracks_model.rowCount()
        if text:
            self.count_label.setText(f"{filtered_count} of {total_count} songs")
        else:
            self.count_label.setText(f"{total_count} songs")
            
    def set_playlists(self, playlists):
        """Set the list of playlists."""
        self.playlist_list.clear()
        for playlist in playlists:
            item = QListWidgetItem(playlist['name'])
            item.setData(Qt.ItemDataRole.UserRole, playlist['id'])
            self.playlist_list.addItem(item)
            
    def set_tracks(self, tracks: List[Track]):
        """Set the tracks to display in the current playlist."""
        self.tracks_model.setTracks(tracks)
        self.count_label.setText(f"{len(tracks)} songs")
        
        # Clear search filter when loading new tracks
        self.search_box.clear()
        
        # Auto-adjust column widths
        self.tracks_table.resizeColumnsToContents() 