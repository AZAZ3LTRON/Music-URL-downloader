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

Enjoy!
"""

# Basic Import required
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

"""==== Logger: Initialize the log files before write ==== """
# Basic Logger info
logger = logging.getLogger("YouTube Downloader")
log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(funcName)s - %(message)s") 
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

""" =========================================== The Downloader Class =========================================== """
class Youtube_Downloader:
    def __init__(self):
        """
        Initialize the downloader with default values
        Args:
        output_dir - The output directory we wish to send our playlist once downloaded
        audio_quality - The quality of the audio
        audio_format - The format we wish to download the YouTube url
        
        The values here are set to default and can be changed later to fit your preference 
        """
        self.__output_dir = Path("Albums")
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.__filepath = r"links/youtube_links.txt"
        self.__ytdlp_version = None

    # Logger Functions -----------------------------------------------------------------
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
     
    # Preference getters & helper functions ------------------------------------------------
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
            print("Invalid bitrate. Please choose from the specified values.")
            
        # Handles choice of audio format
        while True:
            audio_format_input = input("What format do you wish to download in (mp3, flac, ogg, opus, m4a, wav, default mp3): ").strip().lower()
            if not audio_format_input:
                self.__audio_format = "mp3"
                break
            if audio_format_input in ["mp3", "flac", "ogg", "opus", "m4a", "wav"]:
                self.__audio_format = audio_format_input
                break
            print("Invalid format. Please choose from the specified formats.")
            
        # Handle choice of output directory
        output_path = input("Enter output directory (default: Albums): ").strip()
        if output_path:
            self.__output_dir = Path(output_path)
        else:
            self.__output_dir = Path("Albums")
            
        self.__output_dir.mkdir(parents=True, exist_ok=True)
    
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

    def run_download(self, url: str, output_template: str, additional_args=None):
        """Run yt-dlp download with modern syntax"""
        # Ensure output directory exists
        output_dir = os.path.dirname(output_template)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        command = [
            "yt-dlp",
            "-x",
            "--audio-format", self.__audio_format,
            "--audio-quality", self.__audio_quality,
            "-o", output_template,
            "--no-overwrites",  # Skip if file exists
            "--add-metadata",  # Add metadata
            "--embed-thumbnail",  # Embed thumbnail if available
            "--quiet"  # Reduce output noise
        ]
        
        if additional_args:
            if isinstance(additional_args, list):
                command.extend(additional_args)
            else:
                command.append(additional_args)
        
        command.append(url)
        
        try:
            result = subprocess.run(
                command,
                stdout=sys.stdout,
                stderr=subprocess.PIPE,
                text=True,
                timeout=DOWNLOAD_TIMEOUT,
                check=True
            )
            
            if result.stdout:
                self.log_success(f"Command output: {result.stdout[:200]}")
            if result.stderr:
                self.log_error(f"Command errors: {result.stderr[:200]}")
            return result
        
        except subprocess.CalledProcessError as e:
            stderr = e.stderr or ""
            # Error Handling for specific errors during download process
            # ------------ NON -RETRYABLE ERRORS ------------
            if "This video is unavailable" in stderr or "Private video" in stderr:
                self.log_error(f"{url} - Video unavailable")
                # Mark as non-retryable by returning a special object
                return type('obj', (object,), {
                    'returncode': 404,  # Custom return code for non-retryable
                    'stdout': e.stdout,
                    'stderr': stderr
                })()
            
            if "Sign in to confirm your age" in stderr:
                self.log_error(f"{url} - Age restriction")
                # Mark as non-retryable
                return type('obj', (object,), {
                    'returncode': 402,  # Custom return code for age restriction
                    'stdout': e.stdout,
                    'stderr': stderr
                })()
            
            if "Video unavailable. This video is private" in stderr:
                self.log_error(f"{url} - Private video")
                return type('obj', (object,), {
                    'returncode': 403,  # Custom return code for private video
                    'stdout': e.stdout,
                    'stderr': stderr
                })()
            
            # ------------ RETRYABLE ERRORS ------------
            if "This video has been removed" in stderr:
                self.log_error(f"{url} - Video removed")
                # This will be retried normally since we raise the exception
            # -------------------------------------------------------------
            
            # For other errors, log and return the exception
            self.log_failure(f"Command failed for {url}: {e}")
            return e

        except subprocess.TimeoutExpired:
            self.log_error(f"Download timeout for {url}")
            return type('obj', (object,), {
                'returncode': 408,  # Timeout
                'stdout': '',
                'stderr': 'Download timeout'        
            })()
            
        except Exception as e:
            self.log_error(f"Unexpected error: {e}")
            return e

    # Extra functions to rely on (in case of program failure) ----------------------------
    def rate_limit(calls_per_minute=60):
        """Added rate limiter to avoid being blocked"""
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

    # Main download functions -----------------------------------------------------------
    @rate_limit(calls_per_minute=30)
    def download_track(self):
        """Download a single track"""
        print("\n" + "="*50)
        print("Single Track Download")
        print("="*50)
        url = input("Enter YouTube/YouTube Music track URL: ").strip()
        
        if not url:
            print("No URL provided")
            return False

        # Validate URL
        if not self.validate_youtube_url(url):
            print("Invalid YouTube URL. Please enter a valid YouTube/YouTube Music URL")
            return False
        
        # Get user preferences
        self.get_user_preferences()
        print("="*50)
        print(f"Starting Track download: {url}. This may take a few minutes...")
        start_time = time.time()
        output_template = str(self.__output_dir/"%(title)s.%(ext)s")
            
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"{'='*50}")
            print(f"Downloading Track URL: Attempt {attempt} of {MAX_RETRIES}")
            print(f"{'='*50}")
            
            result = self.run_download(url, output_template)
            
            if hasattr(result, 'returncode'):
                if result.returncode in [404, 402, 403]:  # Non-retryable errors
                    self.log_error(f"Non-retryable error for {url}: Video unavailable/restricted")
                    return False
            
            # Check if download was successful as well as record time it took to complete download
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                elapsed_time = time.time() - start_time
                self.log_success(f"Successfully downloaded: {url} in {elapsed_time:.1f} seconds!")
                print("="*50)
                return True
            
            # If we get here, there was an error
            elif attempt < MAX_RETRIES:
                self.log_error(f"Download failed. Retrying in {RETRY_DELAY} seconds...")
                print("="*50)
                time.sleep(RETRY_DELAY)
                
            # If the download failed
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                return False
              
        return False
    
    @rate_limit(calls_per_minute=30)
    def download_album(self):
        """Download an album"""
        print("\n" + "="*50)
        print("Album Download")
        print("="*50)
        url = input("Enter YouTube Music album URL: ").strip()
        
        if not url:
            print("No URL provided")
            return False

        # Validate URL
        if not self.validate_youtube_url(url):
            print("Invalid YouTube URL. Please enter a valid YouTube Music URL")
            return False
        
        # Get user preferences
        self.get_user_preferences()
        print("="*50)
        print(f"Starting Album download. This may take a few minutes...")
        start_time = time.time()
        output_template = str(self.__output_dir / "%(artist)s/%(album)s/%(title)s.%(ext)s")
        
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"{'='*50}")
            print(f"Downloading Album URL: Attempt {attempt} of {MAX_RETRIES}")
            print(f"{'='*50}")
            
            result = self.run_download(url, output_template)
            
            if hasattr(result, 'returncode'):
                if result.returncode in [404, 402, 403]:  # Non-retryable errors
                    self.log_error(f"Non-retryable error for {url}: Video unavailable/restricted")
                    return False
            
            # Check if download was successful as well as record time it took to complete download
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                elapsed_time = time.time() - start_time
                self.log_success(f"Successfully downloaded album in {elapsed_time:.1f} seconds!")
                print("="*50)
                return True
            
            # If we get here, there was an error
            elif attempt < MAX_RETRIES:
                self.log_error(f"Download failed. Retrying in {RETRY_DELAY} seconds...")
                print("="*50)
                time.sleep(RETRY_DELAY)
                
            # If the download failed
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                print("="*50)
                return False
        
        return False
    
    @rate_limit(calls_per_minute=30)
    def download_playlist(self):
        """Download a playlist"""
        print("\n" + "="*50)
        print("Playlist Download")
        print("="*50)
        url = input("Enter YouTube/YouTube Music playlist URL: ").strip()
        
        if not url:
            print("No URL provided")
            return False

        if not self.validate_youtube_url(url):
            print("Invalid YouTube URL. Please enter a valid YouTube/YouTube Music URL")
            return False
        
        # Get user preferences
        self.get_user_preferences()
        print("="*50)
        print(f"Starting Playlist download. This may take a few minutes...")
        start_time = time.time()
        output_template = str(self.__output_dir / "%(playlist)s/%(title)s.%(ext)s")
        
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"{'='*50}")
            print(f"Downloading Playlist URL: Attempt {attempt} of {MAX_RETRIES}")
            print(f"{'='*50}")
            
            result = self.run_download(url, output_template)
            
            if hasattr(result, 'returncode'):
                if result.returncode in [404, 402, 403]:  # Non-retryable errors
                    self.log_error(f"Non-retryable error for {url}: Video unavailable/restricted")
                    return False
            
            # Check if download was successful as well as record time it took to complete download
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                elapsed_time = time.time() - start_time
                self.log_success(f"Successfully downloaded playlist in {elapsed_time:.1f} seconds!")
                print("="*50)
                return True
            
            # If we get here, there was an error
            elif attempt < MAX_RETRIES:
                self.log_error(f"Download failed. Retrying in {RETRY_DELAY} seconds...")
                print("="*50)
                time.sleep(RETRY_DELAY)
                
            # If the download failed
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
            if url.endswith("# DOWNLOADED"):
                self.log_success(f"Skipping already downloaded URL: {url}")
                success_count += 1
                continue
            
            # Determine output template based on URL type
            if "playlist" in url.lower():
                output_template = str(self.__output_dir / "Playlists" / "%(playlist)s" / "%(title)s.%(ext)s")
                additional_args = None
            elif "album" in url.lower():
                output_template = str(self.__output_dir / "Albums" / "%(artist)s" / "%(album)s" / "%(title)s.%(ext)s")
                additional_args = None
            else:
                output_template = str(self.__output_dir / "Tracks" / "%(title)s.%(ext)s")
                additional_args = None
            
            success = False
            non_retry_error = False
            
            for attempt in range(1, MAX_RETRIES + 1):
                print("="*50)
                print(f"Downloading URL {i}: Attempt {attempt} of {MAX_RETRIES}")
                
                try:
                    result = self.run_download(url, output_template, additional_args)
                    
                    if hasattr(result, 'returncode'):
                        if result.returncode in [404, 402, 403]:  # Non-retryable errors
                            self.log_error(f"Non-retryable error for {url}: Video unavailable/restricted")
                            non_retry_error = True
                            break
                    
                    if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                        success = True
                        break
                    elif attempt < MAX_RETRIES:
                        self.log_error(f"Download failed. Retrying in {RETRY_DELAY} seconds...")
                        time.sleep(RETRY_DELAY)
                        
                except Exception as e:
                    self.log_failure(f"Exception during the download: {e}")
            
            if success:
                success_count += 1
                self.log_success(f"Successfully downloaded {url}")
                
                if "#" in url:
                    # Keep existing comments before # and add DOWNLOADED
                    parts = url.split('#')
                    file_lines[i-1] = f"{parts[0].strip()} # DOWNLOADED"
                else:
                    file_lines[i-1] = f"{clean_url} # DOWNLOADED"
            else:
                failed_count += 1
                self.log_failure(f"Failed to download {url}")
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
        
        output_template = str(self.__output_dir/ "%(title)s.%(ext)s")
        
        for attempt in range(1, MAX_RETRIES + 1):
            print("="*50)
            print(f"Search and download attempt: {attempt} of {MAX_RETRIES}:")
            
            # Use yt-dlp's search functionality
            command = [
                "yt-dlp",
                "ytsearch1:" + song_query,  # Search for the top result
                "-x",
                "--audio-format", self.__audio_format,
                "--audio-quality", self.__audio_quality,
                "-o", output_template,
                "--no-overwrites",
                "--add-metadata",
                "--embed-thumbnail",
                "--quiet"
            ]
            
            try:
                result = subprocess.run(
                    command,
                    stdout=sys.stdout,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=DOWNLOAD_TIMEOUT,
                    check=True
                )
                
                elapsed_time = time.time() - search_time
                self.log_success(f"Successfully downloaded: '{song_query}' in {elapsed_time:.1f} seconds!")
                print("="*50)
                return True
                
            except subprocess.CalledProcessError as e:
                stderr = e.stderr or ""
                
                if "No video results" in stderr or "No matches found" in stderr:
                    self.log_error(f"No results found for: '{song_query}'")
                    return False
                
                if attempt < MAX_RETRIES:
                    self.log_error(f"Download failed. Retrying in {RETRY_DELAY} seconds...")
                    print("="*50)
                    time.sleep(RETRY_DELAY)
                else:
                    self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: '{song_query}'")
                    print("="*50)
                    return False
                    
            except Exception as e:
                self.log_error(f"Unexpected error: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    return False

        return False

    # Special download functions -------------------------------------------------------
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
        output_template = str(self.__output_dir / "Channels" / "%(channel)s" / "%(title)s.%(ext)s")
        
        # Use yt-dlp with channel download options
        additional_args = [
            "--yes-playlist",  # Treat channel as playlist
            "--download-archive", "downloaded_channels.txt"  # Keep track of downloaded videos
        ]
        
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"{'='*50}")
            print(f"Downloading Channel: Attempt {attempt} of {MAX_RETRIES}")
            print(f"{'='*50}")
            
            result = self.run_download(channel_url, output_template, additional_args)
            
            if hasattr(result, 'returncode'):
                if result.returncode in [404, 402, 403]:  # Non-retryable errors
                    self.log_error(f"Non-retryable error for channel: {channel_url}")
                    return False
            
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                elapsed_time = time.time() - start_time
                self.log_success(f"Successfully downloaded channel in {elapsed_time:.1f} seconds!")
                print("="*50)
                return True
            elif attempt < MAX_RETRIES:
                self.log_error(f"Download failed. Retrying in {RETRY_DELAY} seconds...")
                print("="*50)
                time.sleep(RETRY_DELAY)
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {channel_url}")
                print("="*50)
                return False
        
        return False

    # yt-dlp helpers ----------------------------------------------------------------------------
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
        print("* download_from_file - Downloads from a text file with YouTube URLs")
        print("* search_a_song - Search for a song & download it from YouTube")
        print("\n=== Special Functions ===")
        print("* download_channel - Downloads ALL videos from a YouTube channel")
        print("\n=== Help functions: Provides help with the program ===")
        print("* program_info - Provides context on the program")
        print("* check_ytdlp - Checks for yt-dlp & installs it if doesn't exist")
        print("* show_ytdlp_help - Provides context on yt-dlp commands")
        print("="*80)

""" The downloader """
def display_menu() -> None:
    """Display the main menu."""
    menu = """
    ========================================================================
    INTERACTIVE YOUTUBE/YOUTUBE MUSIC DOWNLOADER
    ========================================================================
    Select an option:
    1.  Download Track
    2.  Download Album
    3.  Download Playlist
    4.  Download from Text File
    5.  Search and Download Song
    6.  Download YouTube Channel (All Videos)
    7.  Check/Install yt-dlp
    8.  Show yt-dlp Help
    9.  Show Program Info
    10. Exit
    ========================================================================
    """
    print(menu)

def main():
    """Main function to run the YouTube Downloader."""
    print("="*50)
    print("Initializing YouTube/YouTube Music Downloader...")
    
    os.makedirs("log", exist_ok=True)
    os.makedirs("Albums", exist_ok=True)
    os.makedirs("links", exist_ok=True)
    
    if not Youtube_Downloader.check_ytdlp():
        print("="*50)
        print("\nFailed to install yt-dlp. Please install it manually using:")
        print("pip install yt-dlp")
        print("Then run the program again.")
        print("="*50)
        return
    
    downloader = Youtube_Downloader()
    
    while True:
        display_menu()
        print("="*50)
        choice = input("\nEnter your choice (1-10): ").strip()
        
        # FIX 1: Handle exit first
        if choice == "10":
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
            "7": downloader.check_ytdlp,
            "8": Youtube_Downloader.show_ytdlp_help,
            "9": Youtube_Downloader.program_info,
        }
        
        action = actions.get(choice)
        if action:
            try:
                action()
            except Exception as e:
                print(f"\nAn error occurred during the operation: {e}")
                print("Check the error log for details.")
        else:
            print("="*50)
            print("Invalid choice. Please enter a number between 1 and 10.")
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