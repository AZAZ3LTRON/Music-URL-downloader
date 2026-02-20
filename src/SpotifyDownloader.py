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

import sys
import os
import subprocess
import shutil
import time
from pathlib import Path
import logging
import re
import urllib.parse
from urllib.parse import urlparse
from typing import List, Dict, Optional, Tuple
import threading
import json
from tqdm import tqdm
import browser_cookie3
from functools import wraps
from colorama import init, Fore, Style
init(autoreset=True)

from EnhancedMenu import Enhanced_Menu
from CookieManager import CookieManager
from Logs_Handler import Logs_Manager
from Downloader_Utils import DownloaderUtils

""" =========================================== Pre Config ===========================================
This part of the pre-configuration of the downloader, it can be change. Each part is explained below:
* MAX_RETRIES - No of times the downloader can retry on a link (subject to change)
* RETRY_DELAY - The delay between each retry (subject to change)
======================================================================================================= """

MAX_RETRIES = 3
RETRY_DELAY = 10
DOWNLOAD_TIMEOUT = 120

class Spotify_Downloader:
    def __init__(self):
        """Initialize the downloader with default settings."""
        # Retry & timeout settings
        self.max_retries = MAX_RETRIES
        self.retry_delay = RETRY_DELAY
        self.download_timeout = DOWNLOAD_TIMEOUT
        self.client_id = None
        self.client_secret = None
        self.auth_token = None

        # Private configuration attributes
        self._output_directory = Path("Albums")
        self._audio_quality = "320k"
        self._audio_format = "mp3"
        self._filepath = Path("links/spotify_links.txt")
        self._configuration_file = Path("config/spotify_downloader.json")
        self.cookie_manager = CookieManager(config_path=self._configuration_file)
        self.log_manager = Logs_Manager()
        self.utils = DownloaderUtils()      
        # Load configuration
        self.load_config()
    
        # After loading config, sync credentials to cookie manager
        self.cookie_manager.set_credentials(
            client_id=self.client_id,
            client_secret=self.client_secret,
            auth_token=self.auth_token,
        )

        # Create necessary directories
        self._output_directory.mkdir(parents=True, exist_ok=True)
        Path("links").mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------
    # Properties for public access to settings (Do not delete)
    # -----------------------------------------------------------------
    @property
    def output_directory(self) -> Path:
        return self._output_directory

    @output_directory.setter
    def output_directory(self, value):
        self._output_directory = Path(value)
        self._output_directory.mkdir(parents=True, exist_ok=True)

    @property
    def audio_quality(self) -> str:
        return self._audio_quality

    @audio_quality.setter
    def audio_quality(self, value):
        self._audio_quality = value

    @property
    def audio_format(self) -> str:
        return self._audio_format

    @audio_format.setter
    def audio_format(self, value):
        self._audio_format = value

    # -----------------------------------------------------------------
    # Configuration management
    # -----------------------------------------------------------------
    def load_config(self):
        """Load configuration from json file"""
        primary_config = {
            "output_directory": "Albums",
            "audio_quality": "320k",
            "audio_format": "mp3",
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "download_timeout": self.download_timeout,
            "use_cookies": False,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "auth_token": self.auth_token,
        }

        try:
            if self._configuration_file.exists():
                with open(self._configuration_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    config = {**primary_config, **user_config}
            else:
                config = primary_config
                self.save_config(config)

            # Apply configuration safely
            if "output_directory" in config:
                self.output_directory = config["output_directory"]
            if "audio_quality" in config:
                self.audio_quality = config["audio_quality"]
            if "audio_format" in config:
                self.audio_format = config["audio_format"]
            if "max_retries" in config:
                self.max_retries = config["max_retries"]
            if "retry_delay" in config:
                self.retry_delay = config["retry_delay"]
            if "download_timeout" in config:
                self.download_timeout = config["download_timeout"]
            if "use_cookies" in config:
                self.use_cookies = config["use_cookies"]
            if "client_id" in config:
                self.client_id = config["client_id"]
            if "client_secret" in config:
                self.client_secret = config["client_secret"]
            if "auth_token" in config:
                self.auth_token = config["auth_token"]
                
            self.cookie_manager.set_credentials(
            client_id=self.client_id,
            client_secret=self.client_secret,
            auth_token=self.auth_token
    )        
        except Exception as e:
            self.log_manager.log_error(f"Error loading configuration: {e}")
            # Use defaults
            self.output_directory = Path(primary_config["output_directory"])
            self.audio_quality = primary_config["audio_quality"]
            self.audio_format = primary_config["audio_format"]
            self.use_cookies = primary_config["use_cookies"]
            self.client_id = primary_config["client_id"]
            self.client_secret = primary_config["client_secret"]
            self.auth_token = primary_config["auth_token"]

    def save_config(self, config: Dict = None):
        """Save configuration to file"""
        try:
            if config is None:
                config = {
                    "output_directory": str(self.output_directory),
                    "audio_quality": self.audio_quality,
                    "audio_format": self.audio_format,
                    "max_retries": self.max_retries,
                    "retry_delay": self.retry_delay,
                    "download_timeout": self.download_timeout,
                    "use_cookies": self.use_cookies,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_token": self.auth_token,
                }

            # Ensure config directory exists
            self._configuration_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self._configuration_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.log_manager.log_error(f"Error saving configuration: {e}")

    def reset_config(self):
        """Reset all settings to default values"""
        self.output_directory = Path("Albums")
        self.audio_quality = "320k"
        self.audio_format = "mp3"
        self.max_retries = MAX_RETRIES
        self.retry_delay = RETRY_DELAY
        self.download_timeout = DOWNLOAD_TIMEOUT
        self.use_cookies = False
        self.client_id = None
        self.client_secret = None
        self.auth_token = None
        self.cookie_manager.set_credentials()   # clear them in cookie manager
        self.save_config()
        Enhanced_Menu.print_status("Configuration reset to defaults", "success")

    def sync_credentials_from_cookie_manager(self):
        """Copy credentials from cookie manager into self and save config."""
        self.client_id = self.cookie_manager._client_id
        self.client_secret = self.cookie_manager._client_secret
        self.auth_token = self.cookie_manager._auth_token
        self.save_config()

    # ====================================
    # Preference & Other Helpers
    # ===================================
    def get_user_preferences(self):
        """Takes in user input for the download settings"""
        Enhanced_Menu.print_header("DOWNLOAD SETTINGS", "Configure your music conversion preferenced")

        # Handle choice of bitrate/audio quality inputs
        while True:
            audio_quality_input = Enhanced_Menu.get_input(
                "What bitrate would you like (enter 'choice' to see options):- ",
                "str", default=self.audio_quality)

            if not audio_quality_input:
                self.audio_quality = "320k"
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
                self.audio_quality = audio_quality_input.lower()
                break
            Enhanced_Menu.print_status("Invalid bitrate. The downloader doesn't support these values", "error")

        # Handle choice of audio format
        while True:
            audio_format_input = Enhanced_Menu.get_input(
                "What format would you like(enter 'choice' to see options):- ",
                "str", default=self.audio_format)

            if not audio_format_input:
                self.audio_format = "mp3"
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
                self.audio_format = audio_format_input
                break
            Enhanced_Menu.print_status("Invalid format. Downloader doesn't support this format", "error")

        # Handle choice of output directory
        output_path = Enhanced_Menu.get_input("Enter output directory (default: Albums):- ", "str").strip()
        if output_path:
            self.output_directory = Path(output_path)
        else:
            self.output_directory = Path("Albums")

        # Handles choice for cookies
        Enhanced_Menu.print_status("Cookie Settings", "info")
        print(f"\n{Fore.CYAN}Cookies can help with:{Style.RESET_ALL}")
        print(" Age-restricted content")
        print(" Region-restricted videos")
        print(" Private playlists")

        Enhanced_Menu.print_status("Note: Make sure you have extracted the cookies beforehand, if make use of Cookie Manager to help you", "info")
        cookie_choice = Enhanced_Menu.get_input("Use cookies for authentication? (y/n):- ", "yn", default=True)
        self.use_cookies = cookie_choice  # cookie_choice is boolean            

    @staticmethod
    def validate_spotify_url(url: str) -> Tuple[bool, Optional[str]]:
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

        for pattern, typ in spotify_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True, typ
        return False, None

    def cleanup_directory(self):
        """Removes empty directories after download"""
        removed_count = 0
        for root, dirs, files in os.walk(self.output_directory, topdown=False):
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

    def validate_resource(self, url: str) -> Tuple[bool, str, Optional[dict]]:
        """ Validate if a resource is available before downloading to the device """
        cmd = [
            "spotdl",
            url,
            "--skip-download",
            "--print-json",
            "--no-warnings"
        ]
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.download_timeout,
                check=False
            )
            if result.returncode == 0 and result.stdout.strip():
                try:
                    metadata = json.loads(result.stdout.strip())
                    # Basic sanity checks
                    if not metadata.get("name") and not metadata.get("title"):
                        return False, "Missing title metadata", metadata
                    typ = metadata.get("type", "")

                    # If a playlist or album link is provided, check if there are any tracks in it
                    if typ in ("playlist", "album"):
                        tracks = metadata.get("tracks", [])
                        available = sum(1 for t in tracks if t.get("available", True))
                        total = len(tracks)
                        if available == 0:
                            return False, f"No available tracks in this {typ}", metadata
                        return True, f"{typ} available ({available}/{total} tracks)", metadata
                    else:  # track
                        duration = metadata.get("duration", 0)
                        if duration <= 0:
                            return False, "Invalid duration", metadata
                        return True, "Track available", metadata
                except json.JSONDecodeError:
                    return False, "Invalid JSON response", None
            else:
                err = result.stderr.lower()
                if "not found" in err:
                    return False, "Resource not found on Spotify", None
                elif "private" in err or "access" in err:
                    return False, "Private resource – requires authentication", None
                elif "unavailable" in err:
                    return False, "Resource unavailable in your region", None
                elif "quota" in err or "rate limit" in err:
                    return False, "Rate limit exceeded, try later", None
                else:
                    return False, f"{err[:100]}", None
        except subprocess.TimeoutExpired:
            return False, "Validation timeout", None
        except FileNotFoundError:
            return False, "spotdl not found – please install it first", None
        except Exception as e:
            return False, f"Validation error: {str(e)[:100]}", None

    def parse_size(self, size_str: str) -> Optional[int]:
        """
        Convert a size string (e.g., '3.45 MiB', '1.2GB', '5M') into bytes.
        Supports both base‑10 (KB, MB) and base‑2 (KiB, MiB) units.
        Returns an integer number of bytes, or None if the string cannot be parsed.
        """
        if not size_str:
            return None

        size_str = size_str.strip()
        # Regex: captures numeric part and optional unit (e.g., 'MiB', 'KB', 'M')
        match = re.match(r'^([\d.]+)\s*([kmgt]?(?:i?b)?)$', size_str, re.IGNORECASE)
        if not match:
            return None

        num_str, unit = match.groups()
        unit = unit.upper() if unit else ''

        try:
            value = float(num_str)
        except ValueError:
            return None

        multipliers = {
            'B':   1,
            'KB':  10**3,
            'MB':  10**6,
            'GB':  10**9,
            'TB':  10**12,
            'KIB': 1024,
            'MIB': 1024**2,
            'GIB': 1024**3,
            'TIB': 1024**4,
            'K':   10**3,
            'M':   10**6,
            'G':   10**9,
            'T':   10**12,
        }

        multiplier = multipliers.get(unit)
        if multiplier is None:
            return None

        return int(value * multiplier)

    # ==================================== The Download Function ===================================
    @staticmethod
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

    @rate_limit(calls_per_minute=30)
    def run_download(self, url: str, output_template: str, additional_args=None):
        """ Run spotdl download with modern syntax """
        command = [
            "spotdl",
            "download", url,
            "--output", output_template,
            "--overwrite", "skip",
            "--bitrate", self.audio_quality,
            "--format", self.audio_format
        ]
        
        # Authentication flags (only if values exist)
        if self.client_id and self.client_secret:
            command.extend(["--client-id", self.client_id,
                            "--client-secret", self.client_secret])
        if self.auth_token:
            command.extend(["--auth-token", self.auth_token])

        # Cookies (from CookieManager)
        if self.use_cookies and self.cookie_manager.current_cookie_file:
            command.extend(["--cookie-file", str(self.cookie_manager.current_cookie_file)])

        if additional_args:
            command.extend(additional_args)

        # Initialize progress bar
        with tqdm(
            desc="Downloading",
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            leave=False,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]",
            dynamic_ncols=True
        ) as pbar:
            try:
                # Start the subprocess
                result = subprocess.Popen(
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
                for line in iter(result.stdout.readline, ''):
                    line = line.strip()

                    if "[download]" in line:
                        # Parse percentage
                        percent_match = re.search(r'(\d+\.?\d*)%', line)
                        if percent_match:
                            percent = float(percent_match.group(1))
                            pbar.set_description(f"{Fore.CYAN}Downloading: {percent:.1f}%{Style.RESET_ALL}")

                        # Parse total size
                        size_match = re.search(r'of\s+([\d\.]+\s*[KMGT]?i?B)', line)
                        if size_match and pbar.total is None:
                            total_str = size_match.group(1)
                            total_bytes = self.parse_size(total_str)
                            if total_bytes:
                                pbar.total = total_bytes

                        # Parse downloaded size
                        downloaded_match = re.search(r'([\d\.]+\s*[KMGT]?i?B)\s+at', line) or \
                                           re.search(r'([\d\.]+\s*[KMGT]?i?B)\s+ETA', line) or \
                                           re.search(r'([\d\.]+\s*[KMGT]?i?B)\s*\/', line)
                        if downloaded_match:
                            downloaded_str = downloaded_match.group(1)
                            downloaded_bytes = self.parse_size(downloaded_str)
                            if downloaded_bytes:
                                pbar.n = downloaded_bytes
                                pbar.refresh()

                        # Speed & ETA (fixed)
                        speed_match = re.search(r'at\s+([\d\.]+\s*[KMGT]?i?B/s)', line)
                        eta_match = re.search(r'ETA\s+([\d:]+)', line)
                        if speed_match or eta_match:
                            postfix = []
                            if speed_match:
                                postfix.append(f"Speed: {speed_match.group(1)}")
                            if eta_match:
                                postfix.append(f"ETA: {eta_match.group(1)}")
                            pbar.set_postfix_str(" ".join(postfix))

                    # When finished
                    if "100%" in line or "already been downloaded" in line or "[Merger]" in line:
                        if pbar.total and pbar.n < pbar.total:
                            pbar.n = pbar.total
                        pbar.set_description(f"{Fore.GREEN}Downloaded{Style.RESET_ALL}")
                        pbar.set_postfix_str("")

                # Wait for process to finish with timeout
                result.wait(timeout=self.download_timeout)
                if result.returncode == 0:
                    self.log_manager.log_success(f"Downloaded: {url}")
                    return True
                else:
                    return False
            except subprocess.TimeoutExpired:
                result.kill()
                self.log_manager.log_error(f"Timeout downloading {url}")
                return False
            except Exception as e:
                self.log_manager.log_error(f"Unexpected error: {e}", exc_info=True)
                return False

    # ====================================
    # Main Download Functions
    # ===================================
    def _download_item(self, item_type: str, url_prompt: str, output_template: str, additional_args: list = None, confirm_large: bool = False):
        """Unified download function for tracks, albums, and playlists"""
        while True:
            print("\n" + "=" * 55)
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header(f"Download {item_type.title()}")

            # Get URL from user
            url = Enhanced_Menu.get_input(f"Enter Spotify {url_prompt} (or 'back' to return)", "str")
            if url and url.lower() == 'back':
                return False

            if not url:
                Enhanced_Menu.print_status("No URL provided", "error")
                continue

            # Validate URL format
            valid, typ = self.validate_spotify_url(url)
            if not valid:
                Enhanced_Menu.print_status("Invalid Spotify URL. Enter a valid Spotify URL", "error")
                continue

            # Validate resource availability
            Enhanced_Menu.print_status("Validating resource...", "info")
            is_available, message, metadata = self.validate_resource(url)
            if not is_available:
                Enhanced_Menu.print_status(f"{message}", "error")
                retry = Enhanced_Menu.get_input("Try to download anyway?", "yn", default=True)
                if not retry:
                    continue
            else:
                Enhanced_Menu.print_status(f"Resource validated: {message}", "success")
                if metadata:
                    print(f"\n{Fore.CYAN}Track details:{Style.RESET_ALL}")
                    print(f"  Title:  {Fore.YELLOW}{metadata.get('name', 'Unknown')}{Style.RESET_ALL}")
                    artists = metadata.get('artists', [{}])
                    if artists:
                        print(f"  Artist: {Fore.YELLOW}{artists[0].get('name', 'Unknown')}{Style.RESET_ALL}")
                    duration = metadata.get('duration', 0)
                    if duration:
                        print(f"  Duration: {Fore.YELLOW}{duration // 60}:{duration % 60:02d}{Style.RESET_ALL}")

                # For large playlists/albums, show count and ask for confirmation
                if confirm_large and metadata:
                    tracks = metadata.get('tracks', [])
                    track_count = len(tracks)
                    if track_count > 50:
                        Enhanced_Menu.print_status(
                            f"This {item_type} contains {track_count} items. This may take a while.",
                            "warning"
                        )
                        if not Enhanced_Menu.get_input("Continue with download? (y/n)", "yn", default=False):
                            Enhanced_Menu.print_status("Download cancelled", "info")
                            continue

            # Get user preferences if they want to configure
            if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
                self.get_user_preferences()

            Enhanced_Menu.print_status(f"Starting {item_type} download...", "info")

            # Attempt download with retries
            success = self._download_with_retry(url, output_template, additional_args, item_type)

            if success:
                time.sleep(0.5)  # Small delay for clean UI
                # Ask if user wants to download another
                another = Enhanced_Menu.get_input(f"\nDownload another {item_type}? (y/n): ", "yn", default=True)
                if another:
                    continue
                else:
                    return True
            else:
                # Download failed after all retries
                retry = Enhanced_Menu.get_input(f"\nDownload failed. Try another {item_type}? (y/n): ", "yn", default=True)
                if retry:
                    continue
                else:
                    return False

    def _download_with_retry(self, url: str, output_template: str, additional_args: list = None, item_type: str = "item") -> bool:
        """Unified retry logic for downloads"""
        for attempt in range(1, self.max_retries + 1):
            Enhanced_Menu.print_section(f"Downloading {item_type} (Attempt {attempt}/{self.max_retries})")

            if attempt > 1:
                print(f"Waiting {self.retry_delay} seconds before retry...")
                time.sleep(self.retry_delay)

            try:
                success = self.run_download(url, output_template, additional_args)
                if success:
                    self.log_manager.log_success(f"Successfully downloaded {item_type}: {url}")

                    # Clean up empty directories after successful download
                    if item_type in ['album', 'playlist']:
                        self.cleanup_directory()

                    return True
                else:
                    # run_download returned False, treat as failure
                    if attempt == self.max_retries:
                        self.log_manager.log_failure(f"Failed after {self.max_retries} attempts: {url}")
                    else:
                        self.log_manager.log_error(f"Attempt {attempt} failed for {item_type}")
            except Exception as e:
                self.log_manager.log_error(f"Unexpected error in attempt {attempt}: {e}")
                if attempt == self.max_retries:
                    self.log_manager.log_failure(f"Failed after {self.max_retries} attempts: {url}")

        return False

    # Replace the original functions with simplified versions
    def download_track(self):
        """Download a single track"""
        return self._download_item(
            item_type="track",
            url_prompt="track URL",
            output_template=str(self.output_directory / "{artist} - {title}.{output-ext}"),
            confirm_large=False
        )

    def download_album(self):
        """Download an album"""
        return self._download_item(
            item_type="album",
            url_prompt="album URL",
            output_template=str(self.output_directory / "{artist}/{album}/{artist} - {title}.{output-ext}"),
            confirm_large=True
        )

    def download_playlist(self):
        """Download a playlist"""
        return self._download_item(
            item_type="playlist",
            url_prompt="playlist URL",
            output_template=str(self.output_directory / "{playlist}/{artist} - {title}.{output-ext}"),
            confirm_large=True,
            additional_args=["--yes-playlist"]  # Ensure playlist is downloaded fully
        )

    def download_from_file(self) -> bool:
        """Batch download from a text file containing one URL per line."""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Batch Download", "Download multiple URLs from a file")
        default_file = "links/spotify_links.txt"
        Path("links").mkdir(exist_ok=True)

        filepath = Enhanced_Menu.get_input(
            f"Path to text file (default: {default_file})",
            "str", default=default_file
        )
        filepath = Path(filepath)
        if not filepath.exists():
            Enhanced_Menu.print_status(f"File not found: {filepath}", "error")
            return False

        # Validation options
        Enhanced_Menu.print_section("Validation Options")
        Enhanced_Menu.print_menu_item(1, "Validate all resources before downloading", "Recommended")
        Enhanced_Menu.print_menu_item(2, "Skip validation (faster, may fail more)")
        Enhanced_Menu.print_menu_item(3, "Validate without cache (fresh check)")
        val_choice = Enhanced_Menu.get_input("Choose (1-3)", "int", 1, 3, default=1)

        if Enhanced_Menu.get_input("Configure download settings for this batch?", "yn", default=False):
            self.get_user_preferences()

        # Read file, strip comments, skip empty lines
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = [line.rstrip() for line in f if line.strip()]
        except Exception as e:
            self.log_manager.log_failure(f"Cannot read file: {e}")
            return False

        urls_to_process = []
        for line in lines:
            if "# DOWNLOADED" in line or "# FAILED" in line:
                continue
            url_part = line.split("#")[0].strip()
            if url_part:
                urls_to_process.append(url_part)

        if not urls_to_process:
            Enhanced_Menu.print_status("No new URLs to process", "info")
            return True

        # Validate if chosen
        validation_results = {}
        if val_choice in (1, 3):
            Enhanced_Menu.print_status(f"Validating {len(urls_to_process)} URLs...", "info")
            for i, url in enumerate(urls_to_process, 1):
                print(f"  {i}/{len(urls_to_process)}: {url[:60]}...")
                available, msg, _ = self.validate_resource(url)
                validation_results[url] = (available, msg)
            available_count = sum(1 for v in validation_results.values() if v[0])
            Enhanced_Menu.print_section("Validation Summary")
            Enhanced_Menu.print_status(f"Available: {available_count}/{len(urls_to_process)}", "success")
            Enhanced_Menu.print_status(f"Unavailable: {len(urls_to_process) - available_count}",
                                       "failure" if available_count < len(urls_to_process) else "info")

            # Ask how to proceed
            Enhanced_Menu.print_section("Download Options")
            Enhanced_Menu.print_menu_item(1, "Download only available resources")
            Enhanced_Menu.print_menu_item(2, "Download all resources (may fail)")
            Enhanced_Menu.print_menu_item(3, "Cancel")
            dl_choice = Enhanced_Menu.get_input("Choose (1-3)", "int", 1, 3, default=1)
            if dl_choice == 3:
                Enhanced_Menu.print_status("Cancelled", "info")
                return False
            if dl_choice == 1:
                urls_to_download = [url for url in urls_to_process if validation_results[url][0]]
            else:
                urls_to_download = urls_to_process
        else:
            urls_to_download = urls_to_process

        Enhanced_Menu.print_status(f"Downloading {len(urls_to_download)} item(s)...", "info")

        success_count = 0
        failed_count = 0

        # We'll rewrite the file after download with status markers
        updated_lines = lines[:]  # copy

        for i, url in enumerate(urls_to_download, 1):
            Enhanced_Menu.print_section(f"Processing {i}/{len(urls_to_download)}")
            print(f"URL: {url[:80]}...")

            # Determine output template based on URL type
            valid, typ = self.validate_spotify_url(url)
            if valid and typ == "playlist":
                out_tmpl = str(self.output_directory / "{playlist}/{artists} - {title}.{output-ext}")
                extra = ["--playlist-numbering", "--playlist-retain-track-cover"]
            elif valid and typ == "album":
                out_tmpl = str(self.output_directory / "{artists}/{album}/{artist} - {title}.{output-ext}")
                extra = None
            else:
                out_tmpl = str(self.output_directory / "{artists} - {title}.{output-ext}")
                extra = None

            success = False
            for attempt in range(1, self.max_retries + 1):
                if attempt > 1:
                    Enhanced_Menu.print_status(f"Retry {attempt}/{self.max_retries}", "info")
                    time.sleep(self.retry_delay)
                if self.run_download(url, out_tmpl, additional_args=extra):
                    success = True
                    break
            if success:
                success_count += 1
                self.log_manager.log_success(f"Downloaded: {url}")
                # Mark as DOWNLOADED in file
                for idx, line in enumerate(updated_lines):
                    if line.strip().startswith(url.split("#")[0].strip()):
                        if "#" in line:
                            base = line.split("#")[0].strip()
                            updated_lines[idx] = f"{base} # DOWNLOADED"
                        else:
                            updated_lines[idx] = f"{line} # DOWNLOADED"
                        break
            else:
                failed_count += 1
                self.log_manager.log_failure(f"Failed: {url}")
                for idx, line in enumerate(updated_lines):
                    if line.strip().startswith(url.split("#")[0].strip()):
                        if "#" in line:
                            base = line.split("#")[0].strip()
                            updated_lines[idx] = f"{base} # FAILED"
                        else:
                            updated_lines[idx] = f"{line} # FAILED"
                        break

        # Write updated file
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(updated_lines))
        except Exception as e:
            self.log_manager.log_failure(f"Could not update file: {e}")

        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Batch Download Summary")
        Enhanced_Menu.print_status(f"Successful: {success_count}", "success")
        Enhanced_Menu.print_status(f"Failed: {failed_count}", "failure" if failed_count > 0 else "info")
        Enhanced_Menu.print_status(f"Total: {len(urls_to_download)}", "info")
        return failed_count == 0

    def search_and_download(self) -> bool:
        """Search for a song by name and download."""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Search & Download")
        song_query = Enhanced_Menu.get_input("Enter song name or search query", "str")
        if not song_query:
            Enhanced_Menu.print_status("No query entered", "error")
            return False

        if Enhanced_Menu.get_input("Configure download settings?", "yn", default=False):
            self.get_user_preferences()

        output_template = str(self.output_directory / "{artists} - {title}.{output-ext}")
        success = False
        for attempt in range(1, self.max_retries + 1):
            Enhanced_Menu.print_status(f"Attempt {attempt}/{self.max_retries}", "info")
            if attempt > 1:
                Enhanced_Menu.print_status(f"Waiting {self.retry_delay} seconds before retry...", "info")
                time.sleep(self.retry_delay)
            try:
                if self.run_download(f":{song_query}", output_template):
                    success = True
                    break
            except Exception as e:
                self.log_manager.log_error(f"Unexpected error: {e}")
        if success:
            self.log_manager.log_success(f"Successfully downloaded: '{song_query}'")
            return True
        else:
            self.log_manager.log_failure(f"Failed to download after {self.max_retries} attempts: '{song_query}'")
            return False

    # ====================================
    # Special Download Functions
    # ===================================
    def download_user_playlist(self):
        """Download a user's playlist (requires authentication)"""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("User Playlist Download", "Download your personal playlists")

        Enhanced_Menu.print_status("Note: This requires Spotify authentication", "warning")
        Enhanced_Menu.print_status("You will be redirected to the Spotify website for authorization", "info")

        proceed = Enhanced_Menu.get_input("Continue? (y/n): ", "yn", default=True)
        if not proceed:
            return False

        if Enhanced_Menu.get_input("Configure download settings? (y/n): ", "yn", default=False):
            self.get_user_preferences()

        output_template = str(self.output_directory / "{playlist}/{artists} - {title}.{output-ext}")

        Enhanced_Menu.print_status("Starting download...", "info")

        try:
            result = subprocess.run([
                "spotdl",
                "download",
                "all-user-playlists",
                "--user-auth",
                "--client-id", self.client_id,
                "--client-secret", self.client_secret,
                "--output", output_template,
                "--overwrite", "skip",
                "--bitrate", self.audio_quality,
                "--format", self.audio_format,
            ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                timeout=self.download_timeout
            )

            if result.returncode == 0:
                self.log_manager.log_success("Successfully downloaded user playlists")
                if result.stdout:
                    print(f"\n{Fore.CYAN}Output:{Style.RESET_ALL}")
                    print(result.stdout[:500])
                return True
            else:
                self.log_manager.log_failure(f"Failed to download user playlists. Return code: {result.returncode}")
                if result.stderr:
                    self.log_manager.log_error(f"Error: {result.stderr[:500]}")
                return False

        except Exception as e:
            self.log_manager.log_error(f"Unexpected exception: {e}")
            return False

    def download_user_liked_songs(self):
        """Download a user's liked songs"""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Download Liked Songs", "Download your liked songs")

        Enhanced_Menu.print_status("Note: This requires Spotify authentication", "warning")
        Enhanced_Menu.print_status("You will be redirected to the Spotify website for authorization", "info")

        proceed = Enhanced_Menu.get_input("Continue? (y/n): ", "yn", default=True)
        if not proceed:
            return False

        if Enhanced_Menu.get_input("Configure download settings? (y/n): ", "yn", default=False):
            self.get_user_preferences()

        output_template = str(self.output_directory / "Liked Songs/{artists} - {title}.{output-ext}")
        Enhanced_Menu.print_status("Starting download...", "info")

        try:
            result = subprocess.run([
                "spotdl",
                "download",
                "saved",
                "--user-auth",
                "--client-id", self.client_id,
                "--client-secret", self.client_secret,
                "--output", output_template,
                "--overwrite", "skip",
                "--bitrate", self.audio_quality,
                "--format", self.audio_format,
            ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                timeout=self.download_timeout
            )

            if result.returncode == 0:
                self.log_manager.log_success("Successfully downloaded liked songs")
                if result.stdout:
                    print(f"\n{Fore.CYAN}Output:{Style.RESET_ALL}")
                    print(result.stdout[:500])
                return True
            else:
                self.log_manager.log_failure(f"Failed to download liked songs. Return code: {result.returncode}")
                if result.stderr:
                    self.log_manager.log_error(f"Error: {result.stderr[:500]}")
                return False

        except Exception as e:
            self.log_manager.log_error(f"Unexpected exception: {e}")
            return False

    def download_user_saved_albums(self):
        """Download a user's saved albums"""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Download Saved Albums", "Download your saved albums")

        Enhanced_Menu.print_status("Note: This requires Spotify authentication", "warning")
        Enhanced_Menu.print_status("You will be redirected to the Spotify website for authorization", "info")

        proceed = Enhanced_Menu.get_input("Continue? (y/n): ", "yn", default=True)
        if not proceed:
            return False

        if Enhanced_Menu.get_input("Configure download settings? (y/n): ", "yn", default=False):
            self.get_user_preferences()

        output_template = str(self.output_directory / "{artists}/{album}/{artists} - {title}.{output-ext}")

        Enhanced_Menu.print_status("Starting download...", "info")

        try:
            result = subprocess.run([
                "spotdl",
                "download",
                "all-user-saved-albums",
                "--user-auth",
                "--client-id", self.client_id,
                "--client-secret", self.client_secret,
                "--output", output_template,
                "--overwrite", "skip",
                "--bitrate", self.audio_quality,
                "--format", self.audio_format,
            ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                timeout=self.download_timeout
            )

            if result.returncode == 0:
                self.log_manager.log_success("Successfully downloaded saved albums")
                if result.stdout:
                    print(f"\n{Fore.CYAN}Output:{Style.RESET_ALL}")
                    print(result.stdout[:500])
                return True
            else:
                self.log_manager.log_failure(f"Failed to download saved albums. Return code: {result.returncode}")
                if result.stderr:
                    self.log_manager.log_error(f"Error: {result.stderr[:500]}")
                return False

        except Exception as e:
            self.log_manager.log_error(f"Unexpected exception: {e}")
            return False

    # ====================================
    # Check Spotdl Functions
    # ===================================
    def check_spotdl(self):
        """Check if spotdl is installed using utils"""
        return self.utils.check_spotdl()

    def check_ffmpeg(self):
        """Check if ffmpeg is installed using utils"""
        return self.utils.check_ffmpeg()

    def show_spotdl_help(self):
        """Display spotdl help"""
        try:
            result = subprocess.run(["spotdl", "--help"], capture_output=True, text=True)
            print(result.stdout)
        except Exception as e:
            print(f"Error showing help: {e}")

    def check_dependencies(self):
        """Check for missing dependencies using utils"""
        return self.utils.check_dependencies()

    def setup_dependencies(self):
        """Setup dependencies using utils"""
        self.utils.setup_dependencies()

    def program_info(self):
        """Display program information using utils"""
        return self.utils.program_info()

    def troubleshooting(self):
        """Run a diagnostic and suggest fixes."""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Troubleshooting")
        print("Running diagnostics...\n")

        # spotdl
        Enhanced_Menu.print_status("1. Checking spotdl...", "info")
        if not self.check_spotdl():
            if Enhanced_Menu.get_input("Install spotdl now?", "yn", default=True):
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "spotdl"])
                except Exception as e:
                    Enhanced_Menu.print_status(f"Installation failed: {e}", "error")
        # ffmpeg
        Enhanced_Menu.print_status("\n2. Checking ffmpeg...", "info")
        self.check_ffmpeg()
        # network test
        Enhanced_Menu.print_status("\n3. Testing Spotify access...", "info")
        test_url = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"  # public track
        available, msg, _ = self.validate_resource(test_url)
        if available:
            Enhanced_Menu.print_status("Spotify accessible", "success")
        else:
            Enhanced_Menu.print_status(f"Spotify access issue: {msg}", "error")
        # directories
        Enhanced_Menu.print_status("\n4. Checking directories...", "info")
        for d in ["Albums", "links"]:
            p = Path(d)
            if p.exists():
                Enhanced_Menu.print_status(f"  {d}/ exists", "success")
            else:
                Enhanced_Menu.print_status(f"  {d}/ missing (will be created)", "warning")
        input("\nPress Enter to continue...")
        return True

def main():
    """Main menu loop."""
    Enhanced_Menu.clear_screen()

    # ASCII art header
    print(f"{Fore.CYAN}{'=' * 80}{Style.RESET_ALL}")
    print(f"""{Fore.GREEN}{Style.BRIGHT}
    ███╗   ███╗██╗   ██╗███████╗██╗ ██████╗     ██████╗ ██████╗ ███╗   ██╗██╗   ██╗███████╗██████╗ ████████╗███████╗██████╗ 
    ████╗ ████║██║   ██║██╔════╝██║██╔════╝    ██╔════╝██╔═══██╗████╗  ██║██║   ██║██╔════╝██╔══██╗╚══██╔══╝██╔════╝██╔══██╗
    ██╔████╔██║██║   ██║███████╗██║██║         ██║     ██║   ██║██╔██╗ ██║██║   ██║█████╗  ██████╔╝   ██║   █████╗  ██████╔╝
    ██║╚██╔╝██║██║   ██║╚════██║██║██║         ██║     ██║   ██║██║╚██╗██║╚██╗ ██╔╝██╔══╝  ██╔══██╗   ██║   ██╔══╝  ██╔══██╗
    ██║ ╚═╝ ██║╚██████╔╝███████║██║╚██████╗    ╚██████╗╚██████╔╝██║ ╚████║ ╚████╔╝ ███████╗██║  ██║   ██║   ███████╗██║  ██║
    ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝ ╚═════╝     ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝                                                                                                 
    {Style.RESET_ALL}""")
    print(f"{Fore.CYAN}{'=' * 80}{Style.RESET_ALL}")

    downloader = Spotify_Downloader()

    # Menu actions
    def settings_menu():
        """Submenu for program settings."""
        while True:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Program Settings")
            Enhanced_Menu.print_section("Audio Settings")
            Enhanced_Menu.print_menu_item(1, f"Audio Format (current: {downloader.audio_format.upper()})")
            Enhanced_Menu.print_menu_item(2, f"Audio Quality (current: {downloader.audio_quality})")
            Enhanced_Menu.print_section("Output")
            Enhanced_Menu.print_menu_item(3, f"Output Directory (current: {downloader.output_directory})")
            Enhanced_Menu.print_section("Configuration")
            Enhanced_Menu.print_menu_item(4, "Save Settings")
            Enhanced_Menu.print_menu_item(5, "Load Settings")
            Enhanced_Menu.print_menu_item(6, "Reset to Defaults")
            Enhanced_Menu.print_section("Navigation")
            Enhanced_Menu.print_menu_item(7, "Back to Main Menu")

            choice = Enhanced_Menu.get_input("Select option", "int", 1, 7)
            if choice == 1:
                fmt = Enhanced_Menu.get_input("Enter format (mp3, flac, m4a, opus, ogg, wav)", "str",
                                              default=downloader.audio_format)
                if fmt:
                    downloader.audio_format = fmt
            elif choice == 2:
                q = Enhanced_Menu.get_input("Enter bitrate (e.g., 320k, 192k, auto)", "str",
                                            default=downloader.audio_quality)
                if q:
                    downloader.audio_quality = q
            elif choice == 3:
                d = Enhanced_Menu.get_input("Enter output directory", "str", default=str(downloader.output_directory))
                if d:
                    downloader.output_directory = d
            elif choice == 4:
                downloader.save_config()
                Enhanced_Menu.print_status("Settings saved", "success")
                time.sleep(1)
            elif choice == 5:
                downloader.load_config()
                Enhanced_Menu.print_status("Settings loaded", "success")
                time.sleep(1)
            elif choice == 6:
                if Enhanced_Menu.get_input("Reset all settings to defaults?", "yn", default=False):
                    downloader.reset_config()
                    Enhanced_Menu.print_status("Settings reset", "success")
                    time.sleep(1)
            elif choice == 7:
                break
            input("Press Enter to continue...")

    def exit_program():
        """Clean shutdown."""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Thank you for using Spotify Downloader!")
        print("\nGoodbye!\n")
        downloader.cleanup_directory()
        sys.exit(0)

    actions = {
        1: downloader.download_track,
        2: downloader.download_album,
        3: downloader.download_playlist,
        4: downloader.download_from_file,
        5: downloader.search_and_download,
        6: downloader.download_user_playlist,
        7: downloader.download_user_liked_songs,
        8: downloader.download_user_saved_albums,
        9: downloader.check_spotdl,
        10: downloader.show_spotdl_help,
        11: settings_menu,
        12: downloader.troubleshooting,
        13: lambda: downloader.cookie_manager.interactive_menu(),
        14: downloader.program_info,
        15: exit_program
    }

    # Main loop
    while True:
        try:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Main Menu", "Select an option")

            Enhanced_Menu.print_section("📥 Download")
            Enhanced_Menu.print_menu_item(1, "Download Track")
            Enhanced_Menu.print_menu_item(2, "Download Album")
            Enhanced_Menu.print_menu_item(3, "Download Playlist")
            Enhanced_Menu.print_menu_item(4, "Batch Download (from file)")
            Enhanced_Menu.print_menu_item(5, "Search & Download")

            Enhanced_Menu.print_section("👤 Personal (requires login)")
            Enhanced_Menu.print_menu_item(6, "Download Your Playlists")
            Enhanced_Menu.print_menu_item(7, "Download Liked Songs")
            Enhanced_Menu.print_menu_item(8, "Download Saved Albums")

            Enhanced_Menu.print_section("🛠️ Tools")
            Enhanced_Menu.print_menu_item(9, "Check spotdl Installation")
            Enhanced_Menu.print_menu_item(10, "Show spotdl Help")
            Enhanced_Menu.print_menu_item(11, "Settings")
            Enhanced_Menu.print_menu_item(12, "Troubleshooting")
            Enhanced_Menu.print_menu_item(13, "Cookie Manager")

            Enhanced_Menu.print_section("ℹ️ Info")
            Enhanced_Menu.print_menu_item(14, "About")
            Enhanced_Menu.print_menu_item(15, "Exit")

            print(f"\n{Style.DIM}Current settings: {downloader.audio_format.upper()} / {downloader.audio_quality} / {downloader.output_directory}{Style.RESET_ALL}")

            choice = Enhanced_Menu.get_input("Enter choice", "int", 1, 15)
            if choice == 13:
                downloader.cookie_manager.interactive_menu()
                downloader.sync_credentials_from_cookie_manager()   # <-- add this line
                input("\nPress Enter to continue...")
                continue   # or let the loop handle the return to menu
            
            if choice == 15:
                exit_program()
            action = actions.get(choice)
            if action:
                Enhanced_Menu.clear_screen()
                try:
                    result = action()
                    if result is False:  # explicit failure
                        Enhanced_Menu.print_status("Operation failed", "failure")
                    elif result is None:  # cancelled etc.
                        Enhanced_Menu.print_status("Operation cancelled", "info")
                except KeyboardInterrupt:
                    Enhanced_Menu.print_status("Interrupted", "warning")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Unexpected error: {e}", "error")
            else:
                Enhanced_Menu.print_status("Invalid choice", "error")

            if choice != 15:
                if Enhanced_Menu.get_input("Return to main menu?", "yn", default=True):
                    continue
                else:
                    exit_program()
                    
        except KeyboardInterrupt:
            print("\nInterrupted by user")
            exit_program()
        except Exception as e:
            if Enhanced_Menu.get_input("Continue?", "yn", default=True):
                continue
            else:
                exit_program()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting... Goodbye!")
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)