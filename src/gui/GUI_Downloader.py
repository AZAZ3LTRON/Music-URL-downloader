"""
YouTube Music Downloader GUI - Dark Grey & Red Theme with Enhanced Logs & Metadata
Requires: pip install PySide6
"""

import sys
import os
import webbrowser
from pathlib import Path
from typing import Optional, List, Dict, Any
import urllib.request
import tempfile

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QLineEdit,
    QComboBox, QCheckBox, QTextEdit, QProgressBar,
    QFileDialog, QMessageBox, QRadioButton, QButtonGroup, QGroupBox,
    QTabWidget, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QFont, QTextCursor, QIcon, QPixmap, QPainter, QColor

# Add the include directory (adjust as needed)
include_path = Path(r"C:\Users\Ayomide Ajimuda\Documents\03 - Projects\Music-URL-downloader\src\include")
if str(include_path) not in sys.path:
    sys.path.insert(0, str(include_path))

from YoutubeMusicDownloader import Youtube_Downloader  # type: ignore
from Helpers_Validators import Helpers  # type: ignore

# ============================= Log Entry =============================
class LogEntry:
    def __init__(self, message: str, level: str):
        self.message = message
        self.level = level  # 'info', 'success', 'error', 'warning'

    def to_html(self) -> str:
        color_map = {
            "info": "#cccccc",
            "success": "#00ff00",
            "error": "#ff5555",
            "warning": "#ffff55"
        }
        color = color_map.get(self.level, "#ffffff")
        return f'<span style="color:{color};">[{self.level.upper()}] {self.message}</span><br>'

# ============================= Custom Image Button =============================
class ImageButton(QPushButton):
    def __init__(self, image_path, text="", parent=None):
        super().__init__(parent)
        self.text = text
        self.icon = QIcon(image_path)
        self.setIcon(self.icon)
        self.setIconSize(QSize(40, 40))
        self.setFixedSize(70, 70)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(text)
        self.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #660000;
                border-radius: 8px;
                padding: 5px;
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

        # Button data: (image_path, tooltip_text, page_index)
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
        self.setStyleSheet("background-color: #000000;")  # Sable Black

# ============================= Worker Thread =============================
class DownloadWorker(QThread):
    progress_update = Signal(str, int)
    log_message = Signal(str, str)   # (message, level)
    finished = Signal(bool)

    def __init__(self, downloader: Youtube_Downloader, download_type: str, url: str = None, query: str = None):
        super().__init__()
        self.downloader = downloader
        self.download_type = download_type
        self.url = url
        self.query = query

    def run(self):
        try:
            success = False
            if self.download_type == "track":
                success = self.downloader.download_track(self.url)
            elif self.download_type == "album":
                success = self.downloader.download_album(self.url)
            elif self.download_type == "playlist":
                success = self.downloader.download_playlist(self.url)
            elif self.download_type == "search":
                success = self.downloader.search_and_download(self.query)
            self.finished.emit(success)
        except Exception as e:
            self.log_message.emit(str(e), "error")
            self.finished.emit(False)

