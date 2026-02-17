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

Please use the latest version of YT-DLP, upgrade it using "pip install --upgrade yt-dlp" or "yt-dlp -U" depending on how you installed it
Additionally make sure ffmpeg is installed, as that is necessary to parse the music file's metadata if not you will receive postprocessing error in your output

Enjoy!
"""

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
from colorama import init, Fore, Style

from CookieManager import CookieManager
from EnhancedMenu import Enhanced_Menu
from Logs_Handler import Logs_Manager
from Downloader_Utils import DownloaderUtils

init(autoreset=True)

""" =========================================== Pre Config ===========================================
This part of the pre-configuration of the downloader, it can be change. Each part is explained below:
* MAX_RETRIES - No of times the downloader can retry on a link (subject to change)
* RETRY_DELAY - The delay between each retry (subject to change)
======================================================================================================= """

MAX_RETRIES = 3
RETRY_DELAY = 10
DOWNLOAD_TIMEOUT = 120
COOKIE_DIRECTORY = r"cookies"

os.makedirs(COOKIE_DIRECTORY, exist_ok=True)

class Youtube_Downloader:
    """Downloader Class that handles the downloading process"""
    def __init__(self):
        """Initialize the downloader with default values"""
        if 'MAX_RETRIES' not in globals():
            global MAX_RETRIES, RETRY_DELAY, DOWNLOAD_TIMEOUT
            MAX_RETRIES = 3
            RETRY_DELAY = 5
            DOWNLOAD_TIMEOUT = 300
            
        self.__output_directory = Path("Albums")
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.__filepath = r"links/youtube_links.txt"
        self.__configuration_file = r"config/youtube_downloader.json"
        self.cookie_manager = CookieManager()
        self.log_manager = Logs_Manager()
        self.utils = DownloaderUtils()
        self.use_cookies = False
        self.__output_directory.mkdir(parents=True, exist_ok=True)
        Path("links").mkdir(parents=True, exist_ok=True)
        try:
            self.load_config()
        except Exception as e:
            self.log_manager.log_error(f"Error loading config: {e}")

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
            if "output_directory" in config:
                self.__output_directory = Path(config["output_directory"])
            if "audio_quality" in config:
                self.__audio_quality = config["audio_quality"]
            if "audio_format" in config:
                self.__audio_format = config["audio_format"]
            if "use_cookies" in config:
                self.use_cookies = config["use_cookies"]
        except Exception as e:
            self.log_manager.log_error(f"Error loading configuration: {e}")
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
            self.log_manager.log_error(f"Error saving configuration: {e}")

    #  ============================================= Helper Functions & Resource Validation Functions =============================================
    def get_user_preferences(self):
        """Takes in user input for the download settings"""
        Enhanced_Menu.print_header("Download Settings", "Configure your music conversion preferences")
        
        # Handles audio quality of music conversion       
        while True:
            audio_quality_input = Enhanced_Menu.get_input("What bitrate would you like (enter 'choice' to see options): ", "str", default=self.__audio_quality)
            if not audio_quality_input:
                self.__audio_quality = "320k"
                break
            if audio_quality_input == 'choice':
                print(f"\n{Fore.CYAN}Available qualities:{Style.RESET_ALL}")
                print("  auto     - Let yt-dlp choose the best")
                print("  320k     - High quality (default)")
                print("  256k     - Very good quality")
                print("  192k     - Good quality")
                print("  128k     - Standard quality")
                print("  8k-160k  - Lower qualities")
                continue
            valid_bitrates = ["auto", "disable", "8k", "16k", "24k", "32k", "40k", "48k", "64k",
                              "80k", "96k", "112k", "128k", "160k", "192k", "224k", "256k", "320k"]
            if audio_quality_input in valid_bitrates:
                self.__audio_quality = audio_quality_input.lower()
                break
            Enhanced_Menu.print_status("Invalid bitrate. The downloader doesn't support these values", "error")
            
        # Handles audio format from the user
        while True:
            audio_format_input = Enhanced_Menu.get_input("What format would you like (enter 'choice' to see options): ", "str", default=self.__audio_format)
            if not audio_format_input:
                self.__audio_format = "mp3"
                break
            if audio_format_input == 'choice':
                print(f"\n{Fore.CYAN}Available formats:{Style.RESET_ALL}")
                print("  mp3  - Most compatible (default)")
                print("  m4a  - Apple format, good quality")
                print("  flac - Lossless audio")
                print("  opus - Excellent compression")
                print("  ogg  - Open format")
                print("  wav  - Uncompressed")
                continue
            if audio_format_input in ["mp3", "flac", "ogg", "opus", "m4a", "wav"]:
                self.__audio_format = audio_format_input
                break
            Enhanced_Menu.print_status("Invalid format. Downloader doesn't support this format", "error")
            
        # Choose your output directory
        output_path = Enhanced_Menu.get_input("Enter output directory (default: Albums): ", "str").strip()
        if output_path:
            self.__output_directory = Path(output_path)
        else:
            self.__output_directory = Path("Albums")
        self.__output_directory.mkdir(parents=True, exist_ok=True)
        
        # Cookie choice
        Enhanced_Menu.print_status("Cookie Settings", "info")
        print(f"\n{Fore.CYAN}Cookies can help with:{Style.RESET_ALL}")
        print(" Age-restricted content")
        print(" Region-restricted videos")
        print(" Private playlists")
        cookie_choice = Enhanced_Menu.get_input("Use cookies for authentication? (y/n): ", "yn", default=True)
        if cookie_choice:
            self.use_cookies = True
            Enhanced_Menu.print_status("Note: Make sure you have extracted the cookies beforehand, if make use of Cookie Manager to help you", "info")
        else:
            self.use_cookies = False

    def validate_youtube_url(self, url: str) -> bool:
        """Validate if the URL input is a proper YouTube URL"""
        
        # Subject to edit
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
            self.log_manager.log_success("Cleaned up empty directories")

    def extract_youtube_id(self, url: str) -> str:
        """Extract YouTube ID from URL"""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)',
            r'youtube\.com/playlist\?list=([\w-]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def validate_resource(self, url: str) -> Tuple[bool, str, Optional[Dict]]:
        """Validate if a resource is available before downloading to the device"""
        try:
            # Run a small command 
            command = ["yt-dlp",
                       "--skip-download",
                       "--flat-playlist",
                       "--dump-json",        # <-- Added to get JSON metadata
                       "--no-warnings",
                       url]
            result = subprocess.run(
                command, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
                timeout=30, check=False
            )
            
            # Check on output and get metadata
            if result.returncode == 0:
                try:
                    # Handle multiple JSON lines (for playlists)
                    metadata = None
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            metadata = json.loads(line)
                            break
                    
                    if metadata:
                        title = metadata.get('title', 'Unknown')
                        if metadata.get('availability') == 'unavailable':
                            return False, "Video unavailable", metadata
                        return True, f"Available - {title}", metadata
                    return True, "Music Resource Available", None
                except json.JSONDecodeError:
                    return True, "Music Resource Available", None
            
            # If result or output contains errors
            else:
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
        
        # Convert string of download size,
        units = {
            'B': 1, 'K': 1024, 'M': 1024 ** 2, 'G': 1024 ** 3, 'T': 1024 ** 4,
            'KB': 1024, 'MB': 1024 ** 2, 'GB': 1024 ** 3, 'TB': 1024 ** 4,
            'KIB': 1024, 'MIB': 1024 ** 2, 'GIB': 1024 ** 3, 'TIB': 1024 ** 4
        }
        
        # Match with regex
        match = re.match(r'([\d\.]+)\s*(\w*)', size_str)
        if not match:
            return None
        
        # Check for value in units
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
        
        # For cookie options
        if self.use_cookies and self.cookie_manager.current_cookie_file:
            cookie_args = self.cookie_manager.get_arguments()
            if cookie_args:
                command.extend(cookie_args)
                self.log_manager.log_success("Using cookies from authentication")
            else:
                self.log_manager.log_error("Error using cookies")
                
        # Additional arguments for specific downloads
        if additional_args:
            if isinstance(additional_args, list):
                command.extend(additional_args)
            else:
                command.append(additional_args)
        command.append(url)
        
        try:
            # Initialize progress bar with tqdm
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
            output_lines = []  # capture all output for error analysis
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                output_lines.append(line)
                if "[download]" in line:
                    try:
                        # Parse percentage
                        percent_match = re.search(r'(\d+\.?\d*)%', line)
                        if percent_match:
                            percent = float(percent_match.group(1))
                            progress_bar.set_description(f"{Fore.CYAN}Downloading: {percent:.1f}%{Style.RESET_ALL}")
                        
                        # Parse possible total download size
                        size_match = re.search(r'of\s+([\d\.]+\s*[KMGT]?i?B)', line)
                        if size_match and progress_bar.total is None:
                            total_str = size_match.group(1)
                            total_bytes = self.parse_size(total_str)
                            if total_bytes:
                                progress_bar.total = total_bytes
                                
                        # Parse downloaded size
                        downloaded_match = re.search(r'([\d\.]+\s*[KMGT]?i?B)\s+at', line) or \
                                           re.search(r'([\d\.]+\s*[KMGT]?i?B)\s+ETA', line) or \
                                           re.search(r'([\d\.]+\s*[KMGT]?i?B)\s*\/', line)
                        if downloaded_match:
                            downloaded_str = downloaded_match.group(1)
                            downloaded_bytes = self.parse_size(downloaded_str)
                            if downloaded_bytes:
                                progress_bar.n = downloaded_bytes
                                
                        # Parse download speed
                        speed_match = re.search(r'at\s+([\d\.]+\s*[KMGT]?i?B/s)', line)
                        if speed_match:
                            speed = speed_match.group(1)
                            progress_bar.set_postfix_str(f"Speed: {speed}")
                            
                        # Parse Estimated download time
                        eta_match = re.search(r'ETA\s+([\d:]+)', line)
                        if eta_match:
                            eta = eta_match.group(1)
                            progress_bar.set_postfix_str(f"ETA: {eta}")
                        progress_bar.refresh()
                    except Exception:
                        continue
                    
                # If the download is completed or file already exists
                if "100%" in line or "already been downloaded" in line or "[Merger]" in line:
                    if progress_bar.total and progress_bar.n < progress_bar.total:
                        progress_bar.n = progress_bar.total
                    progress_bar.set_description(f"{Fore.GREEN}Downloaded{Style.RESET_ALL}")
                    progress_bar.set_postfix_str("")
                    progress_bar.refresh()
            
            # Close progress bar and check command output
            process.wait()
            progress_bar.close()
            full_output = "\n".join(output_lines)
            if process.returncode == 0:
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=full_output,
                    stderr=""
                )
            else:
                error_msg = f"Download failed for {url} with code {process.returncode}"
                if "unavailable" in full_output.lower():
                    error_msg += " - Video is unavailable"
                elif "private" in full_output.lower():
                    error_msg += " - Video is private"
                elif "age restriction" in full_output.lower():
                    error_msg += " - Age restricted"
                elif "copyright" in full_output.lower():
                    error_msg += " - Copyright restriction"
                elif "format" in full_output.lower():
                    error_msg += " - Format not available"
                elif "ffmpeg" in full_output.lower():
                    error_msg += " - FFmpeg conversion error"
                else:
                    # extract first 200 chars of error
                    error_msg += f" - Error: {full_output[-200:] if full_output else 'Unknown'}"
                self.log_manager.log_failure(error_msg)
                raise subprocess.CalledProcessError(
                    process.returncode,
                    command,
                    output=full_output,
                    stderr=""
                )
        except FileNotFoundError:
            error_msg = "yt-dlp not found. Please install it with: pip install yt-dlp"
            self.log_manager.log_error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error in run_download: {e}"
            self.log_manager.log_error(error_msg)
            if 'progress_bar' in locals():
                progress_bar.close()
            raise

    def rate_limit(calls_per_minute=60):
        """Rate limit decorator to avoid blockage from (Improved)"""
        def decorator(func):
            last_called = [0.0]
            call_lock = threading.Lock()
            @wraps(func)
            def wrapper(*args, **kwargs):
                with call_lock:
                    elapsed_time = time.time() - last_called[0]
                    wait_time = (60.0 / calls_per_minute) - elapsed_time
                    if wait_time > 0:
                        time.sleep(wait_time)
                    last_called[0] = time.time()
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_called[0] = time.time() - (60.0 / calls_per_minute)
                        raise
            return wrapper
        return decorator

    #  ============================================= Main Download functions =============================================
    def _download_item(self, item_type: str, url_prompt: str, output_template: str, additional_args: list = None, confirm_large: bool = False):
        """Unified download function for tracks, albums, and playlists"""
        while True:
            print("\n" + "=" * 55)
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header(f"Download {item_type.title()}")
            
            # Get URL from user
            url = Enhanced_Menu.get_input(f"Enter YouTube Music {url_prompt} (or 'back' to return)", "str")
            if url.lower() == 'back':
                return False
            
            if not url:
                Enhanced_Menu.print_status("No URL provided", "error")
                continue
            
            # Validate URL format
            if not self.validate_youtube_url(url):
                Enhanced_Menu.print_status("Invalid YouTube URL. Enter a valid YouTube/YouTube Music URL", "error")
                continue
            
            # Validate resource availability
            Enhanced_Menu.print_status("Validating resource...", "info")
            is_valid, message, metadata = self.validate_resource(url)
            
            if not is_valid:
                Enhanced_Menu.print_status(f"Resource validation failed: {message}", "failure")
                self.log_manager.log_failure(f"Resource validation failed for {url}: {message}")
                continue
            else:
                Enhanced_Menu.print_status(f"Resource validated: {message}", "success")
                
                # For large playlists/albums, show count and ask for confirmation
                if confirm_large and metadata:
                    if 'playlist_count' in metadata:
                        count = metadata['playlist_count']
                        if count > 50:  # Arbitrary threshold
                            Enhanced_Menu.print_status(
                                f"This {item_type} contains {count} items. This may take a while.", 
                                "warning"
                            )
                            if not Enhanced_Menu.get_input("Continue with download? (y/n)", "yn", default=False):
                                Enhanced_Menu.print_status("Download cancelled", "info")
                                continue
            
            # Get user preferences if they want to configure
            if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
                self.get_user_preferences()
            
            # Confirm settings before download
            Enhanced_Menu.print_section("Download Settings")
            print(f"  • Type: {Fore.CYAN}{item_type.title()}{Style.RESET_ALL}")
            print(f"  • Format: {Fore.CYAN}{self.__audio_format}{Style.RESET_ALL}")
            print(f"  • Quality: {Fore.CYAN}{self.__audio_quality}{Style.RESET_ALL}")
            print(f"  • Output: {Fore.CYAN}{self.__output_directory}{Style.RESET_ALL}")
            print()
            
            if not Enhanced_Menu.get_input("Proceed with download? (y/n)", "yn", default=True):
                Enhanced_Menu.print_status("Download cancelled", "info")
                continue
            
            Enhanced_Menu.print_status(f"Starting {item_type} download...", "info")
            
            # Attempt download with retries
            success = self._download_with_retry(url, output_template, additional_args, item_type)
            
            if success:
                time.sleep(0.5)  # Small delay for clean UI
                
                # Ask if user wants to download another
                another = Enhanced_Menu.get_input(
                    f"\nDownload another {item_type}? (y/n): ", 
                    "yn", 
                    default=True
                )
                if another:
                    continue
                else:
                    return True
            else:
                # Download failed after all retries
                retry = Enhanced_Menu.get_input(
                    f"\nDownload failed. Try another {item_type}? (y/n): ", 
                    "yn", 
                    default=True
                )
                if retry:
                    continue
                else:
                    return False

    def _download_with_retry(self, url: str, output_template: str, additional_args: list = None, item_type: str = "item") -> bool:
        """Unified retry logic for downloads"""
        for attempt in range(1, MAX_RETRIES + 1):
            Enhanced_Menu.print_section(f"Downloading {item_type} (Attempt {attempt}/{MAX_RETRIES})")
            
            if attempt > 1:
                print(f"Waiting {RETRY_DELAY} seconds before retry...")
                time.sleep(RETRY_DELAY)
            
            try:
                result = self.run_download(url, output_template, additional_args)
                
                # Check if download was successful
                if result and result.returncode == 0:
                    self.log_manager.log_success(f"Successfully downloaded {item_type}: {url}")
                    
                    # Clean up empty directories after successful download
                    if item_type in ['album', 'playlist']:
                        self.cleanup_directory()
                    
                    return True
                else:
                    # This shouldn't happen if run_download raises on error, but just in case
                    raise subprocess.CalledProcessError(
                        result.returncode if result else -1,
                        f"yt-dlp {url}",
                        output=result.stdout if result else "",
                        stderr=result.stderr if result else ""
                    )
                    
            except subprocess.CalledProcessError as e:
                error_msg = str(e)
                if attempt < MAX_RETRIES:
                    self.log_manager.log_error(f"Attempt {attempt} failed for {item_type}: {error_msg[:100]}")
                else:
                    self.log_manager.log_failure(f"Failed after {MAX_RETRIES} attempts: {url}")
                    
            except Exception as e:
                self.log_manager.log_error(f"Unexpected error in attempt {attempt}: {e}")
                if attempt == MAX_RETRIES:
                    self.log_manager.log_failure(f"Failed after {MAX_RETRIES} attempts: {url}")
        
        return False

    # Replace the original functions with simplified versions
    def download_track(self):
        """Download a single track"""
        return self._download_item(
            item_type="track",
            url_prompt="track URL",
            output_template=str(self.__output_directory / "%(artist)s - %(title)s.%(ext)s"),
            confirm_large=False
        )

    def download_album(self):
        """Download an album"""
        return self._download_item(
            item_type="album",
            url_prompt="album URL",
            output_template=str(self.__output_directory / "%(artist)s/%(album)s/%(artist)s - %(title)s.%(ext)s"),
            confirm_large=True
        )

    def download_playlist(self):
        """Download a playlist"""
        return self._download_item(
            item_type="playlist",
            url_prompt="playlist URL",
            output_template=str(self.__output_directory / "%(playlist)s/%(artist)s - %(title)s.%(ext)s"),
            confirm_large=True,
            additional_args=["--yes-playlist"]  # Ensure playlist is downloaded fully
        )

    # Also update download_channel to use the unified retry logic
    def download_channel(self):
        """Download all videos from a YouTube channel"""
        print("\n" + "=" * 50)
        Enhanced_Menu.print_header("Channel Download")
        print("=" * 50)
        Enhanced_Menu.print_status("Warning: This may download many videos", "error")
        Enhanced_Menu.print_status("It could take a long time and use significant disk space", "error")
        print("=" * 50)
        
        channel_url = Enhanced_Menu.get_input("Enter YouTube channel URL: ", "str")
        if not channel_url:
            print("No URL provided")
            return False
        
        if not self.validate_youtube_url(channel_url):
            Enhanced_Menu.print_status("Invalid YouTube URL. Please enter a valid YouTube channel URL", "error")
            return False
        
        # Check if it's a channel (not a video/playlist)
        if "/watch?" in channel_url or "/playlist?" in channel_url:
            Enhanced_Menu.print_status("This doesn't appear to be a channel URL", "error")
            return False
        
        confirm = Enhanced_Menu.get_input("Are you sure you want to download ALL videos from this channel? (y/n)", "yn", default=False)
        if not confirm:
            Enhanced_Menu.print_status("Channel download cancelled", "info")
            return False
        
        if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
            self.get_user_preferences()
        
        print(f"Starting Channel download. This may take a VERY long time...")
        
        output_template = str(self.__output_directory / "%(channel)s/%(artist)s - %(title)s.%(ext)s")
        additional_args = [
            "--yes-playlist",
            "--download-archive", "downloaded_channels.txt"
        ]
        
        return self._download_with_retry(channel_url, output_template, additional_args, "channel")

    # Update download_from_file to use unified retry
    def download_from_file(self):
        """Download various links from a file"""
        Enhanced_Menu.print_header("Batch Download", "Download from a text file containing links")
        
        filepath = Enhanced_Menu.get_input("Enter the directory of the file: ", "str", default=self.__filepath)
        if not filepath:
            filepath = self.__filepath
            
        if not os.path.exists(filepath):
            self.log_manager.log_failure(f"File not found: {filepath}")
            Enhanced_Menu.print_status(f"File not found: {filepath}", "error")
            return False
        
        self.get_user_preferences()
        
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                file_lines = [line.rstrip() for line in file if line.strip()]
        except Exception as e:
            self.log_manager.log_failure(f"Error reading the file: {e}")
            return False
        
        if not file_lines:
            self.log_manager.log_failure("No URLs found in the text file")
            return False
        
        Enhanced_Menu.print_status(f"Found {len(file_lines)} URLs to process", "info")
        
        success_count = 0
        failed_count = 0
        
        # Create progress bar for batch download
        with tqdm(total=len(file_lines), desc="Batch Progress", unit="items") as pbar:
            for i, url in enumerate(file_lines, 1):
                pbar.set_description(f"Processing {i}/{len(file_lines)}")
                
                clean_url = url.split('#')[0].strip()
                
                # Skip already downloaded items
                if "# DOWNLOADED" in url:
                    self.log_manager.log_success(f"Skipping already downloaded: {clean_url}")
                    success_count += 1
                    pbar.update(1)
                    continue
                
                # Validate URL
                print("\nValidating URL...")
                is_valid, message, metadata = self.validate_resource(clean_url)
                if not is_valid:
                    self.log_manager.log_failure(f"URL validation failed: {clean_url} - {message}")
                    file_lines[i - 1] = f"{clean_url} # VALIDATION_FAILED: {message}"
                    failed_count += 1
                    pbar.update(1)
                    continue
                
                # Determine output template based on URL type
                if "playlist" in clean_url.lower():
                    output_template = str(self.__output_directory / "%(playlist)s/%(artist)s - %(title)s.%(ext)s")
                elif "album" in clean_url.lower():
                    output_template = str(self.__output_directory / "%(artist)s/%(album)s/%(artist)s - %(title)s.%(ext)s")
                else:
                    output_template = str(self.__output_directory / "%(artist)s - %(title)s.%(ext)s")
                
                # Download with retry
                success = self._download_with_retry(clean_url, output_template, None, "URL")
                
                if success:
                    success_count += 1
                    self.log_manager.log_success(f"Downloaded {clean_url}")
                    file_lines[i - 1] = f"{clean_url} # DOWNLOADED"
                else:
                    failed_count += 1
                    self.log_manager.log_failure(f"Failed to download {clean_url}")
                    file_lines[i - 1] = f"{clean_url} # FAILED"
                
                pbar.update(1)
        
        # Update the file with status comments
        try:
            with open(filepath, 'w', encoding='utf-8') as file:
                file.write("\n".join(file_lines))
        except Exception as e:
            self.log_manager.log_failure(f"Error updating the file: {e}")
        
        # Print summary
        print("\n" + "=" * 50)
        Enhanced_Menu.print_header("Download Summary:")
        Enhanced_Menu.print_status(f"Successfully downloaded: {success_count}", "success")
        Enhanced_Menu.print_status(f"Failed: {failed_count}", "failure")
        print("=" * 50)
        
        return failed_count == 0
    
    def download_liked_songs(self):
        """Download all liked songs from YouTube Music"""
        print("\n" + "=" * 55)
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Download Liked Songs", "Download your entire YouTube Music liked songs library")
        
        # Warning about potential large download
        Enhanced_Menu.print_status("⚠️  This may download MANY songs depending on your library size", "warning")
        Enhanced_Menu.print_status("Make sure you have enough disk space and a stable connection", "warning")
        print()
        
        # Confirm with user
        confirm = Enhanced_Menu.get_input("Are you sure you want to download ALL your liked songs? (y/n)", "yn", default=False)
        if not confirm:
            Enhanced_Menu.print_status("Liked songs download cancelled", "info")
            return False
        
        # Get user preferences
        if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
            self.get_user_preferences()
        
        # Ask for limit (optional)
        limit_input = Enhanced_Menu.get_input("Enter maximum number of songs to download (or press Enter for all): ", "str", default="")
        max_songs = None
        if limit_input.strip() and limit_input.isdigit():
            max_songs = int(limit_input)
            Enhanced_Menu.print_status(f"Will download up to {max_songs} songs", "info")
        
        # Liked songs playlist URL
        liked_songs_url = "https://music.youtube.com/playlist?list=LM"  # LM = Liked Music
        
        Enhanced_Menu.print_status("Fetching your liked songs... This may take a moment", "info")
        
        # First, get information about the liked songs playlist
        try:
            # Get playlist info to count songs
            info_command = [
                "yt-dlp",
                "--flat-playlist",
                "--dump-json",
                "--no-warnings",
                liked_songs_url
            ]
            
            result = subprocess.run(
                info_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                check=False
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.lower()
                if "private" in error_msg or "login" in error_msg:
                    Enhanced_Menu.print_status(
                        "Cannot access liked songs. You may need to:\n"
                        "1. Export cookies from your browser first\n"
                        "2. Enable cookies in settings\n"
                        "3. Make sure you're logged into YouTube Music",
                        "error"
                    )
                    return False
                else:
                    Enhanced_Menu.print_status(f"Error fetching liked songs: {error_msg[:100]}", "error")
                    return False
            
            # Parse the JSON output to count songs
            songs = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        song_info = json.loads(line)
                        songs.append(song_info)
                    except json.JSONDecodeError:
                        continue
            
            total_songs = len(songs)
            if max_songs:
                total_songs = min(total_songs, max_songs)
            
            Enhanced_Menu.print_status(f"Found {Fore.CYAN}{total_songs}{Style.RESET_ALL} liked songs", "success")
            
            if total_songs == 0:
                Enhanced_Menu.print_status("No liked songs found", "warning")
                return False
            
            # Confirm download
            print()
            print(f"{Fore.YELLOW}Download Summary:{Style.RESET_ALL}")
            print(f"  • Songs to download: {Fore.CYAN}{total_songs}{Style.RESET_ALL}")
            print(f"  • Output directory: {Fore.CYAN}{self.__output_directory}/Liked Songs/{Style.RESET_ALL}")
            print(f"  • Format: {Fore.CYAN}{self.__audio_format}{Style.RESET_ALL}")
            print(f"  • Quality: {Fore.CYAN}{self.__audio_quality}{Style.RESET_ALL}")
            print()
            
            final_confirm = Enhanced_Menu.get_input("Proceed with download? (y/n)", "yn", default=True)
            if not final_confirm:
                Enhanced_Menu.print_status("Download cancelled", "info")
                return False
            
            # Setup output template for liked songs
            output_template = str(self.__output_directory / "Liked Songs" / "%(artist)s - %(title)s.%(ext)s")
            
            # Create the directory
            os.makedirs(os.path.dirname(output_template), exist_ok=True)
            
            # Create a progress file to track downloaded songs
            progress_file = self.__output_directory / "Liked Songs" / "download_progress.json"
            downloaded_songs = set()
            
            # Load previous progress if exists
            if progress_file.exists():
                try:
                    with open(progress_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        downloaded_songs = set(data.get('downloaded', []))
                        Enhanced_Menu.print_status(f"Resuming download - {len(downloaded_songs)} songs already downloaded", "info")
                except:
                    pass
            
            # Filter out already downloaded songs
            if downloaded_songs:
                songs_to_download = [s for s in songs if s.get('id') not in downloaded_songs]
                if max_songs:
                    songs_to_download = songs_to_download[:max_songs - len(downloaded_songs)]
                Enhanced_Menu.print_status(f"{len(songs_to_download)} new songs to download", "info")
            else:
                songs_to_download = songs[:max_songs] if max_songs else songs
            
            if not songs_to_download:
                Enhanced_Menu.print_status("All liked songs are already downloaded!", "success")
                return True
            
            # Start download with progress bar
            print()
            Enhanced_Menu.print_section("Downloading Liked Songs")
            
            success_count = 0
            failed_count = 0
            skipped_count = 0
            
            # Create a tqdm progress bar for overall progress
            with tqdm(total=len(songs_to_download), desc="Overall Progress", unit="songs", 
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} songs [{elapsed}<{remaining}]") as pbar:
                
                for i, song in enumerate(songs_to_download, 1):
                    song_title = song.get('title', 'Unknown')
                    song_artist = song.get('uploader', song.get('artist', 'Unknown Artist'))
                    song_url = f"https://music.youtube.com/watch?v={song.get('id')}"
                    
                    Enhanced_Menu.print_status(f"\n[{i}/{len(songs_to_download)}] Downloading: {song_artist} - {song_title}", "info")
                    
                    # Download the song with retries
                    download_success = False
                    for attempt in range(1, MAX_RETRIES + 1):
                        if attempt > 1:
                            print(f"  Retry {attempt}/{MAX_RETRIES}...")
                            time.sleep(RETRY_DELAY)
                        
                        try:
                            result = self.run_download(song_url, output_template)
                            if result and result.returncode == 0:
                                download_success = True
                                
                                # Mark as downloaded in progress file
                                downloaded_songs.add(song.get('id'))
                                with open(progress_file, 'w', encoding='utf-8') as f:
                                    json.dump({'downloaded': list(downloaded_songs)}, f, indent=2)
                                
                                success_count += 1
                                break
                        except Exception as e:
                            if attempt == MAX_RETRIES:
                                self.log_manager.log_failure(f"Failed to download liked song: {song_url} - {str(e)[:100]}")
                                failed_count += 1
                            else:
                                continue
                    
                    if not download_success:
                        failed_count += 1 # Add to 
                    
                    # Update progress bar
                    pbar.update(1)
                    pbar.set_postfix(success=success_count, failed=failed_count)
                    
                    # Small delay between downloads to avoid rate limiting
                    time.sleep(1)
            
            # Print summary
            print("\n" + "=" * 55)
            Enhanced_Menu.print_header("Download Complete")
            print(f"  {Fore.GREEN}Successfully downloaded: {success_count}{Style.RESET_ALL}")
            if failed_count > 0:
                print(f"  {Fore.RED} Failed: {failed_count}{Style.RESET_ALL}")
            if skipped_count > 0:
                print(f"  {Fore.YELLOW}Skipped (already downloaded): {skipped_count}{Style.RESET_ALL}")
            print("=" * 55)
            
            # Offer to open the folder
            if success_count > 0:
                open_folder = Enhanced_Menu.get_input("\nOpen download folder? (y/n)", "yn", default=False)
                if open_folder:
                    folder_path = str(self.__output_directory / "Liked Songs")
                    if sys.platform == 'win32':
                        os.startfile(folder_path)
                    elif sys.platform == 'darwin':
                        subprocess.run(['open', folder_path])
                    else:
                        subprocess.run(['xdg-open', folder_path])
            
            return failed_count == 0
            
        except subprocess.TimeoutExpired:
            Enhanced_Menu.print_status("Timeout while fetching liked songs", "error")
            return False
        except Exception as e:
            Enhanced_Menu.print_status(f"Error downloading liked songs: {str(e)[:100]}", "error")
            self.log_manager.log_error(f"Liked songs download error: {e}", exc_info=True)
            return False
        
    @rate_limit(calls_per_minute=30)
    def search_a_song(self):
        """Search for a song and download it"""
        Enhanced_Menu.print_header("SEARCH & DOWNLOAD")
        song_query = Enhanced_Menu.get_input("What is the name of the song you're looking for: ").strip()
        if not song_query:
            Enhanced_Menu.print_status("No search query provided", "error")
            return False
        if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
            self.get_user_preferences()
        search_time = time.time()
        Enhanced_Menu.print_header("Searching for the song. Browsing through YouTube...")
        output_template = str(self.__output_directory / "%(artist)s - %(title)s.%(ext)s")
        for attempt in range(1, MAX_RETRIES + 1):
            print("=" * 50)
            Enhanced_Menu.print_header("Search and download")
            if attempt > 1:
                print(f"Waiting {RETRY_DELAY} seconds before retry...")
                time.sleep(RETRY_DELAY)
            try:
                result = self.run_download(f"ytsearch1:{song_query}", output_template)
                self.log_manager.log_success(f"Successfully downloaded: '{song_query}'")
                print("=" * 50)
                return True
            except Exception as e:
                self.log_manager.log_error(f"Unexpected error: {e}")
                if attempt < MAX_RETRIES:
                    continue
                else:
                    return False
        return False

    #  ============================================= Checkers & Yt-DLP Helpers =============================================
    def manage_cookies(self):
        """Calls the cookie management menu"""
        self.cookie_manager.interactive_menu()
        if self.cookie_manager.current_cookie_file:
            use_cookies = Enhanced_Menu.get_input("Enable cookies for future downloads? (y/n)", "yn", default=False)
            if use_cookies:
                self.use_cookies = True
            else:
                self.use_cookies = False
            self.save_config()
    
    # Methods that now call the static methods from DownloaderUtils
    def check_ytdlp(self):
        """Check if ytdlp is installed using utils"""
        return self.utils.check_ytdlp()
    
    def check_ffmpeg(self):
        """Check if ffmpeg is installed using utils"""
        return self.utils.check_ffmpeg()
    
    def show_ytdlp_help(self):
        """Display yt-dlp help using utils"""
        return self.utils.show_ytdlp_help()
    
    def show_spotdl_help(self):
        """Display spotdl help using utils"""
        return self.utils.show_spotdl_help()
    
    def check_dependencies(self):
        """Check for missing dependencies using utils"""
        return self.utils.check_dependencies()
    
    def setup_dependencies(self):
        """Setup dependencies using utils"""
        self.utils.setup_dependencies()
    
    def program_info(self):
        """Display program information using utils"""
        return self.utils.program_info()

    def reset_to_defaults(self):
        """Reset all settings to default values"""
        self.__output_directory = Path("Albums")
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.use_cookies = False
        self.save_config()
        Enhanced_Menu.print_status("Settings reset to defaults", "success")

def main():
    """Main function to run the YouTube Downloader with integrated menus."""
    Enhanced_Menu.clear_screen()
    print(f"""{Fore.RED}{Style.BRIGHT}
    ███╗   ███╗██╗   ██╗███████╗██╗ ██████╗     ██████╗ ██████╗ ███╗   ██╗██╗   ██╗███████╗██████╗ ████████╗███████╗██████╗ 
    ████╗ ████║██║   ██║██╔════╝██║██╔════╝    ██╔════╝██╔═══██╗████╗  ██║██║   ██║██╔════╝██╔══██╗╚══██╔══╝██╔════╝██╔══██╗
    ██╔████╔██║██║   ██║███████╗██║██║         ██║     ██║   ██║██╔██╗ ██║██║   ██║█████╗  ██████╔╝   ██║   █████╗  ██████╔╝
    ██║╚██╔╝██║██║   ██║╚════██║██║██║         ██║     ██║   ██║██║╚██╗██║╚██╗ ██╔╝██╔══╝  ██╔══██╗   ██║   ██╔══╝  ██╔══██╗
    ██║ ╚═╝ ██║╚██████╔╝███████║██║╚██████╗    ╚██████╗╚██████╔╝██║ ╚████║ ╚████╔╝ ███████╗██║  ██║   ██║   ███████╗██║  ██║
    ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝ ╚═════╝     ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝                                                                                                 
    {Style.RESET_ALL}""")
    print(f"{Fore.YELLOW}{Style.BRIGHT}YouTube Music Downloader{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{Style.BRIGHT}Initializing...{Style.RESET_ALL}")

    directories = ["Albums", "links", "cookies"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"{Fore.GREEN}✓{Style.RESET_ALL} Directory '{directory}/' ready")

    try:
        downloader = Youtube_Downloader()
        Enhanced_Menu.print_status("Downloader initialized successfully", "success")
        time.sleep(1)
    except Exception as e:
        Enhanced_Menu.print_status(f"Initialization error: {e}", "error")
        input("\nPress Enter to exit...")
        sys.exit(1)

    def handle_exit():
        """Handles exiting the program function"""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("THANK YOU", "Goodbye!")
        print(f"""{Fore.CYAN}
                ╔══════════════════════════════════════════════════════════════╗
                ║                                                              ║
                ║          Thank you for using YouTube Music Downloader!       ║
                ║                                                              ║
                ║                      Happy Listening!                        ║
                ║                                                              ║
                ║                                                              ║
                ╚══════════════════════════════════════════════════════════════╝
                {Style.RESET_ALL}""")
        try:
            downloader.save_config()
            print(f"{Fore.GREEN}Settings saved.{Style.RESET_ALL}")
        except:
            pass
        print(f"\n{Fore.CYAN}Goodbye!{Style.RESET_ALL}\n")
        sys.exit(0)

    def handle_settings():
        """Handle program settings menu"""
        while True:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("PROGRAM SETTINGS", "Configure download preferences")
            
            Enhanced_Menu.print_section("🎵 Download Settings")
            current_format = downloader._Youtube_Downloader__audio_format
            current_quality = downloader._Youtube_Downloader__audio_quality
            Enhanced_Menu.print_menu_item(1, "Audio Format", f"Current: {Fore.GREEN}{current_format.upper()}{Style.RESET_ALL}")
            Enhanced_Menu.print_menu_item(2, "Audio Quality", f"Current: {Fore.GREEN}{current_quality}{Style.RESET_ALL}")
            current_dir = str(downloader._Youtube_Downloader__output_directory)
            Enhanced_Menu.print_menu_item(3, "Output Directory", f"Current: {Fore.CYAN}{current_dir}{Style.RESET_ALL}")
            
            Enhanced_Menu.print_section("🌐 NETWORK SETTINGS")
            cookie_status = "ENABLED" if downloader.use_cookies else "DISABLED"
            cookie_color = Fore.GREEN if downloader.use_cookies else Fore.YELLOW
            Enhanced_Menu.print_menu_item(4, "Cookie Authentication", f"Current: {cookie_color}{cookie_status}{Style.RESET_ALL}")
            
            Enhanced_Menu.print_section("💾 Download Configuration")
            Enhanced_Menu.print_menu_item(5, "Save Configuration")
            Enhanced_Menu.print_menu_item(6, "Load Configuration")
            Enhanced_Menu.print_menu_item(7, "Reset to Defaults")
            Enhanced_Menu.print_section("↩️  NAVIGATION")
            Enhanced_Menu.print_menu_item(8, "Back to Main Menu")
            print()
            choice = Enhanced_Menu.get_input("Select option", "int", 1, 8)
            if choice == 1:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("AUDIO FORMAT", "Select output format")
                formats = [
                    ("MP3", "mp3", "Most compatible, good quality"),
                    ("FLAC", "flac", "Lossless audio, large files"),
                    ("M4A", "m4a", "Apple format, good quality"),
                    ("OPUS", "opus", "Excellent compression, high quality"),
                    ("OGG", "ogg", "Open format, good compression"),
                    ("WAV", "wav", "Uncompressed, large files"),
                ]
                for i, (name, code, desc) in enumerate(formats, 1):
                    is_current = " ✓" if code == current_format else ""
                    print(f"  {Fore.YELLOW}[{i}]{Style.RESET_ALL} {Fore.CYAN}{name:6}{Style.RESET_ALL} - {desc}{Fore.GREEN}{is_current}{Style.RESET_ALL}")
                print()
                format_choice = Enhanced_Menu.get_input("Select format (1-6)", "int", 1, 6, default=1)
                if format_choice:
                    new_format = formats[format_choice - 1][1]
                    downloader._Youtube_Downloader__audio_format = new_format
                    Enhanced_Menu.print_status(f"Audio format set to {new_format.upper()}", "success")
                    
            elif choice == 2:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("AUDIO QUALITY", "Select bitrate/quality")
                qualities = [
                    ("320k", "High quality (320 kbps)", "Excellent for most music"),
                    ("256k", "Very good (256 kbps)", "Great quality, smaller files"),
                    ("192k", "Good (192 kbps)", "Good balance of quality/size"),
                    ("128k", "Standard (128 kbps)", "Acceptable quality, small files"),
                    ("auto", "Auto-select", "Let yt-dlp choose the best"),
                    ("disable", "Original quality", "Keep original audio as-is"),
                ]
                for i, (code, name, desc) in enumerate(qualities, 1):
                    is_current = " ✓" if code == current_quality else ""
                    print(f"  {Fore.YELLOW}[{i}]{Style.RESET_ALL} {Fore.CYAN}{name:20}{Style.RESET_ALL} - {desc}{Fore.GREEN}{is_current}{Style.RESET_ALL}")
                print()
                quality_choice = Enhanced_Menu.get_input("Select quality (1-6)", "int", 1, 6)
                if quality_choice:
                    new_quality = qualities[quality_choice - 1][0]
                    downloader._Youtube_Downloader__audio_quality = new_quality
                    Enhanced_Menu.print_status(f"Audio quality set to {new_quality}", "success")
            
            # Set output
            elif choice == 3:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("OUTPUT DIRECTORY", "Set where files are saved")
                print(f"{Fore.YELLOW}Current directory:{Style.RESET_ALL} {Fore.CYAN}{current_dir}{Style.RESET_ALL}")
                print()
                print(f"{Fore.WHITE}Enter new directory path:{Style.RESET_ALL}")
                print(f"{Style.DIM}Examples:{Style.RESET_ALL}")
                print(f"  {Fore.CYAN}./Music{Style.RESET_ALL} - Save to 'Music' folder in current directory")
                print(f"  {Fore.CYAN}~/Downloads{Style.RESET_ALL} - Save to Downloads folder")
                print(f"  {Fore.CYAN}C:\\Users\\You\\Music{Style.RESET_ALL} - Windows absolute path")
                print()
                new_dir = Enhanced_Menu.get_input("New directory path", "str", default=current_dir)
                if new_dir and new_dir != current_dir:
                    try:
                        downloader._Youtube_Downloader__output_directory = Path(new_dir)
                        downloader._Youtube_Downloader__output_directory.mkdir(parents=True, exist_ok=True)
                        Enhanced_Menu.print_status(f"Output directory changed to {new_dir}", "success")
                    except Exception as e:
                        Enhanced_Menu.print_status(f"Error: {str(e)[:50]}", "error")
                        
            elif choice == 4:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("COOKIE SETTINGS", "Manage authentication")
                print(f"{Fore.WHITE}Cookies help with:{Style.RESET_ALL}")
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Age-restricted content")
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Region-restricted videos")
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Private playlists")
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} YouTube Premium content")
                print()
                print(f"{Fore.YELLOW}Current status:{Style.RESET_ALL} ", end="")
                if downloader.use_cookies:
                    print(f"{Fore.GREEN}ENABLED{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}DISABLED{Style.RESET_ALL}")
                print()
                new_setting = Enhanced_Menu.get_input("Enable cookies? (y/n)", "yn", default=downloader.use_cookies)
                if new_setting is not None:
                    downloader.use_cookies = new_setting
                    status = "enabled" if new_setting else "disabled"
                    Enhanced_Menu.print_status(f"Cookies {status}", "success")
                    
            elif choice == 5:
                try:
                    downloader.save_config()
                    Enhanced_Menu.print_status("Settings saved successfully", "success")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Error saving settings: {e}", "error")
                    
            elif choice == 6:
                try:
                    downloader.load_config()
                    Enhanced_Menu.print_status("Settings loaded successfully", "success")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Error loading settings: {e}", "error")
                    
            elif choice == 7:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("RESET SETTINGS", "Restore defaults")
                print(f"{Fore.YELLOW}⚠️  WARNING:{Style.RESET_ALL}")
                print(f"{Fore.WHITE}This will reset ALL settings to their default values.{Style.RESET_ALL}")
                print()
                print(f"{Fore.CYAN}Default settings:{Style.RESET_ALL}")
                print(f"  Format: {Fore.YELLOW}mp3{Style.RESET_ALL}")
                print(f"  Quality: {Fore.YELLOW}320k{Style.RESET_ALL}")
                print(f"  Output: {Fore.YELLOW}Albums/{Style.RESET_ALL}")
                print(f"  Cookies: {Fore.YELLOW}Disabled{Style.RESET_ALL}")
                print()
                confirm = Enhanced_Menu.get_input("Are you sure? (y/n)", "yn", default=False)
                if confirm:
                    downloader.reset_to_defaults()
            elif choice == 8:
                break
            if choice != 8:
                input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")

    # Define actions as lambdas to ensure they're called only when selected
    actions = {
        1: lambda: downloader.download_track(),
        2: lambda: downloader.download_album(),
        3: lambda: downloader.download_playlist(),
        4: lambda: downloader.download_from_file(),
        5: lambda: downloader.search_a_song(),
        6: lambda: downloader.download_channel(),
        7: lambda: downloader.download_liked_songs(),
        8: lambda: downloader.manage_cookies(),
        9: lambda: downloader.check_dependencies(),
        10: lambda: handle_settings(),
        11: lambda: downloader.program_info(),
        12: lambda: downloader.troubleshooting(),
        13: lambda: downloader.show_ytdlp_help(),
        14: lambda: downloader.log_manager.interactive_menu(),
        15: lambda: handle_exit()
    }

    while True:
        try:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Main Menu", "Select an option below:")
            Enhanced_Menu.print_section("📥 DOWNLOAD OPTIONS")
            Enhanced_Menu.print_menu_item(1, "Download Track")
            Enhanced_Menu.print_menu_item(2, "Download Album")
            Enhanced_Menu.print_menu_item(3, "Download Playlist")
            Enhanced_Menu.print_menu_item(4, "Download From Text File")
            Enhanced_Menu.print_menu_item(5, "Search & Download a Song")
            Enhanced_Menu.print_menu_item(6, "Download a YouTube Channel")
            Enhanced_Menu.print_menu_item(7, "Download Liked Songs") # Added feature
            
            Enhanced_Menu.print_section("⚙️  TOOLS & SETTINGS")
            Enhanced_Menu.print_menu_item(8, "Manage Cookies (for restricted content)")
            Enhanced_Menu.print_menu_item(9, "Check Dependencies")
            Enhanced_Menu.print_menu_item(10, "Program Settings")
            
            Enhanced_Menu.print_section("❓ HELP & INFORMATION")
            Enhanced_Menu.print_menu_item(11, "Show Program Info")
            Enhanced_Menu.print_menu_item(12, "Troubleshooting")
            Enhanced_Menu.print_menu_item(13, "Show yt-dlp Help")
            
            Enhanced_Menu.print_section("📊 LOG MANAGEMENT")
            Enhanced_Menu.print_menu_item(14, "Log Manager")
            
            Enhanced_Menu.print_section("🚪 EXIT")
            Enhanced_Menu.print_menu_item(15, "Exit Program")
            print(f"\n{Style.DIM}{'─' * 60}{Style.RESET_ALL}")
            Enhanced_Menu.print_status("Current Settings:", "info", "⚙️")
            settings = [
                ("Format", downloader._Youtube_Downloader__audio_format),
                ("Quality", downloader._Youtube_Downloader__audio_quality),
                ("Output", str(downloader._Youtube_Downloader__output_directory)),
            ]
            for setting_name, setting_value in settings:
                print(f"  {Fore.CYAN}{setting_name}:{Style.RESET_ALL} {Fore.YELLOW}{setting_value}{Style.RESET_ALL}")
            cookie_status = "Enabled" if downloader.use_cookies else "Disabled"
            cookie_color = Fore.GREEN if downloader.use_cookies else Fore.YELLOW
            print(f"  {Fore.CYAN}Cookies:{Style.RESET_ALL} {cookie_color}{cookie_status}{Style.RESET_ALL}")
            print(f"{Style.DIM}{'─' * 60}{Style.RESET_ALL}")
            
            choice = Enhanced_Menu.get_input("\nEnter your choice (1-15)", "int", 1, 15)
            action = actions.get(choice)
            
            if action:
                Enhanced_Menu.clear_screen()
                try:
                    # Call the lambda function
                    result = action()
                    
                    # Handle the result if needed
                    if result is False and choice not in [8, 10, 11, 12, 13, 14, 15]:
                        print()
                        retry = Enhanced_Menu.get_input("Operation failed. Try again? (y/n)", "yn", default=True)
                        if retry:
                            continue
                except KeyboardInterrupt:
                    Enhanced_Menu.print_status("Operation cancelled", "warning")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Error: {e}", "error")
                    import traceback
                    traceback.print_exc()
            else:
                Enhanced_Menu.print_status("Invalid option", "error")
                
            if choice != 15:
                print()
                cont = Enhanced_Menu.get_input("Return to main menu? (y/n)", "yn", default=True)
                if not cont:
                    handle_exit()
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Interrupted by user{Style.RESET_ALL}")
            handle_exit()
        except Exception as e:
            Enhanced_Menu.print_status(f"Unexpected error: {e}", "error")
            import traceback
            traceback.print_exc()
            if Enhanced_Menu.get_input("Continue? (y/n)", "yn", default=True):
                continue
            else:
                handle_exit()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        print("Please check the error log for details.")