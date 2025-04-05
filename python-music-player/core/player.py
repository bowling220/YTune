import os
import platform
from PySide6 import QtMultimedia
from PySide6.QtCore import QUrl, QObject, Signal, Property
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaFormat

class PlayerSignals(QObject):
    """Signals for the media player."""
    position_changed = Signal(int)  # Current position in milliseconds
    duration_changed = Signal(int)  # Total duration in milliseconds
    state_changed = Signal(int)     # Player state
    media_changed = Signal(str)     # Current media path
    audio_device_changed = Signal(str)  # Current audio device

class Player(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Create signals
        self.signals = PlayerSignals()
        
        # Create audio output
        self.audio_output = QAudioOutput()
        
        # Create media player
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)
        
        # Connect signals
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        
        # Set default volume
        self.audio_output.setVolume(0.5)
        
        # Get available audio devices
        self.available_audio_devices = self._get_audio_devices()
        
    def _get_audio_devices(self):
        """Get a list of available audio output devices"""
        devices = {}
        
        try:
            # Modern PySide6 versions
            if hasattr(QMediaFormat, 'supportedAudioOutputDevices'):
                for device in QMediaFormat.supportedAudioOutputDevices():
                    devices[device.id()] = device.description()
            # Older PySide6 versions
            else:
                # Use QMediaDevices if available (PySide6 6.4+)
                if hasattr(QtMultimedia, 'QMediaDevices'):
                    from PySide6.QtMultimedia import QMediaDevices
                    for device in QMediaDevices.audioOutputs():
                        devices[device.id()] = device.description()
                # Fallback to platform-specific methods
                else:
                    # On Windows, try to use system audio API
                    if platform.system() == 'Windows':
                        try:
                            import pyaudio
                            p = pyaudio.PyAudio()
                            for i in range(p.get_device_count()):
                                info = p.get_device_info_by_index(i)
                                if info['maxOutputChannels'] > 0:  # Output device
                                    devices[str(i)] = info['name']
                            p.terminate()
                        except ImportError:
                            print("PyAudio not available for device detection")
                    # Add a dummy device as fallback
                    if not devices:
                        devices["default"] = "Default Audio Device"
        except Exception as e:
            print(f"Error detecting audio devices: {e}")
            devices["default"] = "Default Audio Device"
            
        return devices
    
    def set_audio_device(self, device_id):
        """Set the audio output device by ID"""
        device_exists = False
        
        try:
            # Modern PySide6 versions
            if hasattr(QMediaFormat, 'supportedAudioOutputDevices'):
                for device in QMediaFormat.supportedAudioOutputDevices():
                    if device.id() == device_id:
                        self.audio_output.setDevice(device)
                        self.signals.audio_device_changed.emit(device_id)
                        device_exists = True
                        break
            # Older PySide6 versions
            else:
                # Try to create a QAudioDevice from the ID
                try:
                    from PySide6.QtMultimedia import QMediaDevices, QAudioDevice
                    # Try to find the device by ID
                    for device in QMediaDevices.audioOutputs():
                        if device.id() == device_id:
                            self.audio_output.setDevice(device)
                            self.signals.audio_device_changed.emit(device_id)
                            device_exists = True
                            break
                except (ImportError, AttributeError):
                    print(f"Warning: Cannot create QAudioDevice, device ID {device_id} cannot be used directly")
        except Exception as e:
            print(f"Error setting audio device: {e}")
                
        if not device_exists:
            print(f"Warning: Audio device {device_id} not found")
            
        return device_exists
            
    def get_audio_devices(self):
        """Return a dictionary of available audio devices (id: description)"""
        return self.available_audio_devices
        
    def refresh_audio_devices(self):
        """Refresh the list of available audio devices"""
        self.available_audio_devices = self._get_audio_devices()
        return self.available_audio_devices
    
    def _on_position_changed(self, position):
        """Handle position change events."""
        self.signals.position_changed.emit(position)
        
    def _on_duration_changed(self, duration):
        """Handle duration change events."""
        self.signals.duration_changed.emit(duration)
        
    def _on_state_changed(self, state):
        """Handle state change events."""
        self.signals.state_changed.emit(state)
        
    def _on_media_status_changed(self, status):
        """Handle media status change events."""
        # Emit current media path when loaded
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            source = self.player.source().toString()
            if source.startswith("file:///"):
                # Convert URL to file path
                file_path = QUrl(source).toLocalFile()
                self.signals.media_changed.emit(file_path)
                
    def play(self):
        """Start or resume playback."""
        self.player.play()
        
    def pause(self):
        """Pause playback."""
        self.player.pause()
        
    def stop(self):
        """Stop playback."""
        self.player.stop()
        
    def set_position(self, position):
        """Set the playback position in milliseconds."""
        self.player.setPosition(position)
        
    def get_position(self):
        """Get the current playback position in milliseconds."""
        return self.player.position()
        
    def get_duration(self):
        """Get the total duration in milliseconds."""
        return self.player.duration()
        
    def set_volume(self, volume):
        """Set the volume (0.0 to 1.0)."""
        self.audio_output.setVolume(volume)
        
    def get_volume(self):
        """Get the current volume (0.0 to 1.0)."""
        return self.audio_output.volume()
        
    def set_muted(self, muted):
        """Set whether audio is muted."""
        self.audio_output.setMuted(muted)
        
    def is_muted(self):
        """Check if audio is muted."""
        return self.audio_output.isMuted()
        
    def load(self, file_path):
        """Load a media file."""
        if os.path.exists(file_path):
            url = QUrl.fromLocalFile(file_path)
            self.player.setSource(url)
            return True
        return False

    def find_bluetooth_device(self, name_contains=None):
        """
        Find a Bluetooth audio device, optionally filtering by name
        
        Args:
            name_contains: String to search for in device names (optional)
            
        Returns:
            Tuple of (device_id, device_name) if found, otherwise (None, None)
        """
        devices = self._get_audio_devices()
        
        # Look for common Bluetooth device indicators
        bluetooth_keywords = ["bluetooth", "airpods", "wireless", "bt"]
        
        if name_contains:
            bluetooth_keywords.append(name_contains.lower())
            
        for device_id, device_name in devices.items():
            device_name_lower = device_name.lower()
            
            # Check if any of the Bluetooth keywords are in the device name
            for keyword in bluetooth_keywords:
                if keyword in device_name_lower:
                    return device_id, device_name
                    
        return None, None
        
    def auto_select_bluetooth(self):
        """
        Automatically select a Bluetooth audio device if available
        
        Returns:
            True if a Bluetooth device was found and selected, False otherwise
        """
        device_id, device_name = self.find_bluetooth_device()
        
        if device_id:
            successful = self.set_audio_device(device_id)
            if successful:
                print(f"Auto-selected Bluetooth device: {device_name}")
            return successful
            
        return False
        
    def find_and_select_airpods(self):
        """
        Specifically look for AirPods and select them
        
        Returns:
            True if AirPods were found and selected, False otherwise
        """
        device_id, device_name = self.find_bluetooth_device("airpods")
        
        if device_id:
            successful = self.set_audio_device(device_id)
            if successful:
                print(f"Selected AirPods device: {device_name}")
            return successful
            
        return False
        
    def enable_multi_output(self):
        """
        Enable audio output to both speakers and AirPods/Bluetooth device.
        
        Note: This is a limited functionality that works by telling Windows to:
        1. Open Sound settings
        2. Let the user enable the 'Stereo Mix' or set up multi-output manually
        
        Returns:
            True if the Sound settings were opened, False otherwise
        """
        try:
            import subprocess
            import platform
            
            # Open Windows sound settings
            if platform.system() == 'Windows':
                print("Opening Windows Sound settings...")
                subprocess.Popen('start ms-settings:sound', shell=True)
                
                # Inform the user about manual setup
                print("Please enable both your speakers and AirPods in the Windows Sound settings:")
                print("1. In Sound settings, click on 'App volume and device preferences'")
                print("2. Under 'Advanced', find this app and select both output devices")
                return True
            else:
                print("Multi-output functionality is currently only supported on Windows")
                return False
        except Exception as e:
            print(f"Error enabling multi-output: {e}")
            return False

    def play_next(self):
        """Play the next track (emits a signal for handlers to handle)."""
        # This method will be handled by external code that's tracking the playlist
        print("Player: Next track requested")
        # Stop current playback to indicate we're ready for a new track
        self.stop()
        
    def play_previous(self):
        """Play the previous track (emits a signal for handlers to handle)."""
        # This method will be handled by external code that's tracking the playlist
        print("Player: Previous track requested")
        # Stop current playback to indicate we're ready for a new track
        self.stop() 