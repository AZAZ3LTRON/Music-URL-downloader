"""
Interactive Playlist/Album/Track Downloader using SpotDL

With the rise of Artificial Intelligence and the music industry scraping artist work to run in LLMs, Spotify has been the biggest profit from this.
From the support of ICE, promoting AI Artist on the platform without proper regulations, their exploitative subscriptions fees which they have increased once again, 
putting out Zionist Advertisement, underpaying artist and Daniel Ek's investment in German military AI company Helsing.

I created this python script to allow you, the user, to download track, albums, personal playlist etc from the Spotify Website. Unfortunately, Spotify have blocked all API request from
being made due to mass web scrape of their platform by Anna's Archive. If you wish to download from them, you can go to 

The program function is to allow you to download music from Spotify urls.

Its features a:
- Audio Format choice
- Download Quality choice
- Output Directory Choice
- Metadata Support
- Organizes albums by artist
- Mass download support (from text file)
- Log successful downloads
- Log failed downloads
- Log errors in between downloads
- Retry downloads
- Resource validation

Enjoy! 
"""

# Basic Import required
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
import json
from typing import List, Dict, Optional, Tuple
from tqdm import tqdm  # Already imported


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
class Spotify_Downloader:
    def __init__(self):
        """
        Initialize the downloader with default values
        Args:
        output_dir - The output directory we wish to send our playlist once downloaded
        bitrate - The quality of the audio
        audio_format - The format we wish to download the Spotify url
        
        The values here are set to default and can be changed later to fit your preference 
        """
        self.__output_directory = Path("Albums")
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.__filepath = r"links/spotify_links.txt"
        self.__spotdl_version = None
        self.__configuration_file = "spotdl_config.json"
        self.__spotdl_version = None
        
    def load_config(self):
        """Load configuration from json file"""
        primary_config = {
            "output_directory": str(self.__output_directory),
            "audio_quality": self.__audio_quality,
            "audio_format": self.__audio_format,
        }

        try:
            if os.path.exists(self.__configuration_file):
                with open(self.__configuration_file, 'r') as f:
                    user_config = json.load(f)
                    config = {**primary_config, **user_config}
            else:
                config = primary_config
                with open(self.__configuration_file, 'w') as f:
                    json.dump(config, f, indent=2)
                
            # Apply configuration
            self.__output_directory = Path(config.get("output_directory", "Albums"))
            self.__audio_quality = config.get("audio_quality", "320k")
            self.__audio_format = config.get("audio_format", "mp3")
        
        except Exception as e:
            self.log_error(f"Error loading configuration: {e}")
            # Use defaults
            self.__output_directory = Path("Albums")
            self.__audio_quality = "320k"
            self.__audio_format = "mp3"   

    def save_config(self, config: Dict = None):
        """Save configuration to file"""
        try:
            config = {
                "output_dir": str(self.__output_dir),
                "audio_quality": self.__audio_quality,
                "audio_format": self.__audio_format,
                "max_parallel_downloads": self.__parallel_downloads,
                "max_retries": MAX_RETRIES,
                "retry_delay": RETRY_DELAY,
                "download_timeout": DOWNLOAD_TIMEOUT
            }
            
            with open(self.__config_file, 'w') as f:
                json.dump(config, f, indent=2)
                
        except Exception as e:
            self.log_error(f"Error saving configuration: {e}")
            
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
    
    def log_warning(self, message: str):
        """Log warning messages"""
        console_logger.warning(message)
     
    # Preference getters & helper functions ------------------------------------------------        
    def get_user_preferences(self):
        """ Takes in user input for the download settings """
        
        # Handle choice of bitrate inputs
        while True:
            bitrate_input = input("What bitrate would you like (8k-320k, default:- 320k):- ").strip().lower()
            
            if not bitrate_input:
                self.__audio_quality = "320K"
                break
            if bitrate_input in ["auto", "disable", "8k", "16k", "24k", "32k", "40k", "48k", "64k",
                                "80k", "96k", "112k", "128k", "160k", "192k", "224k", "256k", "320k"]:
                self.__audio_quality = bitrate_input
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
            
        # Handle choice of output directory
        output_path = input("Enter output directory (default: Albums):- ").strip()
        if output_path:
            self.__output_directory = Path(output_path)
        else:
            self.__output_directory = Path("Albums")
            
        self.__output_directory.mkdir(parents=True, exist_ok=True)
    
    def validate_spotify_url(self, url: str) -> Tuple[bool, str]:
        """ Validate if the URL input is a proper URL and return type"""
        
        spotify_patterns = [
            (r'^https://open\.spotify\.com/track/[A-Za-z0-9]+', 'track'),
            (r'^https://open\.spotify\.com/album/[A-Za-z0-9]+', 'album'),
            (r'^https://open\.spotify\.com/playlist/[A-Za-z0-9]+', 'playlist'),
            (r'^https://open\.spotify\.com/artist/[A-Za-z0-9]+', 'artist'),
            (r'^spotify:track:[A-Za-z0-9]+$', 'track'),
            (r'^spotify:album:[A-Za-z0-9]+$', 'album'),
            (r'^spotify:playlist:[A-Za-z0-9]+$', 'playlist'),
            (r'^spotify:artist:[A-Za-z0-9]+$', 'artist')
        ]
        
        for pattern, resource_type in spotify_patterns:
            if re.match(pattern, url):
                return True, resource_type
        
        return False, "unknown"
    
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
    
    def extract_spotify_id(self, url: str) -> str:
        """ Extract Spotify ID from URL """
        patterns = [
            r'spotify\.com/(track|album|playlist)/([A-Za-z0-9]+)',
            r'spotify:(track|album|playlist):([A-Za-z0-9]+)'           
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(2)
        return None

    def validate_resource(self, url: str, skip_cache: bool = False) -> Tuple[bool, str, Optional[Dict]]:
        """ Validate if a resource is available before downloading to the device """
        
        print(f"Validating resource: {url}")
        
        try:
            # Use spotdl's metadata fetching capability
            command = ["spotdl", 
                       url,
                       "--skip-download",
                       "--print-json",
                       "--no-warnings"]
            
            result = subprocess.run(
                command, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
                timeout=30, check=False
            )
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    metadata = json.loads(result.stdout.strip())
                    
                    # Check for critical metadata
                    if not metadata.get('name') and not metadata.get('title'):
                        return False, "Invalid metadata - no title found", metadata
                    
                    # Check duration for tracks
                    if 'duration' in metadata:
                        duration = metadata.get('duration', 0)
                        if duration <= 0:
                            return False, "Invalid duration", metadata
                    
                    # Check if it's a playlist/album and get track count
                    if metadata.get('type') in ['playlist', 'album']:
                        tracks = metadata.get('tracks', [])
                        if not tracks:
                            return False, f"No tracks found in {metadata.get('type')}", metadata
                        
                        available_tracks = 0
                        unavailable_tracks = []
                        
                        for track in tracks:
                            if track.get('available', True):
                                available_tracks += 1
                            else:
                                unavailable_tracks.append(track.get('name', 'Unknown'))
                        
                        total_tracks = len(tracks)
                        if available_tracks == 0:
                            return False, f"No available tracks in {metadata.get('type')}", metadata
                        
                        if unavailable_tracks:
                            self.log_warning(f"{len(unavailable_tracks)} tracks unavailable in {metadata.get('type')}")
                        
                        message = f"{metadata.get('type').title()} available with {available_tracks}/{total_tracks} tracks"
                        return True, message, metadata
                    
                    # For single tracks
                    return True, "Track available", metadata
                    
                except json.JSONDecodeError as e:
                    # Try to parse error message from stderr
                    error_msg = result.stderr.lower() if result.stderr else str(e)
                    
                    if "not found" in error_msg:
                        return False, "Resource not found on Spotify", None
                    elif "private" in error_msg:
                        return False, "Private resource - requires authentication", None
                    elif "unavailable" in error_msg:
                        return False, "Resource unavailable in your region", None
                    else:
                        return False, f"Invalid response: {error_msg[:100]}", None
            
            else:
                # Parse error from stderr
                error_msg = result.stderr.lower() if result.stderr else "Unknown error"
                
                if "not found" in error_msg:
                    return False, "Resource not found", None
                elif "private" in error_msg or "access" in error_msg:
                    return False, "Private or restricted access", None
                elif "unavailable" in error_msg:
                    return False, "Resource unavailable", None
                elif "quota" in error_msg or "rate limit" in error_msg:
                    return False, "Rate limit exceeded - try again later", None
                else:
                    return False, f"Validation failed: {error_msg[:100]}", None

        except subprocess.TimeoutExpired:
            return False, "Validation timeout - resource may be too large", None
        except FileNotFoundError:
            return False, "spotdl not found - please install it first", None
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
        """Parse size string to bytes"""
        return self.parse_size(size_str)
    
    def run_download(self, url: str, output_template: str, additional_args=None):
        """ Run spotdl download with modern syntax """
        command = [
            "spotdl",
            "download",
            url,
            "--output", output_template,
            "--overwrite", "skip",
            "--bitrate", self.__audio_quality,
            "--format", self.__audio_format
        ]
        
        if additional_args:
            command.extend(additional_args)
        
        try:
            print(f"Executing: {' '.join(command)}")
            
            # Simple implementation without complex progress parsing
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=DOWNLOAD_TIMEOUT
            )
            
            if result.returncode == 0:
                self.log_success(f"Successfully downloaded: {url}")
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=result.stdout,
                    stderr=result.stderr
                )
            else:
                self.log_failure(f"Download failed for {url} with code {result.returncode}")
                if result.stderr:
                    self.log_error(f"Error: {result.stderr[:200]}")
                return subprocess.CalledProcessError(
                    result.returncode, 
                    command, 
                    result.stdout, 
                    result.stderr
                )
                
        except subprocess.TimeoutExpired:
            self.log_error(f"Download timeout for {url}")
            return None
        except Exception as e:
            self.log_error(f"Unexpected error in run_download: {e}")
            return None

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

    # Main download functions -----------------------------------------------------------
    @rate_limit(calls_per_minute=60)
    def download_track(self):
        """ Download a single track """
        print("\n =========== Single Track Download =================")
        url = input("Enter Spotify track url:- ").strip()
        
        if not url:
            print("No URL provided")
            return False
        
        # Validate URL
        is_valid, resource_type = self.validate_spotify_url(url)
        if not is_valid:
            print("Invalid Spotify URL. Please enter a valid Spotify track URL")
            return False
        
        if resource_type != "track":
            print(f"Warning: URL appears to be a {resource_type}, not a track")
            proceed = input("Continue anyway? (y/n): ").strip().lower()
            if proceed not in ['y', 'yes']:
                return False
        
        # Validate resource availability
        print("\nValidating resource availability...")
        is_available, message, metadata = self.validate_resource(url)
        
        if not is_available:
            print(f"\n❌ Resource unavailable: {message}")
            retry = input("Try to download anyway? (y/n): ").strip().lower()
            if retry not in ['y', 'yes']:
                return False
        
        print(f"\n✅ {message}")
        if metadata:
            print(f"Track: {metadata.get('name', 'Unknown')}")
            print(f"Artist: {metadata.get('artists', [{}])[0].get('name', 'Unknown')}")
            duration = metadata.get('duration', 0)
            if duration:
                print(f"   Duration: {duration//60}:{duration%60:02d}")
        
        
        # Get user preferences
        self.get_user_preferences()
        print("===========================================================================")
        print(f"Starting Track download: {url}. This may take a few minutes...")
        start_time = time.time()
        output_template = str(self.__output_directory / "{title}.{output-ext}")
            
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"===========  Downloading Track URL: Attempt {attempt} of {MAX_RETRIES} =========== ")
            
            result = self.run_download(url, output_template)
            
            if hasattr(result, 'returncode'):
                if result.returncode == 100: # Metadata TypeError
                    self.log_error(f"Non -retryable error for {url}: Metadata TypeError")
                    return False
                elif result.returncode == 101: # No results found
                    self.log_error(f"Non -retryable error for {url}: No results found")
                    return False
            
            # Check if download was successful as well as record time it took to complete download
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                elapsed_time = time.time() - start_time
                self.log_success(f"Successfully downloaded: {url} in {elapsed_time:.1f} seconds!")
                print("==================================================================")
                return True
            
            # If we get here, there was an error
            elif attempt < MAX_RETRIES:
                self.log_error(f"Download failed. Retrying in {RETRY_DELAY} seconds...")
                print("==================================================================")
                time.sleep(RETRY_DELAY)
                
            # If the download failed
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                return False
              
        return False
    
    @rate_limit(calls_per_minute=60)
    def download_album(self):
        url = input("Enter Spotify Album url:- ").strip()
        
        if not url:
            print("No URL provided")
            return False
        
        # Validate URL
        is_valid, resource_type = self.validate_spotify_url(url)
        if not is_valid:
            print("Invalid Spotify URL. Please enter a valid Spotify album URL")
            return False

        if resource_type != "album":
            print(f"Warning: URL appears to be a {resource_type}, not an album")
            proceed = input("Continue anyway? (y/n): ").strip().lower()
            if proceed not in ['y', 'yes']:
                return False
        
        # Validate resource availability
        print("\nValidating album availability...")
        is_available, message, metadata = self.validate_resource(url)
        
        if not is_available:
            print(f"\n❌ Album unavailable: {message}")
            retry = input("Try to download anyway? (y/n): ").strip().lower()
            if retry not in ['y', 'yes']:
                return False
        
        print(f"\n✅ {message}")
        if metadata:
            print(f"   Album: {metadata.get('name', 'Unknown')}")
            print(f"   Artist: {metadata.get('artists', [{}])[0].get('name', 'Unknown')}")
            tracks = metadata.get('tracks', [])
            if tracks:
                available_tracks = sum(1 for t in tracks if t.get('available', True))
                print(f"   Tracks: {available_tracks}/{len(tracks)} available")

        # Get user preferences
        self.get_user_preferences()
        print("===========================================================================")
        print(f" ============== Starting Album download. This may take a few minutes")
        start_time = time.time()
        output_template = str(self.__output_directory / "{artist}/{album}/{title}.{output-ext}")
        
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"============== Downloading Album URL: attempt {attempt} of {MAX_RETRIES} ==============")
            result = self.run_download(url, output_template)
            
            if hasattr(result, 'returncode'):
                if result.returncode == 100:
                    self.log_error(f"Non - retryable error for {url}: Metadata TypeError")
                    return False
                elif result.returncode == 101:
                    self.log_error(f"Non-retryable error for {url}: No results found")
                    return False
                    
            # Check if download was successful as well as record time it took to complete download
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                elapsed_time = time.time() - start_time
                self.log_success(f"Successfully downloaded album: took {elapsed_time:.1f} seconds!")
                print("==================================================================")                
                return True
            
            # If we get here, there was an error
            if attempt < MAX_RETRIES:
                self.log_error(f"Download failed. Retrying in {RETRY_DELAY} seconds...")
                print("==================================================================")
                time.sleep(RETRY_DELAY)
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                print("==================================================================")                
                return False
            
        return False
         
    @rate_limit(calls_per_minute=60)
    def download_playlist(self):
        """Function to download playlist"""
        url = input("Enter Spotify Playlist url:- ").strip()
        
        if not url:
            print("No URL provided")
            return False
        
        # Validate URL
        is_valid, resource_type = self.validate_spotify_url(url)
        if not is_valid:
            print("Invalid Spotify URL. Please enter a valid Spotify playlist URL")
            return False
    
        if resource_type != "playlist":
            print(f"Warning: URL appears to be a {resource_type}, not a playlist")
            proceed = input("Continue anyway? (y/n): ").strip().lower()
            if proceed not in ['y', 'yes']:
                return False
        
        # Validate resource availability
        print("\nValidating playlist availability...")
        is_available, message, metadata = self.validate_resource(url)
        
        if not is_available:
            print(f"\n❌ Playlist unavailable: {message}")
            retry = input("Try to download anyway? (y/n): ").strip().lower()
            if retry not in ['y', 'yes']:
                return False
        
        print(f"\n✅ {message}")
        if metadata:
            print(f"   Playlist: {metadata.get('name', 'Unknown')}")
            tracks = metadata.get('tracks', [])
            if tracks:
                available_tracks = sum(1 for t in tracks if t.get('available', True))
                print(f"   Tracks: {available_tracks}/{len(tracks)} available")
    
        self.get_user_preferences()
        print("===========================================================================")
        print(f"============== Starting Playlist download. This may take a few minutes")
        start_time = time.time()
        output_template = str(self.__output_directory / "{playlist}/{title}.{output-ext}")
        
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"============== Downloading Playlist URL: Attempt {attempt}/{MAX_RETRIES} ==============")
            result = self.run_download(
                url, 
                output_template,
                ["--playlist-numbering", "--playlist-retain-track-cover"])
            
            if hasattr(result, 'returncode'):
                if result.returncode == 100:
                    self.log_error(f"Non -retryable error for {url}: Metadata TypeError")
                    return False
                elif result.returncode == 101: # No results found
                    self.log_error(f"Non -retryable error for {url}: No results found")
                    return False
                
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                elapsed_time = time.time() - start_time
                self.log_success(f"Successfully downloaded: {url} in {elapsed_time:.1f} seconds!")
                print("==================================================================")                                
                return True
            
            elif attempt < MAX_RETRIES:
                self.log_error(f"Download failed. Retrying in {RETRY_DELAY} seconds...")
                print("==================================================================")                
                time.sleep(RETRY_DELAY)
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                print("==================================================================")                
                return False
            
        return False

    @rate_limit(calls_per_minute=60)
    def download_from_file(self):
        """ Download various links from a file """
        filepath = input("Enter the directory of the file:- ").strip()
        
        if not filepath or not os.path.exists(filepath):
            self.log_failure(f"File not found: {filepath}")
            return False
        
        # Ask about validation
        print("\nResource Validation Options:")
        print("1. Validate all resources before downloading (recommended)")
        print("2. Skip validation and download directly")
        print("3. Validate but ignore cache")
        validation_choice = input("Choose option (1-3, default 1): ").strip() or "1"
        
        self.get_user_preferences()
        
        try:
            with open(filepath, 'r') as file:
                file_lines = [line.rstrip() for line in file if line.strip()]
        except FileNotFoundError:
            self.log_failure(f" File not found: {filepath}")
            return False
        except Exception as e:
            self.log_failure(f"Error reading the file: {e}")
            return False
        
        if not file_lines:
            self.log_failure("No URLs found in the text file")
            return False
        
        # Filter out already downloaded URLs
        urls_to_process = []
        for line in file_lines:
            if "# DOWNLOADED" not in line:
                # Extract URL (remove comments)
                url = line.split('#')[0].strip()
                if url:
                    urls_to_process.append(url)
        
        if not urls_to_process:
            print("All URLs in file are already marked as downloaded.")
            return True
        
        # Validate resources if chosen
        if validation_choice in ["1", "3"]:
            skip_cache = (validation_choice == "3")
            
            # Validate each URL individually
            validation_results = {}
            for url in urls_to_process:
                print(f"Validating: {url[:80]}...")
                is_available, message, metadata = self.validate_resource(url, skip_cache)
                validation_results[url] = (is_available, message, metadata)
            
            # Show validation summary
            available_count = sum(1 for result in validation_results.values() if result[0])
            total_count = len(validation_results)
            
            print(f"\nValidation Summary:")
            print(f"  ✅ Available: {available_count}/{total_count}")
            print(f"  ❌ Unavailable: {total_count - available_count}/{total_count}")
            
            # Ask user how to proceed
            print("\nDownload Options:")
            print("1. Download only available resources")
            print("2. Download all resources (including unavailable)")
            print("3. Show detailed validation results")
            print("4. Cancel download")
            
            download_choice = input("Choose option (1-4, default 1): ").strip() or "1"
            
            if download_choice == "3":
                print("\nDetailed Validation Results:")
                for url, (is_available, message, _) in validation_results.items():
                    status = "✅" if is_available else "❌"
                    print(f"  {status} {url[:60]}...")
                    print(f"     {message}")
                
                print("\nNow choose download option:")
                print("1. Download only available resources")
                print("2. Download all resources (including unavailable)")
                print("3. Cancel download")
                download_choice = input("Choose option (1-3, default 1): ").strip() or "1"
            
            if download_choice == "4" or (download_choice == "3" and download_choice == "3"):
                print("Download cancelled.")
                return False
            
            # Filter URLs based on choice
            if download_choice == "1":
                urls_to_download = [url for url in urls_to_process if validation_results[url][0]]
                print(f"\nDownloading {len(urls_to_download)} available resources...")
            else:
                urls_to_download = urls_to_process
                print(f"\nDownloading all {len(urls_to_download)} resources...")
        else:
            urls_to_download = urls_to_process
            print(f"\nDownloading {len(urls_to_download)} resources without validation...")
        
        success_count = 0 # How many urls download successfully
        failed_count = 0 # How many urls failed to download
        
        for i, url in enumerate(urls_to_download, 1):
            print("===========================================================================")
            print(f"Processing URL {i}/{len(urls_to_download)}: {url[:80]}...")
            
            clean_url = url.split('#')[0].strip()
            
            # Determine output template based on URL type
            if "playlist" in url.lower():
                output_template = str(self.__output_directory / "{playlist}/{title}.{output-ext}")
                additional_args = ["--playlist-numbering", "--playlist-retain-track-cover"]
            elif "album" in url.lower():
                output_template = str(self.__output_directory / "{artist}/{album}/{title}.{output-ext}")
                additional_args = None
            else:
                output_template = str(self.__output_directory / "{artist} - {title}.{output-ext}")
                additional_args = None
                
            success = False
            non_retry_error = False
            for attempt in range(1, MAX_RETRIES + 1):
                print(f"Downloading URL {i}: Attempt {attempt} of {MAX_RETRIES} tries")
                
                try:
                    result = self.run_download(url, output_template, additional_args)
                    
                    if hasattr(result, 'returncode'):
                        if result.returncode == 100: # Metadata TypeError
                            self.log_error(f"Non -retryable error for {url}: Metadata TypeError")
                            non_retry_error = True
                            break
                        elif result.returncode == 101: # No results found
                            self.log_error(f"Non -retryable error for {url}: No results found")
                            non_retry_error = True
                            break
                        
                    if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                        success = True
                        break
                    elif attempt < MAX_RETRIES:
                        self.log_error(f"Download failed. Retrying in {RETRY_DELAY} seconds...")
                        time.sleep(RETRY_DELAY)
                except Exception as e:
                    self.log_failure(f"Exception during the download {e}")
                    
            if success:
                success_count += 1
                self.log_success(f"Successfully download {url}")
                
                # Update the original file lines
                for idx, line in enumerate(file_lines):
                    if line.startswith(clean_url):
                        if "#" in line:
                            parts = line.split('#')
                            file_lines[idx] = f"{parts[0].strip()} # DOWNLOADED"
                        else:
                            file_lines[idx] = f"{clean_url} # DOWNLOADED"
                        break
            else:
                failed_count += 1
                self.log_failure(f"Failed download {url}")
                # Update the original file lines
                for idx, line in enumerate(file_lines):
                    if line.startswith(clean_url):
                        if "#" in line:
                            parts = line.split('#')
                            file_lines[idx] = f"{parts[0].strip()} # FAILED"
                        else:
                            file_lines[idx] = f"{clean_url} # FAILED"
                        break
        
        # Update the file
        try: 
            with open(filepath, 'w') as file:
                file.write("\n".join(file_lines))    
        except Exception as e:
            self.log_failure(f"Error updating the file: {e}")
        
        print(f"\nDownload Summary:")
        print(f" Successful Downloads: {success_count}")
        print(f"Failed Downloads: {failed_count}")
        print(f"Total Downloadeds: {len(urls_to_download)}")
        
        return failed_count == 0
    
    @rate_limit(calls_per_minute=60)
    def search_a_song(self):
        """ Search for a song and download"""    
        song_query = input("What is the name of the song you're looking for: ").strip()

        if not song_query:
            print("No input provided")
            return False
        
        self.get_user_preferences()
        search_time = time.time()
        print("Searching for the song. Browsing through the web.")
        
        output_template = str(self.__output_directory / "{title}.{output-ext}")
        
        for attempt in range(1, MAX_RETRIES + 1):
            print("===========================================================================")
            print(f"Search and download attempt: {attempt} of {MAX_RETRIES}:")
            result = self.run_download(song_query, output_template)
            
            
            if hasattr(result, 'returncode'):
                if result.returncode == 100: 
                    self.log_error(f"Non -retryable error: Metadata TypeError")
                    return False
                elif result.returncode == 101: 
                    self.log_error(f"Non -retryable error: No results found")
                    return False
                
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                self.log_success(f"Successfully downloaded: {song_query}")
                print("==================================================================")                
                return True
            
            elif attempt < MAX_RETRIES:
                self.log_error(f"Download failed. Retrying in {RETRY_DELAY} seconds....")
                print("==================================================================")                                
                time.sleep(RETRY_DELAY)

            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {song_query}")
                print("==================================================================")                                
                return False   

    # Special download functions -------------------------------------------------------
    def download_user_playlist(self):
        """
        Download a user's playlist (requires authentication)
        """
        print("\n=== User Playlist Download ===")
        print("Note: This requires Spotify authentication")
        print("This requires a Spotify Account")
        print("You will be redirected to the Spotify website for authorization")
        
        self.get_user_preferences()
        output_template = str(self.__output_directory / "{playlist}/{title}.{output-ext}")
        
        try:
            print("Downloading user's playlist from Spotify...")
            result = subprocess.run([
                "spotdl",
                "download",
                "all-user-playlists",
                "--user-auth",
                "output", output_template,
                "overwrite", "skip",
                "--bitrate", self.__audio_quality,
                "--format", self.__audio_format,
            ],
                stdout=sys.stdout,
                stderr=subprocess.PIPE,
                text=True
            )
            stderr = result.stderr or ""
            
            # Error handling for specific errors during download process
            # ------------ NON -RETRYABLE ERRORS ------------
            if "TypeError: expected string or bytes-line object, got 'NoneType'" in stderr:
                self.log_error("Metadata Type Error")
                return False
            
            if "LookupError: No results found for song:" in stderr:
                self.log_error("No results found")
                return False
            
            # ------------ RETRYABLE ERROR ------------
            if "AudioProviderError" in stderr:
                self.log_error(f"YT-DLP audio provider error")
            # -----------------------------------------------------------------------------------

            if result.stdout:
                print(f"spotdl output: {result.stdout.strip()}")
            
            if result.stderr and not ("AudioProviderError" in stderr):
                self.log_error(f"spotdl stderr: {result.stderr.strip()}")
            
            if result.returncode == 0:
                self.log_success("Successfully downloaded user playlists")
                print("==================================================================")                                
                return True
            else:
                self.log_failure(f"Failed to download user playlists. Return code: {result.returncode}")
                print("==================================================================")                                                
                return False
            
        except Exception as e:
            self.log_error(f"Unexpected exception: {e}")
            print("==================================================================")                                
            return False
        
    def download_user_liked_songs(self):
        """Download a user's liked songs"""
        print("\n=== User Liked Song's Download ===")
        print("Note: This requires Spotify authentication")
        print("This requires a Spotify Account")
        print("You will be redirected to the Spotify website for authorization")
        print("==================================================================")                                
        
        self.get_user_preferences()
        output_template = str(self.__output_directory / "{title}/{artist}.{output-ext}")
        
        try:
            print("==================================================================")                                
            print("Downloading the User's Liked Song's from Spotify")
            result = subprocess.run([
                "spotdl",
                "download",
                "saved",
                "--user-auth",
                "--output", output_template,
                "--overwrite", "skip",
                "--bitrate", self.__audio_quality,
                "--format", self.__audio_format,
            ],
                stdout=sys.stdout,
                stderr=subprocess.PIPE,
                text=True
            )
            stderr = result.stderr or ""
            
            # Error handling for specific errors during download process
            # ------------ NON -RETRYABLE ERRORS ------------
            if "TypeError: expected string or bytes-line object, got 'NoneType'" in stderr:
                self.log_failure("Metadata Type Error")
                return False
            
            if "LookupError: No results found for song:" in stderr:
                self.log_failure("No results found")
                return False
            
            # ------------ RETRYABLE ERROR ------------
            if "AudioProviderError" in stderr:
                self.log_error(f"YT-DLP audio provider error")

            if result.stdout:
                self.log_success(f"spotdl output: {result.stdout.strip()}")
            
            if result.stderr and not ("AudioProviderError" in stderr):
                self.log_failure(f"spotdl stderr: {result.stderr.strip()}")
            
            if result.returncode == 0:
                self.log_success("Successfully downloaded user playlist")
                print("==================================================================")                  
                return True
            else:
                self.log_failure(f"Failed to download user playlists. Return code: {result.returncode}")
                print("==================================================================")  
                return False
            
        except Exception as e:
            self.log_error(f"Unexpected exception: {e}") 
            print("==================================================================")              
            return False

    def download_user_saved_albums(self):
        """ Download a user's saved albums """
        print("\n=== User Playlist Download ===")
        print("Note: This requires Spotify authentication")
        print("This requires a Spotify Account")
        print("You will be redirected to the Spotify website for authorization")
        
        self.get_user_preferences()
        output_template = str(self.__output_directory / "{artist}/{album}/{title}.{output-ext}")
        print("==================================================================")
        try:
            print("Downloading the User's Saved Albums")
            result = subprocess.run([
                "spotdl",
                "download",
                "all-user-saved-albums",
                "--user-auth",
                "--output", output_template,
                "--overwrite", "skip",
                "--bitrate", self.__audio_quality,
                "--format", self.__audio_format,
            ],
                stdout=sys.stdout,
                stderr=subprocess.PIPE,
                text=True
            )
            stderr = result.stderr or ""
            
            # Error handling for specific errors during download process
            # ------------ NON -RETRYABLE ERRORS ------------
            if "TypeError: expected string or bytes-line object, got 'NoneType'" in stderr:
                self.log_error("Metadata Type Error")
                return False
            
            if "LookupError: No results found for song:" in stderr:
                self.log_error("No results found")
                return False
            
            # ------------ RETRYABLE ERROR ------------
            if "AudioProviderError" in stderr:
                self.log_error(f"YT-DLP audio provider error")
            # -----------------------------------------------------------------------------------

            if result.stdout:
                print(f"spotdl output: {result.stdout.strip()}")
            
            if result.stderr and not ("AudioProviderError" in stderr):
                self.log_failure(f"spotdl stderr: {result.stderr.strip()}")
            
            if result.returncode == 0:
                self.log_success("Successfully downloaded user saved albums")
                print("==================================================================")
                return True
            else:
                self.log_failure(f"Failed to download user saved albums. Return code: {result.returncode}")
                print("==================================================================")
                return False
            
        except Exception as e:
            self.log_error(f"Unexpected exception: {e}") 
            return False

    # Spotdl helpers ----------------------------------------------------------------------------
    @staticmethod
    def check_spotdl():
        """
        Check if spotdl is installed (cache spotdl)
        """
        if shutil.which("spotdl"):
            print("spotdl is already installed")
            
            # Check version
            try:
                result = subprocess.run(
                    ["spotdl", "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                    timeout=10
                )
                if result.returncode == 0:
                    version = result.stdout.strip()
                    print(f"spotdl version: {version}")
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
                print("Could not determine spotdl version")
                return False
        else:
            print("spotdl not found. Installing...")
            
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "spotdl"])
                print("spotdl installed successfully")
                return True
            except subprocess.CalledProcessError as e:
                print(f"Failed to install spotdl: {e}")
                return False
    
    @staticmethod     
    def show_spotdl_help():
        """
        Display spotdl help
        """
        try:
            result = subprocess.run(
                ["spotdl", "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            print("\n" + "="*50)
            print("SPOTDL HELP")
            print("="*50)
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"Could not get spotdl help: {e}")
    
    @staticmethod     
    def program_info():
        """
        Display program information
        """
        print("="*80)
        print("Interactive Spotify Playlist/Album/Track Downloader")
        print("="*80)
        print("This is a simple to use downloader that can help in downloading")
        print("albums/playlist/single tracks etc from Spotify")
        print("\n" + "-"*80)
        print("Each function explained:")
        print("\n=== Basic Functions: Can work without having a Spotify account ===")
        print("* download_track_album - Downloads a single track or a single album")
        print("* download_playlist - Downloads a playlist and compile it into a single folder")
        print("* download_from_file - Downloads from a text file")
        print("* search_a_song - Search for a song & download it")
        print("\n=== Special Functions: For those with a Spotify account (requires authentication) ===")
        print("* download_user_playlist - Downloads a user's playlist from their Spotify Account")
        print("* download_user_liked_songs - Downloads a user's liked songs from their Spotify Account")
        print("* download_user_saved_albums - Downloads a user's saved albums from their Spotify Account")
        print("\n=== Help functions: Provides help with the program ===")
        print("* program_info - Provides context on the program")
        print("* check_spotdl - Checks for spotdl & installs it if doesn't exist")
        print("* show_spotdl_help - Provides context on spotdl commands")
        print("="*80)

""" The downloader """
def display_menu() -> None:
    """Display the main menu."""
    menu = """
    ========================================================================
    INTERACTIVE SPOTIFY DOWNLOADER
    ========================================================================
    Select an option:
    1.  Download Track
    2.  Download Album
    3.  Download Playlist
    4.  Download from Text File
    5.  Search and Download Song
    6.  Download User Playlists (Requires Spotify Account)
    7.  Download Liked Songs (Requires Spotify Account)
    8.  Download Saved Albums (Requires Spotify Account)
    9.  Check/Install spotdl
    10. Show spotdl Help
    11. Show Program Info
    12. Exit
    ========================================================================
    """
    print(menu)

def main():
    """Main function to run the Spotify Downloader."""
    print("==================================================================")
    print("Initializing Spotify Downloader...")
    
    # Check spotdl installation
    if not Spotify_Downloader.check_spotdl():
        print("==================================================================")
        print("\nFailed to install spotdl. Please install it manually using:")
        print("pip install spotdl")
        print("Then run the program again.")
        print("==================================================================")
        return
    
    downloader = Spotify_Downloader()
    
    while True:
        display_menu()
        print("==================================================================")
        choice = input("\nEnter your choice (1-12):- ").strip()
        
        actions = {
            "1": downloader.download_track,
            "2": downloader.download_album,
            "3": downloader.download_playlist,
            "4": downloader.download_from_file,
            "5": downloader.search_a_song,
            "6": downloader.download_user_playlist,
            "7": downloader.download_user_liked_songs,
            "8": downloader.download_user_saved_albums,
            "9": downloader.check_spotdl,
            "10": Spotify_Downloader.show_spotdl_help,
            "11": Spotify_Downloader.program_info,
        }
        
        if choice == "12":
            print("\nThank you for using Spotify Downloader. Goodbye!")
            print("Cleaning up empty directories...")
            downloader.cleanup_directory()
            print("==================================================================")
            
            break
        
        action = actions.get(choice)
        if action:
            action()
        else:
            print("==================================================================")
            print("Invalid choice. Please enter a number between 1 and 12.")
            continue
        
        # Ask if user wants to continue (except for help/info actions)
        if choice not in ["10", "11"]:
            cont = input("\nDo you want to perform another operation? (y/n): ").strip().lower()
            if cont not in ['y', 'yes']:
                print("==================================================================")
                print("\nThank you for using Spotify Downloader. Goodbye!")
                break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user.")
        print("Goodbye!")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        print("Please check the error log for details.")