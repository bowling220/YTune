# core/database.py
import sqlite3
import os
from typing import List, Optional
from .models import Track

DB_FILE = "music_library.db"

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    # Return rows as dictionary-like objects (makes accessing columns easier)
    # conn.row_factory = sqlite3.Row # Alternative way to access cols by name
    return conn

def initialize_db():
    """Creates the database tables if they don't exist."""
    if os.path.exists(DB_FILE):
        return # Assume already initialized if file exists

    print("Initializing database...")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filepath TEXT UNIQUE NOT NULL,
                title TEXT,
                artist TEXT,
                album TEXT,
                track_number INTEGER,
                duration REAL,
                year INTEGER,
                genre TEXT,
                album_art BLOB
            )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_artist ON tracks (artist);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_album ON tracks (album);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_filepath ON tracks (filepath);")
        # Add playlists table later if needed
        conn.commit()
        print("Database initialized.")
    except sqlite3.Error as e:
        print(f"Database initialization error: {e}")
    finally:
        conn.close()

def create_tables():
    """Create required database tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create tracks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filepath TEXT UNIQUE NOT NULL,
        title TEXT,
        artist TEXT,
        album TEXT,
        track_number INTEGER,
        duration REAL,
        year INTEGER,
        genre TEXT,
        album_art BLOB
    )
    """)
    
    # Create playlists table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    """)
    
    # Create playlist_tracks table for playlist-track associations
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS playlist_tracks (
        playlist_id INTEGER,
        track_id INTEGER,
        position INTEGER,
        PRIMARY KEY (playlist_id, track_id),
        FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE,
        FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE
    )
    """)
    
    conn.commit()
    conn.close()

def add_or_update_track(track):
    """Adds a new track or updates existing based on filepath."""
    conn = get_db_connection()
    cursor = conn.cursor()
    track_id = None
    try:
        # Check if track exists first
        cursor.execute("SELECT id FROM tracks WHERE filepath = ?", (track.filepath,))
        result = cursor.fetchone()
        
        if result:
            # Update existing track
            track_id = result[0]
            cursor.execute('''
                UPDATE tracks SET
                title = ?, artist = ?, album = ?, genre = ?, duration = ?, album_art = ?
                WHERE id = ?
            ''', (
                track.title, track.artist, track.album, track.genre,
                track.length, track.album_art, track_id
            ))
        else:
            # Insert new track
            cursor.execute('''
                INSERT INTO tracks
                (filepath, title, artist, album, genre, duration, album_art)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                track.filepath, track.title, track.artist, track.album,
                track.genre, track.length, track.album_art
            ))
            track_id = cursor.lastrowid
        
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error adding/updating track {track.filepath}: {e}")
    finally:
        conn.close()
    return track_id


def get_all_tracks():
    """Get all tracks from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, filepath, title, artist, album, genre, duration, album_art FROM tracks"
    )
    rows = cursor.fetchall()
    conn.close()
    
    tracks = []
    for row in rows:
        track = Track(
            id=row[0],
            filepath=row[1],
            title=row[2],
            artist=row[3],
            album=row[4],
            genre=row[5],
            length=row[6],
            album_art=row[7]
        )
        tracks.append(track)
    return tracks

