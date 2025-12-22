"""
GUI for Interactive Spotify Playlist/Album/Track Downloader
Requires: PyQt5 (install with pip install PyQt5)
"""

import sys
import os
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                             QTextEdit, QComboBox, QFileDialog, QMessageBox,
                             QTabWidget, QGroupBox, QProgressBar, QCheckBox,
                             QSpinBox, QDoubleSpinBox, QListWidget, QListWidgetItem,
                             QSplitter, QFrame, QSizePolicy)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor

# Import your Downloader class
from interactive_downloader import Downloader


class DownloadThread(QThread):
    """Thread for running download operations without freezing the GUI"""
    update_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, downloader, url, download_type, output_dir, bitrate, audio_format):
        super().__init__()
        self.downloader = downloader
        self.url = url
        self.download_type = download_type
        self.output_dir = output_dir
        self.bitrate = bitrate
        self.audio_format = audio_format
        
    def run(self):
        try:
            # Configure downloader with GUI settings
            self.downloader._Downloader__bitrate = self.bitrate
            self.downloader._Downloader__audio_format = self.audio_format
            self.downloader._Downloader__output_dir = Path(self.output_dir)
            
            self.update_signal.emit(f"Starting download...\nURL: {self.url}")
            
            # Determine which download method to use based on type
            if self.download_type == "track_album":
                if "album" in self.url.lower():
                    output_template = str(Path(self.output_dir) / "{artist}/{album}/{title}.{output-ext}")
                else:
                    output_template = str(Path(self.output_dir) / "{artist} - {title}.{output-ext}")
                    
                result = self.downloader.run_download(self.url, output_template)
                
            elif self.download_type == "playlist":
                output_template = str(Path(self.output_dir) / "{playlist}/{title}.{output-ext}")
                result = self.downloader.run_download(
                    self.url, 
                    output_template,
                    ["--playlist-numbering", "--playlist-retain-track-cover"]
                )
                
            elif self.download_type == "search":
                output_template = str(Path(self.output_dir) / "{artist} - {title}.{output-ext}")
                result = self.downloader.run_download(self.url, output_template)
                
            elif self.download_type == "file":
                # For file downloads, we'll handle this differently
                self.update_signal.emit("Batch download from file selected. Use the 'Batch Download' tab.")
                self.finished_signal.emit(False, "Use Batch Download tab for file downloads")
                return
                
            # Check result
            if hasattr(result, 'returncode'):
                if result.returncode == 100:  # Metadata TypeError
                    self.update_signal.emit("Error: Metadata TypeError")
                    self.finished_signal.emit(False, "Metadata TypeError")
                elif result.returncode == 101:  # No results found
                    self.update_signal.emit("Error: No results found")
                    self.finished_signal.emit(False, "No results found")
                elif result.returncode == 0:
                    self.update_signal.emit("Download completed successfully!")
                    self.finished_signal.emit(True, "Download successful")
            else:
                self.update_signal.emit("Download failed")
                self.finished_signal.emit(False, "Download failed")
                
        except Exception as e:
            self.update_signal.emit(f"Error: {str(e)}")
            self.finished_signal.emit(False, str(e))


