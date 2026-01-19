"""
Interactive Playlist/Album/Track Downloader using yt-dlp

This is a simple to use downloader that can help in downloading albums/playlist/single tracks etc from Youtube Music

Since Spotify have blocked all API requests, this program will make use of the yt-dlp library to facilitate music downloads. 
Make sure you have the yt-dlp library downlaoded as well as Deno, a open-source JavaScript runtime for the modern web.

You can find information on both here:
 - Deno: https://docs.deno.com/runtime/getting_started/installation/
 - Yt-dlp: https://github.com/yt-dlp/yt-dlp

Also use links from either Youtube music or Youtube. The program the same features as the other downloader but has less functions that it.


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
"""

# Basic Import required
import sys
import os # For directory creation
import subprocess # To run the spotdl in the background
import shutil
import time # Time
from functools import wraps
from pathlib import Path
import logging # Logging
import re # Regex
import urllib.parse
import json
from typing import Optional, List, DIct, Union
import traceback

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

os.makedirs("log", exist_ok=True)

"""==== Logger: Initialize the log fies before write ====  """
# Basic Logger info
logger = logging.getLogger("Spotify Downloader")
log_format = logging.Formatter("YT-DLP - %(asctime)s - %(levelname)s - %(funcName)s - %(message)s") 
error_format = logging.Formatter("From YT-DLP - %(asctime)s - %(levelname)s - %(message)s") 

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

