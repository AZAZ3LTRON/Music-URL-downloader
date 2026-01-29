import sys
import json
import time
import random
import urllib.request
import tempfile
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional, List
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

# ================== Download System Classes ==================
@dataclass
class DownloadItem:
    """Data class for download items"""
    id: str
    url: str
    filename: str
    size: int = 0
    downloaded: int = 0
    speed: float = 0.0
    status: str = "Pending"  # Pending, Downloading, Paused, Completed, Error
    error: Optional[str] = None
    start_time: Optional[float] = None
    
    @property
    def progress(self) -> float:
        """Calculate download progress percentage"""
        if self.size == 0:
            return 0
        return (self.downloaded / self.size) * 100
    
    @property
    def remaining_time(self) -> Optional[float]:
        """Calculate estimated remaining time in seconds"""
        if self.speed <= 0 or self.size <= self.downloaded:
            return None
        return (self.size - self.downloaded) / self.speed

class DownloadWorker(QObject):
    """Worker thread for downloading files"""
    progress_updated = Signal(str, int, float)  # id, downloaded, speed
    download_completed = Signal(str)
    download_error = Signal(str, str)
    
    def __init__(self, download_item: DownloadItem):
        super().__init__()
        self.download_item = download_item
        self._is_paused = False
        self._is_cancelled = False
        
    def download(self):
        """Main download method"""
        try:
            self.download_item.status = "Downloading"
            self.download_item.start_time = time.time()
            
            # Create request with headers
            req = urllib.request.Request(
                self.download_item.url,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            
            # Open connection
            with urllib.request.urlopen(req) as response:
                # Get file size
                self.download_item.size = int(response.headers.get('Content-Length', 0))
                
                # Create download directory if it doesn't exist
                os.makedirs("downloads", exist_ok=True)
                filepath = os.path.join("downloads", self.download_item.filename)
                
                # Download file in chunks
                chunk_size = 8192  # 8KB chunks
                last_update_time = time.time()
                downloaded_since_update = 0
                
                with open(filepath, 'wb') as file:
                    while True:
                        if self._is_cancelled:
                            os.remove(filepath)
                            return
                            
                        if self._is_paused:
                            time.sleep(0.1)
                            continue
                            
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                            
                        file.write(chunk)
                        self.download_item.downloaded += len(chunk)
                        downloaded_since_update += len(chunk)
                        
                        # Calculate and emit speed every 0.5 seconds
                        current_time = time.time()
                        if current_time - last_update_time >= 0.5:
                            elapsed = current_time - last_update_time
                            self.download_item.speed = downloaded_since_update / elapsed
                            
                            self.progress_updated.emit(
                                self.download_item.id,
                                self.download_item.downloaded,
                                self.download_item.speed
                            )
                            
                            last_update_time = current_time
                            downloaded_since_update = 0
                
                # Download completed successfully
                self.download_completed.emit(self.download_item.id)
                
        except Exception as e:
            self.download_error.emit(self.download_item.id, str(e))
    
    def pause(self):
        """Pause the download"""
        self._is_paused = True
        
    def resume(self):
        """Resume the download"""
        self._is_paused = False
        
    def cancel(self):
        """Cancel the download"""
        self._is_cancelled = True

class DownloadItemWidget(QWidget):
    """Widget for displaying individual download items"""
    
    def __init__(self, download_item: DownloadItem):
        super().__init__()
        self.download_item = download_item
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Top row: Filename and status
        top_layout = QHBoxLayout()
        
        # File icon and name
        file_info_layout = QHBoxLayout()
        file_icon = QLabel()
        file_icon.setPixmap(self.create_file_icon().scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        file_info_layout.addWidget(file_icon)
        
        self.filename_label = QLabel(self.download_item.filename)
        self.filename_label.setStyleSheet("font-weight: bold; color: #ffffff;")
        file_info_layout.addWidget(self.filename_label)
        
        file_info_layout.addStretch()
        top_layout.addLayout(file_info_layout)
        
        # Status label
        self.status_label = QLabel(self.download_item.status)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 12px;
                padding: 2px 8px;
                border-radius: 10px;
                background-color: #3a3a3a;
            }
        """)
        top_layout.addWidget(self.status_label)
        
        layout.addLayout(top_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 6px;
                text-align: center;
                background-color: #2d2d2d;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #0078d7;
                border-radius: 5px;
            }
        """)
        
        # Set initial progress
        self.progress_bar.setValue(int(self.download_item.progress))
        
        # Custom progress text
        self.update_progress_text()
        
        layout.addWidget(self.progress_bar)
        
        # Bottom row: Speed and details
        bottom_layout = QHBoxLayout()
        
        # Speed indicator
        speed_layout = QHBoxLayout()
        speed_icon = QLabel()
        speed_icon.setPixmap(self.create_speed_icon().scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        speed_layout.addWidget(speed_icon)
        
        self.speed_label = QLabel("0 B/s")
        self.speed_label.setStyleSheet("color: #888888; font-size: 11px;")
        speed_layout.addWidget(self.speed_label)
        bottom_layout.addLayout(speed_layout)
        
        # Size and remaining time
        details_layout = QHBoxLayout()
        
        self.size_label = QLabel(self.format_size(self.download_item.downloaded))
        self.size_label.setStyleSheet("color: #888888; font-size: 11px;")
        details_layout.addWidget(self.size_label)
        
        details_layout.addWidget(QLabel("•"))
        
        self.time_label = QLabel("Estimating...")
        self.time_label.setStyleSheet("color: #888888; font-size: 11px;")
        details_layout.addWidget(self.time_label)
        
        bottom_layout.addLayout(details_layout)
        
        bottom_layout.addStretch()
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)
        
        self.pause_btn = QPushButton("⏸")
        self.pause_btn.setFixedSize(28, 28)
        self.pause_btn.setStyleSheet(self.get_button_style("#ffb900"))
        self.pause_btn.setToolTip("Pause download")
        
        self.cancel_btn = QPushButton("✕")
        self.cancel_btn.setFixedSize(28, 28)
        self.cancel_btn.setStyleSheet(self.get_button_style("#d13438"))
        self.cancel_btn.setToolTip("Cancel download")
        
        button_layout.addWidget(self.pause_btn)
        button_layout.addWidget(self.cancel_btn)
        
        bottom_layout.addLayout(button_layout)
        
        layout.addLayout(bottom_layout)
        
        self.setLayout(layout)
        
        # Set widget background
        self.setStyleSheet("""
            QWidget {
                background-color: #252525;
                border-radius: 8px;
                border: 1px solid #333;
            }
        """)
        
        # Set fixed height
        self.setFixedHeight(120)
        
    def get_button_style(self, color):
        """Get style sheet for action buttons"""
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {color}cc;
            }}
            QPushButton:pressed {{
                background-color: {color}99;
            }}
        """
        
    def create_file_icon(self):
        """Create a file icon"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw file shape
        painter.setBrush(QColor(66, 133, 244))
        painter.setPen(QPen(QColor(30, 30, 30), 1))
        
        # File body
        painter.drawRoundedRect(4, 2, 24, 26, 2, 2)
        
        # File tab
        painter.drawRect(4, 2, 8, 6)
        painter.drawRect(12, 2, 16, 2)
        
        painter.end()
        return pixmap
        
    def create_speed_icon(self):
        """Create a speedometer icon"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw speedometer
        painter.setPen(QPen(QColor(100, 100, 100), 2))
        painter.drawArc(4, 4, 24, 24, 30 * 16, 120 * 16)
        
        # Draw needle
        painter.setPen(QPen(QColor(66, 133, 244), 2))
        center_x, center_y = 16, 16
        painter.drawLine(center_x, center_y, center_x + 8, center_y - 8)
        
        painter.end()
        return pixmap
        
    def format_size(self, size_bytes):
        """Format bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
        
    def format_time(self, seconds):
        """Format seconds to human readable time"""
        if seconds is None:
            return "--:--"
        
        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}:{seconds % 60:02d}"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}:{minutes:02d}:{seconds % 60:02d}"
        
    def update_progress(self, downloaded: int, speed: float):
        """Update progress display"""
        self.download_item.downloaded = downloaded
        self.download_item.speed = speed
        
        # Update progress bar
        self.progress_bar.setValue(int(self.download_item.progress))
        
        # Update labels
        self.update_progress_text()
        self.speed_label.setText(f"{self.format_size(speed)}/s")
        self.size_label.setText(f"{self.format_size(downloaded)} / {self.format_size(self.download_item.size)}")
        
        # Update time estimate
        if self.download_item.remaining_time:
            self.time_label.setText(f"{self.format_time(self.download_item.remaining_time)} remaining")
        else:
            self.time_label.setText("Calculating...")
            
    def update_progress_text(self):
        """Update the progress bar text"""
        progress_text = f"{self.download_item.progress:.1f}%"
        if self.download_item.size > 0:
            progress_text += f" ({self.format_size(self.download_item.downloaded)} / {self.format_size(self.download_item.size)})"
        self.progress_bar.setFormat(progress_text)
        
    def update_status(self, status: str):
        """Update download status"""
        self.download_item.status = status
        self.status_label.setText(status)
        
        # Update status color
        colors = {
            "Downloading": "#107c10",
            "Paused": "#ffb900",
            "Completed": "#107c10",
            "Error": "#d13438",
            "Pending": "#888888"
        }
        
        color = colors.get(status, "#888888")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: 12px;
                padding: 2px 8px;
                border-radius: 10px;
                background-color: {color};
            }}
        """)

# ================== Page Classes ==================
class PageWidget(QWidget):
    """Base class for all pages"""
    def __init__(self, page_name):
        super().__init__()
        self.page_name = page_name
        self.setup_ui()
    
    def setup_ui(self):
        """Implemented by subclasses"""
        pass

# The Page for the simple download
class DownloadPage(PageWidget):
    def __init__(self):
        super().__init__("Download")
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("Simple Download Manager")
        title_label.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Create download manager instance
        self.download_manager = SimpleDownloadManager()
        layout.addWidget(self.download_manager)
        
        self.setLayout(layout)

class SimpleDownloadManager(QWidget):
    """Simplified download manager for the DownloadPage"""
    
    def __init__(self):
        super().__init__()
        self.downloads: List[DownloadItem] = []
        self.workers: dict[str, DownloadWorker] = {}
        self.threads: dict[str, QThread] = {}
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # URL input section
        url_frame = QFrame()
        url_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 10px;
                border: 1px solid #444444;
            }
        """)
        
        url_layout = QVBoxLayout()
        url_layout.setContentsMargins(20, 15, 20, 15)
        
        # URL input
        url_input_layout = QHBoxLayout()
        url_label = QLabel("Enter URL:")
        url_label.setStyleSheet("color: #cccccc; font-weight: bold;")
        url_input_layout.addWidget(url_label)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/file.mp3")
        self.url_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e;
                color: white;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #0078d7;
            }
        """)
        url_input_layout.addWidget(self.url_input, 1)
        
        # Add sample button
        sample_btn = QPushButton("📋")
        sample_btn.setToolTip("Insert sample URL")
        sample_btn.setFixedSize(40, 40)
        sample_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d7;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #1088e7;
            }
        """)
        sample_btn.clicked.connect(self.insert_sample_url)
        url_input_layout.addWidget(sample_btn)
        
        url_layout.addLayout(url_input_layout)
        
        # Download button
        download_btn = QPushButton("Start Download")
        download_btn.setStyleSheet("""
            QPushButton {
                background-color: #107c10;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 12px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #128c12;
            }
            QPushButton:pressed {
                background-color: #0e6c0e;
            }
        """)
        download_btn.clicked.connect(self.start_download)
        url_layout.addWidget(download_btn)
        
        url_frame.setLayout(url_layout)
        layout.addWidget(url_frame)
        
        # Active downloads section
        downloads_label = QLabel("Active Downloads")
        downloads_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 18px;
                font-weight: bold;
            }
        """)
        layout.addWidget(downloads_label)
        
        # Scroll area for downloads
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        
        # Container for download widgets
        self.downloads_container = QWidget()
        self.downloads_layout = QVBoxLayout()
        self.downloads_layout.setSpacing(10)
        self.downloads_layout.setContentsMargins(0, 0, 0, 0)
        self.downloads_layout.addStretch()  # Add stretch to push items to top
        
        self.downloads_container.setLayout(self.downloads_layout)
        self.scroll_area.setWidget(self.downloads_container)
        
        layout.addWidget(self.scroll_area, 1)
        
        self.setLayout(layout)
        
    def insert_sample_url(self):
        """Insert a sample download URL"""
        sample_urls = [
            "https://download.samplelib.com/mp4/sample-5s.mp4",
            "https://file-examples.com/storage/fef1706276640fa2f99d5cd/2017/11/file_example_MP3_1MG.mp3",
            "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
        ]
        self.url_input.setText(random.choice(sample_urls))
        
    def start_download(self):
        """Start a new download"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Warning", "Please enter a download URL")
            return
            
        # Extract filename from URL
        filename = os.path.basename(url)
        if not filename:
            filename = f"download_{int(time.time())}.mp3"
        
        # Create download item
        download_id = f"dl_{int(time.time())}_{random.randint(1000, 9999)}"
        download_item = DownloadItem(
            id=download_id,
            url=url,
            filename=filename
        )
        
        # Add to downloads list
        self.downloads.append(download_item)
        
        # Create and add widget
        widget = DownloadItemWidget(download_item)
        self.downloads_layout.insertWidget(0, widget)
        
        # Connect widget buttons
        widget.pause_btn.clicked.connect(lambda: self.toggle_download(download_id))
        widget.cancel_btn.clicked.connect(lambda: self.cancel_download(download_id))
        
        # Start download in thread
        self.start_download_thread(download_item)
        
        # Clear URL input
        self.url_input.clear()
        
    def start_download_thread(self, download_item: DownloadItem):
        """Start download in a separate thread"""
        # Create worker and thread
        worker = DownloadWorker(download_item)
        thread = QThread()
        
        # Move worker to thread
        worker.moveToThread(thread)
        
        # Connect signals
        thread.started.connect(worker.download)
        worker.progress_updated.connect(self.on_download_progress)
        worker.download_completed.connect(self.on_download_completed)
        worker.download_error.connect(self.on_download_error)
        
        # Clean up thread when done
        worker.download_completed.connect(thread.quit)
        worker.download_error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        
        # Store references
        self.workers[download_item.id] = worker
        self.threads[download_item.id] = thread
        
        # Start thread
        thread.start()
        
    def on_download_progress(self, download_id: str, downloaded: int, speed: float):
        """Handle download progress updates"""
        widget = self.find_widget_by_id(download_id)
        if widget:
            widget.update_progress(downloaded, speed)
            widget.update_status("Downloading")
            
    def on_download_completed(self, download_id: str):
        """Handle download completion"""
        widget = self.find_widget_by_id(download_id)
        if widget:
            widget.update_status("Completed")
            widget.pause_btn.setEnabled(False)
            widget.cancel_btn.setEnabled(False)
            
    def on_download_error(self, download_id: str, error: str):
        """Handle download error"""
        widget = self.find_widget_by_id(download_id)
        if widget:
            widget.update_status("Error")
            widget.time_label.setText(f"Error: {error[:30]}...")
            
    def find_widget_by_id(self, download_id: str) -> Optional[DownloadItemWidget]:
        """Find a widget by download ID"""
        for i in range(self.downloads_layout.count()):
            item = self.downloads_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if hasattr(widget, 'download_item') and widget.download_item.id == download_id:
                    return widget
        return None
        
    def toggle_download(self, download_id: str):
        """Toggle pause/resume for a download"""
        worker = self.workers.get(download_id)
        widget = self.find_widget_by_id(download_id)
        
        if worker and widget:
            if widget.download_item.status == "Paused":
                worker.resume()
                widget.update_status("Downloading")
            else:
                worker.pause()
                widget.update_status("Paused")
                
    def cancel_download(self, download_id: str):
        """Cancel a download"""
        worker = self.workers.get(download_id)
        if worker:
            worker.cancel()
            
        widget = self.find_widget_by_id(download_id)
        if widget:
            widget.update_status("Cancelled")

