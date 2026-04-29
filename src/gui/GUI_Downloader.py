"""
YouTube Music Downloader GUI - Dark Grey & Red Theme with Enhanced Logs & Metadata
Requires: pip install PySide6
"""

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

current_dir = Path(__file__).parent

include_path = (current_dir / ".." / "include").resolve()
interface_path = (current_dir / ".." / "interface").resolve()

sys.path.insert(0, str(include_path))
sys.path.insert(1, str(interface_path))

from YoutubeMusicDownloader import Youtube_Downloader  # type: ignore
from Helpers_Validators import Helpers  # type: ignore
from Interface import DownloaderInterface # type: ignore

# ============================= Log Entry =============================
class LogEntry:
    def __init__(self, message: str, level: str):
        self.message = message
        self.level = level  # 'info', 'success', 'error', 'warning', 'failure'

    def to_html(self) -> str:
        color_map = {
            "info": "#cccccc",
            "success": "#00ff00",
            "error": "#ff5555",
            "warning": "#ffff55",
            "failure": "#ffa500"
        }
        color = color_map.get(self.level, "#ffffff")
        return f'<span style="color:{color};">[{self.level.upper()}] {self.message}</span><br>'

# ============================= Custom Image Button =============================
class ImageButton(QPushButton):
    def __init__(self, image_path, text="", parent=None):
        super().__init__(parent)
        self.text = text
        # Try to load icon, use fallback if file doesn't exist
        if os.path.exists(image_path):
            self.icon = QIcon(image_path)
            self.setIcon(self.icon)
            self.setIconSize(QSize(40, 40))
        else:
            self.setText(text[:1])  # Fallback to first letter of text
        self.setFixedSize(70, 70)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(text)
        self.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #660000;
                border-radius: 8px;
                padding: 5px;
                font-size: 24px;
            }
            QPushButton:hover {
                background-color: #4a0000;
                border: 1px solid #cc0000;
            }
            QPushButton:pressed {
                background-color: #5a0000;
                border: 1px solid #ff3333;
            }
        """)

# ============================= Sidebar Widget =============================
class SidebarWidget(QWidget):
    page_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(15)

        button_data = [
            ("assets/download_icon.png", "Download", 0),
            ("assets/settings_icon.png", "Settings", 1),
            ("assets/log_icon.png", "Logs", 2),
            ("assets/info_icon.png", "Info", 3),
        ]

        for img_path, tooltip, page_idx in button_data:
            btn = ImageButton(img_path, tooltip)
            btn.clicked.connect(lambda checked, idx=page_idx: self.page_selected.emit(idx))
            layout.addWidget(btn)

        layout.addStretch()
        self.setStyleSheet("background-color: #000000;")

# ============================= Enhanced Worker Thread with Subprocess =============================
class DownloadWorker(QThread):
    progress_update = Signal(str, int)
    log_message = Signal(str, str)
    finished = Signal(bool)

    def __init__(self, downloader, download_type, url=None, query=None):
        super().__init__()
        self.adapter = DownloaderInterface(downloader)
        self.download_type = download_type
        self.url = url
        self.query = query
        self.cancel_event = threading.Event()

    def progress_callback(self, percent: int, msg: str):
        self.progress_update.emit(msg, percent)

    def cancel(self):
        self.cancel_event.set()
        self.log_message.emit("Cancelling download...", "warning")

    def run(self):
        try:
            if self.download_type == "track":
                ok = self.adapter.download_track(
                    self.url, self.progress_callback, self.cancel_event)
            elif self.download_type == "album":
                ok = self.adapter.download_album(
                    self.url, self.progress_callback, self.cancel_event)
            elif self.download_type == "playlist":
                ok = self.adapter.download_playlist(
                    self.url, self.progress_callback, self.cancel_event)
            elif self.download_type == "search":
                ok = self.adapter.search_and_download(
                    self.query, self.progress_callback, self.cancel_event)
            else:
                raise ValueError("Unknown download type")
            self.finished.emit(ok)
        except Exception as e:
            self.log_message.emit(str(e), "error")
            self.finished.emit(False)
            
# ============================= Main Window =============================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.downloader = Youtube_Downloader()
        self.current_worker: Optional[DownloadWorker] = None
        self.log_entries: List[LogEntry] = []
        self.current_log_filter = "ALL"

        self.album_art_label = None
        self.search_group = None

        self.init_ui()
        # Try to set window icon, ignore if not found
        if os.path.exists("assets/download.png"):
            self.setWindowIcon(QIcon("assets/download.png"))

    def init_ui(self):
        self.setWindowTitle("YouTube Music Downloader")
        self.setMinimumSize(950, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---- HEADER ----
        header = QWidget()
        header.setFixedHeight(50)
        header.setStyleSheet("background-color: #1e1e1e;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 0, 10, 0)

        logo_label = QLabel()
        if os.path.exists("assets/download.png"):
            logo_pix = QPixmap("assets/download.png")
            if not logo_pix.isNull():
                logo_label.setPixmap(logo_pix.scaled(40, 40, Qt.KeepAspectRatio))
        else:
            logo_label.setText("YT")
            logo_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #cc0000;")
        header_layout.addWidget(logo_label)
        header_layout.addStretch()

        main_layout.addWidget(header)

        # ---- BODY ----
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.sidebar = SidebarWidget()
        self.sidebar.setFixedWidth(100)
        self.sidebar.page_selected.connect(self.switch_page)
        body_layout.addWidget(self.sidebar)

        self.stacked_widget = QStackedWidget()
        body_layout.addWidget(self.stacked_widget, 1)
        main_layout.addLayout(body_layout)

        # ---- FOOTER (improved: larger progress bar, percentage label) ----
        footer = QWidget()
        footer.setFixedHeight(50)
        footer.setStyleSheet("background-color: #1e1e1e;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(10, 5, 10, 5)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(25)
        footer_layout.addWidget(self.progress_bar, 1)

        self.progress_percent_label = QLabel("0%")
        self.progress_percent_label.setStyleSheet("color: #cccccc;")
        self.progress_percent_label.setVisible(False)
        footer_layout.addWidget(self.progress_percent_label)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #cccccc;")
        footer_layout.addWidget(self.status_label)
        footer_layout.addStretch()
        main_layout.addWidget(footer)

        # Create pages
        self.download_page = self.create_download_page()
        self.settings_page = self.create_settings_page()
        self.logs_page = self.create_logs_page()
        self.tools_page = self.create_tools_page()

        self.stacked_widget.addWidget(self.download_page)
        self.stacked_widget.addWidget(self.settings_page)
        self.stacked_widget.addWidget(self.logs_page)
        self.stacked_widget.addWidget(self.tools_page)

        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2e2e2e;
                color: #e0e0e0;
            }
            QGroupBox {
                border: 1px solid #cc0000;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
                color: #cc0000;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLineEdit, QComboBox, QTextEdit {
                background-color: #3a3a3a;
                border: 1px solid #660000;
                border-radius: 3px;
                padding: 5px;
                color: #ffffff;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 1px solid #cc0000;
            }
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #cc0000;
                border-radius: 5px;
                padding: 8px;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #cc0000;
            }
            QPushButton:pressed {
                background-color: #990000;
            }
            QPushButton:disabled {
                background-color: #4a4a4a;
                border-color: #888888;
                color: #aaaaaa;
            }
            QCheckBox, QRadioButton {
                color: #e0e0e0;
            }
            QCheckBox::indicator, QRadioButton::indicator {
                width: 13px;
                height: 13px;
                background-color: #3a3a3a;
                border: 1px solid #cc0000;
            }
            QCheckBox::indicator:checked, QRadioButton::indicator:checked {
                background-color: #cc0000;
            }
            QRadioButton::indicator {
                border-radius: 7px;
            }
            QProgressBar {
                border: 1px solid #cc0000;
                border-radius: 3px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #cc0000;
            }
            QListWidget {
                background-color: #3a3a3a;
                border: 1px solid #660000;
                outline: none;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #cc0000;
                color: white;
            }
            QTabWidget::pane {
                border: 1px solid #660000;
                background-color: #2e2e2e;
            }
            QTabBar::tab {
                background-color: #3a3a3a;
                color: #e0e0e0;
                padding: 5px 10px;
            }
            QTabBar::tab:selected {
                background-color: #cc0000;
            }
        """)

        self.refresh_settings_display()

    def switch_page(self, index: int):
        self.stacked_widget.setCurrentIndex(index)

    # ==================== Download Page ====================
    def create_download_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel("YouTube Music Downloader")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #cc0000;")
        layout.addWidget(title_label)

        subtitle_label = QLabel("Free. No signup. Download now.")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("font-size: 12px; color: #aaaaaa;")
        layout.addWidget(subtitle_label)

        url_layout = QHBoxLayout()
        url_layout.setSpacing(8)

        clear_btn = QPushButton("✕")
        clear_btn.setFixedWidth(30)
        clear_btn.clicked.connect(lambda: self.url_input.clear())
        url_layout.addWidget(clear_btn)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter YouTube or YouTube Music URL...")
        url_layout.addWidget(self.url_input, 1)

        self.fetch_meta_btn = QPushButton("Search")
        self.fetch_meta_btn.setFixedWidth(120)
        self.fetch_meta_btn.clicked.connect(self.fetch_metadata)
        url_layout.addWidget(self.fetch_meta_btn)

        layout.addLayout(url_layout)

        meta_type_layout = QHBoxLayout()
        meta_type_layout.setSpacing(15)

        self.album_art_label = QLabel()
        self.album_art_label.setFixedSize(120, 120)
        self.album_art_label.setStyleSheet("border: 1px solid #660000; background-color: #3a3a3a;")
        self.album_art_label.setAlignment(Qt.AlignCenter)
        self.album_art_label.setText("No Image")
        meta_type_layout.addWidget(self.album_art_label)

        self.metadata_text = QTextEdit()
        self.metadata_text.setReadOnly(True)
        self.metadata_text.setMaximumHeight(120)
        self.metadata_text.setPlaceholderText("Click 'Search' to see details about this resource...")
        
        # Make metadata font larger and bolder
        self.metadata_text.setStyleSheet("""
            QTextEdit {
                font-size: 13px;
                font-weight: 400;
                font-family: 'Segoe UI', Arial, sans-serif;
                background-color: #3a3a3a;
                border: 2px solid #cc0000;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        
        meta_type_layout.addWidget(self.metadata_text, 1)

        type_group = QGroupBox("Download Type")
        type_group_layout = QVBoxLayout()
        type_group_layout.setSpacing(8)

        self.radio_track = QRadioButton("Track")
        self.radio_album = QRadioButton("Album")
        self.radio_playlist = QRadioButton("Playlist")
        self.radio_search = QRadioButton("Search")
        self.radio_track.setChecked(True)
        self.type_group = QButtonGroup()
        for rb in (self.radio_track, self.radio_album, self.radio_playlist, self.radio_search):
            self.type_group.addButton(rb)
            type_group_layout.addWidget(rb)

        type_group_layout.addSpacing(5)

        # Download and Stop buttons in a horizontal row
        action_layout = QHBoxLayout()
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.start_download)
        action_layout.addWidget(self.download_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_download)
        self.stop_btn.setEnabled(False)
        action_layout.addWidget(self.stop_btn)

        type_group_layout.addLayout(action_layout)

        self.open_folder_btn = QPushButton("Open Folder")
        self.open_folder_btn.clicked.connect(self.open_downloads_folder)
        self.open_folder_btn.setEnabled(False)
        type_group_layout.addWidget(self.open_folder_btn)

        type_group.setLayout(type_group_layout)
        meta_type_layout.addWidget(type_group)

        layout.addLayout(meta_type_layout)

        self.search_group = QGroupBox("Search Query")
        search_layout = QHBoxLayout(self.search_group)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter song name...")
        search_layout.addWidget(self.search_input)
        self.search_group.setVisible(False)
        layout.addWidget(self.search_group)

        self.radio_search.toggled.connect(lambda checked: self.search_group.setVisible(checked))

        layout.addStretch()
        return page

    # ==================== Metadata Fetching ====================
    def fetch_metadata(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "No URL", "Please enter a URL first.")
            return
        if not Helpers.validate_youtube_url(url):
            QMessageBox.warning(self, "Invalid URL", "Not a valid YouTube/YouTube Music URL.")
            return

        self.album_art_label.clear()
        self.album_art_label.setText("Loading...")

        try:
            is_valid, message, metadata = Helpers.validate_resource_youtube(url)
        except Exception as e:
            self.metadata_text.setHtml(f'<span style="color:#ff5555;">Unexpected error: {e}</span>')
            self.album_art_label.setText("Error")
            return

        if not is_valid:
            self.metadata_text.setHtml(f'<span style="color:#ff5555;">Error: {message}</span>')
            self.album_art_label.setText("No Image")
            return

        if metadata:
            info_text = f"""
            <b>Title:</b> {metadata.get('title', 'Unknown')}<br>
            <b>Album:</b> {metadata.get('album', 'Unknown')}<br>
            <b>Artist:</b> {metadata.get('artist', 'Unknown')}<br>
            <b>Duration:</b> {metadata.get('duration', 'Unknown')}<br>
            """
            if metadata.get('playlist_count'):
                info_text += f"<b>Items in playlist/album:</b> {metadata['playlist_count']}<br>"
            self.metadata_text.setHtml(info_text)
            
            thumb_url = metadata.get('thumbnail')
            if thumb_url:
                self.load_thumbnail(thumb_url)
            else:
                self.album_art_label.setText("No Image")
        else:
            self.metadata_text.setText("No metadata available.")
            self.album_art_label.setText("No Image")

    def load_thumbnail(self, url: str):
        """Download thumbnail asynchronously using QNetworkAccessManager."""
        self.album_art_label.setText("...")
        if not hasattr(self, 'network_manager'):
            self.network_manager = QNetworkAccessManager(self)
        request = QNetworkRequest(QUrl(url))
        reply = self.network_manager.get(request)
        reply.finished.connect(lambda r=reply: self._thumbnail_ready(r))

    def _thumbnail_ready(self, reply):
        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(self.album_art_label.size(),
                                       Qt.KeepAspectRatio,
                                       Qt.SmoothTransformation)
                self.album_art_label.setPixmap(pixmap)
            else:
                self.album_art_label.setText("Invalid Image")
        else:
            self.album_art_label.setText("No Image")
        reply.deleteLater()

    def open_downloads_folder(self):
        """Open the downloads folder using QDesktopServices (cross-platform)"""
        output_dir = self.downloader._Youtube_Downloader__output_directory
        if output_dir.exists():
            # Use QDesktopServices for cross-platform folder opening
            folder_url = QUrl.fromLocalFile(str(output_dir.absolute()))
            QDesktopServices.openUrl(folder_url)
        else:
            QMessageBox.warning(self, "Folder not found", f"The folder '{output_dir}' does not exist yet.")

    # ==================== Settings Page ====================
    def create_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Audio Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp3", "flac", "m4a", "opus", "ogg", "wav"])
        row1.addWidget(self.format_combo)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Audio Quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["320k", "256k", "192k", "128k", "auto", "disable"])
        row2.addWidget(self.quality_combo)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Output Directory:"))
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setReadOnly(True)
        row3.addWidget(self.output_dir_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_output_dir)
        row3.addWidget(browse_btn)
        layout.addLayout(row3)

        self.metadata_check = QCheckBox("Embed metadata (artist, album, cover art)")
        layout.addWidget(self.metadata_check)

        self.cookies_check = QCheckBox("Use cookies for authentication")
        layout.addWidget(self.cookies_check)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        load_btn = QPushButton("Load Settings")
        load_btn.clicked.connect(self.load_settings)
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.reset_settings)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(load_btn)
        btn_row.addWidget(reset_btn)
        layout.addLayout(btn_row)

        layout.addStretch()
        return page

    def refresh_settings_display(self):
        self.format_combo.setCurrentText(self.downloader._Youtube_Downloader__audio_format)
        self.quality_combo.setCurrentText(self.downloader._Youtube_Downloader__audio_quality)
        self.output_dir_edit.setText(str(self.downloader._Youtube_Downloader__output_directory))
        self.metadata_check.setChecked(self.downloader._Youtube_Downloader__embed_metadata)
        self.cookies_check.setChecked(self.downloader.use_cookies)

    def browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def save_settings(self):
        self.downloader._Youtube_Downloader__audio_format = self.format_combo.currentText()
        self.downloader._Youtube_Downloader__audio_quality = self.quality_combo.currentText()
        self.downloader._Youtube_Downloader__output_directory = Path(self.output_dir_edit.text())
        self.downloader._Youtube_Downloader__embed_metadata = self.metadata_check.isChecked()
        self.downloader.use_cookies = self.cookies_check.isChecked()
        self.downloader.save_config()
        self.append_log("Settings saved successfully.", "success")

    def load_settings(self):
        self.downloader.load_config()
        self.refresh_settings_display()
        self.append_log("Settings loaded from file.", "info")

    def reset_settings(self):
        self.downloader.reset_to_defaults()
        self.refresh_settings_display()
        self.append_log("Settings reset to defaults.", "info")

    # ==================== Logs Page ====================
    def create_logs_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)

        filter_layout = QHBoxLayout()
        self.filter_all_btn = QPushButton("All")
        self.filter_success_btn = QPushButton("Success")
        self.filter_failed_btn = QPushButton("Failed")
        self.filter_error_btn = QPushButton("Error")

        self.filter_buttons = [
            self.filter_all_btn,
            self.filter_success_btn,
            self.filter_failed_btn,
            self.filter_error_btn
        ]
        for btn in self.filter_buttons:
            btn.setCheckable(True)
            btn.setFixedWidth(80)
            btn.clicked.connect(self.on_filter_button_clicked)
            filter_layout.addWidget(btn)

        filter_layout.addStretch()
        self.filter_all_btn.setChecked(True)

        layout.addLayout(filter_layout)

        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Monospace", 10))
        layout.addWidget(self.log_display)

        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self.clear_logs)
        layout.addWidget(clear_btn)

        return page

    def on_filter_button_clicked(self):
        """Make filter buttons mutually exclusive and update filter."""
        sender = self.sender()
        if not sender.isChecked():
            sender.setChecked(True)
            return

        for btn in self.filter_buttons:
            if btn is not sender:
                btn.setChecked(False)

        if sender == self.filter_all_btn:
            flt = "ALL"
        elif sender == self.filter_success_btn:
            flt = "SUCCESS"
        elif sender == self.filter_failed_btn:
            flt = "FAILURE"
        else:
            flt = "ERROR"
        self.set_log_filter(flt)

    def set_log_filter(self, filter_type: str):
        self.current_log_filter = filter_type
        self.refresh_log_display()

    def refresh_log_display(self):
        self.log_display.clear()
        for entry in self.log_entries:
            level_upper = entry.level.upper()
            if self.current_log_filter == "ALL":
                self.log_display.insertHtml(entry.to_html())
            elif self.current_log_filter == "SUCCESS" and level_upper == "SUCCESS":
                self.log_display.insertHtml(entry.to_html())
            elif self.current_log_filter == "FAILURE" and level_upper == "FAILURE":
                self.log_display.insertHtml(entry.to_html())
            elif self.current_log_filter == "ERROR" and level_upper == "ERROR":
                self.log_display.insertHtml(entry.to_html())
            elif self.current_log_filter == "WARNING" and level_upper == "WARNING":
                self.log_display.insertHtml(entry.to_html())
        self.log_display.moveCursor(QTextCursor.MoveOperation.End)

    def append_log(self, message: str, level: str):
        entry = LogEntry(message, level)
        self.log_entries.append(entry)
        self.refresh_log_display()
        if level in ("error", "failure"):
            self.status_label.setText(f"Error: {message[:100]}")
        elif level == "success":
            self.status_label.setText(message[:100])

    def clear_logs(self):
        self.log_entries.clear()
        self.log_display.clear()

    # ==================== Tools Page ====================
    def create_tools_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        dep_btn = QPushButton("Check Dependencies")
        dep_btn.clicked.connect(self.check_dependencies)
        layout.addWidget(dep_btn)

        cookie_btn = QPushButton("Manage Cookies")
        cookie_btn.clicked.connect(self.manage_cookies)
        layout.addWidget(cookie_btn)

        trouble_btn = QPushButton("Run Troubleshooter")
        trouble_btn.clicked.connect(self.run_troubleshooter)
        layout.addWidget(trouble_btn)

        help_btn = QPushButton("Show yt-dlp Help")
        help_btn.clicked.connect(self.show_ytdlp_help)
        layout.addWidget(help_btn)

        layout.addStretch()
        return page

    # ==================== Download Logic with Proper Cancellation ====================
    def start_download(self):
        if self.current_worker and self.current_worker.isRunning():
            QMessageBox.warning(self, "Busy", "A download is already in progress.")
            return

        url = self.url_input.text().strip()
        if self.radio_search.isChecked():
            query = self.search_input.text().strip()
            if not query:
                QMessageBox.warning(self, "Missing Query", "Please enter a search query.")
                return
            download_type = "search"
        else:
            if not url:
                QMessageBox.warning(self, "Missing URL", "Please enter a URL.")
                return
            if not Helpers.validate_youtube_url(url):
                QMessageBox.warning(self, "Invalid URL", "Not a valid YouTube/YouTube Music URL.")
                return
            download_type = ("track" if self.radio_track.isChecked()
                             else "album" if self.radio_album.isChecked()
                             else "playlist")

        # Disable UI during download
        self.download_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.open_folder_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_percent_label.setVisible(True)
        self.progress_percent_label.setText("0%")
        self.status_label.setText("Starting download...")

        self.current_worker = DownloadWorker(
            self.downloader, download_type,
            url=url if not self.radio_search.isChecked() else None,
            query=self.search_input.text().strip() if self.radio_search.isChecked() else None
        )
        self.current_worker.log_message.connect(self.append_log)
        self.current_worker.progress_update.connect(self.update_progress)
        self.current_worker.finished.connect(self.download_finished)
        self.current_worker.start()

    def stop_download(self):
        """Stop the current download by terminating the subprocess"""
        if self.current_worker and self.current_worker.isRunning():
            self.status_label.setText("Stopping download...")
            self.append_log("Attempting to stop download...", "warning")
            self.current_worker.cancel()
            # The worker will emit finished when it terminates

    def update_progress(self, message: str, percent: int):
        """Update progress bar with download percentage"""
        self.progress_bar.setValue(percent)
        self.progress_percent_label.setText(f"{percent}%")
        self.status_label.setText(message)

    def download_finished(self, success: bool):
        """Handle download completion or cancellation"""
        self.download_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.open_folder_btn.setEnabled(success)
        self.progress_bar.setVisible(False)
        self.progress_percent_label.setVisible(False)
        
        if success:
            self.status_label.setText("Download completed successfully.")
            self.append_log("Download completed.", "success")
        else:
            self.status_label.setText("Download failed or cancelled.")
            self.append_log("Download finished with errors.", "failure")
        
        self.current_worker = None

    # ==================== Tools Methods ====================
    def check_dependencies(self):
        """Check if yt-dlp is installed and accessible"""
        self.append_log("Checking dependencies...", "info")
        try:
            result = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip()
                QMessageBox.information(self, "Dependency Check", f"yt-dlp is installed (version: {version})")
                self.append_log(f"yt-dlp version: {version}", "success")
            else:
                QMessageBox.warning(self, "Dependency Check", "yt-dlp is not installed or not in PATH.")
                self.append_log("yt-dlp not found", "error")
        except FileNotFoundError:
            QMessageBox.warning(self, "Dependency Check", "yt-dlp is not installed. Please install it first.")
            self.append_log("yt-dlp not found in system", "error")

    def manage_cookies(self):
        """Open a file dialog to select a cookies file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Cookies File", "", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            self.downloader.cookies_file = file_path
            self.append_log(f"Cookies file set to: {file_path}", "info")
            QMessageBox.information(self, "Cookies File", f"Using cookies from:\n{file_path}")
        else:
            self.append_log("Cookie file selection cancelled.", "warning")

    def run_troubleshooter(self):
        """Run basic troubleshooting"""
        self.append_log("Running troubleshooter...", "info")
        
        # Check yt-dlp
        try:
            result = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                self.append_log(f"✓ yt-dlp found: {result.stdout.strip()}", "success")
            else:
                self.append_log("✗ yt-dlp not responding correctly", "error")
        except FileNotFoundError:
            self.append_log("✗ yt-dlp not installed", "error")
        
        # Check output directory
        output_dir = self.downloader._Youtube_Downloader__output_directory
        if output_dir.exists():
            self.append_log(f"✓ Output directory exists: {output_dir}", "success")
        else:
            self.append_log(f"✗ Output directory does not exist: {output_dir}", "warning")
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                self.append_log(f"✓ Created output directory", "success")
            except Exception as e:
                self.append_log(f"✗ Cannot create output directory: {e}", "error")
        
        QMessageBox.information(self, "Troubleshooter", "Troubleshooter completed. Check logs for details.")

    def show_ytdlp_help(self):
        """Open yt-dlp documentation in browser"""
        webbrowser.open("https://github.com/yt-dlp/yt-dlp#readme")
        self.append_log("Opened yt-dlp help in browser.", "info")

# ============================= Main =============================
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
    
print("Downloader imported from:", Youtube_Downloader.__module__)
print("Interface imported from:", DownloaderInterface.__module__)