class Youtube_Downloader:
    def __init__(self):
        """
        Initialize the downloader with default values
        Args:
        output_dir - The output directory we wish to send our playlist once downloaded
        bitrate - The quality of the audio
        audio_format - The format we wish to download the Spotify url
        
        The values here are set to default and can be changed later to fit your preference 
        """
        self.__output_dir = Path("Albums")
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.__output_template = "%(title)s.%(ext)s"
        
        self.__filepath = r"links/spotify_links.txt"
        self.__ytdlp_version = None
        self.__max_retries = MAX_RETRIES
        self.__retry_delay = RETRY_DELAY

    # Logger Functions -----------------------------------------------------------------
    def log_success(self, message: str):
        """Logs only successful downloads (to success log)"""
        success_downloads.info(message)
        console_logger.info(f"{message}")
        
    def log_failure(self, message: str):
        """ Logs only failed downlaods (to failed log)"""
        failed_downloads.info(message)
        console_logger.info(f"{message}")
        
    def log_error(self, message: str, exc_info=False):
        """ Logs only  error in download process (to error log)"""
        error_downloads.error(message, exc_info=exc_info)
        console_logger.error(f"{message}")
        
    # Preference getters & helper functions ------------------------------------------------        
    def get_user_preferences(self):
        """ Takes in user input for the download settings """
        
        # Handle choice of bitrate/audio quality inputs
        while True:
            audio_quality_input = input("What bitrate would you like (8k-320k, default:- 320k):- ").strip().lower()
            
            if not audio_quality_input:
                self.__audio_quality = "320K"
                break
            if audio_quality_input in ["auto", "disable", "8k", "16k", "24k", "32k", "40k", "48k", "64k",
                                "80k", "96k", "112k", "128k", "160k", "192k", "224k", "256k", "320k"]:
                self.__audio_quality = audio_quality_input
                break
            print("Invalid bitrate. Please choose from the specified values.")
            
        # Handles choice of audio format
        while True:
            audio_format_input = input("What format do you wish to download in:(mp3, flac, ogg, opus, m4a, wav, default mp3):- ").strip().lower()
            if not audio_format_input:
                self.__audio_format = "mp3"
                break
            if audio_format_input in ["mp3", "flac", "ogg", "opus", "m4a", "wav"]:
                self.__audio_format = audio_format_input
                break
            print("Invalid format. Please choose from the specified formats.")
          
        # Handles output template choice  
        while True:
            print("Choose your output template format:- ")
            print("  [A] Album: artist/album/track.ext")
            print("  [T] Track: track.ext")
            print("  [P] Playlist: playlist/track.ext")
            
            output_template = input("Choose (A/T/P, default T):- ")
            if not output_template or output_template == 'T':
                self.__output_template = "%(title)s.%(ext)s"
                break
            if output_template in ['Album', 'A']:
                self.__output_template = "%(artist)s/%(album)s/%(title)s.%(ext)s"
                break
            elif output_template in ['Playlist', 'P']:
                self.__output_template = "%(playlist)s/%(title)s.%(ext)s"
                break
            else:
                print("Invalid choice. Please enter A, T or P")
        
        # Handle choice of output directory
        output_path = input("Enter output directory (default: Albums):- ").strip()
        if output_path:
            self.__output_dir = Path(output_path)
        else:
            self.__output_dir = Path("Albums")
            
        self.__output_dir.mkdir(parents=True, exist_ok=True)

    def validate_youtube_url(self, url: str) -> bool:
        """ Validate if the URL input is a proper URL"""
        
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
                    if parsed.scheme in ['http', 'https', 'music', 'youtube']:
                        return True
                except:
                    continue
        return False

    def extract_youtube_id(self, url: str) -> str:
        """ Extract Youtube ID from URL """
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)', # Video ID
            r'youtube\.com/playlist\?list=([\w-]+)'          
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def run_download(self, url: str, output_dir: Path, additional_args=None):
        """ Run yt-dlp download with modern syntax """
        command = [
            "yt-dlp",
            "-x",
            "--audio-format", self.__audio_format,
            "--audio-quality", self.__audio_quality,
            "-o", str(output_dir / self.__output_template),
            url,
            "--no-overwrites" # Skip if file exists
            "--no-playlist", # Download only single video if URL is playlist
            "--add-metadata", # Add metadata
            "--embed-thumbnail", # Embed thumbnail if available
            "--"
        ]
        
        if additional_args:
            if isinstance(additional_args, list):
                command.extend(additional_args)
            else:
                command.append(additional_args)
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=DOWNLOAD_TIMEOUT,
                check=True
            )
            
            if result.stdout:
                self.log_success(f"Output: {result.stdout[:200]}")
            return result
        
        except subprocess.CalledProcessError as e:
            stderr = e.stderr or ""
                # Error Handling for specific errors during download process ----------------------------
            # ----- NON - RETRYABLE ERRORS -------------------
            if "This video is unavailable" or "Privae video" in stderr:
                self.log_failure(f"{url} - Video unavailable")
                return type('obj', (object,), {
                    'returncode': 404,  # Custom return code for non-retryable
                    'stdout': e.stdout,
                    'stderr': stderr
                })()
            
            elif "Sign in to confirm your age" in stderr:
                self.log_failure(f"{url} - Age restriction")
                return type('obj', (object,), {
                    'returncode': 402,  
                    'stdout': e.stdout,
                    'stderr': stderr
                })()
            else:
                self.log_error(f"Command failed for {url}: {stderr[:500]}")
                raise

        except subprocess.TimeoutExpired:
            self.log_error(f"Download timeout for {url}")
            return type('obj', (object,), {
                'returncode': 400, # Timeout
                'stdout': '',
                'stderr': 'Download timeout'        
            })()
            
        except Exception as e:
            self.log_error(f"Unexpected error: {e}")
            return e

    # Extra functions to really on (incase of program failure) ----------------------------
    def rate_limit(calls_per_minute=60):
        """ Added rate limiter to avoid being blocked """
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

    # Download Functions
    def download_single(self, url):
        """Download a single URL"""
        if not self.validate_youtube_url(url):
            self.log_failure(f"Invalid URL: {url}")
            return False
        
        for attempt in range(self.__max_retries):
            try:
                console_logger.info(f"Attempt {attempt + 1}/{self.__max_retries} for {url}")
                result = self.run_download(url, self.__output_dir)
                
                if hasattr(result, 'returncode'):
                    if result.returncode == 0:
                        self.log_success(f"Successfully downloaded: {url}")
                        return True
                    elif result.returncode in [404, 403, 408]:  # Non-retryable errors
                        self.log_failure(f"Non-retryable error for {url}")
                        return False
                
                # If we get here, it was successful
                self.log_success(f"Successfully downloaded: {url}")
                return True
                
            except Exception as e:
                self.log_error(f"Attempt {attempt + 1} failed for {url}: {str(e)[:100]}")
                if attempt < self.__max_retries - 1:
                    console_logger.info(f"Retrying in {self.__retry_delay} seconds...")
                    time.sleep(self.__retry_delay)
                else:
                    self.log_failure(f"Failed after {self.__max_retries} attempts: {url}")
                    return False
        
        return False

    def check_ytdlp(self):
        """Check if yt-dlp is installed"""
        try:
            result = subprocess.run(
                ["yt-dlp", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            self.__ytdlp_version = result.stdout.strip()
            self.log_success(f"yt-dlp founded| version: {self.__ytdlp_version}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log_error("yt-dlp not found. Installing yt-dlp..........")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp"])
                print("yt-dlp installed successfully")
                return True
            except subprocess.CalledProcessError as e:
                print(f"Failed to install yt-dlp: {e}")
                return False