# A page for massive downloads
class BatchDownloadPage(PageWidget):
    def __init__(self):
        super().__init__("Batch Download")
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        label = QLabel("Batch Download Page - Coming Soon")
        label.setStyleSheet("color: white; font-size: 24px;")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        self.setLayout(layout)

# A page for the settings of the app
class SettingsPage(PageWidget):
    def __init__(self):
        super().__init__("Settings")
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        label = QLabel("Settings Page - Coming Soon")
        label.setStyleSheet("color: white; font-size: 24px;")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        self.setLayout(layout)

# A Page to see the logs of the app
class LogsPage(PageWidget):
    def __init__(self):
        super().__init__("Logs")
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        label = QLabel("Logs Page - Coming Soon")
        label.setStyleSheet("color: white; font-size: 24px;")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        self.setLayout(layout)

# A page to see the application's info
class InfoPage(PageWidget):
    def __init__(self):
        super().__init__("Info")
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        label = QLabel("Info Page - Coming Soon")
        label.setStyleSheet("color: white; font-size: 24px;")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        self.setLayout(layout)

# ================================== Sidebar Classes ===========================================
class ImageButton(QPushButton):
    """Custom button that displays an image with hover effects, works with Sidebar class"""
    def __init__(self, image_path, text="", parent=None):
        super().__init__(parent)
        self.button_name = text
        self.is_selected = False  # Track selection state
        
        # Load and scale the image if it exists
        if os.path.exists(image_path):
            self.icon = QIcon(image_path)
        else:
            # Create a fallback icon if image doesn't exist
            pixmap = QPixmap(40, 40)
            pixmap.fill(QColor("#444444"))
            painter = QPainter(pixmap)
            painter.setPen(QColor("white"))
            painter.setFont(QFont("Arial", 16))
            painter.drawText(pixmap.rect(), Qt.AlignCenter, text[0] if text else "?")
            painter.end()
            self.icon = QIcon(pixmap)
            
        self.setIcon(self.icon)
        self.setIconSize(QSize(40, 40))
        
        # Button styling
        self.setFixedSize(70, 70)
        self.setCursor(Qt.PointingHandCursor)
        
        # Tooltip
        self.setToolTip(text)
        
        # Initial style
        self.update_style()
    
    def update_style(self):
        """Update button style based on selection state"""
        if self.is_selected:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #4a4a4a;
                    border: 1px solid #6a6a6a;
                    border-radius: 8px;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #5a5a5a;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #2d2d2d;
                    border: none;
                    border-radius: 8px;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #3a3a3a;
                    border: 1px solid #5a5a6a;
                }
            """)
    
    def set_selected(self, selected):
        """Set the selection state of the button"""
        self.is_selected = selected
        self.update_style()

class Sidebar(QWidget):
    """Main sidebar widget containing image buttons"""
    buttonClicked = Signal(str)  # Signal to notify which sidebar button was clicked
    
    def __init__(self):
        super().__init__()
        self.buttons = {}  # Dictionary to store buttons by name
        self.current_button = None
        self.setup_ui()
        self.load_sample_images()
        
    def setup_ui(self):
        # Sidebar Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(15)
        
        title_label = self.image_title()
        layout.addWidget(title_label)
        
        # Button 1: Download
        self.download_btn = ImageButton(self.get_image_path("download"), "Download")
        self.download_btn.clicked.connect(lambda: self.on_button_clicked("Download"))
        self.buttons["Download"] = self.download_btn
        layout.addWidget(self.download_btn)
        
        # Button 2: Batch Download
        self.batch_download_btn = ImageButton(self.get_image_path("batch_download"), "Batch Download")
        self.batch_download_btn.clicked.connect(lambda: self.on_button_clicked("Batch Download"))
        self.buttons["Batch Download"] = self.batch_download_btn
        layout.addWidget(self.batch_download_btn)
        
        # Button 3: Settings
        self.settings_btn = ImageButton(self.get_image_path("settings"), "Settings")
        self.settings_btn.clicked.connect(lambda: self.on_button_clicked("Settings"))
        self.buttons["Settings"] = self.settings_btn
        layout.addWidget(self.settings_btn)
        
        # Button 4: Theme Change Button
        self.theme_btn = ImageButton(self.get_image_path("theme"), "Theme")
        self.theme_btn.clicked.connect(lambda: self.on_button_clicked("Theme"))
        self.buttons["Theme"] = self.theme_btn
        layout.addWidget(self.theme_btn)

        # Button 5: Logs Button
        self.log_btn = ImageButton(self.get_image_path("log"), "Log")
        self.log_btn.clicked.connect(lambda: self.on_button_clicked("Log"))
        self.buttons["Log"] = self.log_btn
        layout.addWidget(self.log_btn)
        
        # Add stretch to push buttons to the top
        layout.addStretch()
        
        # Button 6: Info Button
        self.info_btn = ImageButton(self.get_image_path("info"), "Info")
        self.info_btn.clicked.connect(lambda: self.on_button_clicked("Info"))
        self.buttons["Info"] = self.info_btn
        layout.addWidget(self.info_btn)
        
        self.setLayout(layout)
        
        self.setStyleSheet("""
            QWidget {
                background-color: #2D2D2D;
            }
        """)
        
        # Set initial selection
        self.select_button("Download")
    
    def get_image_path(self, image_name):
        """Helper method to get image path from assets folder"""
        # Hardcoded base path
        base_path = r"C:\Users\Ayomide Ajimuda\Documents\Projects\Personal\Music-URL-downloader\assets"
        
        # Map the requested image_name to the correct filename
        if image_name == "download":
            filename = "download_icon.png"
        elif image_name == "batch_download":
            filename = "batch_download_icon.png"
        elif image_name == "settings":
            filename = "settings_icon.png"
        elif image_name == "theme":
            filename = "theme_icon.png"
        elif image_name == "log":
            filename = "log_icon.png"
        elif image_name == "info":
            filename = "info_icon.png"
        elif image_name == "main":
            filename = "main_icon.png"
        else:
            filename = f"{image_name}_icon.png"
        
        full_path = os.path.join(base_path, filename)
        
        if os.path.exists(full_path):
            return full_path
        
        print(f"Warning: Image not found for {image_name} at {full_path}")
        
        # Return a default path even if it doesn't exist
        return full_path
    
    def load_sample_images(self):
        """Alternative method to download sample icons from the web if local files don't exist"""
        try:
            # Sample icon URLs (using placeholder images from a public CDN)
            icon_urls = {
                "download": "https://cdn-icons-png.flaticon.com/512/3588/3588778.png",
                "batch_download": "https://cdn-icons-png.flaticon.com/512/3588/3588792.png",
                "settings": "https://cdn-icons-png.flaticon.com/512/3588/3588788.png",
                "theme": "https://cdn-icons-png.flaticon.com/512/3588/3588774.png",
                "log": "https://cdn-icons-png.flaticon.com/512/3588/3588772.png",
                "info": "https://cdn-icons-png.flaticon.com/512/3588/3588768.png"
            }
            
            # Set button image icons
            for btn_type, url in icon_urls.items():
                temp_dir = tempfile.gettempdir()
                image_path = os.path.join(temp_dir, f"sidebar_{btn_type}_web.png")
                
                # Download if not already downloaded AND local file doesn't exist
                local_path = self.get_image_path(btn_type)
                if not os.path.exists(local_path):
                    try:
                        urllib.request.urlretrieve(url, image_path)
                        print(f"Downloaded {btn_type} icon from web")
                        
                        # Update button icon if download successful
                        icon = QIcon(image_path)
                        if btn_type == "download":
                            self.download_btn.setIcon(icon)
                        elif btn_type == "batch_download":
                            self.batch_download_btn.setIcon(icon)
                        elif btn_type == "settings":
                            self.settings_btn.setIcon(icon)
                        elif btn_type == "theme":
                            self.theme_btn.setIcon(icon)
                        elif btn_type == "log":
                            self.log_btn.setIcon(icon)
                        elif btn_type == "info":
                            self.info_btn.setIcon(icon)
                    except Exception as download_error:
                        print(f"Could not download {btn_type} icon: {download_error}")
                        
        except Exception as e:
            print(f"Could not download web icons: {e}. Using fallback icons instead.")

    def on_button_clicked(self, button_name):
        """Handle button click events"""
        print(f"{button_name} button clicked")
        
        # Update button selection
        self.select_button(button_name)
        
        # Emit the buttonClicked signal
        self.buttonClicked.emit(button_name)
    
    def select_button(self, button_name):
        """Select a button and deselect others"""
        # Deselect all buttons
        for name, btn in self.buttons.items():
            btn.set_selected(False)
        
        # Select the clicked button
        if button_name in self.buttons:
            self.buttons[button_name].set_selected(True)
            self.current_button = button_name
    
    def image_title(self):
        """Create image title for sidebar"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # 1. Image/Icon
        icon_label = QLabel()
        
        # Try to load the image
        icon_path = self.get_image_path("main")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            # Scale the pixmap if needed
            if not pixmap.isNull():
                pixmap = pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            else:
                # Create fallback pixmap
                pixmap = QPixmap(32, 32)
                pixmap.fill(QColor("#444444"))
        else:
            # Create a simple icon if image doesn't exist
            pixmap = QPixmap(32, 32)
            pixmap.fill(QColor("#444444"))
        
        icon_label.setPixmap(pixmap)
        layout.addWidget(icon_label)
        
        # 2. Title text
        title_label = QLabel("Yt DLP")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        layout.addWidget(title_label)
        
        layout.addStretch()
        widget.setLayout(layout)
        
        # Style the title widget
        widget.setStyleSheet("""
            QWidget {
                background-color: #252525;
                padding: 10px;
                border-bottom: 1px solid #444;
            }
        """)
        widget.setFixedHeight(60)
        
        return widget

# ================== Main Window ======================
class MainWindow(QMainWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Music URL Downloader - Youtube Version")
        self.setGeometry(100, 100, 900, 600)
        
        # Initialize pages
        self.pages = {
            "Download": DownloadPage(),
            "Batch Download": BatchDownloadPage(),
            "Settings": SettingsPage(),
            "Theme": SettingsPage(),  # Reusing settings for now
            "Log": LogsPage(),
            "Info": InfoPage()
        }
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create and add sidebar
        self.sidebar = Sidebar()
        self.sidebar.setFixedWidth(100)
        main_layout.addWidget(self.sidebar)
        
        # Create stacked widget for pages
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
            }
        """)
        
        # Add all pages to stacked widget
        for page_name, page_widget in self.pages.items():
            self.stacked_widget.addWidget(page_widget)
        
        main_layout.addWidget(self.stacked_widget)
        
        central_widget.setLayout(main_layout)
        
        # Connect sidebar button clicks to switch pages
        self.sidebar.buttonClicked.connect(self.switch_page)
        
        # Set initial page
        self.switch_page("Download")
        
    def switch_page(self, page_name):
        """Switch to the requested page"""
        # Map button names to page names
        page_mapping = {
            "Download": "Download",
            "Batch Download": "Batch Download",
            "Settings": "Settings",
            "Theme": "Theme",
            "Log": "Log",
            "Info": "Info"
        }
        
        target_page = page_mapping.get(page_name, "Download")
        
        if target_page in self.pages:
            self.stacked_widget.setCurrentWidget(self.pages[target_page])
            print(f"Switched to {target_page} page")
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Use Fusion style for better dark theme support
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())