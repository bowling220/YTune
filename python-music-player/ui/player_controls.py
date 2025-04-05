from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider,
    QLabel, QStyle, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtGui import QIcon

class PlayerControls(QWidget):
    # Define signals
    play_clicked = Signal()
    pause_clicked = Signal()
    stop_clicked = Signal()
    previous_clicked = Signal()
    next_clicked = Signal()
    position_changed = Signal(int)
    volume_changed = Signal(float)
    bluetooth_clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._media_position = 0
        self._media_duration = 0
        
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the UI."""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Transport controls
        transport_layout = QHBoxLayout()
        
        # Previous button
        self.previous_button = QPushButton()
        self.previous_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward))
        self.previous_button.clicked.connect(self.previous_clicked)
        transport_layout.addWidget(self.previous_button)
        
        # Play button
        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_button.clicked.connect(self._on_play_clicked)
        transport_layout.addWidget(self.play_button)
        
        # Stop button
        self.stop_button = QPushButton()
        self.stop_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_button.clicked.connect(self.stop_clicked)
        transport_layout.addWidget(self.stop_button)
        
        # Next button
        self.next_button = QPushButton()
        self.next_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward))
        self.next_button.clicked.connect(self.next_clicked)
        transport_layout.addWidget(self.next_button)
        
        # Bluetooth button
        self.bluetooth_button = QPushButton("🎧")
        self.bluetooth_button.setToolTip("Connect to Bluetooth audio")
        self.bluetooth_button.clicked.connect(self.bluetooth_clicked)
        self.bluetooth_button.setMaximumWidth(40)
        transport_layout.addWidget(self.bluetooth_button)
        
        # Volume
        transport_layout.addStretch(1)
        
        volume_label = QLabel("Volume:")
        transport_layout.addWidget(volume_label)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setMaximumWidth(100)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        transport_layout.addWidget(self.volume_slider)
        
        main_layout.addLayout(transport_layout)
        
        # Seek and position
        position_layout = QHBoxLayout()
        
        self.position_label = QLabel("00:00")
        position_layout.addWidget(self.position_label)
        
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self._on_position_slider_moved)
        self.position_slider.sliderReleased.connect(self._on_position_slider_released)
        position_layout.addWidget(self.position_slider)
        
        self.duration_label = QLabel("00:00")
        position_layout.addWidget(self.duration_label)
        
        main_layout.addLayout(position_layout)
        
        # Set padding and spacing
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
    def _on_play_clicked(self):
        """Handle play button click."""
        if self.play_button.icon().name() == self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay).name():
            self.play_clicked.emit()
        else:
            self.pause_clicked.emit()
            
    def _on_volume_changed(self, value):
        """Handle volume slider change."""
        volume = value / 100.0
        self.volume_changed.emit(volume)
        
    def _on_position_slider_moved(self, position):
        """Handle position slider being moved by user."""
        self.position_label.setText(self._format_time(position))
        
    def _on_position_slider_released(self):
        """Handle position slider being released."""
        self.position_changed.emit(self.position_slider.value())
        
    def _format_time(self, milliseconds):
        """Format time in milliseconds to minutes:seconds."""
        seconds = milliseconds // 1000
        minutes = seconds // 60
        seconds %= 60
        return f"{minutes:02}:{seconds:02}"
        
    def set_position(self, position):
        """Set the current media position."""
        if position != self._media_position:
            self._media_position = position
            self.position_label.setText(self._format_time(position))
            
            # Only update slider if it's not being dragged
            if not self.position_slider.isSliderDown():
                self.position_slider.setValue(position)
                
    def set_duration(self, duration):
        """Set the media duration."""
        if duration != self._media_duration:
            self._media_duration = duration
            self.position_slider.setRange(0, duration)
            self.duration_label.setText(self._format_time(duration))
            
    def set_volume(self, volume):
        """Set the volume level."""
        self.volume_slider.setValue(int(volume * 100))
        
    def set_playing(self, playing):
        """Update the play/pause button state."""
        if playing:
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)) 