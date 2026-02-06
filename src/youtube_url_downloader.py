"""
Interactive Playlist/Album/Track Downloader using yt-dlp

While Spotify faces ethical challenges, YouTube remains a massive platform for music discovery.
This program allows you to download music directly from YouTube and YouTube Music.

Its features include:
- Audio Format choice
- Download Quality choice
- Output Directory Choice
- Zip Downloads choice
- Metadata Support
- Organizes albums by artist
- Mass download support (from text file)
- Log successful downloads
- Log failed downloads
- Log errors in between downloads
- Retry downloads

Now Improved with
- Progress bar for downloads
- Batch Processing (with parallel downloads)
- Resource Validation (Check if links are available)

Note: Please use the latest version of YT-DLP, upgrade it using "pip install --upgrade yt-dlp" or "yt-dlp -U" depending on how you installed it
Additionally make sure ffmpeg is installed, as that is necessary to parse the music file's metadata if not you will receive postprocessing error in your output

Enjoy!
"""
import sys
import os  # For directory creation
import subprocess  # To run the yt-dlp in the background
import shutil
import time  # Time
from functools import wraps
from pathlib import Path
import logging  # Logging
import re  # Regex
import urllib.parse
from urllib.parse import urlparse
from typing import List, Dict, Optional, Tuple
import json
from tqdm import tqdm
import browser_cookie3
from functools import wraps
from colorama import init, Fore, Back, Style


""" =========================================== Pre Config ===========================================
This part of the pre-configuration of the downloader, it can be change. Each part is explained below:
* SUCCESS_LOG - Logs the successful downloads (subject to change)
* FAILED_LOG - Logs failed downloads (subject to change)
* ERROR_LOG - Logs error in the download process (subject to change)
* MAX_RETRIES - No of times the downloader can retry on a link (subject to change)
* RETRY_DELAY - The delay between each retry (subject to change)
======================================================================================================= """

SUCCESS_LOG = r"log\success.log" 
FAILED_LOG = r"log\failed.log"
ERROR_LOG = r"log\error.log"
MAX_RETRIES = 3
RETRY_DELAY = 10
DOWNLOAD_TIMEOUT = 120
COOKIE_DIRECTORY = r"cookies\cookies"
COOKIE_TEMP_DIR = r"cookies\temp_cookies"

os.makedirs("log", exist_ok=True)
os.makedirs(COOKIE_DIRECTORY, exist_ok=True)
os.makedirs(COOKIE_TEMP_DIR, exist_ok=True)


"""==== Logger: Initialize the log files before write ==== """
# Basic Logger info
logger = logging.getLogger("YouTube Downloader")
log_format = logging.Formatter("YT-DLP %(asctime)s - %(levelname)s - %(funcName)s - %(lineno)d - %(message)s") 
error_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s") 

success_downloads = logging.getLogger("successful downloads")
failed_downloads = logging.getLogger("failed downloads")
error_downloads = logging.getLogger("error in downloads")
console_logger = logging.getLogger("console")
    
# Create loggers (successful downloads logger) ----------------------------------------------
success_downloads.setLevel(logging.INFO)
success_downloads.propagate = False

success_handler = logging.FileHandler(SUCCESS_LOG, encoding='utf-8')
success_handler.setLevel(logging.INFO)
success_handler.setFormatter(log_format)
success_downloads.addHandler(success_handler)

# Failed download logger ---------------------------------------------------------------
failed_downloads.setLevel(logging.INFO)
failed_downloads.propagate = False

failed_handler = logging.FileHandler(FAILED_LOG, encoding='utf-8')
failed_handler.setLevel(logging.INFO)
failed_handler.setFormatter(log_format)
failed_downloads.addHandler(failed_handler)

# Error in download logger ----------------------------------------------------------
error_downloads.setLevel(logging.INFO)
error_downloads.propagate = False

error_handler = logging.FileHandler(ERROR_LOG, encoding='utf-8')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(log_format)
error_downloads.addHandler(error_handler)

# General console logger (stream handler for console output)
console_logger.setLevel(logging.INFO)
console_logger.propagate = False

console_stream_handler = logging.StreamHandler()
console_stream_handler.setLevel(logging.INFO)
console_stream_handler.setFormatter(log_format)
console_logger.addHandler(console_stream_handler)


