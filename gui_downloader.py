""" 
GUI for Interactive Spotify Playlist/Album/Track Downloader 

A simple graphical interface for the interactive Downloader made previously
As usual, it requires the following packages:
    - PyQt5 
    - SpotDL
    - Previous interactive downloader
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime
from interactive_downloader import Downloader # Downloader class
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer # For core non GUI Components
from PyQt5.QtGui import QFont, QPalette, QColor # For GUI's components  
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, QTextEdit,
                             QComboBox, QFileDialog, QMessageBox, QTableWidget, QGroupBox,
                             QProgressBar, QCheckBox, QSpinBox, QDoubleSpinBox, QListWidget,
                             QListWidgetItem, QSplitter, QFrame, QSizePolicy)

"""CONFIG (Subject to change)"""
MAX_RETRIES = 5
RETRY_DELAY = 30

class DownloadThread(QThread):
    """ """
    update_signal = pyqtSignal(str) # Handles console messages
    progress_signal = pyqtSignal(str) # Updates GUI progress bar
    finished_signal = pyqtSignal(bool, str) # Enable buttons, show result
    
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
            
            # Detect a link
            self.update_signal.emit(f"Starting download...\n URL: {self.url}")
            
            # Self-determine which download method to use based on type
            
            # Download track
            if self.download_type == "track":
                output_template = str(Path(self.output_dir) / "{title}.{output-ext}")
                result = self.downloader.run_download(
                    self.url,
                    output_template)
            
            # Download album
            elif self.download_type == "album":
                output_template = str(Path(self.output_dir) / "{artist}/{album}/{title}.{output-ext}")
                result = self.downloader.run_download(
                    self.url,
                    output_template)
            
            # Download playlist                
            elif self.download_type == "playlist":
                output_template = str(self.__output_dir / "{playlist}/{title}.{output-ext}")
                result = self.downloader.run_download(
                    self.url,
                    output_template,
                    ["--playlist-numbering", "--playlist-retaining"])
                
            elif self.download_type == "search":
                output_template = str(Path(self.output_dir) / "{title}.{output-ext} ")
                result = self.downloader.run_download(self.url, output_template)
            
            elif self.download_type == "file":
                self.update_signal.emit("Batch download from file selected. Use the 'Batch Download' tab. ")
                self.finished_signal.emit(False, "Use Batch Download tab for file download")
                return
            
            # Check returncodes from Interactive Downloader
            if hasattr(result, 'returncode'):
                if result.returncode == 0: # Successful download
                    self.update_signal.emit("Download Completed")
                    self.finished_signal.emit(True, "Successful Download")
                elif result.returncode == 100: # Error in the metadata type
                    self.update_signal.emit("Error: Metadata TypeError")
                    self.finished_signal.emit(False, "Metadata TypeError")
                elif result.returncode == 101: # Error finding a song during search
                    self.update_signal.emit("Error: Lookup Error")
                    self.finished_signal.emit(False, "Lookup Error")
            else:
                self.update_signal.emit("Download Failed") # Failed download 
                self.finished_signal.emit(False, "Download failed")
        
        except Exception as e:
            self.update_signal.emit(f"Error: {str(e)}")
            self.finished_signal.emit(False, str(e))

class BatchDownloadThread(QThread):
    """ Download a file containing spotify album""" 
    
    update_signal = pyqtSignal(str, str) # (message, type)
    progress_signal = pyqtSignal(int, int) # (current, total)
    finished_signal = pyqtSignal(int, int) # (successful, total)
    
    def __init__(self, downloader, filepath, output_dir, bitrate, audio_format, max_retries, retry_delay):
        super().__init__()
        self.downloader = downloader
        self.filepath = filepath
        self.output_dir = output_dir
        self.bitrate = bitrate
        self.audio_format = audio_format
        
    def run(self):
        # Configure downloader
        self.downloader._Downloader__bitrate = self.bitrate
        self.downloader._Downloader__audio_format = self.audio_format
        self.downloader._Downloader__output_dir = Path(self.output_dir)
        
        # Reading URLs from the file
        try:
            with open(self.filepath, 'r') as file:
                urls = [line.strip() for line in file if line.strip() and not line.strip().startswith('#')]
        except Exception as e:
            self.update_signal.emit(f"Couldn't read the file: {(str(e))}")
            self.finished_signal.emit(0, 0)
            return

        if not urls:
            self.update_signal.emit("No URLs in the file", "warning")
            self.finished_signal.emit(0, 0)
            return
        
        total = len(urls)
        success = 0
        
        for i, url in enumerate(urls, 1):
            self.progress_signal.emit(i, total)
            self.update_signal.emit(f"Processing {i}/{total}: {url}", "info")
            
            # Download based on URL type
            # Download album
            if "album" in url.lower():
                output_template = str(Path(self.output_dir) / "{artist}/{album}/{title}.{output-ext}")
                additional_args = None
                
            # Download playlist                
            elif "playlist" in url.lower():
                output_template = str(self.__output_dir / "{playlist}/{title}.{output-ext}")
                additional_args = ["--playlist-numbering", "--playlist-retain-track-cover"]
            
            # If it is a track
            else:
                output_template = str(Path(self.output_dir) / "{title}.{output-ext}")
                additional_args = None
            
            for attempt in range(1, MAX_RETRIES + 1):
                self.update_signal.emit(f"Download Attempt {attempt}/{MAX_RETRIES}", "info")
                
                try:
                    result = self.downloader.run_download(url, output_template, additional_args)
                        
                    # Check returncodes from Interactive Downloader
                    if hasattr(result, 'returncode'):
                        if result.returncode == 0: # Successful download
                            success += 1
                            self.update_signal.emit("Download Completed")
                            break
                            
                        elif result.returncode == 100: # Error in the metadata type
                            self.update_signal.emit("Error: Metadata TypeError")
                            break
                        
                        elif result.returncode == 101: # Error finding a song during search
                            self.update_signal.emit("Error: Lookup Error")
                            break
                    
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY)
                    else:
                        self.update_signal.emit(f"Download Failed after {MAX_RETRIES} attempts") # Failed download 
                        self.finished_signal.emit(False, "Download failed")
                
                except Exception as e:
                    self.update_signal.emit(f"Exception: {str(e)}", "error")
                    if attempt == MAX_RETRIES:
                        break
                    time.sleep(RETRY_DELAY)
                    
        self.finished_signal.emit(success, total)
        
class DownloaderGUI(QMainWindow):
    pass