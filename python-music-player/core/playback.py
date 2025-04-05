# core/playback.py
from PySide6.QtCore import QObject, Signal, QUrl, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaFormat
from PySide6.QtGui import QPixmap
from typing import Optional, List
import random
import os

from .models import Track
from . import database
from utils.formatters import format_duration_ms # Import utility

class PlaybackState:
    STOPPED = QMediaPlayer.PlaybackState.StoppedState
    PLAYING = QMediaPlayer.PlaybackState.PlayingState
    PAUSED = QMediaPlayer.PlaybackState.PausedState

class PlaybackMode:
    NORMAL = 0      # Play tracks in order, stop at end
    REPEAT_ONE = 1  # Repeat current track
    REPEAT_ALL = 2  # Repeat playlist, looping back to start
    SHUFFLE = 3     # Play tracks in random order

DEFAULT_VOLUME = 50 # 0-100

class PlaybackManager(QObject):
    """Manages audio playback using QMediaPlayer."""

    # Signals
    state_changed = Signal(QMediaPlayer.PlaybackState)
    track_changed = Signal(Track) # Emits the new track being played (or None if stopped)
    position_changed = Signal(int) # position in ms
    duration_changed = Signal(int) # duration in ms
    volume_changed = Signal(int) # volume 0-100
    playback_error = Signal(str)
    # For UI updates based on queue/mode changes
    queue_changed = Signal(list) # List of track IDs
    mode_changed = Signal(int) # PlaybackMode

    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self.current_track: Optional[Track] = None
        self.current_playlist_ids: List[int] = [] # All tracks in the current context
        self.playback_queue_ids: List[int] = [] # The actual order being played
        self.current_queue_index: int = -1
        self.playback_mode = PlaybackMode.REPEAT_ALL  # Default to repeat all
        self.volume = DEFAULT_VOLUME # Store volume internally (0-100)
        self.audio_output.setVolume(self.volume / 100.0) # QAudioOutput uses 0.0-1.0

        # Internal flag to prevent double next track on EndOfMedia
        self._playing_next_automatically = False

        # Connect QMediaPlayer signals
        self.player.playbackStateChanged.connect(self.on_state_changed)
        self.player.positionChanged.connect(self.position_changed.emit)
        self.player.durationChanged.connect(self.duration_changed.emit)
        self.player.errorOccurred.connect(self.on_error)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)
        # QAudioOutput volumeChanged is float 0-1, convert for our signal
        self.audio_output.volumeChanged.connect(lambda v: self.volume_changed.emit(int(v * 100)))


    def set_playlist(self, track_ids, playlist_mode=PlaybackMode.NORMAL, start_track_id=None):
        """
        Set the playlist for playback.
        
        Args:
            track_ids (list): List of track IDs to play
            playlist_mode (PlaybackMode): The playback mode (normal, repeat, shuffle)
            start_track_id (int, optional): If provided, playback will start with this track
        """
        if not track_ids:
            print("Playlist set with empty track list")
            return
        
        self.playback_queue_ids = list(track_ids)
        self.playback_mode = playlist_mode

        # Set initial index
        if start_track_id is not None and start_track_id in self.playback_queue_ids:
            self.current_queue_index = self.playback_queue_ids.index(start_track_id)
        else:
            self.current_queue_index = 0
        
        print(f"Playlist set. Mode: {self.playback_mode}. Start Index: {self.current_queue_index}. Queue size: {len(self.playback_queue_ids)}")
        
        # Immediately load the track to prepare it for playback
        track_id = self.playback_queue_ids[self.current_queue_index]
        track = database.get_track_by_id(track_id)

        if track and track.filepath and os.path.exists(track.filepath):
            self.current_track = track
            print(f"Playing [{self.current_queue_index+1}/{len(self.playback_queue_ids)}]: {track.display_title()} ({track.filepath})")
            source = QUrl.fromLocalFile(track.filepath)
            self._playing_next_automatically = True # Prevent double next on status change
            self.player.setSource(source)
            # Automatically play the track
            self.player.play()
            self.track_changed.emit(self.current_track)
            self._playing_next_automatically = False # Reset flag
        else:
            error_msg = f"Track not found or file missing: ID {track_id}"
            if track: error_msg += f" Path: {track.filepath}"
            print(error_msg)
            self.playback_error.emit(error_msg)
            # Skip to next track if file is missing
            QTimer.singleShot(50, self.play_next) # Use timer to avoid recursion issues

    def play_track_by_id(self, track_id: int):
        """Plays a specific track ID, assuming it's in the current playlist context."""
        if track_id in self.playback_queue_ids:
             index = self.playback_queue_ids.index(track_id)
             self.play_track_at_index(index)
        elif track_id in self.current_playlist_ids:
            # Track is in original list but not current queue (e.g. shuffle was active)
            # Decide behavior: Rebuild queue or just play this one?
            # Simple approach: Set it as the current index in the *original* list
            # (This might break shuffle continuity)
            try:
                original_index = self.current_playlist_ids.index(track_id)
                # For simplicity, let's just rebuild the queue starting here if mode allows
                if self.playback_mode == PlaybackMode.SHUFFLE:
                    # Re-shuffle but try to place this track first? Complex.
                    # Easiest: Just rebuild and play.
                     self.playback_queue_ids = self.current_playlist_ids[:]
                     self._shuffle_queue()
                     try:
                         self.current_queue_index = self.playback_queue_ids.index(track_id)
                         self.play_track_at_index(self.current_queue_index)
                     except ValueError: # Should not happen if shuffle keeps all elements
                         self.play_next()
                else:
                    self.playback_queue_ids = self.current_playlist_ids[:]
                    self.current_queue_index = original_index
                    self.play_track_at_index(self.current_queue_index)

            except ValueError:
                 print(f"Track ID {track_id} found in original list but index failed?")
                 self.play_next() # Fallback
        else:
            print(f"Track ID {track_id} not found in current playlist or queue.")
            # Optionally load just this single track
            # self.set_playlist([track_id], start_track_id=track_id)

    def play_track_at_index(self, index: int):
        """Plays the track at the specified index in the playback_queue_ids."""
        if 0 <= index < len(self.playback_queue_ids):
            self.current_queue_index = index
            track_id = self.playback_queue_ids[self.current_queue_index]
            track = database.get_track_by_id(track_id)

            if track and track.filepath and os.path.exists(track.filepath):
                self.current_track = track
                print(f"Playing [{self.current_queue_index+1}/{len(self.playback_queue_ids)}]: {track.display_title()} ({track.filepath})")
                source = QUrl.fromLocalFile(track.filepath)
                # Check if format is supported (optional, basic check)
                # media_format = QMediaFormat(source)
                # if not self.player.hasSupport(media_format):
                #      print(f"Warning: Format potentially not supported: {track.filepath}")

                self._playing_next_automatically = True # Prevent double next on status change
                self.player.setSource(source)
                self.player.play()
                self.track_changed.emit(self.current_track)
                self._playing_next_automatically = False # Reset flag
            else:
                error_msg = f"Track not found or file missing: ID {track_id}"
                if track: error_msg += f" Path: {track.filepath}"
                print(error_msg)
                self.playback_error.emit(error_msg)
                # Skip to next track if file is missing
                QTimer.singleShot(50, self.play_next) # Use timer to avoid recursion issues
        else:
            print(f"Invalid index for playback: {index}")
            self.stop()

    def play(self):
        """Starts playback from the current track or the beginning of the queue."""
        print("Play command received")
        if self.player.playbackState() == PlaybackState.PAUSED:
            print("Resuming from paused state")
            self.player.play()
        elif self.current_queue_index != -1 and self.current_track:
            print(f"Starting playback from current track: {self.current_track.display_title()}")
            # The track is already loaded, just play it
            self.player.play()
            
            # Force emit the track changed signal to update UI
            self.track_changed.emit(self.current_track)
        elif self.playback_queue_ids:
            print("Starting playback from beginning of queue")
            self.play_track_at_index(0)
        else:
            print("Playback queue is empty.")

    def pause(self):
        """Pauses playback."""
        if self.player.playbackState() == PlaybackState.PLAYING:
            self.player.pause()

    def toggle_play_pause(self):
        """Toggles between play and pause states."""
        if self.player.playbackState() == PlaybackState.PLAYING:
            self.pause()
        else:
            self.play() # Handles both Paused and Stopped states

    def stop(self):
        """Stops playback completely."""
        print("Playback stopped.")
        self.player.stop()
        self.current_track = None
        # self.current_queue_index = -1 # Keep index for potential restart? Or reset? Resetting is safer.
        self.current_queue_index = -1
        self.track_changed.emit(None) # Signal that nothing is playing
        # Don't clear the queue here, stop just stops playback

    def play_next(self):
        """Plays the next track in the queue based on playback mode."""
        if not self.playback_queue_ids:
            self.stop()
            return

        current_index = self.current_queue_index
        next_index = -1

        if self.playback_mode == PlaybackMode.REPEAT_ONE:
            next_index = current_index # Play same track again
        else:
            next_index = current_index + 1

        # Handle end of queue
        if next_index >= len(self.playback_queue_ids):
            if self.playback_mode in [PlaybackMode.REPEAT_ALL, PlaybackMode.SHUFFLE]:
                print("End of playlist reached, looping back to start (REPEAT_ALL mode).")
                next_index = 0 # Wrap around
                if self.playback_mode == PlaybackMode.SHUFFLE:
                     # Reshuffle when wrapping around? Optional. Spotify doesn't typically.
                     # self._shuffle_queue() # Uncomment to reshuffle each loop
                     pass
            else: # Normal mode, end of playlist
                print("End of playlist reached in NORMAL mode.")
                self.stop()
                return

        if next_index != -1:
             print(f"Playing next track at index {next_index}")
             self.play_track_at_index(next_index)
             # Ensure it starts playing
             self.player.play()
        else:
            # Should not happen if logic is correct, but fallback
             self.stop()


    def play_previous(self):
        """Plays the previous track in the queue."""
        # If track is more than a few seconds in, restart current track instead
        if self.player.position() > 3000: # 3 seconds
            self.player.setPosition(0)
            return

        if not self.playback_queue_ids:
            self.stop()
            return

        current_index = self.current_queue_index
        prev_index = -1

        if self.playback_mode == PlaybackMode.REPEAT_ONE:
             prev_index = current_index # Play same track again
        else:
            prev_index = current_index - 1

        # Handle beginning of queue
        if prev_index < 0:
            if self.playback_mode in [PlaybackMode.REPEAT_ALL, PlaybackMode.SHUFFLE]:
                prev_index = len(self.playback_queue_ids) - 1 # Wrap around to end
            else: # Normal mode, beginning of playlist
                 # Restart first track? Or do nothing? Restart is common.
                 if len(self.playback_queue_ids) > 0:
                     prev_index = 0
                 else:
                     self.stop()
                     return

        if prev_index != -1:
            print(f"Playing previous track at index {prev_index}")
            self.play_track_at_index(prev_index)
            # Ensure it starts playing
            self.player.play()
        else:
            self.stop()

    def set_volume(self, volume: int):
        """Sets the volume (0-100)."""
        self.volume = max(0, min(100, volume)) # Clamp value
        self.audio_output.setVolume(self.volume / 100.0)
        # volume_changed signal is emitted by audio_output automatically

    def seek(self, position_ms: int):
        """Seeks to a position in the current track (milliseconds)."""
        if self.player.isSeekable():
            self.player.setPosition(position_ms)

    def set_playback_mode(self, mode: int):
        """Sets the playback mode (NORMAL, REPEAT_ONE, REPEAT_ALL, SHUFFLE)."""
        if mode == self.playback_mode:
            return

        self.playback_mode = mode
        print(f"Playback mode set to: {mode}")

        # Rebuild queue if shuffle is turned on/off
        current_id_playing = self.playback_queue_ids[self.current_queue_index] if self.current_queue_index != -1 else None

        if mode == PlaybackMode.SHUFFLE:
            self.playback_queue_ids = self.current_playlist_ids[:] # Start from original list
            self._shuffle_queue()
        else:
            # Switching back from shuffle, restore original order
            self.playback_queue_ids = self.current_playlist_ids[:]

        # Try to find the currently playing track in the new queue order
        if current_id_playing and current_id_playing in self.playback_queue_ids:
            try:
                self.current_queue_index = self.playback_queue_ids.index(current_id_playing)
            except ValueError:
                 # Should not happen if shuffle keeps all elements, but fallback
                 self.current_queue_index = 0 if self.playback_queue_ids else -1
        elif self.playback_queue_ids:
             self.current_queue_index = 0 # Default to start if current track lost
        else:
            self.current_queue_index = -1

        self.queue_changed.emit(self.playback_queue_ids)
        self.mode_changed.emit(self.playback_mode)


    def _shuffle_queue(self):
        """Shuffles the playback_queue_ids in place."""
        if len(self.playback_queue_ids) > 1:
            # Keep track of current song if playing
            current_id = None
            if self.current_queue_index != -1:
                current_id = self.playback_queue_ids[self.current_queue_index]

            random.shuffle(self.playback_queue_ids)

            # Optional: Put current song back at the start of shuffled list?
            # Spotify often does this.
            if current_id and current_id in self.playback_queue_ids:
                 current_shuffled_index = self.playback_queue_ids.index(current_id)
                 # Swap current song to index 0
                 self.playback_queue_ids[0], self.playback_queue_ids[current_shuffled_index] = \
                     self.playback_queue_ids[current_shuffled_index], self.playback_queue_ids[0]
                 self.current_queue_index = 0 # We just moved it to the start
            elif self.playback_queue_ids:
                self.current_queue_index = 0 # Default to new start if no current track
            else:
                self.current_queue_index = -1

            print("Queue shuffled.")
        else:
             # If only 0 or 1 song, index is easy
             self.current_queue_index = 0 if self.playback_queue_ids else -1


    # --- Signal Handlers ---
    def on_state_changed(self, state):
        """Handles state changes from QMediaPlayer."""
        self.state_changed.emit(state)
        # print(f"Playback state changed: {state}")

    def on_error(self, error, error_string=""):
        """Handles errors from QMediaPlayer."""
        # error is QMediaPlayer.Error enum, error_string provides more detail
        print(f"Player Error: {error} - {error_string}")
        print(f"Current source: {self.player.source()}")
        self.playback_error.emit(f"Playback error: {error_string}")
        # Maybe try skipping to next track on error?
        # QTimer.singleShot(100, self.play_next)

    def on_media_status_changed(self, status):
        """Handles media status changes, especially EndOfMedia."""
        print(f"Media Status Changed: {status}")
        if status == QMediaPlayer.MediaStatus.EndOfMedia and not self._playing_next_automatically:
            print("Track finished naturally. Playing next track.")
            self._playing_next_automatically = True
            QTimer.singleShot(100, self.play_next)
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            error_msg = f"Invalid media: {self.player.source().toLocalFile()}"
            print(error_msg)
            self.playback_error.emit(error_msg)
            QTimer.singleShot(50, self.play_next) # Skip invalid track
        elif status == QMediaPlayer.MediaStatus.LoadedMedia:
            print("Media loaded. Starting playback.")
            # Ensure playback starts when media is loaded
            self.player.play()

    def play_track(self, track):
        """Play a single track directly.
        This sets up a queue with just this track and plays it."""
        if track and track.id is not None:
            print(f"Playing track: {track.display_title()}")
            # Get other tracks in the database to be ready to continue playback
            from core.database import get_all_tracks
            all_tracks = get_all_tracks()
            all_track_ids = [t.id for t in all_tracks]
            
            # If there are other tracks, set up a playlist starting with this one
            if all_track_ids:
                self.set_playlist(all_track_ids, start_track_id=track.id)
            else:
                # Fallback to just playing this track alone
                self.set_playlist([track.id], start_track_id=track.id)
        else:
            print("Cannot play track: Invalid track object")
            self.playback_error.emit("Cannot play track: Invalid track object")