class CookieManager:
    """ Manages cookies for Youtube authentication"""
    
    def __init__(self):
        self.cookie_directory = Path(COOKIE_DIRECTORY)
        self.temp_directory = Path(COOKIE_TEMP_DIR)
        self.current_cookie_file = None
        self.cookie_sources = {
            'chrome': browser_cookie3.chrome,
            'firefox': browser_cookie3.firefox,
            'edge': browser_cookie3.edge, 
            'opera': browser_cookie3.opera,
            'opera_gx': browser_cookie3.opera_gx,
            'brave': browser_cookie3.brave,
            'safari': browser_cookie3.safari
        }
        
    def get_status(self):
        """Get cookie status"""
        print(f"\n Checking available browser cookies.... ")
        available_browsers = []
        failed_browsers = []
        
        for browser, cookie_func in self.cookie_sources.items():
            try:
                # Get cookies from this browser
                cookies = cookie_func(domain_name="https://music.youtube.com/")
                if cookies and len(list(cookies)) > 0:
                    available_browsers.append(browser)
                    print(f"Cookies found ")
                else:
                    print("No cookies found")
            except Exception as e:
                failed_browsers.append(browser)
                print()
                
        if available_browsers:
            return f" Available cookies from: {', '.join(available_browsers)}"
        return "No browser cookies found for Youtube Music"  

    def extract_cookies(self, browser_name: str = 'brave') -> Optional[Path]:
        """Extract cookies from your browser of choice & saves to files"""
        if browser_name not in self.cookie_sources:
            print(" Browser not supported")
            print(f"Available browsers: {', '.join(self.cookie_sources.keys())}")
            return None
        
        try:
            print(f" Extract cookies from {browser_name}....")
            
            # Retrieve cookies from Youtube domains
            domains = ['youtube.com', 'music.youtube.com']
            all_cookies = []
            
            for domain in domains:
                try:
                    cookies = self.cookie_sources[browser_name](domain_name=domain)
                    for cookie in cookies:
                        if cookie not in all_cookies:
                            all_cookies.append(cookie)
                except Exception as e:
                    print(f" Couldn't get cookies for {domain}: {e}")

            if not all_cookies:
                print(f" No cookies found for Youtube in {browser_name}")
                return None
            
            cookie_file = self.temp_directory / f"{browser_name}_cookies.txt"
            with open(cookie_file, "w", encoding='utf-8') as f:
                f.write("# Netscape HTTP cookie file\n")
                f.write("# This file was generated by Youtube Downloader\n")
                f.write("# https://curl.haxx.se/docs/http-cookies.html\n\n")
                
                for cookie in all_cookies:
                    # Convert to Netscape format
                    netloc = urlparse(cookie.domain).netloc if cookie.domain.startswith('http') else cookie.domain
                    if not netloc:
                        netloc = cookie.domain
                        
                    # Handle secure flag
                    secure = "TRUE" if cookie.secure else "FALSE"
                    
                    # Write cookie in Netscape format
                    f.write(f"{netloc}\t")
                    f.write("TRUE\t")  # Include subdomains
                    f.write(f"{cookie.path}\t")
                    f.write(f"{secure}\t")
                    f.write(f"{int(time.time()) + 3600*24*365}\t")  # Expiry (1 year from now)
                    f.write(f"{cookie.name}\t")
                    f.write(f"{cookie.value}\n")
                    
            print(f" Successfully extracted {len(all_cookies)} cookies to {cookie_file}")
            self.current_cookie_file = cookie_file
            return cookie_file
        
        except Exception as e:
            print(f" Failed to extract cookies from {browser_name}: {e}")
            return None
        
    def load_cookies(self, cookie_file: str) -> Optional[Path]:
        """Load cookies from an existing file"""
        cookie_path = Path(cookie_file)
        
        # Check if file exists in cookies directory
        if not cookie_path.exists():
            # Try to find it in the cookie directory
            cookie_path = self.cookie_directory / cookie_file
            if not cookie_path.exists():
                cookie_path = Path(cookie_file)
                if not cookie_path.exists():
                    print(f" Cookie file not found: {cookie_file}")
                    return None
        
        try:
            with open(cookie_path, 'r', encoding='utf-8') as f:
                content = f.read(200)
                if "# Netscape HTTP Cookie File" not in content:
                    print(f" Warning: Cookie file may not be in Netscape format")
            
            temp_cookie = self.temp_directory / f"loaded_{cookie_path.name}"
            shutil.copy2(cookie_path, temp_cookie)
            
            self.current_cookie_file = temp_cookie
            print(f" Cookies loaded from: {cookie_path}")
            return temp_cookie
        
        except Exception as e:
            print(f" Failed to load cookies: {e}")
            return None
        
    def save_cookies(self, name: str = "cookies") -> List[Path]:
        """Save current cookie file to persistent storage"""
        if not self.current_cookie_file or not self.current_cookie_file.exists():
            print(f" No active cookie file to save ")
            return None
        
        try:
            # Create a text file for the cookies
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_path = self.cookie_directory / f"{name}_{timestamp}.txt"
            
            
            # Copy the cookie file
            shutil.copy2(self.current_cookie_file, save_path)
            
            print(f" Cookies saved to: {save_path}")
            return save_path
        
        except Exception as e:
            print(f" Failed to save cookies: {e}")
            return None 
    
    def list_cookies(self) -> List[Path]:
        """List all saved cookie files"""
        cookie_files = list(self.cookie_directory.glob("* .txt"))
        
        if not cookie_files:
            print(f" No saved cookies files found.")
            return []
        
        print(f" Saved cookie files:")
        for i, cookie_file in enumerate(cookie_files, 1):
            file_size = cookie_file.stat().st_size
            mod_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(cookie_file.stat().st_mtime))
            print(f"{i}. {cookie_file.name} ({file_size} bytes, {mod_time})")
            
        return cookie_files
    
    def clear_cookies(self):
        """ Clear temporary cookie files"""
        try:
            for file in self.temp_directory.glob("*"):
                try:
                    file.unlink()
                except:
                    pass
            print(" Cleared cookies")
        except Exception as e:
            print(f" Could not clear cookies: {e}")
            
    def get_arguments(self) -> List[str]:
        """Get yt-dlp cookie arguments if cookies are available"""
        if self.current_cookie_file and self.current_cookie_file.exists():
            return ["--cookies", str(self.current_cookie_file)]
        return []
                
    def interactive_menu(self):
        """Interactive cookie setup menu"""
        while True:
            print('='*50)
            print("Cookie Manager Menu")
            print('='*50)
            print(" A simple program to help manager")
            print("Choose:- ")       
            print("1. Check available browser cookies")
            print("2. Extract cookies from browser")
            print("3. List saved cookie files")
            print("4. Load cookies from file")
            print("5. Save current cookies")
            print("6. Clear temporary cookies")
            print("7. Show current cookie status")
            print("8. Return to main menu")               

            choice = input("Select option (1-8): ").strip()
            
            if choice == "1":
                self.get_status()
                
            elif choice == "2":
                print("\nAvailable browsers:")
                for i, browser in enumerate(self.cookie_sources.keys(), 1):
                    print(f"{i}. {browser}")
                
                browser_choice = input("\nSelect browser (name or number): ").strip()
                
                # Try to interpret as number
                if browser_choice.isdigit():
                    browser_num = int(browser_choice)
                    if 1 <= browser_num <= len(self.cookie_sources):
                        browser_name = list(self.cookie_sources.keys())[browser_num - 1]
                        self.extract_cookies(browser_name)
                else:
                    self.extract_cookies(browser_choice)
                    
                # Ask to save
                if self.current_cookie_file:
                    save = input("Save these cookies for future use? (y/n): ").strip().lower()
                    if save in ['y', 'yes']:
                        name = input("Enter name for cookie file (optional): ").strip()
                        if not name:
                            name = "cookies"
                        self.save_cookies(name)
                
            elif choice == "3":
                cookie_files = self.list_cookies()
                if cookie_files:
                    load_choice = input("\nEnter number to load cookie file (or press Enter to skip): ").strip()
                    if load_choice.isdigit():
                        idx = int(load_choice) - 1
                        if 0 <= idx < len(cookie_files):
                            self.load_cookies(str(cookie_files[idx]))
                
            elif choice == "4":
                cookie_file = input("Enter cookie filename or path: ").strip()
                if cookie_file:
                    self.load_cookies(cookie_file)
                
            elif choice == "5":
                if self.current_cookie_file:
                    name = input("Enter name for cookie file (optional): ").strip()
                    if not name:
                        name = "cookies"
                    self.save_cookies(name)
                else:
                    print(f"{Fore.YELLOW}No active cookies to save{Style.RESET_ALL}")
                
            elif choice == "6":
                self.clear_cookies()
                
            elif choice == "7":
                status = self.get_status()
                if self.current_cookie_file:
                    print(f"{Fore.GREEN}✓ Active cookie file: {self.current_cookie_file.name}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}No active cookie file{Style.RESET_ALL}")
                
            elif choice == "8":
                break
                
            else:
                print(f"{Fore.RED}Invalid choice{Style.RESET_ALL}")
            
            input("\nPress Enter to continue...")                
    
    def __del__(self):
        """Cleanup cookies on program termination on destruction"""
        try:
            self.clear_cookies()
        except:
            pass           
                
