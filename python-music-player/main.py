#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# main.py
import os
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QDir, Qt

from ui.main_window import MainWindow
from core.database import initialize_db

# --- Application Details ---
APP_NAME = "PythonMusicPlayer"
APP_VERSION = "0.1.0"
ORG_NAME = "MyCompany" # Used for QSettings path
ORG_DOMAIN = "mycompany.com" # Used for QSettings path

def main():
    # Make sure the database is initialized
    initialize_db()
    
    # Create application
    app = QApplication(sys.argv)
    
    # Set app info
    app.setApplicationName("PythonMusicPlayer")
    app.setApplicationVersion("0.1.0")
    
    # Enable High DPI support
    if hasattr(Qt, 'HighDpiScaleFactorRoundingPolicy'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    else:
        # Fall back to deprecated methods for older Qt versions
        # QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        # QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        pass
    
    # Load stylesheet
    try:
        style_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "style.qss")
        if os.path.exists(style_path):
            with open(style_path, "r") as f:
                app.setStyleSheet(f.read())
        else:
            print(f"Style file not found at {style_path}")
    except Exception as e:
        print(f"Error loading stylesheet: {e}")
    
    # Create and show main window
    main_window = MainWindow()
    main_window.show()
    
    # Run application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()