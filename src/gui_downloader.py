"""
Spotifyte - Modern Spotify Downloader GUI
Based on the design mockup with sidebar navigation
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                             QTextEdit, QFileDialog, QMessageBox, QFrame, QGroupBox,
                             QCheckBox, QComboBox, QSpinBox, QProgressBar, QTabWidget,
                             QScrollArea)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

# Import your Downloader class
from interactive_downloader import Downloader

# Setup debug logging
os.makedirs("../logs", exist_ok=True)
debug_logger = logging.getLogger("Spotifyte_Debug")
debug_logger.setLevel(logging.DEBUG)

debug_handler = logging.FileHandler("../logs/gui_debug.log", encoding="utf-8")
debug_handler.setLevel(logging.DEBUG)
debug_format = logging.Formatter("%(asctime)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s")
debug_handler.setFormatter(debug_format)
debug_logger.addHandler(debug_handler)


class DownloadThread(QThread):
    """Thread for running download operations without freezing the GUI"""
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, downloader, url, output_dir, bitrate, audio_format):
        super().__init__()
        self.downloader = downloader
        self.url = url
        self.output_dir = output_dir
        self.bitrate = bitrate
        self.audio_format = audio_format
        
    def run(self):
        try:
            # Create output directory
            output_path = Path(self.output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Configure downloader
            self.downloader._Downloader__bitrate = self.bitrate
            self.downloader._Downloader__audio_format = self.audio_format
            self.downloader._Downloader__output_dir = output_path
            
            self.update_signal.emit(f"Starting download...\nURL: {self.url}")
            
            # Determine download type
            if "playlist" in self.url.lower():
                output_template = str(Path(self.output_dir) / "{playlist}/{title}.{output-ext}")
                result = self.downloader.run_download(
                    self.url, 
                    output_template,
                    ["--playlist-numbering", "--playlist-retain-track-cover"]
                )
            elif "album" in self.url.lower():
                output_template = str(Path(self.output_dir) / "{artist}/{album}/{title}.{output-ext}")
                result = self.downloader.run_download(self.url, output_template)
            else:
                output_template = str(Path(self.output_dir) / "{artist} - {title}.{output-ext}")
                result = self.downloader.run_download(self.url, output_template)
                
            # Check result
            if hasattr(result, 'returncode'):
                if result.returncode == 0:
                    self.update_signal.emit("✅ Download completed successfully!")
                    self.finished_signal.emit(True, "Download successful")
                else:
                    self.update_signal.emit(f"❌ Download failed")
                    self.finished_signal.emit(False, "Download failed")
            else:
                self.update_signal.emit("❌ Download failed")
                self.finished_signal.emit(False, "Download failed")
                
        except Exception as e:
            self.update_signal.emit(f"❌ Error: {str(e)}")
            self.finished_signal.emit(False, str(e))

class Spotifyte(QMainWindow):
    def __init__(self):
        super().__init__()
        self.downloader = Downloader()
        self.download_thread = None
        self.batch_thread = None
        self.current_page = "download"
        self.dark_mode = True  # Start with dark mode
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Spotifyte")
        self.setGeometry(100, 100, 1200, 750)
        self.setStyleSheet(self.get_stylesheet())
        
        # Main container
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # Main layout
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # LEFT SIDEBAR
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)
        
        # RIGHT CONTENT AREA with header
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        # Header with theme toggle
        header = self.create_header()
        right_layout.addWidget(header)
        
        # Content area
        content = self.create_content()
        right_layout.addWidget(content, 1)
        
        right_container = QWidget()
        right_container.setLayout(right_layout)
        main_layout.addWidget(right_container, 1)
        
    def create_header(self):
        """Create header with theme toggle"""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #282828;
                border-bottom: 1px solid #404040;
            }
        """)
        header.setFixedHeight(60)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(10)
        
        # Spacer on the left
        layout.addStretch()
        
        # Theme toggle button
        self.theme_btn = QPushButton("🌙 Dark")
        self.theme_btn.setFixedWidth(120)
        self.theme_btn.setStyleSheet("""
            QPushButton {
                background-color: #1DB954;
                color: #000;
                border: none;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
            QPushButton:pressed {
                background-color: #1aa34a;
            }
        """)
        self.theme_btn.clicked.connect(self.toggle_theme)
        layout.addWidget(self.theme_btn)
        
        return header
        
    def toggle_theme(self):
        """Toggle between light and dark theme"""
        self.dark_mode = not self.dark_mode
        
        # Update main stylesheet
        self.setStyleSheet(self.get_stylesheet())
        
        # Update button text and styling
        if self.dark_mode:
            self.theme_btn.setText("🌙 Dark")
            header_bg = "#282828"
            header_border = "#404040"
            sidebar_bg = "#121212"
            content_bg = "#181818"
            log_bg = "#121212"
            log_text = "#1DB954"
            input_bg = "#404040"
            input_text = "#ffffff"
            input_border = "#505050"
            section_bg = "#282828"
            label_text = "#b3b3b3"
            section_label = "#1DB954"
            preview_bg = "#404040"
            preview_text = "#b3b3b3"
            preview_border = "#505050"
        else:
            self.theme_btn.setText("☀️ Light")
            header_bg = "#f5f5f5"
            header_border = "#e0e0e0"
            sidebar_bg = "#f5f5f5"
            content_bg = "#ffffff"
            log_bg = "#f9f9f9"
            log_text = "#333"
            input_bg = "#f5f5f5"
            input_text = "#000"
            input_border = "#d0d0d0"
            section_bg = "#f9f9f9"
            label_text = "#666"
            section_label = "#1DB954"
            preview_bg = "#f5f5f5"
            preview_text = "#333"
            preview_border = "#d0d0d0"
        
        # Update header
        header = self.findChild(QFrame, "header")
        if header is None:
            # Find the header frame by looking for the theme button parent
            for frame in self.findChildren(QFrame):
                if self.theme_btn in frame.findChildren(QPushButton):
                    header = frame
                    break
        
        if header:
            header.setStyleSheet(f"""
                QFrame {{
                    background-color: {header_bg};
                    border-bottom: 1px solid {header_border};
                }}
            """)
        
        # Update sidebar
        for frame in self.findChildren(QFrame):
            # Find sidebar frame (has nav buttons)
            if any(btn in frame.findChildren(QPushButton) for btn in self.nav_buttons.values()):
                if self.dark_mode:
                    frame.setStyleSheet("""
                        QFrame {
                            background-color: #121212;
                            border-right: 1px solid #282828;
                        }
                    """)
                else:
                    frame.setStyleSheet("""
                        QFrame {
                            background-color: #f5f5f5;
                            border-right: 1px solid #e0e0e0;
                        }
                    """)
                break
        
        # Update main content area background
        if hasattr(self, 'content') and self.content:
            if self.dark_mode:
                self.content.setStyleSheet("QFrame { background-color: #181818; }")
            else:
                self.content.setStyleSheet("QFrame { background-color: #ffffff; }")
        
        # Update content frame backgrounds
        for frame in self.findChildren(QFrame):
            frame_style = frame.styleSheet()
            if "border-radius: 10px" in frame_style:  # Content frames
                if self.dark_mode:
                    frame.setStyleSheet(f"background-color: {section_bg}; border-radius: 10px; padding: 20px;")
                else:
                    frame.setStyleSheet(f"background-color: {section_bg}; border-radius: 10px; padding: 20px; border: 1px solid #e0e0e0;")
        
        # Update all QLineEdit styles
        for line_edit in self.findChildren(QLineEdit):
            line_edit.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {input_bg};
                    color: {input_text};
                    border: 1px solid {input_border};
                    border-radius: 8px;
                    padding: 15px 20px;
                    font-size: 14px;
                    min-width: 300px;
                }}
                QLineEdit:focus {{
                    background-color: {input_bg};
                    border: 1px solid #1DB954;
                }}
            """)
        
        # Update all QTextEdit styles
        for text_edit in self.findChildren(QTextEdit):
            text_style = text_edit.styleSheet()
            if "Courier" in text_style or "monospace" in text_style:
                # Log output areas
                text_edit.setStyleSheet(f"""
                    QTextEdit {{
                        background-color: {log_bg};
                        color: {log_text};
                        border: 1px solid {input_border};
                        border-radius: 8px;
                        padding: 10px;
                        font-family: Courier;
                        font-size: 11px;
                    }}
                """)
            else:
                # Regular text areas (file preview, etc)
                text_edit.setStyleSheet(f"""
                    QTextEdit {{
                        background-color: {preview_bg};
                        color: {preview_text};
                        border: 1px solid {preview_border};
                        border-radius: 5px;
                        padding: 8px;
                        font-size: 11px;
                    }}
                """)
        
        # Update all QLabel colors
        for label in self.findChildren(QLabel):
            label_style = label.styleSheet()
            if "#1DB954" in label_style or "font-weight: bold" in label_style:
                # Section labels (keep green)
                label.setStyleSheet("color: #1DB954; font-weight: bold;")
            elif "color:" in label_style:
                # Regular labels
                label.setStyleSheet(f"color: {label_text};")
        
        # Update all ComboBox styles
        for combo in self.findChildren(QComboBox):
            combo.setStyleSheet(self.get_modern_combobox_style())
        
        # Update all QProgressBar styles
        for progress_bar in self.findChildren(QProgressBar):
            progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: {preview_bg};
                    border-radius: 5px;
                    border: 1px solid {preview_border};
                }}
                QProgressBar::chunk {{
                    background-color: #1DB954;
                }}
            """)
        
        # Update all primary buttons that are modern style
        for btn in self.findChildren(QPushButton):
            if "⬇️" in btn.text() or "📦" in btn.text() or "Browse" in btn.text():
                btn.setStyleSheet(self.get_modern_button_style("primary"))
        
    def create_sidebar(self):
        """Create left sidebar with navigation"""
        sidebar = QFrame()
        
        if self.dark_mode:
            bg_color = "#121212"
            border_color = "#282828"
        else:
            bg_color = "#f5f5f5"
            border_color = "#e0e0e0"
        
        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-right: 1px solid {border_color};
            }}
        """)
        sidebar.setMaximumWidth(100)
        sidebar.setMinimumWidth(100)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 20, 0, 20)
        layout.setSpacing(30)
        
        # Logo/Title
        logo_label = QLabel("🎵")
        logo_label.setFont(QFont("Arial", 24, QFont.Bold))
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet("color: #1DB954;")
        layout.addWidget(logo_label)
        
        # Navigation buttons (top)
        nav_items = [
            ("⬇️", "Download", "download"),
            ("📦", "Batch", "batch"),
            ("⚙️", "Settings", "settings"),
            ("📋", "Logs", "logs"),
        ]
        
        self.nav_buttons = {}
        for icon, label, page in nav_items:
            btn = self.create_nav_button(icon, label, page)
            self.nav_buttons[page] = btn
            layout.addWidget(btn)
        
        # Set Download as active by default
        self.nav_buttons["download"].setStyleSheet("""
            QPushButton {
                background-color: #1DB954;
                color: #000;
                border: none;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        
        layout.addStretch()
        
        # Help/Info button at bottom
        about_btn = self.create_nav_button("ℹ️", "About", "about")
        self.nav_buttons["about"] = about_btn
        layout.addWidget(about_btn)
        
        return sidebar
        
    def create_nav_button(self, icon, label, page):
        """Create a navigation button"""
        btn = QPushButton(f"{icon}\n{label}")
        
        if self.dark_mode:
            idle_style = """
                QPushButton {
                    background-color: transparent;
                    color: #b3b3b3;
                    border: none;
                    border-radius: 8px;
                    padding: 10px;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #282828;
                    color: #1DB954;
                }
            """
        else:
            idle_style = """
                QPushButton {
                    background-color: transparent;
                    color: #666;
                    border: none;
                    border-radius: 8px;
                    padding: 10px;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #e8e8e8;
                    color: #1DB954;
                }
            """
        
        btn.setStyleSheet(idle_style)
        btn.setMinimumHeight(70)
        btn.clicked.connect(lambda: self.switch_page(page))
        return btn
        
    def switch_page(self, page):
        """Switch between pages"""
        self.current_page = page
        
        # Update button colors
        for name, btn in self.nav_buttons.items():
            if name == page:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1DB954;
                        color: #000;
                        border: none;
                        border-radius: 8px;
                        padding: 10px;
                        font-weight: bold;
                        font-size: 12px;
                    }
                """)
            else:
                if self.dark_mode:
                    idle_style = """
                        QPushButton {
                            background-color: transparent;
                            color: #b3b3b3;
                            border: none;
                            border-radius: 8px;
                            padding: 10px;
                            font-weight: bold;
                            font-size: 11px;
                        }
                        QPushButton:hover {
                            background-color: #282828;
                            color: #1DB954;
                        }
                    """
                else:
                    idle_style = """
                        QPushButton {
                            background-color: transparent;
                            color: #666;
                            border: none;
                            border-radius: 8px;
                            padding: 10px;
                            font-weight: bold;
                            font-size: 11px;
                        }
                        QPushButton:hover {
                            background-color: #e8e8e8;
                            color: #1DB954;
                        }
                    """
                btn.setStyleSheet(idle_style)
        
        # Update content
        self.update_content()
        
    def create_content(self):
        """Create main content area"""
        self.content = QFrame()
        
        if self.dark_mode:
            bg_color = "#181818"
            text_color = "#1DB954"
            subtitle_color = "#b3b3b3"
        else:
            bg_color = "#ffffff"
            text_color = "#1DB954"
            subtitle_color = "#666"
        
        self.content.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
            }}
        """)
        
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        
        # Store layout for later updates
        self.content_layout = layout
        
        # Title
        title = QLabel("Spotifyte")
        title_font = QFont("Arial", 28, QFont.Bold)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {text_color};")
        layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("Download your favorite tracks, playlists, and albums")
        subtitle.setStyleSheet(f"color: {subtitle_color}; font-size: 14px;")
        layout.addWidget(subtitle)
        
        # Add content based on current page
        self.download_content = self.create_songs_content()
        self.batch_content = self.create_playlists_content()
        self.settings_content = self.create_settings_content()
        self.logs_content = self.create_logs_content()
        self.about_content = self.create_about_content()
        
        layout.addWidget(self.download_content)
        layout.addWidget(self.batch_content)
        layout.addWidget(self.settings_content)
        layout.addWidget(self.logs_content)
        layout.addWidget(self.about_content)
        
        # Show only download by default
        self.batch_content.hide()
        self.settings_content.hide()
        self.logs_content.hide()
        self.about_content.hide()
        
        layout.addStretch()
        
        return self.content
        
    def create_songs_content(self):
        """Create download section"""
        frame = QFrame()
        
        if self.dark_mode:
            frame.setStyleSheet("background-color: #282828; border-radius: 10px; padding: 20px;")
            input_bg = "#404040"
            input_text = "#ffffff"
            input_border = "#505050"
            focus_bg = "#505050"
            label_color = "#b3b3b3"
            log_bg = "#121212"
            log_text = "#1DB954"
        else:
            frame.setStyleSheet("background-color: #f9f9f9; border-radius: 10px; padding: 20px; border: 1px solid #e0e0e0;")
            input_bg = "#f5f5f5"
            input_text = "#000"
            input_border = "#d0d0d0"
            focus_bg = "#ffffff"
            label_color = "#666"
            log_bg = "#f9f9f9"
            log_text = "#333"
        
        layout = QVBoxLayout(frame)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Single Track Download")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setStyleSheet("color: #1DB954;")
        layout.addWidget(title)
        
        # URL Input
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter Spotify Track URL or search by song name")
        self.url_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {input_bg};
                color: {input_text};
                border: 1px solid {input_border};
                border-radius: 8px;
                padding: 15px 20px;
                font-size: 14px;
                min-width: 300px;
            }}
            QLineEdit:focus {{
                background-color: {focus_bg};
                border: 1px solid #1DB954;
            }}
        """)
        layout.addWidget(self.url_input)
        
        # Search checkbox
        self.search_checkbox = QCheckBox("Search by song name instead of URL")
        self.search_checkbox.setStyleSheet(f"color: {label_color};")
        layout.addWidget(self.search_checkbox)
        
        # Download button
        self.download_btn = QPushButton("⬇️ Download Track")
        self.download_btn.setStyleSheet(self.get_modern_button_style("primary"))
        self.download_btn.clicked.connect(self.start_single_download)
        layout.addWidget(self.download_btn)
        
        # Status/Log
        log_label = QLabel("📝 Download Log:")
        log_label.setStyleSheet("color: #1DB954; font-weight: bold;")
        layout.addWidget(log_label)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet(f"""
            QTextEdit {{
                background-color: {log_bg};
                color: {log_text};
                border: 1px solid {input_border};
                border-radius: 8px;
                padding: 10px;
                font-family: Courier;
                font-size: 11px;
            }}
        """)
        self.log_output.setMaximumHeight(250)
        layout.addWidget(self.log_output)
        
        layout.addStretch()
        return frame
        
    def create_playlists_content(self):
        """Create batch download section"""
        frame = QFrame()
        
        if self.dark_mode:
            frame.setStyleSheet("background-color: #282828; border-radius: 10px; padding: 20px;")
            input_bg = "#404040"
            input_text = "#ffffff"
            input_border = "#505050"
            focus_bg = "#505050"
            label_color = "#b3b3b3"
            preview_bg = "#404040"
            preview_text = "#b3b3b3"
            preview_border = "#505050"
            log_bg = "#121212"
            log_text = "#1DB954"
        else:
            frame.setStyleSheet("background-color: #f9f9f9; border-radius: 10px; padding: 20px; border: 1px solid #e0e0e0;")
            input_bg = "#f5f5f5"
            input_text = "#000"
            input_border = "#d0d0d0"
            focus_bg = "#ffffff"
            label_color = "#666"
            preview_bg = "#f5f5f5"
            preview_text = "#333"
            preview_border = "#d0d0d0"
            log_bg = "#f9f9f9"
            log_text = "#333"
        
        layout = QVBoxLayout(frame)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Batch Download")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setStyleSheet("color: #1DB954;")
        layout.addWidget(title)
        
        # File selection
        file_layout = QHBoxLayout()
        file_label = QLabel("Select File:")
        file_label.setStyleSheet(f"color: {label_color};")
        file_layout.addWidget(file_label)
        
        self.batch_file_input = QLineEdit()
        self.batch_file_input.setPlaceholderText("Select a text file containing URLs (one per line)")
        self.batch_file_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {input_bg};
                color: {input_text};
                border: 1px solid {input_border};
                border-radius: 5px;
                padding: 8px 12px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                background-color: {focus_bg};
                border: 1px solid #1DB954;
            }}
        """)
        file_layout.addWidget(self.batch_file_input)
        
        self.batch_browse_button = QPushButton("📁 Browse...")
        self.batch_browse_button.setStyleSheet(self.get_modern_button_style("primary"))
        self.batch_browse_button.clicked.connect(self.browse_batch_file)
        file_layout.addWidget(self.batch_browse_button)
        layout.addLayout(file_layout)
        
        # File preview
        preview_label = QLabel("File Preview:")
        preview_label.setStyleSheet("color: #1DB954; font-weight: bold;")
        layout.addWidget(preview_label)
        
        self.file_preview = QTextEdit()
        self.file_preview.setReadOnly(True)
        self.file_preview.setMaximumHeight(120)
        self.file_preview.setStyleSheet(f"""
            QTextEdit {{
                background-color: {preview_bg};
                color: {preview_text};
                border: 1px solid {preview_border};
                border-radius: 5px;
                padding: 8px;
                font-size: 11px;
            }}
        """)
        layout.addWidget(self.file_preview)
        
        # Batch settings
        settings_label = QLabel("Batch Settings:")
        settings_label.setStyleSheet("color: #1DB954; font-weight: bold;")
        layout.addWidget(settings_label)
        
        retry_layout = QHBoxLayout()
        retry_label = QLabel("Max Retries:")
        retry_label.setStyleSheet(f"color: {label_color};")
        retry_layout.addWidget(retry_label)
        self.max_retries_spin = QSpinBox()
        self.max_retries_spin.setRange(1, 10)
        self.max_retries_spin.setValue(5)
        self.max_retries_spin.setStyleSheet(self.get_stylesheet())
        retry_layout.addWidget(self.max_retries_spin)
        
        retry_layout.addSpacing(20)
        delay_label = QLabel("Retry Delay (sec):")
        delay_label.setStyleSheet(f"color: {label_color};")
        retry_layout.addWidget(delay_label)
        self.retry_delay_spin = QSpinBox()
        self.retry_delay_spin.setRange(1, 60)
        self.retry_delay_spin.setValue(20)
        self.retry_delay_spin.setStyleSheet(self.get_stylesheet())
        retry_layout.addWidget(self.retry_delay_spin)
        retry_layout.addStretch()
        layout.addLayout(retry_layout)
        
        # Download button
        self.batch_download_button = QPushButton("📦 Start Batch Download")
        self.batch_download_button.setStyleSheet(self.get_modern_button_style("primary"))
        self.batch_download_button.clicked.connect(self.start_batch_download)
        layout.addWidget(self.batch_download_button)
        
        # Progress
        progress_label = QLabel("Progress:")
        progress_label.setStyleSheet("color: #1DB954; font-weight: bold;")
        layout.addWidget(progress_label)
        
        self.batch_progress_label = QLabel("Ready")
        self.batch_progress_label.setStyleSheet(f"color: {label_color};")
        layout.addWidget(self.batch_progress_label)
        
        self.batch_progress_bar = QProgressBar()
        self.batch_progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {preview_bg};
                border-radius: 5px;
                border: 1px solid {preview_border};
            }}
            QProgressBar::chunk {{
                background-color: #1DB954;
            }}
        """)
        layout.addWidget(self.batch_progress_bar)
        
        # Console
        self.batch_console = QTextEdit()
        self.batch_console.setReadOnly(True)
        self.batch_console.setMaximumHeight(200)
        self.batch_console.setStyleSheet(f"""
            QTextEdit {{
                background-color: {log_bg};
                color: {log_text};
                border: 1px solid {input_border};
                border-radius: 8px;
                padding: 10px;
                font-family: Courier;
                font-size: 10px;
            }}
        """)
        layout.addWidget(self.batch_console)
        
        layout.addStretch()
        return frame
        
    def create_artists_content(self):
        """Create artists section"""
        frame = QFrame()
        frame.setStyleSheet("background-color: #282828; border-radius: 10px; padding: 20px;")
        
        layout = QVBoxLayout(frame)
        label = QLabel("Artists")
        label.setStyleSheet("color: #1DB954; font-size: 18px; font-weight: bold;")
        layout.addWidget(label)
        
        info = QLabel("Browse and download music by your favorite artists.")
        info.setStyleSheet("color: #b3b3b3;")
        layout.addWidget(info)
        
        return frame
        
    def create_settings_content(self):
        """Create settings section"""
        frame = QFrame()
        frame.setStyleSheet("background-color: #282828; border-radius: 10px; padding: 20px;")
        
        layout = QVBoxLayout(frame)
        
        label = QLabel("Settings")
        label.setFont(QFont("Arial", 16, QFont.Bold))
        label.setStyleSheet("color: #1DB954;")
        layout.addWidget(label)
        
        # Search bar at the top
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("🔍 Search:"))
        self.settings_search_input = QLineEdit()
        self.settings_search_input.setPlaceholderText("Search for a setting...")
        self.settings_search_input.setMaximumWidth(300)
        self.settings_search_input.setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                color: #ffffff;
                border: 1px solid #505050;
                border-radius: 5px;
                padding: 8px 12px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #1DB954;
            }
        """)
        self.settings_search_input.textChanged.connect(self.filter_settings)
        search_layout.addWidget(self.settings_search_input)
        search_layout.addStretch()
        layout.addLayout(search_layout)
        
        layout.addSpacing(15)
        
        # Download Settings
        download_settings_label = QLabel("Download Settings")
        download_settings_label.setStyleSheet("color: #1DB954; font-weight: bold;")
        layout.addWidget(download_settings_label)
        
        # Audio format
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Audio Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp3", "flac", "ogg", "opus", "m4a", "wav"])
        self.format_combo.setCurrentText("mp3")
        self.format_combo.setStyleSheet(self.get_modern_combobox_style())
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        layout.addLayout(format_layout)
        
        # Bitrate
        bitrate_layout = QHBoxLayout()
        bitrate_layout.addWidget(QLabel("Bitrate:"))
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItems(["320k", "256k", "192k", "160k", "128k", "96k", "64k"])
        self.bitrate_combo.setCurrentText("320k")
        self.bitrate_combo.setStyleSheet(self.get_modern_combobox_style())
        bitrate_layout.addWidget(self.bitrate_combo)
        bitrate_layout.addStretch()
        layout.addLayout(bitrate_layout)
        
        # Output directory
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output Dir:"))
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setText("Downloads")
        self.output_dir_input.setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                color: #ffffff;
                border: 1px solid #505050;
                border-radius: 5px;
                padding: 8px 12px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #1DB954;
            }
        """)
        output_layout.addWidget(self.output_dir_input)
        
        browse_btn = QPushButton("Browse")
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #1DB954;
                color: #000;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
        """)
        browse_btn.clicked.connect(self.browse_output_dir)
        output_layout.addWidget(browse_btn)
        layout.addLayout(output_layout)
        
        layout.addSpacing(15)
        
        # General Settings
        general_label = QLabel("General Settings")
        general_label.setStyleSheet("color: #1DB954; font-weight: bold;")
        layout.addWidget(general_label)
        
        # Temp directory
        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel("Temp Directory:"))
        self.temp_dir_input = QLineEdit()
        self.temp_dir_input.setText("Temporary")
        self.temp_dir_input.setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                color: #ffffff;
                border: 1px solid #505050;
                border-radius: 5px;
                padding: 8px 12px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #1DB954;
            }
        """)
        temp_layout.addWidget(self.temp_dir_input)
        temp_browse_button = QPushButton("Browse")
        temp_browse_button.setStyleSheet("""
            QPushButton {
                background-color: #1DB954;
                color: #000;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
        """)
        temp_browse_button.clicked.connect(lambda: self.browse_directory(self.temp_dir_input))
        temp_layout.addWidget(temp_browse_button)
        layout.addLayout(temp_layout)
        
        # Log directory
        log_layout = QHBoxLayout()
        log_layout.addWidget(QLabel("Log Directory:"))
        self.log_dir_input = QLineEdit()
        self.log_dir_input.setText("../log")
        self.log_dir_input.setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                color: #ffffff;
                border: 1px solid #505050;
                border-radius: 5px;
                padding: 8px 12px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #1DB954;
            }
        """)
        log_layout.addWidget(self.log_dir_input)
        log_browse_button = QPushButton("Browse")
        log_browse_button.setStyleSheet("""
            QPushButton {
                background-color: #1DB954;
                color: #000;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
        """)
        log_browse_button.clicked.connect(lambda: self.browse_directory(self.log_dir_input))
        log_layout.addWidget(log_browse_button)
        layout.addLayout(log_layout)
        
        layout.addSpacing(15)
        
        # spotdl settings
        spotdl_label = QLabel("spotdl Configuration")
        spotdl_label.setStyleSheet("color: #1DB954; font-weight: bold;")
        layout.addWidget(spotdl_label)
        
        self.check_spotdl_button = QPushButton("Check spotdl Installation")
        self.check_spotdl_button.setStyleSheet("""
            QPushButton {
                background-color: #1DB954;
                color: #000;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
        """)
        self.check_spotdl_button.clicked.connect(self.check_spotdl_installation)
        layout.addWidget(self.check_spotdl_button)
        
        layout.addStretch()
        return frame
        
    def create_logs_content(self):
        """Create logs section"""
        frame = QFrame()
        frame.setStyleSheet("background-color: #282828; border-radius: 10px; padding: 20px;")
        
        layout = QVBoxLayout(frame)
        
        label = QLabel("Download Logs")
        label.setFont(QFont("Arial", 16, QFont.Bold))
        label.setStyleSheet("color: #1DB954;")
        layout.addWidget(label)
        
        # Log file selection
        log_select_layout = QHBoxLayout()
        log_select_layout.addWidget(QLabel("Select Log:"))
        self.log_combo = QComboBox()
        self.log_combo.addItems(["success.log", "failed.log", "error.log"])
        self.log_combo.setStyleSheet(self.get_modern_combobox_style())
        self.log_combo.currentTextChanged.connect(self.load_log_file)
        log_select_layout.addWidget(self.log_combo)
        
        refresh_button = QPushButton("Refresh")
        refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #1DB954;
                color: #000;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
        """)
        refresh_button.clicked.connect(self.refresh_logs)
        log_select_layout.addWidget(refresh_button)
        
        clear_button = QPushButton("Clear Log")
        clear_button.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                color: #fff;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
        """)
        clear_button.clicked.connect(self.clear_log)
        log_select_layout.addWidget(clear_button)
        log_select_layout.addStretch()
        layout.addLayout(log_select_layout)
        
        # Log content
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setStyleSheet("""
            QTextEdit {
                background-color: #121212;
                color: #00ff00;
                border: 1px solid #404040;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.log_viewer)
        
        return frame
        
    def create_about_content(self):
        """Create about section"""
        frame = QFrame()
        frame.setStyleSheet("background-color: #282828; border-radius: 10px; padding: 20px;")
        
        layout = QVBoxLayout(frame)
        
        label = QLabel("About Spotifyte")
        label.setStyleSheet("color: #1DB954; font-size: 18px; font-weight: bold;")
        layout.addWidget(label)
        
        about_text = QLabel(
            "Spotifyte v1.0\n\n"
            "A modern Spotify downloader built with PyQt5\n"
            "Download your favorite tracks, playlists, and albums\n\n"
            "Project: Spotifee (GitHub)\n"
            "License: MIT"
        )
        about_text.setStyleSheet("color: #b3b3b3; line-height: 1.6;")
        layout.addWidget(about_text)
        
        layout.addStretch()
        
        return frame
        
    def update_content(self):
        """Update content visibility based on current page"""
        self.download_content.setVisible(self.current_page == "download")
        self.batch_content.setVisible(self.current_page == "batch")
        self.settings_content.setVisible(self.current_page == "settings")
        self.logs_content.setVisible(self.current_page == "logs")
        self.about_content.setVisible(self.current_page == "about")
        
    def browse_output_dir(self):
        """Browse for output directory"""
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_dir_input.setText(directory)
            
    def start_download(self):
        """Start download process"""
        url = self.url_input.text().strip()
        output_dir = self.output_dir_input.text().strip()
        
        if not url:
            QMessageBox.warning(self, "Invalid Input", "Please enter a Spotify URL or search query")
            return
            
        if not output_dir:
            output_dir = "Downloads"
            
        self.log_output.clear()
        self.download_btn.setEnabled(False)
        self.download_btn.setText("Downloading...")
        
        self.download_thread = DownloadThread(
            self.downloader,
            url,
            output_dir,
            self.bitrate_combo.currentText(),
            self.format_combo.currentText()
        )
        self.download_thread.update_signal.connect(self.log_output.append)
        self.download_thread.finished_signal.connect(self.on_download_finished)
        self.download_thread.start()
        
    def on_download_finished(self, success, message):
        """Called when download finishes"""
        self.download_btn.setEnabled(True)
        self.download_btn.setText("Download Track")
        if success:
            self.log_output.append("\n✅ Download completed successfully!")
        else:
            self.log_output.append(f"\n❌ Download failed: {message}")
    
    def start_single_download(self):
        """Start a single download (alias for start_download)"""
        self.start_download()
    
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
    
    def preview_batch_file(self, file_path):
        """Preview the contents of the batch file"""
        try:
            with open(file_path, 'r') as file:
                lines = file.readlines()[:10]
                content = ''.join(lines)
                if len(content) > 500:
                    content = content[:500] + "\n... (truncated)"
                self.file_preview.setText(content)
        except Exception as e:
            self.file_preview.setText(f"Error reading file: {str(e)}")
    
    def start_batch_download(self):
        """Start batch download from file"""
        file_path = self.batch_file_input.text()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Warning", "Please select a valid text file.")
            return
            
        output_dir = self.output_dir_input.text()
        bitrate = self.bitrate_combo.currentText()
        audio_format = self.format_combo.currentText()
        
        os.makedirs(output_dir, exist_ok=True)
        
        self.batch_download_button.setEnabled(False)
        self.batch_download_button.setText("Downloading...")
        self.batch_console.clear()
        
        self.batch_thread = BatchDownloadThread(
            self.downloader,
            file_path,
            output_dir,
            bitrate,
            audio_format,
            self.max_retries_spin.value(),
            self.retry_delay_spin.value()
        )
        
        self.batch_thread.update_signal.connect(self.update_batch_console)
        self.batch_thread.progress_signal.connect(self.update_batch_progress)
        self.batch_thread.finished_signal.connect(self.batch_download_finished)
        self.batch_thread.start()
    
    def update_batch_console(self, message, msg_type):
        """Update batch console with colored messages"""
        color_map = {
            "info": "#b3b3b3",
            "success": "#1DB954",
            "error": "#ff4444",
            "warning": "#ffaa00"
        }
        
        color = color_map.get(msg_type, "#b3b3b3")
        self.batch_console.append(f'<font color="{color}">{message}</font>')
        self.batch_console.verticalScrollBar().setValue(
            self.batch_console.verticalScrollBar().maximum()
        )
    
    def update_batch_progress(self, current, total):
        """Update batch progress bar"""
        self.batch_progress_bar.setMaximum(total)
        self.batch_progress_bar.setValue(current)
        self.batch_progress_label.setText(f"Processing {current} of {total}")
    
    def batch_download_finished(self, success_count, total_count):
        """Handle completion of batch download"""
        self.batch_download_button.setEnabled(True)
        self.batch_download_button.setText("Start Batch Download")
        
        if total_count > 0:
            self.batch_console.append(f"\n{'='*50}")
            self.batch_console.append(f'<font color="#1DB954"><b>Batch Download Complete!</b></font>')
            self.batch_console.append(f'<font color="#1DB954">Successfully downloaded: {success_count}/{total_count}</font>')
        
    def browse_directory(self, line_edit):
        """Browse for directory"""
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            line_edit.setText(directory)
    
    def filter_settings(self):
        """Filter settings based on search input"""
        # Safety check - only filter if settings_groups exists
        if not hasattr(self, 'settings_groups'):
            return
            
        try:
            search_text = self.settings_search_input.text().lower()
            
            if not search_text:
                # Show all groups if search is empty
                for group in self.settings_groups:
                    group.setVisible(True)
            else:
                # Filter based on search text
                for group in self.settings_groups:
                    group_title = group.title().lower()
                    visible = search_text in group_title
                    
                    # Also check if any text in the group matches the search
                    if not visible:
                        for widget in group.findChildren(QLabel):
                            if search_text in widget.text().lower():
                                visible = True
                                break
                    
                    group.setVisible(visible)
        except Exception as e:
            print(f"Error filtering settings: {e}")
    
    def load_log_file(self):
        """Load the selected log file"""
        log_file = self.log_combo.currentText()
        log_path = os.path.join("../log", log_file)
        
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
        log_path = os.path.join("../log", log_file)
        
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
        
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "spotdl"])
            QMessageBox.information(self, "Success", "spotdl installed successfully!")
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "Error", f"Failed to install spotdl: {str(e)}")
            
    def get_stylesheet(self):
        """Get main stylesheet based on theme"""
        if self.dark_mode:
            return """
                QMainWindow {
                    background-color: #121212;
                }
                QLineEdit, QTextEdit, QComboBox, QSpinBox {
￼
￼
 zshsrc
 pythonsrc
CHAT
FIX LIGHT THEM NOT WORKING IT ONLY ACTIVATE ON HEADER AND SIDEBAR
Reviewed GUI test file and analyzed application structure
I'll help you fix the light theme issue. Let me start by examining the GUI files to understand the current theme implementation.

Read files gui_test.py and gui_downloader.py
Let me see more of the gui_test.py file to find the theme/stylesheet implementation:

Searched for specific regex patterns
Now let me find and read the get_stylesheet method:

Searched for text in specified file
Now I can see the issue! The light theme stylesheet is being defined but only the header and sidebar have explicit inline styles. Let me find where the sidebar and header are styled, and then I'll update the stylesheet to apply the light theme to all content areas properly.

Let me read more of the gui_test.py to find the content area styling:

Read gui_test.py, lines 90 to 500

Now I understand the issue better. The content area and input fields have hardcoded dark theme colors. When light mode is enabled, these elements need to update their stylesheets. Let me create a comprehensive fix that updates all elements when the theme is switched:

Read gui_test.py, lines 500 to 800

Now I understand the full scope of the problem. The issue is that many UI elements have hardcoded dark theme styles. When light mode is activated, they don't update. I need to fix the toggle_theme() method to update all these elements. Let me make the necessary changes:

Created 2 todos

Edited
gui_test.py+110-1
Now I need to fix the light theme color scheme in the URL input area and other hardcoded dark styles. Let me update the create_songs_content method to support both themes:

Edited
gui_test.py+30-16
Now let's update the batch download content section:

Edited
gui_test.py+63-32
Now let's find and update the settings content section:

Read gui_test.py, lines 800 to 900

Let me get more of the settings 
                    font-family: Arial;
                    background-color: #404040;
                    color: #ffffff;
                    border: 1px solid #505050;
                    border-radius: 6px;
                    padding: 8px;
                }
                QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
                    border: 2px solid #1DB954;
                }
                QComboBox::drop-down {
                    border: none;
                    background-color: transparent;
                    width: 30px;
                }
                QComboBox::down-arrow {
                    image: none;
                    border: none;
                }
                QComboBox QAbstractItemView {
                    background-color: #404040;
                    color: #ffffff;
                    selection-background-color: #1DB954;
                    selection-color: #000;
                    border: 1px solid #505050;
                }
                QPushButton {
                    outline: none;
                    color: #000;
                    font-weight: bold;
                    border-radius: 6px;
                }
                QLabel {
                    color: #ffffff;
                }
                QCheckBox {
                    color: #ffffff;
                    spacing: 5px;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border: 1px solid #505050;
                    border-radius: 3px;
                    background-color: #404040;
                }
                QCheckBox::indicator:checked {
                    background-color: #1DB954;
                    border: 1px solid #1DB954;
                }
                QProgressBar {
                    background-color: #404040;
                    border-radius: 6px;
                    border: 1px solid #505050;
                    height: 10px;
                }
                QProgressBar::chunk {
                    background-color: #1DB954;
                    border-radius: 6px;
                }
            """
        else:
            return """
                QMainWindow {
                    background-color: #ffffff;
                }
                QLineEdit, QTextEdit, QComboBox, QSpinBox {
                    font-family: Arial;
                    background-color: #f5f5f5;
                    color: #000;
                    border: 1px solid #d0d0d0;
                    border-radius: 6px;
                    padding: 8px;
                }
                QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
                    border: 2px solid #1DB954;
                    background-color: #ffffff;
                }
                QComboBox::drop-down {
                    border: none;
                    background-color: transparent;
                    width: 30px;
                }
                QComboBox::down-arrow {
                    image: none;
                    border: none;
                }
                QComboBox QAbstractItemView {
                    background-color: #f5f5f5;
                    color: #000;
                    selection-background-color: #1DB954;
                    selection-color: #fff;
                    border: 1px solid #d0d0d0;
                }
                QPushButton {
                    outline: none;
                    color: #000;
                    font-weight: bold;
                    border-radius: 6px;
                }
                QLabel {
                    color: #333;
                }
                QCheckBox {
                    color: #333;
                    spacing: 5px;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border: 1px solid #d0d0d0;
                    border-radius: 3px;
                    background-color: #f5f5f5;
                }
                QCheckBox::indicator:checked {
                    background-color: #1DB954;
                    border: 1px solid #1DB954;
                }
                QProgressBar {
                    background-color: #f0f0f0;
                    border-radius: 6px;
                    border: 1px solid #d0d0d0;
                    height: 10px;
                }
                QProgressBar::chunk {
                    background-color: #1DB954;
                    border-radius: 6px;
                }
            """
    
    def get_modern_combobox_style(self):
        """Get modern ComboBox style based on theme"""
        if self.dark_mode:
            return """
                QComboBox {
                    background-color: #404040;
                    color: #ffffff;
                    border: 1px solid #505050;
                    border-radius: 6px;
                    padding: 8px;
                }
                QComboBox:focus {
                    border: 2px solid #1DB954;
                }
                QComboBox::drop-down {
                    border: none;
                    background-color: transparent;
                    width: 30px;
                }
                QComboBox QAbstractItemView {
                    background-color: #404040;
                    color: #ffffff;
                    selection-background-color: #1DB954;
                    selection-color: #000;
                    border: 1px solid #505050;
                    padding: 5px;
                }
            """
        else:
            return """
                QComboBox {
                    background-color: #f5f5f5;
                    color: #000;
                    border: 1px solid #d0d0d0;
                    border-radius: 6px;
                    padding: 8px;
                }
                QComboBox:focus {
                    border: 2px solid #1DB954;
                    background-color: #ffffff;
                }
                QComboBox::drop-down {
                    border: none;
                    background-color: transparent;
                    width: 30px;
                }
                QComboBox QAbstractItemView {
                    background-color: #f5f5f5;
                    color: #000;
                    selection-background-color: #1DB954;
                    selection-color: #fff;
                    border: 1px solid #d0d0d0;
                    padding: 5px;
                }
            """
    
    def get_modern_button_style(self, button_type="primary"):
        """Get modern button style"""
        if button_type == "primary":
            return """
                QPushButton {
                    background-color: #1DB954;
                    color: #000;
                    border: none;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #1ed760;
                }
                QPushButton:pressed {
                    background-color: #1aa34a;
                }
            """
        elif button_type == "secondary":
            if self.dark_mode:
                return """
                    QPushButton {
                        background-color: #282828;
                        color: #ffffff;
                        border: 1px solid #404040;
                        border-radius: 6px;
                        padding: 8px 15px;
                        font-weight: bold;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #404040;
                        color: #1DB954;
                    }
                """
            else:
                return """
                    QPushButton {
                        background-color: #f5f5f5;
                        color: #000;
                        border: 1px solid #d0d0d0;
                        border-radius: 6px;
                        padding: 8px 15px;
                        font-weight: bold;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #e8e8e8;
                        color: #1DB954;
                    }
                """
        elif button_type == "danger":
            return """
                QPushButton {
                    background-color: #ff4444;
                    color: #fff;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 15px;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #ff6666;
                }
            """
        
        return ""


def main():
    app = QApplication(sys.argv)
    window = Spotifyte()
    window.show()
    sys.exit(app.exec_())


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
        
        # Info label about settings
        settings_info = QLabel("📝 Configure audio format, bitrate, and output directory in the Settings tab")
        settings_info.setStyleSheet("color: #2196F3; font-style: italic; padding: 10px;")
        layout.addWidget(settings_info)
        
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
        
        # Search bar at the top
        search_group = QGroupBox("Search Settings")
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("🔍 Search:"))
        self.settings_search_input = QLineEdit()
        self.settings_search_input.setPlaceholderText("Search for a setting...")
        self.settings_search_input.setMaximumWidth(400)
        self.settings_search_input.textChanged.connect(self.filter_settings)
        search_layout.addWidget(self.settings_search_input)
        search_layout.addStretch()
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # Create a scroll area for settings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Download Settings (moved from Single Download tab)
        download_settings_group = QGroupBox("Download Settings")
        download_settings_layout = QVBoxLayout()
        
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
        
        download_settings_layout.addLayout(format_layout)
        download_settings_layout.addLayout(bitrate_layout)
        download_settings_layout.addLayout(output_layout)
        download_settings_group.setLayout(download_settings_layout)
        scroll_layout.addWidget(download_settings_group)
        
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
        self.log_dir_input.setText("../log")
        log_layout.addWidget(self.log_dir_input)
        log_browse_button = QPushButton("Browse...")
        log_browse_button.clicked.connect(lambda: self.browse_directory(self.log_dir_input))
        log_layout.addWidget(log_browse_button)
        
        general_layout.addLayout(temp_layout)
        general_layout.addLayout(log_layout)
        general_group.setLayout(general_layout)
        scroll_layout.addWidget(general_group)
        
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
        scroll_layout.addWidget(spotdl_group)
        
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
        scroll_layout.addWidget(auth_group)
        
        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # Store reference to settings groups for search filtering
        self.settings_groups = [download_settings_group, general_group, spotdl_group, auth_group]
        
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
        
    def filter_settings(self):
        """Filter settings based on search input"""
        # Safety check - only filter if settings_groups exists
        if not hasattr(self, 'settings_groups'):
            return
            
        try:
            search_text = self.settings_search_input.text().lower()
            
            if not search_text:
                # Show all groups if search is empty
                for group in self.settings_groups:
                    group.setVisible(True)
            else:
                # Filter based on search text
                for group in self.settings_groups:
                    group_title = group.title().lower()
                    visible = search_text in group_title
                    
                    # Also check if any text in the group matches the search
                    if not visible:
                        for widget in group.findChildren(QLabel):
                            if search_text in widget.text().lower():
                                visible = True
                                break
                    
                    group.setVisible(visible)
        except Exception as e:
            print(f"Error filtering settings: {e}")
        
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
        log_path = os.path.join("../log", log_file)
        
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
        log_path = os.path.join("../log", log_file)
        
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
    
    # Create and show the main window
    window = Spotifyte()
    window.show()
    
    # Run the application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()