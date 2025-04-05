# core/models.py
from dataclasses import dataclass, field
from typing import Optional

class Track:
    """Represents a single music track."""
    
    def __init__(self, id=None, filepath="", title="", artist="", album="", genre="", length=0, album_art=None):
        self.id = id
        self.filepath = filepath
        self.title = title if title else self._extract_title_from_path(filepath)
        self.artist = artist if artist else self._extract_artist_from_path(filepath)
        self.album = album if album else ""
        self.genre = genre if genre else ""
        self.length = length
        self.album_art = album_art
        
    def _extract_title_from_path(self, filepath):
        """Extract a title from the filepath if possible."""
        if not filepath:
            return "Unknown Title"
            
        import os
        filename = os.path.basename(filepath)
        # Remove file extension
        filename = os.path.splitext(filename)[0]
        
        # Check for YouTube-style "Artist - Title" format
        if " - " in filename:
            parts = filename.split(" - ", 1)
            if len(parts) == 2:
                return parts[1].strip()
        
        # Fallback to the whole filename
        return filename.strip()
        
    def _extract_artist_from_path(self, filepath):
        """Extract artist from the filepath if possible."""
        if not filepath:
            return "Unknown Artist"
            
        import os
        filename = os.path.basename(filepath)
        # Remove file extension
        filename = os.path.splitext(filename)[0]
        
        # Check for YouTube-style "Artist - Title" format
        if " - " in filename:
            parts = filename.split(" - ", 1)
            if len(parts) == 2:
                return parts[0].strip()
        
        # Fallback - unknown artist
        return "Unknown Artist"
        
    def display_title(self):
        """Get the title to display."""
        if not self.title:
            return "Unknown Title"
        return self.title
        
    def display_artist(self):
        """Get the artist to display."""
        if not self.artist:
            return "Unknown Artist"
        return self.artist
        
    def __str__(self):
        """String representation of the track."""
        return f"{self.artist} - {self.title}"

    def display_album(self):
        """Get the album to display."""
        if not self.album:
            return "Unknown Album"
        return self.album

    def display_duration(self) -> str:
        if self.length:
            secs = int(self.length)
            mins, secs = divmod(secs, 60)
            return f"{mins}:{secs:02d}"
        return "0:00"