# ============================= Main Window =============================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.downloader = Youtube_Downloader()
        self.current_worker: Optional[DownloadWorker] = None
        self.log_entries: List[LogEntry] = []   # store all logs
        self.current_log_filter = "ALL"        # ALL, SUCCESS, FAILED, ERROR

        # New instance variables for album art and search group
        self.album_art_label = None
        self.search_group = None

        self.init_ui()
        self.setWindowIcon(QIcon("assets/download.png")) # Window Image

    def init_ui(self):
        self.setWindowTitle("YouTube Music Downloader - Dark Grey & Red")
        self.setMinimumSize(950, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        # Main layout now vertical to accommodate header/footer
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
        logo_pix = QPixmap("assets/download.png")
        if not logo_pix.isNull():
            logo_label.setPixmap(logo_pix.scaled(40, 40, Qt.KeepAspectRatio))
        header_layout.addWidget(logo_label)
        header_layout.addStretch()

        main_layout.addWidget(header)

        # ---- BODY: Sidebar + Stacked Pages ----
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

        # ---- FOOTER (progress + status) ----
        footer = QWidget()
        footer.setFixedHeight(40)
        footer.setStyleSheet("background-color: #1e1e1e;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(10, 0, 10, 0)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(15)
        footer_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #cccccc;")
        footer_layout.addWidget(self.status_label)
        footer_layout.addStretch()
        main_layout.addWidget(footer)

        # Create pages (download page no longer holds progress bar / status label)
        self.download_page = self.create_download_page()
        self.settings_page = self.create_settings_page()
        self.logs_page = self.create_logs_page()
        self.tools_page = self.create_tools_page()

        self.stacked_widget.addWidget(self.download_page)
        self.stacked_widget.addWidget(self.settings_page)
        self.stacked_widget.addWidget(self.logs_page)
        self.stacked_widget.addWidget(self.tools_page)

        # Global stylesheet (dark grey & red)
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

    # ==================== Download Page (revamped) ====================
    def create_download_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # ----- 1. Big title and subheading -----
        title_label = QLabel("YouTube Music Downloader")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #cc0000;")
        layout.addWidget(title_label)

        subtitle_label = QLabel("Free. No signup. Download now.")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("font-size: 12px; color: #aaaaaa;")
        layout.addWidget(subtitle_label)

        # ----- 2. URL row (clear button + url + get metadata) -----
        url_layout = QHBoxLayout()
        url_layout.setSpacing(8)

        clear_btn = QPushButton("✕")
        clear_btn.setFixedWidth(30)
        clear_btn.setToolTip("Clear URL")
        clear_btn.clicked.connect(lambda: self.url_input.clear())
        url_layout.addWidget(clear_btn)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter YouTube or YouTube Music URL...")
        self.url_input.setMinimumWidth(0)
        url_layout.addWidget(self.url_input, 1)  # stretch

        self.fetch_meta_btn = QPushButton("Search")
        self.fetch_meta_btn.setFixedWidth(120)
        self.fetch_meta_btn.clicked.connect(self.fetch_metadata)
        url_layout.addWidget(self.fetch_meta_btn)

        layout.addLayout(url_layout)

        # ----- 3. Metadata + Download Type (horizontal) -----
        meta_type_layout = QHBoxLayout()
        meta_type_layout.setSpacing(15)

        # Album art placeholder
        self.album_art_label = QLabel()
        self.album_art_label.setFixedSize(120, 120)
        self.album_art_label.setStyleSheet("border: 1px solid #660000; background-color: #3a3a3a;")
        self.album_art_label.setAlignment(Qt.AlignCenter)
        self.album_art_label.setText("No Image")
        meta_type_layout.addWidget(self.album_art_label)

        # Metadata text (compact)
        self.metadata_text = QTextEdit()
        self.metadata_text.setReadOnly(True)
        self.metadata_text.setMaximumHeight(120)
        self.metadata_text.setPlaceholderText("Click 'Get Metadata' to see info about this resource...")
        meta_type_layout.addWidget(self.metadata_text, 1)

        # Download Type group (right side)
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

        # Download and Open Folder buttons inside the group
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.start_download)
        type_group_layout.addWidget(self.download_btn)

        self.open_folder_btn = QPushButton("Open Folder")
        self.open_folder_btn.clicked.connect(self.open_downloads_folder)
        self.open_folder_btn.setEnabled(False)
        type_group_layout.addWidget(self.open_folder_btn)

        type_group.setLayout(type_group_layout)
        meta_type_layout.addWidget(type_group)

        layout.addLayout(meta_type_layout)

        # ----- 4. Search query (hidden by default) -----
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

        # Clear old art
        self.album_art_label.clear()
        self.album_art_label.setText("Loading...")

        is_valid, message, metadata = Helpers.validate_resource_youtube(url)
        if not is_valid:
            self.metadata_text.setHtml(f'<span style="color:#ff5555;">Error: {message}</span>')
            self.album_art_label.setText("No Image")
            return

        if metadata:
            info_text = f"""
            <b>Title:</b> {metadata.get('title', 'Unknown')}<br>
            <b>Type:</b> {metadata.get('type', 'Unknown')}<br>
            <b>Duration:</b> {metadata.get('duration', 'Unknown')}<br>
            <b>Uploader:</b> {metadata.get('uploader', 'Unknown')}<br>
            <b>View count:</b> {metadata.get('view_count', 'Unknown')}<br>
            """
            if metadata.get('playlist_count'):
                info_text += f"<b>Items in playlist/album:</b> {metadata['playlist_count']}<br>"
            if metadata.get('description'):
                desc = metadata['description'][:200] + "..." if len(metadata['description']) > 200 else metadata['description']
                info_text += f"<b>Description:</b> {desc}<br>"
            self.metadata_text.setHtml(info_text)

            # Load album art if available
            thumb_url = metadata.get('thumbnail')
            if thumb_url:
                self.load_thumbnail(thumb_url)
            else:
                self.album_art_label.setText("No Image")
        else:
            self.metadata_text.setText("No metadata available.")
            self.album_art_label.setText("No Image")

    def load_thumbnail(self, url: str):
        """Download thumbnail from URL and display it in the album art label."""
        try:
            # Use a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp_path = tmp.name
            urllib.request.urlretrieve(url, tmp_path)

            pixmap = QPixmap(tmp_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.album_art_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.album_art_label.setPixmap(scaled)
            else:
                self.album_art_label.setText("No Image")
        except Exception as e:
            self.album_art_label.setText("No Image")
            self.append_log(f"Could not load thumbnail: {e}", "warning")

    def open_downloads_folder(self):
        """Open the output directory in the system file explorer."""
        output_dir = self.downloader._Youtube_Downloader__output_directory
        if output_dir.exists():
            webbrowser.open(str(output_dir))
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
        for btn in (self.filter_all_btn, self.filter_success_btn, self.filter_failed_btn, self.filter_error_btn):
            btn.setCheckable(True)
            btn.setFixedWidth(80)
            filter_layout.addWidget(btn)
        filter_layout.addStretch()
        self.filter_all_btn.setChecked(True)

        self.filter_all_btn.clicked.connect(lambda: self.set_log_filter("ALL"))
        self.filter_success_btn.clicked.connect(lambda: self.set_log_filter("SUCCESS"))
        self.filter_failed_btn.clicked.connect(lambda: self.set_log_filter("FAILED"))
        self.filter_error_btn.clicked.connect(lambda: self.set_log_filter("ERROR"))

        layout.addLayout(filter_layout)

        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Monospace", 10))
        layout.addWidget(self.log_display)

        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self.clear_logs)
        layout.addWidget(clear_btn)

        return page

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
            elif self.current_log_filter == "FAILED" and level_upper == "FAILURE":
                self.log_display.insertHtml(entry.to_html())
            elif self.current_log_filter == "ERROR" and level_upper == "ERROR":
                self.log_display.insertHtml(entry.to_html())
        self.log_display.moveCursor(QTextCursor.MoveOperation.End)

    def append_log(self, message: str, level: str):
        entry = LogEntry(message, level)
        self.log_entries.append(entry)
        self.refresh_log_display()
        # Update status label in footer for errors/success
        if level == "error":
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

    # ==================== Download Logic ====================
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
            download_type = "track" if self.radio_track.isChecked() else "album" if self.radio_album.isChecked() else "playlist"

        self.download_btn.setEnabled(False)
        self.open_folder_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
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

    def update_progress(self, message: str, percent: int):
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)

    def download_finished(self, success: bool):
        self.download_btn.setEnabled(True)
        self.open_folder_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        if success:
            self.status_label.setText("Download completed successfully.")
            self.append_log("Download completed.", "success")
        else:
            self.status_label.setText("Download failed. Check logs.")
            self.append_log("Download failed.", "failure")
        self.current_worker = None

    # ==================== Tools Methods ====================
    def check_dependencies(self):
        self.append_log("Checking dependencies...", "info")
        result = self.downloader.check_dependencies()
        self.append_log(f"Dependency check result: {result}", "info")

    def manage_cookies(self):
        QMessageBox.information(self, "Cookie Manager", "Integrate your CookieManager class here.")

    def run_troubleshooter(self):
        self.append_log("Running troubleshooter...", "info")
        self.downloader.troubleshooting()

    def show_ytdlp_help(self):
        self.downloader.show_ytdlp_help()

# ============================= Main =============================
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()