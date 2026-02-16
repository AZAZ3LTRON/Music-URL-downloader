import sys
import os
import subprocess
import shutil
import time
from functools import wraps
from pathlib import Path
import logging
import re
import urllib.parse
from urllib.parse import urlparse
from typing import List, Dict, Optional, Tuple
import threading
import json
from tqdm import tqdm
from colorama import init, Fore, Back, Style

from CookieManager import CookieManager
from EnhancedMenu import Enhanced_Menu

init(autoreset=True)


class Log_History:
    """ Log Manager and history viewer for the Downlaoder"""
    def __init__(self):
        self.log_dir = Path("log")
        self.log_dir.mkdir(exist_ok=True)
        
        # Define log file paths
        self.success_log = self.log_dir/"success.log"
        self.failed_log = self.log_dir/"failed.log"
        self.error_log = self.log_dir/"error.log"
        
        # Initialize the log path
        self.setup_logs()
        
        self.color_map = {
            'success': Fore.GREEN,
            'failed': Fore.RED,
            'error': Fore.YELLOW,
            'warning': Fore.MAGENTA           
        }
        
    def setup_logs(self):
        """Setup all log with format and configuration"""
        
        # log format
        log_format = logging.Formatter("YT-DLP - %(asctime)s - %(levelname)s - %(funcName)s - %(lineno)d - %(message)s")
        error_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        
        # Successful downloads log
        self.success_log = logging.getLogger("successful_downloads")
        self.success_log.setLevel(logging.INFO)
        self.success_log.propagate = False
        success_handler = logging.FileHandler(str(self.success_log), encoding='utf-8')
        success_handler.setLevel(logging.INFO)
        success_handler.setFormatter(log_format)
        self.success_log.addHandler(success_handler)
        
        # Failed download log
        self.failed_log = logging.getLogger("failed_downloads")
        self.failed_log.setLevel(logging.INFO)
        self.failed_log.propagate = False
        failed_handler = logging.FileHandler(str(self.failed_log), encoding='utf-8')
        failed_handler.setLevel(logging.INFO)
        failed_handler.setFormatter(log_format)
        self.success_log.addHandler(failed_handler)
        
        # Error log
        self.error_log = logging.getLogger("Errors")
        self.error_log.setLevel(logging.INFO)
        self.error_log.propagate = False
        error_handler = logging.FileHandler(str(self.error_log), encoding='utf-8')
        error_handler.setLevel(logging.INFO)
        error_handler.setFormatter(error_format)
        self.error_log.addHandler(error_handler)
        
        
        # Console logs
        self.console_logger = logging.getLogger("console")
        self.console_logger.setLevel(logging.INFO)
        self.console_logger.propagate = False
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(log_format)
        self.console_logger.addHandler(console_handler)        
    
    # ========== Logging Methods ==============
    
    def log_success(self, message: str, console: bool = True):
        """ Log successful music downloads"""
        self.success_log.info(message)
        if console:
            self.console_logger.info(f"{self.color_map['success']}{message}{Style.RESET_ALL}")
        
    def log_failure(self, message: str, console: bool = True):
        """ Log failed music downloads"""
        self.failed_log.info(message)
        if console:
            self.console_logger.info(f"{self.color_map['failed']}{message}{Style.RESET_ALL}")
            
    def log_error(self, message: str, exc_info=False, console: bool = True):
        """ Log error during music download process"""
        self.error_log.error(message, exc_info=exc_info)
        if console:
            self.console_logger.info(f"{self.color_map['error']}{message}{Style.RESET_ALL}")
    
    
    # =============== Log Statistics ============
    
    def log_statistics(self):
        """ Get the statistics for all log files."""
        
        # Stats dictionary to hold all possible records
        stats = {
            'success_count': 0,
            'failed_count': 0,
            'error_count': 0,
            'total_count': 0,
            'last_download': 0,
            'success_rate': 0
        }
        
        # Count entries in each log
        for log_file, key in [(self.success_log, 'success_count'), 
                              (self.failed_log, 'failed_count'), 
                              (self.error_log, 'error_count')]:
            
            # Check if file exist
            if log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        # Coi
                        lines = [l for l in f.readlines() if l.strip()]
                        stats[key] = len(lines)
                        stats['total_count'] += len(lines)
                
                except Exception as e:
                    self.log_error(f"Error reading log file {log_file}: {e}", console=False)

            # Calculate Download success rate
            if stats['total_count'] >0:
                stats['success_rate'] = (int(stats['success_count'])) / int(stats['total_count']) * 100
                
            return stats
        
    def get_common_errors(self)