class Youtube_Downloader:
    """ Downloader Class that handles the downloading process"""
    def __init__(self):
        """ Initialize the downloader with default values """
        self.__output_directory = Path("Albums")
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.__filepath = r"links/youtube_links.txt"
        self.__configuration_file = "downloader_config.json"
        self.cookie_manager = CookieManager()
        self.use_cookies = False

        self.__output_directory.mkdir(parents=True, exist_ok=True)
        Path("links").mkdir(parents=True, exist_ok=True)
        Path("log").mkdir(parents=True, exist_ok=True)
        
        try:
            self.load_config()
        except Exception as e:
            self.log_error(f"Error loading config: {e}")
        
    # ============================================= Configuration Managers ===========================================
    def load_config(self):
        """Load configuration from json file"""
        primary_config = {
            "output_directory": "Albums",
            "audio_quality": "320k",
            "audio_format": "mp3",
            "max_retries": MAX_RETRIES,
            "retry_delay": RETRY_DELAY,
            "download_timeout": DOWNLOAD_TIMEOUT,
            "use_cookies": False
            }

        try:
            if os.path.exists(self.__configuration_file):
                with open(self.__configuration_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    config = {**primary_config, **user_config}
            else:
                config = primary_config
                self.save_config(config)

            # Apply configuration safely
            if "output_directory" in config:
                self.__output_directory = Path(config["output_directory"])
            if "audio_quality" in config:
                self.__audio_quality = config["audio_quality"]
            if "audio_format" in config:
                self.__audio_format = config["audio_format"]
            if "use_cookies" in config:
                self.use_cookies = config["use_cookies"]
        
        except Exception as e:
            self.log_error(f"Error loading configuration: {e}")
            # Use defaults
            self.__output_directory = Path(primary_config["output_directory"])
            self.__audio_quality = primary_config["audio_quality"]
            self.__audio_format = primary_config["audio_format"]
            self.use_cookies = primary_config["use_cookies"]    
        
    def save_config(self, config: Dict = None):
        """Save configuration to file"""
        try:
            if config is None:
                config = {
                    "output_directory": str(self.__output_directory),
                    "audio_quality": self.__audio_quality,
                    "audio_format": self.__audio_format,
                    "max_retries": MAX_RETRIES,
                    "retry_delay": RETRY_DELAY,
                    "download_timeout": DOWNLOAD_TIMEOUT,
                    "use_cookies": self.use_cookies
                }
            
            with open(self.__configuration_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.log_error(f"Error saving configuration: {e}")
            
    # ============================================= Logger Functions ===========================================
    def log_success(self, message: str):
        """Logs only successful downloads (to success log)"""
        success_downloads.info(message)
        console_logger.info(f"{message}")
        
    def log_failure(self, message: str):
        """Logs only failed downloads (to failed log)"""
        failed_downloads.info(message)
        console_logger.info(f"{message}")
        
    def log_error(self, message: str, exc_info=False):
        """Logs only error in download process (to error log)"""
        error_downloads.error(message, exc_info=exc_info)
        console_logger.error(f"{message}")
             
    #  ============================================= Helper Functions & Resource Validation Functions =============================================
    def get_user_preferences(self):
        """Takes in user input for the download settings"""
        # Handle choice of bitrate/audio quality inputs
        while True:
            audio_quality_input = input("What bitrate would you like (8k-320k, default: 320k): ").strip().lower()
            
            if not audio_quality_input:
                self.__audio_quality = "320k"
                break
            if audio_quality_input in ["auto", "disable", "8k", "16k", "24k", "32k", "40k", "48k", "64k",
                                "80k", "96k", "112k", "128k", "160k", "192k", "224k", "256k", "320k"]:
                self.__audio_quality = audio_quality_input
                break
            print("Invalid bitrate. The downloader support values the following values 8k, 16k, 24k, 32k, 40k, 48k, 64k, 80k, 96k, 112k, 128k, 160k ,192k, 224k and more.")
            
        # Handles choice of audio format
        while True:
            audio_format_input = input("What format do you wish to download in (mp3, flac, ogg, opus, m4a, wav, default mp3): ").strip().lower()
            if not audio_format_input:
                self.__audio_format = "mp3"
                break
            if audio_format_input in ["mp3", "flac", "ogg", "opus", "m4a", "wav"]:
                self.__audio_format = audio_format_input
                break
            print("Invalid format. Your poosible choice are:- mp3, flac, ogg, opus, m4a, wav.")
            
        # Handle choice of output directory
        output_path = input("Enter output directory (default: Albums): ").strip()
        if output_path:
            self.__output_directory = Path(output_path)
        else:
            self.__output_directory = Path("Albums")
            
        self.__output_directory.mkdir(parents=True, exist_ok=True)  

        # Handles choice for cookies
        print("\n Cookie Settings: ")
        print("Cookies can help with age-restricted/region-restricted content.")
        cookie_choice = input("Use cookies for authentication? (y/n, default n): ").strip().lower()
        if cookie_choice in ['y', 'yes']:
            self.use_cookies = True
            print("Note: Make sure you have used the Cookie Manager to extract the cookies beforehand, if not I recommend you to")
        else:
            self.use_cookies = False
        
    def validate_youtube_url(self, url: str) -> bool:
        """Validate if the URL input is a proper YouTube URL"""
        youtube_patterns = [
            r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$',
            r'^(https?://)?music\.youtube\.com/.+$',
            r'^(https?://)?youtube\.com/watch\?v=[\w-]+(&.*)?$',
            r'^(https?://)?youtube\.com/playlist\?list=[\w-]+(&.*)?$',
            r'^(https?://)?youtu\.be/[\w-]+$'        
        ]

        for pattern in youtube_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                try:
                    parsed = urllib.parse.urlparse(url)
                    if parsed.scheme in ['http', 'https', ''] or parsed.netloc:
                        return True
                except:
                    continue
        return False
    
    def cleanup_directory(self):
        """Removes empty directories after download"""
        removed_count = 0
        for root, dirs, files in os.walk(self.__output_directory, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    if not os.listdir(dir_path):
                        os.rmdir(dir_path)
                        removed_count += 1
                except OSError:
                    pass
                
        if removed_count > 0:
            self.log_success("Cleaned up empty directories")
    
    def get_resource_type(self, url: str):
        """Determine the type of Youtube Music Resource is provided"""
        patterns = {
            "video": r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)',
            "playlist": r'youtube\.com/playlist\?list=([\w-]+)',
            "album": r'music\.youtube\.com/album/([\w-]+)',
            "channel": r'youtube\.com/(?:c/|channel/|@|user/)([\w-]+)'
        }
        
        for resource_type, pattern in patterns.items():
            if re.search(pattern, url, re.IGNORECASE):
                return resource_type
        return None
    
    def extract_youtube_id(self, url: str) -> str:
        """Extract YouTube ID from URL"""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)',  # Video ID
            r'youtube\.com/playlist\?list=([\w-]+)'          
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def resource_validation(self, url: str) -> Tuple[bool, str, Optional[Dict]]:
        """Validate if a resource is available before downloading to the device"""
        
        try:
            command = ["yt-dlp", 
                       "--skip-download",
                       "--print-json",
                       "--no-warnings",
                       url]
            result = subprocess.run(
                command, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
                timeout=30, check=False
            )
            
            if result.returncode == 0:
                try:
                    metadata = json.loads(result.stdout)
                    title = metadata.get('title', 'Unknown')
                    duration = metadata.get('duration', 0)
                    
                    if metadata.get('availability') == 'unavailable':
                        return False, "Video unavailable", metadata
                    
                    return True, f"Available", metadata
                
                except json.JSONDecodeError:
                    return True, "Music Resource Available - Complication in Metadata", None
                
            else:
                # Handles errors when locating the resource
                error_message = result.stderr.lower()
                if "unavailable" in error_message:
                    return False, "Resource unavailable", None
                elif "private" in error_message:
                    return False, "Restricted Access", None
                elif "age restriction" in error_message:
                    return False, "Age restricted video", None
                elif "not found" in error_message:
                    return False, "Resource not found", None
                else:
                    return False, f"Validation failed: {error_message[:100]}", None

        except subprocess.TimeoutExpired:
            return False, "Validation timeout", None
        except Exception as e:
            return False, f"Validation error: {str(e)[:100]}", None
    
    def parse_size(self, size_str: str) -> Optional[int]:
        """Parse size string to bytes"""
        if not size_str:
            return None
        
        size_str = size_str.strip().upper()
        units = {
        'B': 1,
        'K': 1024,
        'M': 1024**2,
        'G': 1024**3,
        'T': 1024**4,
        'KB': 1024,
        'MB': 1024**2,
        'GB': 1024**3,
        'TB': 1024**4,
        'KIB': 1024,
        'MIB': 1024**2,
        'GIB': 1024**3,
        'TIB': 1024**4           
        }
        
        match = re.match(r'([\d\.]+)\s*(\w*)', size_str)
        if not match:
            return None
        
        value, unit = match.groups()
        try:
            value = float(value)
            if not unit:
                return int(value)
            if unit in units:
                return int(value * units[unit])
        except ValueError:
            return None
        return None
    
    def _parse_size_to_bytes(self, size_str: str) -> Optional[int]:
        """Parse size string to bytes (for progress bar)"""
        return self.parse_size(size_str)

    #  ============================================= Download Functions =============================================
    def run_download(self, url: str, output_template: str, additional_args=None):
        """Run yt-dlp download with modern syntax & tqdm progress bar"""
        # Ensure output directory exists
        output_directory = os.path.dirname(output_template)
        if output_directory:
            os.makedirs(output_directory, exist_ok=True)
        
        command = [
            "yt-dlp",
            "-x",
            "--audio-format", self.__audio_format,  
            "--audio-quality", self.__audio_quality,  
            "-o", output_template,
            "--no-overwrites",
            "--add-metadata",
            "--embed-thumbnail",
            "--newline",
            "--progress",
            "--console-title",
            "--quiet",
            "--no-warnings",
            "--ignore-errors",
            "--retries", "10",
            "--fragment-retries", "10",
            "--buffer-size", "16K",
            "--http-chunk-size", "10M",
            "--extractor-args", "youtube:player_client=android",
        ]
        
        if self.use_cookies and self.cookie_manager.current_cookie_file:
            cookie_args = self.cookie_manager.get_arguments()
            if cookie_args:
                command.extend(cookie_args)
                self.log_success(f"Using cookies from {self.cookie_manager.current_cookie_file}")
            
        if additional_args:
            if isinstance(additional_args, list):
                command.extend(additional_args)
            else:
                command.append(additional_args)
        
        command.append(url)
        
        try:
            # Initialize progress bar
            progress_bar = tqdm(
                desc="Downloading",
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                leave=False,
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]",
                dynamic_ncols=True
            )
            
            # Start the subprocess
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',
                errors='replace'
            )
            
            # Parse output in real-time
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                
                if "[download]" in line:
                    try:
                        # Parse percentage
                        percent_match = re.search(r'(\d+\.?\d*)%', line)
                        if percent_match:
                            percent = float(percent_match.group(1))
                            progress_bar.set_description(f"Downloading: {percent:.1f}%")
                        
                        # Parse total size
                        size_match = re.search(r'of\s+([\d\.]+\s*[KMGT]?i?B)', line)
                        if size_match and progress_bar.total is None:
                            total_str = size_match.group(1)
                            total_bytes = self._parse_size_to_bytes(total_str)
                            if total_bytes:
                                progress_bar.total = total_bytes
                        
                        # Parse downloaded size
                        downloaded_match = re.search(r'([\d\.]+\s*[KMGT]?i?B)\s+at', line) or \
                                        re.search(r'([\d\.]+\s*[KMGT]?i?B)\s+ETA', line) or \
                                        re.search(r'([\d\.]+\s*[KMGT]?i?B)\s*\/', line)
                        if downloaded_match:
                            downloaded_str = downloaded_match.group(1)
                            downloaded_bytes = self._parse_size_to_bytes(downloaded_str)
                            if downloaded_bytes:
                                progress_bar.n = downloaded_bytes
                        
                        # Parse download speed
                        speed_match = re.search(r'at\s+([\d\.]+\s*[KMGT]?i?B/s)', line)
                        if speed_match:
                            speed = speed_match.group(1)
                            progress_bar.set_postfix_str(f"Speed: {speed}")
                        
                        # Parse ETA
                        eta_match = re.search(r'ETA\s+([\d:]+)', line)
                        if eta_match:
                            eta = eta_match.group(1)
                            progress_bar.set_postfix_str(f"ETA: {eta}")
                        
                        progress_bar.refresh()
                        
                    except Exception:
                        continue
                
                if "100%" in line or "already been downloaded" in line or "[Merger]" in line:
                    if progress_bar.total and progress_bar.n < progress_bar.total:
                        progress_bar.n = progress_bar.total
                    progress_bar.set_description("DOWNLOADED")
                    progress_bar.set_postfix_str("")
                    progress_bar.refresh()
                    break
            
            # Wait for process to complete
            process.wait()
            stdout, stderr = process.communicate()
            
            if progress_bar:
                progress_bar.close()
        
            
            # Check for common errors in stderr
            error_output = stderr.strip() if stderr else ""
            
            if process.returncode == 0:
                self.log_success(f"Successfully downloaded: {url}")
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=stdout,
                    stderr=""
                )
            else:
                # Log detailed error information
                error_msg = f"Download failed for {url} with code {process.returncode}"
                
                # Parse common error messages
                if "unavailable" in error_output.lower():
                    error_msg += " - Video is unavailable"
                elif "private" in error_output.lower():
                    error_msg += " - Video is private"
                elif "age restriction" in error_output.lower():
                    error_msg += " - Age restricted"
                elif "copyright" in error_output.lower():
                    error_msg += " - Copyright restriction"
                elif "format" in error_output.lower():
                    error_msg += " - Format not available"
                elif "ffmpeg" in error_output.lower():
                    error_msg += " - FFmpeg conversion error"
                elif error_output:
                    error_msg += f" - Error: {error_output[:200]}"
                
                self.log_failure(error_msg)
                
                # Return the error
                return subprocess.CalledProcessError(
                    process.returncode, 
                    command, 
                    stdout, 
                    stderr
                )
                
        except FileNotFoundError:
            error_msg = "yt-dlp not found. Please install it with: pip install yt-dlp"
            self.log_error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error in run_download: {e}"
            self.log_error(error_msg)
            if progress_bar:
                progress_bar.close()
            raise
        
    def rate_limit(calls_per_minute=60):
        """Rate limit to avoid blockage from """
        def decorator(func):
            last_called = [0.0]
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                elapsed_time = time.time() - last_called[0]
                wait_time = (60.0 / calls_per_minute) - elapsed_time
                if wait_time > 0:
                    time.sleep(wait_time)
                last_called[0] = time.time()
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    #  ============================================= Main Download functions (Improved with Batch Processing) =============================================
    @rate_limit(calls_per_minute=30)
    def download_track(self):
        """Download a single track"""
        while True:  # Add outer loop for URL input retry
            print("\n" + "="*50)
            print("Track Download")
            print("="*50)
            url = input("Enter YouTube/YouTube Music track URL (or 'back' to return to menu): ").strip()
            
            if url.lower() == 'back':
                return False
            
            if not url:
                print(f"No URL provided")
                continue  # Go back to asking for URL
            
            # Validate URL
            if not self.validate_youtube_url(url):
                print("Invalid YouTube URL. Please enter a valid YouTube/YouTube Music URL")
                continue
            
            # Validate resource before downloading
            print("Validating resource...")
            is_valid, message, metadata = self.resource_validation(url)
            if not is_valid:
                print(f"Resource validation failed: {message}")
                self.log_failure(f"Resource validation failed for {url}: {message}")
                print("Please try a different URL. ")
                continue
            
            print(f"Resource validated: {message}")
            break
            
        # Get user preferences
        self.get_user_preferences()
        print("="*50)
        print(f"Starting Track download: {url}. This may take a few minutes...")
        start_time = time.time()
        output_template = str(self.__output_directory / "%(artist,Unknown Artist)s - %(title)s.%(ext)s")
            
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"{'='*50}")
            print(f"Downloading Track URL: Attempt {attempt} of {MAX_RETRIES}")
            print(f"{'='*50}")
            
            # Add a small delay between retries
            if attempt > 1:
                print(f"Waiting {RETRY_DELAY} seconds before retry...")
                time.sleep(RETRY_DELAY)
            
            result = self.run_download(url, output_template)
            
            # Check if download was successful as well as record time it took to complete download
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                elapsed_time = time.time() - start_time
                self.log_success(f"Successfully downloaded: {url} in {elapsed_time:.1f} seconds!")
                print("="*50)
                
                # Ask if user wants to download another track
                another = input("Download another track? (y/n): ").strip().lower()
                if another in ['y', 'yes']:
                    continue  # Go back to URL input
                else:
                    return True  # Return success but exit to menu
            
            # If we get here, there was an error
            elif attempt < MAX_RETRIES:
                error_msg = f"Download failed (attempt {attempt}/{MAX_RETRIES})."
                if result.stderr:
                    error_msg += f" Error: {result.stderr[:200]}"
                self.log_error(error_msg)
                print("="*50)
                
            # If the download failed after all retries
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                print("="*50)
                return False  # Return to main menu    
                
        return False
    
    @rate_limit(calls_per_minute=30)
    def download_album(self):
        """Download an album"""
        while True:
            print("\n" + "="*50)
            print("Album Download")
            print("="*50)
            url = input("Enter YouTube Music album URL (or 'back' to return to menu):- ").strip()
            
            if url.lower() == 'back':
                return False
            
            if not url:
                print("No URL provided")
                continue

            # Validate URL
            if not self.validate_youtube_url(url):
                print("Invalid YouTube URL. Please enter a valid YouTube Music URL")
                continue
            
            # Validate resource before downloading
            print("Validating resource...")
            is_valid, message, metadata = self.resource_validation(url)
            if not is_valid:
                print(f"Resource validation failed: {message}")
                self.log_failure(f"Resource validation failed for {url}: {message}")
                print(f"Please try a different URL")
                continue
            
            print(f"Resource validated: {message}")
            break
        
        # Get user preferences
        self.get_user_preferences()
        print("="*50)
        print(f"Starting Album download. This may take a few minutes...")
        start_time = time.time()
        output_template = str(self.__output_directory / "%(artist)s/%(album)s/%(artist)s - %(title)s.%(ext)s")
    
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"{'='*50}")
            print(f"Downloading Album URL: Attempt {attempt} of {MAX_RETRIES}")
            print(f"{'='*50}")
            
            # Add a small delay between retries
            if attempt > 1:
                print(f"Waiting {RETRY_DELAY} seconds before retry...")
                time.sleep(RETRY_DELAY)
            
            result = self.run_download(url, output_template)
            
            # Check if download was successful as well as record time it took to complete download
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                elapsed_time = time.time() - start_time
                self.log_success(f"Successfully downloaded album in {elapsed_time:.1f} seconds!")
                print("="*50)
                
                
                another = input("Download another album? (y/n):- ").strip().lower()
                if another in ['y', 'yes']:
                    continue
                else:
                    return True
                            
            # If we get here, there was an error
            elif attempt < MAX_RETRIES:
                error_msg = f"Download failed (attempt {attempt}/{MAX_RETRIES})."
                if result.stderr:
                    error_msg += f" Error: {result.stderr[:200]}"
                self.log_error(error_msg)
                print("="*50)
                
            # If the download failed after all retries
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                print("="*50)
                return False
        
        return False
    
    @rate_limit(calls_per_minute=30)
    def download_playlist(self):
        """Download a playlist"""
        while True:
            print("\n" + "="*50)
            print("Playlist Download")
            print("="*50)
            url = input("Enter YouTube/YouTube Music playlist URL: ").strip()
            
            if url.lower() == 'back':
                return False
            
            if not url:
                print("No URL provided")
                continue

            if not self.validate_youtube_url(url):
                print("Invalid YouTube URL. Please enter a valid YouTube/YouTube Music URL")
                return False
            
            # Validate resource before downloading
            print("Validating resource...")
            is_valid, message, metadata = self.resource_validation(url)
            if not is_valid:
                print(f"Resource validation failed: {message}")
                self.log_failure(f"Resource validation failed for {url}: {message}")
                print("Please try a different URL. ")
                continue
            
            print(f"Resource validated: {message}")
            break
        
        # Get user preferences
        self.get_user_preferences()
        print("="*50)
        print(f"Starting Playlist download. This may take a few minutes...")
        start_time = time.time()
        output_template = str(self.__output_directory / "%(playlist)s/%(artist)s - %(title)s.%(ext)s")
        
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"{'='*50}")
            print(f"Downloading Playlist URL: Attempt {attempt} of {MAX_RETRIES}")
            print(f"{'='*50}")
            
            # Add a small delay between retries
            if attempt > 1:
                print(f"Waiting {RETRY_DELAY} seconds before retry...")
                time.sleep(RETRY_DELAY)
            
            result = self.run_download(url, output_template)
            
            # Check if download was successful as well as record time it took to complete download
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                elapsed_time = time.time() - start_time
                self.log_success(f"Successfully downloaded playlist in {elapsed_time:.1f} seconds!")
                print("="*50)
            
                another = input("Download another playlist (y/n):- ").strip().lower()
                if another in ['y', 'yes']:
                    continue
                else:
                    return True
                
            # If we get here, there was an error
            elif attempt < MAX_RETRIES:
                error_msg = f"Download failed (attempt {attempt}/{MAX_RETRIES})."
                if result.stderr:
                    error_msg += f" Error: {result.stderr[:200]}"
                self.log_error(error_msg)
                print("="*50)
                
            # If the download failed after all retries
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                print("="*50)
                return False
        
        return False

    def download_from_file(self):
        """Download various links from a file"""
        filepath = input("Enter the directory of the file (default: links/youtube_links.txt): ").strip()
        
        if not filepath:
            filepath = self.__filepath
            
        if not os.path.exists(filepath):
            self.log_failure(f"File not found: {filepath}")
            print(f"Please create a file named 'youtube_links.txt' in the 'links' folder.")
            return False
        
        self.get_user_preferences()
        
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                file_lines = [line.rstrip() for line in file if line.strip()]
        except FileNotFoundError:
            self.log_failure(f"File not found: {filepath}")
            return False
        except Exception as e:
            self.log_failure(f"Error reading the file: {e}")
            return False
        
        if not file_lines:
            self.log_failure("No URLs found in the text file")
            return False
        
        success_count = 0  # How many urls downloaded successfully
        failed_count = 0  # How many urls failed to download
        
        for i, url in enumerate(file_lines, 1):
            print("="*50)
            self.log_success(f"Processing URL {i}/{len(file_lines)}: {url}")
            
            clean_url = url.split('#')[0].strip()
            
            # Check if URL is already downloaded
            if "# DOWNLOADED" in url:
                self.log_success(f"Skipping already downloaded URL: {clean_url}")
                success_count += 1
                continue
            
            # Validate the URL before attempting download
            print("Validating URL...")
            is_valid, message, _ = self.resource_validation(clean_url)
            if not is_valid:
                self.log_failure(f"URL validation failed: {clean_url} - {message}")
                file_lines[i-1] = f"{clean_url} # VALIDATION_FAILED: {message}"
                failed_count += 1
                continue
            
            # Determine output template based on URL type
            if "playlist" in url.lower():
                output_template = str(self.__output_directory / "%(playlist)s/%(artist)s - %(title)s.%(ext)s")
                additional_args = None
            elif "album" in url.lower():
                output_template = str(self.__output_directory / "%(artist)s/%(album)s/%(artist)s - %(title)s.%(ext)s")
                additional_args = None
            else:
                output_template = str(self.__output_directory / "%(artist)s - %(title)s.%(ext)s")
                additional_args = None
            
            success = False
            non_retry_error = False
            
            for attempt in range(1, MAX_RETRIES + 1):
                print("="*50)
                print(f"Downloading URL {i}: Attempt {attempt} of {MAX_RETRIES}")
                
                # Add delay between retries
                if attempt > 1:
                    print(f"Waiting {RETRY_DELAY} seconds before retry...")
                    time.sleep(RETRY_DELAY)
                
                try:
                    result = self.run_download(clean_url, output_template, additional_args)
                    
                    if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                        success = True
                        break
                    elif attempt < MAX_RETRIES:
                        error_msg = f"Download failed (attempt {attempt}/{MAX_RETRIES})."
                        if hasattr(result, 'stderr') and result.stderr:
                            error_msg += f" Error: {result.stderr[:200]}"
                        self.log_error(error_msg)
                        
                except Exception as e:
                    self.log_failure(f"Exception during the download: {e}")
            
            if success:
                success_count += 1
                self.log_success(f"Successfully downloaded {clean_url}")
                
                if "#" in url:
                    # Keep existing comments before # and add DOWNLOADED
                    parts = url.split('#')
                    file_lines[i-1] = f"{parts[0].strip()} # DOWNLOADED"
                else:
                    file_lines[i-1] = f"{clean_url} # DOWNLOADED"
            else:
                failed_count += 1
                self.log_failure(f"Failed to download {clean_url}")
                if "#" in url:
                    parts = url.split('#')
                    file_lines[i-1] = f"{parts[0].strip()} # FAILED"
                else:
                    file_lines[i-1] = f"{clean_url} # FAILED"
        
        # Update the file with download status
        try: 
            with open(filepath, 'w', encoding='utf-8') as file:
                file.write("\n".join(file_lines))    
        except Exception as e:
            self.log_failure(f"Error updating the file: {e}")
        
        print("\n" + "="*50)
        print(f"Download Summary:")
        print(f"Successfully downloaded: {success_count}")
        print(f"Failed: {failed_count}")
        print("="*50)
        
        return failed_count == 0

    def search_a_song(self):
        """Search for a song and download it"""
        song_query = input("What is the name of the song you're looking for: ").strip()

        if not song_query:
            print("No input provided")
            return False
        
        self.get_user_preferences()
        search_time = time.time()
        print("Searching for the song. Browsing through YouTube...")
        
        output_template = str(self.__output_directory / "%(title)s.%(ext)s")
        
        for attempt in range(1, MAX_RETRIES + 1):
            print("="*50)
            print(f"Search and download attempt: {attempt} of {MAX_RETRIES}:")
            
            # Add delay between retries
            if attempt > 1:
                print(f"Waiting {RETRY_DELAY} seconds before retry...")
                time.sleep(RETRY_DELAY)
            
            try:
                # Use our run_download method for consistency
                result = self.run_download(f"ytsearch1:{song_query}", output_template)
                
                elapsed_time = time.time() - search_time
                self.log_success(f"Successfully downloaded: '{song_query}' in {elapsed_time:.1f} seconds!")
                print("="*50)
                return True
                    
            except Exception as e:
                self.log_error(f"Unexpected error: {e}")
                if attempt < MAX_RETRIES:
                    pass  # Will retry
                else:
                    return False

        return False

    def download_channel(self):
        """Download all videos from a YouTube channel"""
        print("\n" + "="*50)
        print("Channel Download")
        print("="*50)
        print("Note: This will download all videos from a YouTube channel")
        print("This may take a long time depending on the channel size")
        print("="*50)
        
        channel_url = input("Enter YouTube channel URL: ").strip()
        
        if not channel_url:
            print("No URL provided")
            return False
        
        if not self.validate_youtube_url(channel_url):
            print("Invalid YouTube URL. Please enter a valid YouTube channel URL")
            return False
        
        self.get_user_preferences()
        
        # Ask for confirmation
        confirm = input(f"\nWARNING: This will download ALL videos from the channel. Continue? (y/n): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("Channel download cancelled.")
            return False
        
        print("="*50)
        print(f"Starting Channel download. This may take a VERY long time...")
        start_time = time.time()
        output_template = str(self.__output_directory / "Channels" / "%(channel)s" / "%(title)s.%(ext)s")
        
        # Use yt-dlp with channel download options
        additional_args = [
            "--yes-playlist",  # Treat channel as playlist
            "--download-archive", "downloaded_channels.txt"  # Keep track of downloaded videos
        ]
        
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"{'='*50}")
            print(f"Downloading Channel: Attempt {attempt} of {MAX_RETRIES}")
            print(f"{'='*50}")
            
            # Add delay between retries
            if attempt > 1:
                print(f"Waiting {RETRY_DELAY} seconds before retry...")
                time.sleep(RETRY_DELAY)
            
            result = self.run_download(channel_url, output_template, additional_args)
            
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                elapsed_time = time.time() - start_time
                self.log_success(f"Successfully downloaded channel in {elapsed_time:.1f} seconds!")
                print("="*50)
                return True
            elif attempt < MAX_RETRIES:
                error_msg = f"Download failed (attempt {attempt}/{MAX_RETRIES})."
                if hasattr(result, 'stderr') and result.stderr:
                    error_msg += f" Error: {result.stderr[:200]}"
                self.log_error(error_msg)
                print("="*50)
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {channel_url}")
                print("="*50)
                return False
        
        return False

    def manage_cookies(self):
        """Calls the cookie management menu"""
        self.cookie_manager.interactive_menu()
        
        # Update the config
        if self.cookie_manager.current_cookie_file:
            use_cookies = input("Enable cookies for future downloads")
            if use_cookies in ['y', 'yes']:
                self.use_cookies = True
                self.save_config()
    
    #  ============================================= Checkers & Yt-DLP Helpers =============================================
    @staticmethod
    def check_ytdlp():
        """
        Check if yt-dlp is installed (cache yt-dlp)
        """
        if shutil.which("yt-dlp"):
            print("yt-dlp is already installed")
            
            # Check version
            try:
                result = subprocess.run(
                    ["yt-dlp", "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                    timeout=10
                )
                if result.returncode == 0:
                    version = result.stdout.strip()
                    print(f"yt-dlp version: {version}")
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
                print("Could not determine yt-dlp version")
                return False
        else:
            print("yt-dlp not found. Installing...")
            
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp"])
                print("yt-dlp installed successfully")
                return True
            except subprocess.CalledProcessError as e:
                print(f"Failed to install yt-dlp: {e}")
                return False
    
    @staticmethod
    def check_ffmpeg():
        """ Check if ffmpeg is installed"""
        if shutil.which("ffmpeg"):
            print("ffmpeg is already installed")
            
            # Check version
            try:
                result = subprocess.run(
                    ["ffmpeg", "-version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                    timeout=10
                )
                if result.returncode == 0:
                    version = result.stdout.strip()
                    print(f"ffmpeg version: {version}")
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
                print("Could not determine ffmpeg version")
                return False
    
    @staticmethod     
    def show_ytdlp_help():
        """
        Display yt-dlp help
        """
        try:
            result = subprocess.run(
                ["yt-dlp", "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            print("\n" + "="*50)
            print("YT-DLP HELP")
            print("="*50)
            print(result.stdout[:2000])  # Show first 2000 characters
            print("\n... (output truncated, use 'yt-dlp --help' for full help)")
        except subprocess.CalledProcessError as e:
            print(f"Could not get yt-dlp help: {e}")
                 
    def troubleshooting(self):
        """Troubleshooting"""
        print("\n" + "="*50)
        print("YT-DLP Troubleshooting")
        print("="*50)
        
        # Check if yt-dlp is installed
        print("Hello, this troubleshooter is to help if you're experiencing problem in the program")
        print("Running a simple daignostic. This might take a while.....")
        
        # Check if yt-dlp is installed
        print("1. Checking yt-dlp installation...")
        if not shutil.which("yt-dlp"):
            print(" yt-dlp not found in PATH")
            print(" Try: Install yt-dlp by running the command in terminal: pip install yt-dlp")
            return False
        else:
            print("yt-dlp found")
        
        try:
            result = subprocess.run(
                ["yt-dlp", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )
            print(f" Version: {result.stdout.strip()}")
        except:
            print(" Could not get version") 

        # Check if FFmpeg (needed for audio conversion)
        print("\n2. Checking FFmpeg...")
        if not shutil.which("ffmpeg"):
            print(" FFmpeg not found (audio conversion might fail & errors might occur when retrieving metadata)")
            print(" Install FFmpeg from: https://ffmpeg.org/download.html")
        else:
            print(" FFmpeg found")

        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )
            print(f" Version: {result.stdout.strip()}")
        except:
            print(" Could not get version")

        # Test with a simple download
        print("\n3. Testing download with a known video...")
        test_url = "https://music.youtube.com/watch?v=215T8NF93kw" 
        try:
            # Simple test without conversion
            test_command = [
                "yt-dlp",
                "--skip-download",
                "--print-json",
                test_url
            ]
            
            result = subprocess.run(
                test_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print("   ✅ Can access YouTube")
                try:
                    data = json.loads(result.stdout)
                    print(f"Test video title: {data.get('title', 'Unknown')[:50]}...")
                except:
                    print(" Can access YouTube (metadata parse failed)")
            else:
                print(f" Cannot access YouTube: {result.stderr[:100]}")            
        
        except Exception as e:
            print("Test failed.")

    @staticmethod     
    def program_info():
        """
        Display program information
        """
        print("="*80)
        print("Interactive YouTube/YouTube Music Playlist/Album/Track Downloader")
        print("="*80)
        print("This is a simple to use downloader that can help in downloading")
        print("albums/playlist/single tracks etc from YouTube and YouTube Music")
        print("\n" + "-"*80)
        print("Each function explained:")
        print("\n=== Basic Functions ===")
        print("* download_track - Downloads a single track from YouTube/YouTube Music")
        print("* download_album - Downloads an album from YouTube Music")
        print("* download_playlist - Downloads a playlist from YouTube/YouTube Music")
        
        print("\n=== Special Functions ===")      
        print("* download_from_file - Downloads from a text file with YouTube URLs")
        print("* search_a_song - Search for a song & download it from YouTube")
        print("* manage_cookies - Manage browser cookies for authentication")       
        print("* download_channel - Downloads ALL videos from a YouTube channel")
        
        print("\n=== Help functions: Provides help with the program ===")
        print("* program_info - Provides context on the program")
        print("* check_ytdlp - Checks for yt-dlp & installs it if doesn't exist")
        print("* show_ytdlp_help - Provides context on yt-dlp commands")
        print("* check_ytdlp - Checks for yt-dlp & installs it if doesn't exist")
        print("* check_ffmpeg - Checks for ffmpeg installation")
        print("* show_ytdlp_help - Provides context on yt-dlp commands")
        print("* troubleshooting - Troubleshoot common download issues")        
        print("="*80)
       
def display_menu() -> None:
    """Display the main menu."""
    menu = """
    ========================================================================
    INTERACTIVE MUSIC DOWNLOADER USING YT-DLP
    ========================================================================
    Select an option:
    1.  Download Track
    2.  Download Album
    3.  Download Playlist
    4.  Download from Text File
    5.  Search and Download Song
    6.  Download YouTube Channel (All Videos)
    7.  Manage Cookies (for age-restricted consent)
    8.  Check/Install yt-dlp
    9.  Show yt-dlp Help
    10.  Check ffmpeg
    11. Show Program Info
    12. Troubleshoot Download Issue
    13. Exit
    ========================================================================
    """
    print(menu)

def main():
    """Main function to run the YouTube Downloader."""
    print("="*50)
    print("Initializing YouTube/YouTube Music Downloader...")
    
    # Create necessary directories
    os.makedirs("log", exist_ok=True)
    os.makedirs("Albums", exist_ok=True)
    os.makedirs("links", exist_ok=True)
    
    if not Youtube_Downloader.check_ytdlp():
        print("="*50)
        print("\n Failed to install yt-dlp. Please install it manually using:")
        print("pip install yt-dlp")
        print("Then run the program again.")
        print("="*50)
        return
    
    downloader = Youtube_Downloader()
    
    while True:
        display_menu()
        print("="*50)
        choice = input("\nEnter your choice (1-13): ").strip()
        
        if choice == "13":
            print("\n" + "="*50)
            print("Thank you for using YouTube Downloader. Goodbye!")
            print("="*50)
            break

        actions = {
            "1": downloader.download_track,
            "2": downloader.download_album,
            "3": downloader.download_playlist,
            "4": downloader.download_from_file,
            "5": downloader.search_a_song,
            "6": downloader.download_channel,
            "7": downloader.manage_cookies,
            "8": Youtube_Downloader.check_ytdlp,
            "9": Youtube_Downloader.show_ytdlp_help,
            "10": Youtube_Downloader.check_ffmpeg,
            "11": Youtube_Downloader.program_info,
            "12": lambda: downloader.troubleshooting(
                input("Enter URL to troubleshoot: ").strip()
            ) if input("Enter URL to troubleshoot: ").strip() else print("No URL provided")
        }
        
        action = actions.get(choice)
        if action:
            try:
                action()
            except KeyboardInterrupt:
                print("\nOperation cancelled by user.")
            except Exception as e:
                print(f"\nAn error occurred during the operation: {e}")
                print("Check the error log for details.")
                downloader.log_error(f"Menu option {choice} error: {e}", exc_info=True)
        else:
            print("="*50)
            print("Invalid choice. Please enter a number between 1 and 12.")
            continue
        
        print("\n" + "="*50)
        cont = input("Return to main menu? (y/n): ").strip().lower()
        if cont not in ['y', 'yes', '']:
            print("="*50)
            print("\nThank you for using YouTube Downloader. Goodbye!")
            break
        
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        print("Please check the error log for details.")