from pathlib import Path
import logging
import re
from colorama import init, Fore, Style
import threading

init(autoreset=True)

class Logs_Manager:
    """ Log Manager and history viewer for the Downloader"""
    def __init__(self):
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # Define log file paths
        self.success_log_path = self.log_dir / "success.log" # Directory for successful downloads
        self.failed_log_path = self.log_dir / "failed.log"  # Directory for failed downloads
        self.error_log_path = self.log_dir / "error.log" # Directory for errors during downloads
        self.warning_log_path = self.log_dir / "warning" # Directory for warnings
        self._lock = threading.Lock() # Locks the thread
        
        # Initialize loggers
        self.success_logger = None
        self.failed_logger = None
        self.error_logger = None
        self.warning_logger = None
        self.console_logger = None
        
        self._session_failed_urls = set()
        self._session_failure_counts = {"not_found": 0, "rate_limited": 0, "download_error": 0}
        self._track_fail_re = re.compile(
            r'(https?://open\.spotify\.com/track/[A-Za-z0-9]+)\s*-\s*(\w+):\s*(.*)')
        
        # Setup the logs
        self.setup_logs()
        
        # Color map for respective logs
        self.color_map = {
            'success': Fore.GREEN,
            'failed': Fore.RED,
            'error': Fore.YELLOW,
            'warning': Fore.MAGENTA           
        }
        
    def setup_logs(self):
        """Setup all log with format and configuration"""
        
        # Full format for file logs (includes date/time)
        file_format = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(funcName)s - %(lineno)d - %(message)s"
        )
        error_format = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )

        # Console format – only the message, no timestamp
        console_format = logging.Formatter("%(message)s")

        # --- Success log (file only) ---
        self.success_logger = logging.getLogger("successful_downloads")
        self.success_logger.setLevel(logging.INFO)
        self.success_logger.propagate = False
        success_handler = logging.FileHandler(str(self.success_log_path), encoding='utf-8')
        success_handler.setLevel(logging.INFO)
        success_handler.setFormatter(file_format)          # full timestamp in file
        self.success_logger.addHandler(success_handler)

        # --- Failed log (file only) ---
        self.failed_logger = logging.getLogger("failed_downloads")
        self.failed_logger.setLevel(logging.INFO)
        self.failed_logger.propagate = False
        failed_handler = logging.FileHandler(str(self.failed_log_path), encoding='utf-8')
        failed_handler.setLevel(logging.INFO)
        failed_handler.setFormatter(file_format)
        self.failed_logger.addHandler(failed_handler)

        # --- Error log (file only) ---
        self.error_logger = logging.getLogger("Errors")
        self.error_logger.setLevel(logging.ERROR)
        self.error_logger.propagate = False
        error_handler = logging.FileHandler(str(self.error_log_path), encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(error_format)
        self.error_logger.addHandler(error_handler)

        # --- Console logger (terminal) – timestamp‑free ---
        self.console_logger = logging.getLogger("console")
        self.console_logger.setLevel(logging.INFO)        # show INFO and above
        self.console_logger.propagate = False
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_format)      # 👈 only the message
        self.console_logger.addHandler(console_handler)     
        
    # ========== Logging Methods ==============
    def log_success(self, message: str, console: bool = True):
        """ Log successful music downloads"""
        with self._lock:
            if self.success_logger:
                self.success_logger.info(message)
            if console and self.console_logger:
                self.console_logger.info(f"{self.color_map['success']}{message}{Style.RESET_ALL}")
        
    def log_failure(self, message: str, console: bool = True):
        """ Log failed music downloads"""
        with self._lock:
            if self.failed_logger:
                self.failed_logger.info(message)
            if console and self.console_logger:
                self.console_logger.info(f"{self.color_map['failed']}{message}{Style.RESET_ALL}")
            
    def log_error(self, message: str, exc_info=False, console: bool = True):
        """ Log error during music download process"""
        with self._lock:
            if self.error_logger:
                self.error_logger.error(message, exc_info=exc_info)
            if console and self.console_logger:
                self.console_logger.info(f"{self.color_map['error']}{message}{Style.RESET_ALL}")
    
    def log_warning(self, message: str, console: bool = True):
        pass
            