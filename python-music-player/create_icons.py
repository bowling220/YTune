#!/usr/bin/env python3
"""
Script to generate basic icons for the music player
Run this script once to create the necessary icon files
"""

import os
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QBrush
from PyQt5.QtCore import Qt, QRect, QSize

def create_dir_if_not_exists(path):
    """Create directory if it doesn't exist"""
    try:
        os.makedirs(path, exist_ok=True)
        print(f"Ensured directory exists: {path}")
    except Exception as e:
        print(f"Error creating directory {path}: {e}")

def create_icon(name, draw_function, directory):
    """Create an icon file using the provided drawing function"""
    filepath = os.path.join(directory, f"{name}.png")
    
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    
    # Call the drawing function
    draw_function(painter)
    
    painter.end()
    
    # Save the pixmap
    success = pixmap.save(filepath, "PNG")
    if success:
        print(f"Created icon: {filepath}")
    else:
        print(f"Failed to create icon: {filepath}")

def draw_play(painter):
    """Draw a play button triangle"""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(200, 200, 200)))
    
    # Draw a triangle pointing right
    points = [
        (20, 15),
        (20, 49), 
        (48, 32)
    ]
    painter.drawPolygon(*points)

def draw_pause(painter):
    """Draw a pause button (two rectangles)"""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(200, 200, 200)))
    
    # Draw two vertical rectangles
    painter.drawRect(20, 15, 8, 34)
    painter.drawRect(36, 15, 8, 34)

def draw_next(painter):
    """Draw a next button (two triangles)"""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(200, 200, 200)))
    
    # Draw two triangles pointing right
    points1 = [(15, 15), (15, 49), (35, 32)]
    painter.drawPolygon(*points1)
    
    points2 = [(35, 15), (35, 49), (55, 32)]
    painter.drawPolygon(*points2)

def draw_previous(painter):
    """Draw a previous button (two triangles pointing left)"""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(200, 200, 200)))
    
    # Draw two triangles pointing left
    points1 = [(55, 15), (55, 49), (35, 32)]
    painter.drawPolygon(*points1)
    
    points2 = [(35, 15), (35, 49), (15, 32)]
    painter.drawPolygon(*points2)

def draw_music_note(painter):
    """Draw a music note"""
    painter.setPen(QPen(QColor(100, 100, 100), 2))
    painter.setBrush(QBrush(QColor(150, 150, 150)))
    
    # Draw a simple music note
    painter.drawEllipse(10, 35, 25, 19)  # Note head
    painter.drawRect(35, 15, 3, 39)      # Note stem

def draw_volume_low(painter):
    """Draw a low volume icon (speaker with one wave)"""
    painter.setPen(QPen(QColor(150, 150, 150), 2))
    painter.setBrush(QBrush(QColor(150, 150, 150)))
    
    # Draw a speaker
    painter.drawRect(15, 25, 10, 14)
    points = [(25, 25), (35, 15), (35, 49), (25, 39)]
    painter.drawPolygon(*points)
    
    # Draw one sound wave
    painter.setPen(QPen(QColor(150, 150, 150), 2, Qt.PenStyle.SolidLine))
    painter.drawArc(38, 29, 6, 6, 0, 180 * 16)

def draw_volume_medium(painter):
    """Draw a medium volume icon (speaker with two waves)"""
    painter.setPen(QPen(QColor(150, 150, 150), 2))
    painter.setBrush(QBrush(QColor(150, 150, 150)))
    
    # Draw a speaker
    painter.drawRect(15, 25, 10, 14)
    points = [(25, 25), (35, 15), (35, 49), (25, 39)]
    painter.drawPolygon(*points)
    
    # Draw two sound waves
    painter.setPen(QPen(QColor(150, 150, 150), 2, Qt.PenStyle.SolidLine))
    painter.drawArc(38, 29, 6, 6, 0, 180 * 16)
    painter.drawArc(42, 25, 10, 14, 0, 180 * 16)

def draw_volume_high(painter):
    """Draw a high volume icon (speaker with three waves)"""
    painter.setPen(QPen(QColor(150, 150, 150), 2))
    painter.setBrush(QBrush(QColor(150, 150, 150)))
    
    # Draw a speaker
    painter.drawRect(15, 25, 10, 14)
    points = [(25, 25), (35, 15), (35, 49), (25, 39)]
    painter.drawPolygon(*points)
    
    # Draw three sound waves
    painter.setPen(QPen(QColor(150, 150, 150), 2, Qt.PenStyle.SolidLine))
    painter.drawArc(38, 29, 6, 6, 0, 180 * 16)
    painter.drawArc(42, 25, 10, 14, 0, 180 * 16)
    painter.drawArc(46, 20, 14, 24, 0, 180 * 16)

def draw_volume_mute(painter):
    """Draw a muted volume icon (speaker with X)"""
    painter.setPen(QPen(QColor(150, 150, 150), 2))
    painter.setBrush(QBrush(QColor(150, 150, 150)))
    
    # Draw a speaker
    painter.drawRect(15, 25, 10, 14)
    points = [(25, 25), (35, 15), (35, 49), (25, 39)]
    painter.drawPolygon(*points)
    
    # Draw X
    painter.setPen(QPen(QColor(150, 40, 40), 3, Qt.PenStyle.SolidLine))
    painter.drawLine(42, 22, 52, 42)
    painter.drawLine(42, 42, 52, 22)

def main():
    """Main function to create all icons"""
    # Get the icon directory path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icon_dir = os.path.join(script_dir, "assets", "icons")
    
    # Create the directory if it doesn't exist
    create_dir_if_not_exists(icon_dir)
    
    # Create all the icons
    create_icon("play", draw_play, icon_dir)
    create_icon("pause", draw_pause, icon_dir)
    create_icon("next", draw_next, icon_dir)
    create_icon("previous", draw_previous, icon_dir)
    create_icon("music_note", draw_music_note, icon_dir)
    create_icon("volume_low", draw_volume_low, icon_dir)
    create_icon("volume_medium", draw_volume_medium, icon_dir)
    create_icon("volume_high", draw_volume_high, icon_dir)
    create_icon("volume_mute", draw_volume_mute, icon_dir)
    
    print("Icon creation complete!")

if __name__ == "__main__":
    main() 