import sys
import os
import webbrowser
from pathlib import Path
from typing import Optional, List, Dict, Any
import tempfile
import urllib.request
import subprocess
import threading
import time
import re

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QLineEdit,
    QComboBox, QCheckBox, QTextEdit, QProgressBar,
    QFileDialog, QMessageBox, QRadioButton, QButtonGroup, QGroupBox,
    QTabWidget, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QUrl
from PySide6.QtGui import QFont, QTextCursor, QIcon, QPixmap, QPainter, QColor, QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from core.SpotifyDownloader import SpotifyMusicDownloader
from src.utils.Helpers import Helpers  # type: ignore


class SpotifyMusicGUI:
    pass