class BatchDownloadThread(QThread):
    """Thread for batch downloads from file"""
    update_signal = pyqtSignal(str, str)  # (message, type)
    progress_signal = pyqtSignal(int, int)  # (current, total)
    finished_signal = pyqtSignal(int, int)  # (success_count, total_count)
    
    def __init__(self, downloader, filepath, output_dir, bitrate, audio_format, max_retries, retry_delay):
        super().__init__()
        self.downloader = downloader
        self.filepath = filepath
        self.output_dir = output_dir
        self.bitrate = bitrate
        self.audio_format = audio_format
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
    def run(self):
        from datetime import datetime
        import time
        
        # Configure downloader
        self.downloader._Downloader__bitrate = self.bitrate
        self.downloader._Downloader__audio_format = self.audio_format
        self.downloader._Downloader__output_dir = Path(self.output_dir)
        
        # Read URLs from file
        try:
            with open(self.filepath, 'r') as file:
                urls = [line.strip() for line in file if line.strip() and not line.strip().startswith('#')]
        except Exception as e:
            self.update_signal.emit(f"Error reading file: {str(e)}", "error")
            self.finished_signal.emit(0, 0)
            return
            
        if not urls:
            self.update_signal.emit("No URLs found in file", "warning")
            self.finished_signal.emit(0, 0)
            return
            
        total = len(urls)
        success_count = 0
        
        for i, url in enumerate(urls, 1):
            self.progress_signal.emit(i, total)
            self.update_signal.emit(f"Processing {i}/{total}: {url}", "info")
            
            # Determine template based on URL type
            if "playlist" in url.lower():
                output_template = str(Path(self.output_dir) / "{playlist}/{title}.{output-ext}")
                additional_args = ["--playlist-numbering", "--playlist-retain-track-cover"]
            elif "album" in url.lower():
                output_template = str(Path(self.output_dir) / "{artist}/{album}/{title}.{output-ext}")
                additional_args = None
            else:
                output_template = str(Path(self.output_dir) / "{artist} - {title}.{output-ext}")
                additional_args = None
            
            # Attempt download with retries
            for attempt in range(1, self.max_retries + 1):
                self.update_signal.emit(f"  Attempt {attempt}/{self.max_retries}", "info")
                
                try:
                    result = self.downloader.run_download(url, output_template, additional_args)
                    
                    if hasattr(result, 'returncode'):
                        if result.returncode == 0:
                            success_count += 1
                            self.update_signal.emit(f"  ✓ Successfully downloaded", "success")
                            break
                        elif result.returncode in [100, 101]:  # Non-retryable errors
                            self.update_signal.emit(f"  ✗ Non-retryable error", "error")
                            break
                    
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay)
                    else:
                        self.update_signal.emit(f"  ✗ Failed after {self.max_retries} attempts", "error")
                        
                except Exception as e:
                    self.update_signal.emit(f"  ✗ Exception: {str(e)}", "error")
                    if attempt == self.max_retries:
                        break
                    time.sleep(self.retry_delay)
        
        self.finished_signal.emit(success_count, total)


class SpotifyDownloaderGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.downloader = Downloader()
        self.download_thread = None
        self.batch_thread = None
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Spotify Downloader GUI")
        self.setGeometry(100, 100, 900, 700)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        tabs = QTabWidget()
        main_layout.addWidget(tabs)
        
        # Create tabs
        self.create_single_download_tab(tabs)
        self.create_batch_download_tab(tabs)
        self.create_settings_tab(tabs)
        self.create_logs_tab(tabs)
        
        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Check spotdl on startup
        self.check_spotdl_installation()
        
    def create_single_download_tab(self, tabs):
        """Create the single download tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # URL input
        url_group = QGroupBox("Download URL")
        url_layout = QVBoxLayout()
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter Spotify URL (track, album, or playlist)")
        url_layout.addWidget(QLabel("Spotify URL:"))
        url_layout.addWidget(self.url_input)
        
        # Search option
        self.search_checkbox = QCheckBox("Search by song name instead of URL")
        url_layout.addWidget(self.search_checkbox)
        
        url_group.setLayout(url_layout)
        layout.addWidget(url_group)
        
        # Settings group
        settings_group = QGroupBox("Download Settings")
        settings_layout = QVBoxLayout()
        
        # Audio format
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Audio Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp3", "flac", "ogg", "opus", "m4a", "wav"])
        self.format_combo.setCurrentText("mp3")
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        
        # Bitrate
        bitrate_layout = QHBoxLayout()
        bitrate_layout.addWidget(QLabel("Bitrate:"))
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItems(["320k", "256k", "192k", "160k", "128k", "96k", "64k"])
        self.bitrate_combo.setCurrentText("320k")
        bitrate_layout.addWidget(self.bitrate_combo)
        bitrate_layout.addStretch()
        
        # Output directory
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output Directory:"))
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setText("Downloads")
        output_layout.addWidget(self.output_dir_input)
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_output_dir)
        output_layout.addWidget(self.browse_button)
        
        settings_layout.addLayout(format_layout)
        settings_layout.addLayout(bitrate_layout)
        settings_layout.addLayout(output_layout)
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # Download button
        self.download_button = QPushButton("Start Download")
        self.download_button.clicked.connect(self.start_single_download)
        self.download_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        layout.addWidget(self.download_button)
        
        # Console output
        console_group = QGroupBox("Console Output")
        console_layout = QVBoxLayout()
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setStyleSheet("""
            QTextEdit {
                background-color: #f0f0f0;
                font-family: 'Courier New', monospace;
            }
        """)
        console_layout.addWidget(self.console_output)
        console_group.setLayout(console_layout)
        layout.addWidget(console_group)
        
        tabs.addTab(tab, "Single Download")
        
    def create_batch_download_tab(self, tabs):
        """Create the batch download tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # File selection
        file_group = QGroupBox("Batch File")
        file_layout = QVBoxLayout()
        
        file_input_layout = QHBoxLayout()
        self.batch_file_input = QLineEdit()
        self.batch_file_input.setPlaceholderText("Select a text file containing URLs (one per line)")
        file_input_layout.addWidget(self.batch_file_input)
        self.batch_browse_button = QPushButton("Browse...")
        self.batch_browse_button.clicked.connect(self.browse_batch_file)
        file_input_layout.addWidget(self.batch_browse_button)
        
        file_layout.addLayout(file_input_layout)
        
        # File preview
        self.file_preview = QTextEdit()
        self.file_preview.setReadOnly(True)
        self.file_preview.setMaximumHeight(150)
        file_layout.addWidget(QLabel("File Preview:"))
        file_layout.addWidget(self.file_preview)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # Batch settings
        batch_settings_group = QGroupBox("Batch Settings")
        batch_settings_layout = QVBoxLayout()
        
        # Retry settings
        retry_layout = QHBoxLayout()
        retry_layout.addWidget(QLabel("Max Retries:"))
        self.max_retries_spin = QSpinBox()
        self.max_retries_spin.setRange(1, 10)
        self.max_retries_spin.setValue(5)
        retry_layout.addWidget(self.max_retries_spin)
        
        retry_layout.addWidget(QLabel("Retry Delay (seconds):"))
        self.retry_delay_spin = QSpinBox()
        self.retry_delay_spin.setRange(1, 60)
        self.retry_delay_spin.setValue(20)
        retry_layout.addWidget(self.retry_delay_spin)
        retry_layout.addStretch()
        
        batch_settings_layout.addLayout(retry_layout)
        
        # Use same settings as single download
        self.use_same_settings_check = QCheckBox("Use same settings as Single Download tab")
        self.use_same_settings_check.setChecked(True)
        batch_settings_layout.addWidget(self.use_same_settings_check)
        
        batch_settings_group.setLayout(batch_settings_layout)
        layout.addWidget(batch_settings_group)
        
        # Batch download button
        self.batch_download_button = QPushButton("Start Batch Download")
        self.batch_download_button.clicked.connect(self.start_batch_download)
        self.batch_download_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        layout.addWidget(self.batch_download_button)
        
        # Batch progress
        batch_progress_group = QGroupBox("Batch Progress")
        batch_progress_layout = QVBoxLayout()
        
        self.batch_progress_label = QLabel("Ready")
        batch_progress_layout.addWidget(self.batch_progress_label)
        
        self.batch_progress_bar = QProgressBar()
        batch_progress_layout.addWidget(self.batch_progress_bar)
        
        self.batch_console = QTextEdit()
        self.batch_console.setReadOnly(True)
        self.batch_console.setMaximumHeight(200)
        batch_progress_layout.addWidget(self.batch_console)
        
        batch_progress_group.setLayout(batch_progress_layout)
        layout.addWidget(batch_progress_group)
        
        tabs.addTab(tab, "Batch Download")
        
    def create_settings_tab(self, tabs):
        """Create the settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # General settings
        general_group = QGroupBox("General Settings")
        general_layout = QVBoxLayout()
        
        # Temp directory
        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel("Temp Directory:"))
        self.temp_dir_input = QLineEdit()
        self.temp_dir_input.setText("Temporary")
        temp_layout.addWidget(self.temp_dir_input)
        temp_browse_button = QPushButton("Browse...")
        temp_browse_button.clicked.connect(lambda: self.browse_directory(self.temp_dir_input))
        temp_layout.addWidget(temp_browse_button)
        
        # Log directory
        log_layout = QHBoxLayout()
        log_layout.addWidget(QLabel("Log Directory:"))
        self.log_dir_input = QLineEdit()
        self.log_dir_input.setText("log")
        log_layout.addWidget(self.log_dir_input)
        log_browse_button = QPushButton("Browse...")
        log_browse_button.clicked.connect(lambda: self.browse_directory(self.log_dir_input))
        log_layout.addWidget(log_browse_button)
        
        general_layout.addLayout(temp_layout)
        general_layout.addLayout(log_layout)
        general_group.setLayout(general_layout)
        layout.addWidget(general_group)
        
        # spotdl settings
        spotdl_group = QGroupBox("spotdl Configuration")
        spotdl_layout = QVBoxLayout()
        
        self.check_spotdl_button = QPushButton("Check spotdl Installation")
        self.check_spotdl_button.clicked.connect(self.check_spotdl_installation)
        spotdl_layout.addWidget(self.check_spotdl_button)
        
        self.show_help_button = QPushButton("Show spotdl Help")
        self.show_help_button.clicked.connect(self.show_spotdl_help)
        spotdl_layout.addWidget(self.show_help_button)
        
        self.show_info_button = QPushButton("Show Program Info")
        self.show_info_button.clicked.connect(self.show_program_info)
        spotdl_layout.addWidget(self.show_info_button)
        
        spotdl_group.setLayout(spotdl_layout)
        layout.addWidget(spotdl_group)
        
        # Authentication settings (for user-specific downloads)
        auth_group = QGroupBox("Spotify Authentication")
        auth_layout = QVBoxLayout()
        
        auth_note = QLabel("Note: User-specific downloads (playlists, liked songs) require Spotify authentication.")
        auth_note.setWordWrap(True)
        auth_layout.addWidget(auth_note)
        
        # Add user-specific download buttons
        self.user_playlists_button = QPushButton("Download My Playlists")
        self.user_playlists_button.clicked.connect(self.download_user_playlists)
        auth_layout.addWidget(self.user_playlists_button)
        
        self.liked_songs_button = QPushButton("Download Liked Songs")
        self.liked_songs_button.clicked.connect(self.download_liked_songs)
        auth_layout.addWidget(self.liked_songs_button)
        
        self.saved_albums_button = QPushButton("Download Saved Albums")
        self.saved_albums_button.clicked.connect(self.download_saved_albums)
        auth_layout.addWidget(self.saved_albums_button)
        
        auth_group.setLayout(auth_layout)
        layout.addWidget(auth_group)
        
        layout.addStretch()
        tabs.addTab(tab, "Settings")
        
    def create_logs_tab(self, tabs):
        """Create the logs tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Log file viewer
        logs_group = QGroupBox("Log Files")
        logs_layout = QVBoxLayout()
        
        # Log selection
        log_select_layout = QHBoxLayout()
        log_select_layout.addWidget(QLabel("Select Log:"))
        self.log_combo = QComboBox()
        self.log_combo.addItems(["success.log", "failed.log", "error.log"])
        self.log_combo.currentTextChanged.connect(self.load_log_file)
        log_select_layout.addWidget(self.log_combo)
        
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_logs)
        log_select_layout.addWidget(refresh_button)
        
        clear_button = QPushButton("Clear Log")
        clear_button.clicked.connect(self.clear_log)
        log_select_layout.addWidget(clear_button)
        
        logs_layout.addLayout(log_select_layout)
        
        # Log content
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #f0f0f0;
                font-family: 'Courier New', monospace;
            }
        """)
        logs_layout.addWidget(self.log_viewer)
        
        logs_group.setLayout(logs_layout)
        layout.addWidget(logs_group)
        
        tabs.addTab(tab, "Logs")
        
    def browse_output_dir(self):
        """Browse for output directory"""
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_dir_input.setText(directory)
            
    def browse_batch_file(self):
        """Browse for batch file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Text File with URLs", 
            "", 
            "Text Files (*.txt);;All Files (*.*)"
        )
        if file_path:
            self.batch_file_input.setText(file_path)
            self.preview_batch_file(file_path)
            
    def browse_directory(self, line_edit):
        """Browse for directory"""
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            line_edit.setText(directory)
            
    def preview_batch_file(self, file_path):
        """Preview the contents of the batch file"""
        try:
            with open(file_path, 'r') as file:
                lines = file.readlines()[:10]  # Show first 10 lines
                content = ''.join(lines)
                if len(content) > 500:  # Limit preview
                    content = content[:500] + "\n... (truncated)"
                self.file_preview.setText(content)
        except Exception as e:
            self.file_preview.setText(f"Error reading file: {str(e)}")
            
    def start_single_download(self):
        """Start a single download"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Warning", "Please enter a URL or search query.")
            return
            
        # Validate URL or search query
        if self.search_checkbox.isChecked():
            download_type = "search"
        elif "spotify.com" not in url.lower() and not url.startswith("spotify:"):
            QMessageBox.warning(self, "Warning", "Please enter a valid Spotify URL or enable search mode.")
            return
        else:
            if "playlist" in url.lower():
                download_type = "playlist"
            else:
                download_type = "track_album"
        
        # Get settings
        output_dir = self.output_dir_input.text()
        bitrate = self.bitrate_combo.currentText()
        audio_format = self.format_combo.currentText()
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Disable download button
        self.download_button.setEnabled(False)
        self.download_button.setText("Downloading...")
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        # Clear console
        self.console_output.clear()
        
        # Start download thread
        self.download_thread = DownloadThread(
            self.downloader,
            url,
            download_type,
            output_dir,
            bitrate,
            audio_format
        )
        
        # Connect signals
        self.download_thread.update_signal.connect(self.update_console)
        self.download_thread.finished_signal.connect(self.download_finished)
        
        # Start thread
        self.download_thread.start()
        
    def start_batch_download(self):
        """Start batch download from file"""
        file_path = self.batch_file_input.text()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Warning", "Please select a valid text file.")
            return
            
        # Get settings
        if self.use_same_settings_check.isChecked():
            output_dir = self.output_dir_input.text()
            bitrate = self.bitrate_combo.currentText()
            audio_format = self.format_combo.currentText()
        else:
            # You could add separate settings for batch downloads here
            output_dir = "BatchDownloads"
            bitrate = "320k"
            audio_format = "mp3"
            
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Disable button
        self.batch_download_button.setEnabled(False)
        self.batch_download_button.setText("Downloading...")
        
        # Clear console
        self.batch_console.clear()
        
        # Start batch download thread
        self.batch_thread = BatchDownloadThread(
            self.downloader,
            file_path,
            output_dir,
            bitrate,
            audio_format,
            self.max_retries_spin.value(),
            self.retry_delay_spin.value()
        )
        
        # Connect signals
        self.batch_thread.update_signal.connect(self.update_batch_console)
        self.batch_thread.progress_signal.connect(self.update_batch_progress)
        self.batch_thread.finished_signal.connect(self.batch_download_finished)
        
        # Start thread
        self.batch_thread.start()
        
    def update_console(self, message):
        """Update console with download messages"""
        self.console_output.append(message)
        
    def update_batch_console(self, message, msg_type):
        """Update batch console with colored messages"""
        color_map = {
            "info": "black",
            "success": "green",
            "error": "red",
            "warning": "orange"
        }
        
        color = color_map.get(msg_type, "black")
        self.batch_console.append(f'<font color="{color}">{message}</font>')
        # Auto-scroll to bottom
        self.batch_console.verticalScrollBar().setValue(
            self.batch_console.verticalScrollBar().maximum()
        )
        
    def update_batch_progress(self, current, total):
        """Update batch progress bar"""
        self.batch_progress_bar.setMaximum(total)
        self.batch_progress_bar.setValue(current)
        self.batch_progress_label.setText(f"Processing {current} of {total}")
        
    def download_finished(self, success, message):
        """Handle completion of single download"""
        self.download_button.setEnabled(True)
        self.download_button.setText("Start Download")
        self.progress_bar.setVisible(False)
        
        if success:
            self.status_bar.showMessage("Download completed successfully!")
            self.console_output.append("\n✓ Download completed!")
        else:
            self.status_bar.showMessage(f"Download failed: {message}")
            self.console_output.append(f"\n✗ Download failed: {message}")
            
    def batch_download_finished(self, success_count, total_count):
        """Handle completion of batch download"""
        self.batch_download_button.setEnabled(True)
        self.batch_download_button.setText("Start Batch Download")
        
        # Show completion message
        if total_count > 0:
            self.batch_console.append(f"\n{'='*50}")
            self.batch_console.append(f"<b>Batch Download Complete!</b>")
            self.batch_console.append(f"Successfully downloaded: {success_count}/{total_count}")
            
            if success_count == total_count:
                self.status_bar.showMessage(f"All downloads completed successfully!")
            else:
                self.status_bar.showMessage(f"Completed with {total_count - success_count} failures")
        else:
            self.status_bar.showMessage("Batch download completed (no URLs found)")
            
    def check_spotdl_installation(self):
        """Check if spotdl is installed"""
        try:
            if self.downloader.check_spotdl():
                QMessageBox.information(self, "spotdl Check", "spotdl is installed and ready!")
            else:
                reply = QMessageBox.question(
                    self,
                    "spotdl Not Found",
                    "spotdl is not installed. Would you like to install it now?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.install_spotdl()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error checking spotdl: {str(e)}")
            
    def install_spotdl(self):
        """Install spotdl"""
        import subprocess
        import sys
        
        self.console_output.append("Installing spotdl...")
        
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "spotdl"])
            QMessageBox.information(self, "Success", "spotdl installed successfully!")
            self.console_output.append("✓ spotdl installed successfully!")
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "Error", f"Failed to install spotdl: {str(e)}")
            self.console_output.append(f"✗ Failed to install spotdl: {str(e)}")
            
    def show_spotdl_help(self):
        """Show spotdl help"""
        try:
            self.downloader.show_spotdl_help()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error showing help: {str(e)}")
            
    def show_program_info(self):
        """Show program information"""
        try:
            self.downloader.program_info()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error showing info: {str(e)}")
            
    def download_user_playlists(self):
        """Download user playlists (requires authentication)"""
        self.run_user_download("playlists")
        
    def download_liked_songs(self):
        """Download liked songs (requires authentication)"""
        self.run_user_download("liked")
        
    def download_saved_albums(self):
        """Download saved albums (requires authentication)"""
        self.run_user_download("albums")
        
    def run_user_download(self, download_type):
        """Run user-specific download with authentication"""
        # Get current settings
        output_dir = self.output_dir_input.text()
        bitrate = self.bitrate_combo.currentText()
        audio_format = self.format_combo.currentText()
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Show warning about authentication
        reply = QMessageBox.warning(
            self,
            "Spotify Authentication Required",
            f"This will open a browser window for Spotify authentication.\n"
            f"You need to be logged into your Spotify account.\n"
            f"Do you want to continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        # Run the appropriate download method
        try:
            self.console_output.append(f"Starting {download_type} download...")
            
            # Configure downloader
            self.downloader._Downloader__bitrate = bitrate
            self.downloader._Downloader__audio_format = audio_format
            self.downloader._Downloader__output_dir = Path(output_dir)
            
            # Call the appropriate method
            if download_type == "playlists":
                success = self.downloader.download_user_playlist()
            elif download_type == "liked":
                success = self.downloader.download_user_liked_songs()
            elif download_type == "albums":
                success = self.downloader.download_user_saved_albums()
                
            if success:
                self.console_output.append(f"✓ {download_type.capitalize()} downloaded successfully!")
                QMessageBox.information(self, "Success", f"{download_type.capitalize()} downloaded successfully!")
            else:
                self.console_output.append(f"✗ Failed to download {download_type}")
                QMessageBox.warning(self, "Warning", f"Failed to download {download_type}")
                
        except Exception as e:
            self.console_output.append(f"✗ Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error downloading {download_type}: {str(e)}")
            
    def load_log_file(self):
        """Load the selected log file"""
        log_file = self.log_combo.currentText()
        log_path = os.path.join("log", log_file)
        
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                self.log_viewer.setText(content)
            except Exception as e:
                self.log_viewer.setText(f"Error reading log file: {str(e)}")
        else:
            self.log_viewer.setText("Log file does not exist yet.")
            
    def refresh_logs(self):
        """Refresh log files"""
        self.load_log_file()
        
    def clear_log(self):
        """Clear the current log file"""
        log_file = self.log_combo.currentText()
        log_path = os.path.join("log", log_file)
        
        if os.path.exists(log_path):
            reply = QMessageBox.question(
                self,
                "Clear Log",
                f"Are you sure you want to clear {log_file}?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                try:
                    with open(log_path, 'w', encoding='utf-8') as file:
                        file.write("")
                    self.load_log_file()
                    QMessageBox.information(self, "Success", "Log cleared successfully!")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Error clearing log: {str(e)}")
                    
    def closeEvent(self, event):
        """Handle window close event"""
        # Stop any running threads
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.terminate()
            self.download_thread.wait()
            
        if self.batch_thread and self.batch_thread.isRunning():
            self.batch_thread.terminate()
            self.batch_thread.wait()
            
        event.accept()


def main():
    """Main function to run the GUI"""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show the main window
    window = SpotifyDownloaderGUI()
    window.show()
    
    # Run the application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()