def get_track_by_id(track_id):
    """Get a track by its ID.
    This is a standalone function to allow easy access from various modules."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT id, filepath, title, artist, album, genre, duration, album_art
    FROM tracks
    WHERE id = ?
    ''', (track_id,))
    
    row = cursor.fetchone()
    if row:
        track = Track(
            id=row[0],
            filepath=row[1],
            title=row[2],
            artist=row[3],
            album=row[4],
            genre=row[5],
            length=row[6],
            album_art=row[7]
        )
        conn.close()
        return track
    conn.close()
    return None

def get_tracks_by_ids(track_ids):
    """Get tracks by IDs."""
    if not track_ids:
        return []
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create placeholder string for SQL IN clause
    placeholders = ','.join(['?'] * len(track_ids))
    
    cursor.execute(
        f"SELECT id, filepath, title, artist, album, genre, duration, album_art "
        f"FROM tracks WHERE id IN ({placeholders})",
        track_ids
    )
    rows = cursor.fetchall()
    conn.close()
    
    tracks = []
    for row in rows:
        track = Track(
            id=row[0],
            filepath=row[1],
            title=row[2],
            artist=row[3],
            album=row[4],
            genre=row[5],
            length=row[6],
            album_art=row[7]
        )
        tracks.append(track)
    return tracks

def remove_tracks_not_in_list(valid_filepaths: List[str]):
    """Removes tracks from DB whose filepaths are not in the provided list."""
    if not valid_filepaths: # Avoid deleting everything if list is empty
        print("Warning: remove_tracks_not_in_list called with empty list. Skipping delete.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Find tracks to delete efficiently
        # Create a temporary table to hold valid filepaths for faster lookup
        cursor.execute("CREATE TEMP TABLE valid_files (path TEXT PRIMARY KEY)")
        cursor.executemany("INSERT OR IGNORE INTO valid_files (path) VALUES (?)", [(fp,) for fp in valid_filepaths])

        # Select tracks from main table that are NOT in the temporary table
        cursor.execute("SELECT id, filepath FROM tracks WHERE filepath NOT IN (SELECT path FROM valid_files)")
        deleted_tracks = cursor.fetchall()

        # Delete them
        cursor.execute("DELETE FROM tracks WHERE filepath NOT IN (SELECT path FROM valid_files)")

        # Drop the temporary table
        cursor.execute("DROP TABLE valid_files")

        conn.commit()
        if deleted_tracks:
            print(f"Removed {len(deleted_tracks)} tracks from DB that no longer exist.")
            # for dt_id, dt_path in deleted_tracks:
            #     print(f"  - Removed: {dt_path} (ID: {dt_id})")

    except sqlite3.Error as e:
        print(f"Database error removing old tracks: {e}")
    finally:
        conn.close()

class Database:
    """Database wrapper class for the music library."""
    
    def __init__(self):
        """Initialize the database."""
        # Make sure tables are created
        create_tables()
    
    def add_or_update_track(self, track):
        """Add or update a track in the database."""
        return add_or_update_track(track)
    
    def get_all_tracks(self):
        """Get all tracks from the database."""
        return get_all_tracks()
    
    def get_track_by_id(self, track_id):
        """Get a track by its ID."""
        return get_track_by_id(track_id)
    
    def get_tracks_by_ids(self, track_ids):
        """Get tracks by IDs."""
        return get_tracks_by_ids(track_ids)
    
    def remove_tracks_not_in_list(self, valid_filepaths):
        """Remove tracks not in the list."""
        return remove_tracks_not_in_list(valid_filepaths)

# Add functions for playlists
def create_playlist(name):
    """Create a new playlist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    playlist_id = None
    
    try:
        cursor.execute("INSERT INTO playlists (name) VALUES (?)", (name,))
        playlist_id = cursor.lastrowid
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error creating playlist: {e}")
    finally:
        conn.close()
        
    return playlist_id

def get_all_playlists():
    """Get all playlists."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM playlists")
    playlists = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
    conn.close()
    return playlists

def add_track_to_playlist(playlist_id, track_id, position=None):
    """Add a track to a playlist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get the next position if not specified
        if position is None:
            cursor.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM playlist_tracks WHERE playlist_id = ?", 
                (playlist_id,)
            )
            position = cursor.fetchone()[0]
        
        # Add the track
        cursor.execute(
            "INSERT OR REPLACE INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
            (playlist_id, track_id, position)
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error adding track to playlist: {e}")
    finally:
        conn.close()

def get_playlist_tracks(playlist_id):
    """Get all tracks in a playlist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get tracks ordered by position
    cursor.execute("""
        SELECT t.id, t.filepath, t.title, t.artist, t.album, t.genre, t.duration, t.album_art
        FROM tracks t
        JOIN playlist_tracks pt ON t.id = pt.track_id
        WHERE pt.playlist_id = ?
        ORDER BY pt.position
    """, (playlist_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    # Convert to Track objects
    tracks = []
    for row in rows:
        track = Track(
            id=row[0],
            filepath=row[1],
            title=row[2],
            artist=row[3],
            album=row[4],
            genre=row[5],
            length=row[6],
            album_art=row[7]
        )
        tracks.append(track)
    
    return tracks

def remove_track_from_playlist(playlist_id, track_id):
    """Remove a track from a playlist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
            (playlist_id, track_id)
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error removing track from playlist: {e}")
    finally:
        conn.close()

# Initialize DB when module is imported
initialize_db()