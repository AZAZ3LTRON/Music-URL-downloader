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

Please make sure you use a VPN in tandem with the program

Enjoy!
"""

import re
import sys
import os
import subprocess
import time
import hashlib
import threading
import json

from functools import wraps
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from colorama import init, Fore, Style

from utils.CookieManager import CookieManager
from utils.DownloaderUtils import DownloaderUtils 
from utils.EnhancedMenu import Enhanced_Menu
from utils.Logs_Handler import Logs_Manager
from utils.DownloadHistory import DownloadHistory
from utils.Validators import Helpers 

init(autoreset=True)
# ========================= Configuration ==========================

MAX_RETRIES = 3
RETRY_DELAY = 10
DOWNLOAD_TIMEOUT = 120
COOKIE_DIRECTORY = r"cookies"
os.makedirs(COOKIE_DIRECTORY, exist_ok=True)

class SpotifyMusicDownloader:
    """Downloader class"""
    def __init__(self):
        """Initialize the downloader with default values"""
        self.__output_directory = Path.home() / "Music" / "SpotifyDownloads"
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.__configuration_file = r"config/SpotifyMusicDownloader.json"
        self.cookie_manager = CookieManager()
        self.log_manager = Logs_Manager()          # must be thread‑safe now
        self.utils = DownloaderUtils()
        self.history = DownloadHistory()
        self.use_cookies = False

        self.max_retries = 3
        self.retry_delay = 10
        self.download_timeout = 120
                
        self.archives_dir = Path("archives")
        self.archives_dir.mkdir(exist_ok=True)
        self.__output_directory.mkdir(parents=True, exist_ok=True)
        
    # Ensure config directory exists
        os.makedirs(os.path.dirname(self.__configuration_file), exist_ok=True)
               
        try:
            self.load_config()
        except Exception as e:
            self.log_manager.log_error(f"Error loading config: {e}")
            
    # ==================== Public Properties ====================
    @property
    def audio_format(self) -> str:
        """Current audio format (mp3, flac, etc.)"""
        return self.__audio_format

    @audio_format.setter
    def audio_format(self, value: str):
        if value in ["mp3", "flac", "ogg", "opus", "m4a", "wav"]:
            self.__audio_format = value
        else:
            raise ValueError(f"Unsupported audio format: {value}")

    @property
    def audio_quality(self) -> str:
        """Current audio bitrate (320k, 192k, auto, etc.)"""
        return self.__audio_quality

    @audio_quality.setter
    def audio_quality(self, value: str):
        valid_qualities = ["auto", "disable", "8k", "16k", "24k", "32k", "40k", "48k", "64k",
                        "80k", "96k", "112k", "128k", "160k", "192k", "224k", "256k", "320k"]
        if value in valid_qualities:
            self.__audio_quality = value
        else:
            raise ValueError(f"Unsupported audio quality: {value}")

    @property
    def output_directory(self) -> Path:
        """Output directory path"""
        return self.__output_directory

    @output_directory.setter
    def output_directory(self, path: Path):
        self.__output_directory = Path(path)
        self.__output_directory.mkdir(parents=True, exist_ok=True)
        
    # ==================== Configuration Managers ====================
    
    # Added history_method
    def _log_download(self, url, item_type, status, metadata=None, error=None):
        self.history.add_entry(url, item_type, status, metadata=metadata, error=error)
            
    def load_config(self):
        """Load configuration from json file"""
        primary_config = {
            "output_directory": Path.home() / "Music" / "SpotifyDownloads",
            "audio_quality": "320k",
            "audio_format": "mp3",
            "max_retries": 3,
            "retry_delay": 10,
            "download_timeout": 120,
            "use_cookies": False,
        }
        try:
            if os.path.exists(self.__configuration_file):
                with open(self.__configuration_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    config = {**primary_config, **user_config}
            else:
                config = primary_config
                self.save_config(config)

            self.__output_directory = Path(config["output_directory"])
            self.__audio_quality = config["audio_quality"]
            self.__audio_format = config["audio_format"]
            self.use_cookies = config["use_cookies"]
            
            # Update retry/delay settings
            self.max_retries = config.get("max_retries", 3)
            self.retry_delay = config.get("retry_delay", 10)
            self.download_timeout = config.get("download_timeout", 120)

        except Exception as e:
            self.log_manager.log_error(f"Error loading configuration: {e}")
            self.__output_directory = Path(primary_config["output_directory"])
            self.__audio_quality = primary_config["audio_quality"]
            self.__audio_format = primary_config["audio_format"]
            self.use_cookies = primary_config["use_cookies"]

    def save_config(self, config: Dict = None):
        """Save configuration to file"""
        try:
            os.makedirs(os.path.dirname(self.__configuration_file), exist_ok=True)
            if config is None:
                config = {
                    "output_directory": str(self.__output_directory),
                    "audio_quality": self.__audio_quality,
                    "audio_format": self.__audio_format,
                    "max_retries": self.max_retries,
                    "retry_delay": self.retry_delay,
                    "download_timeout": self.download_timeout,
                    "use_cookies": self.use_cookies,
                }
            with open(self.__configuration_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log_manager.log_error(f"Error saving configuration: {e}")
            
    # ==================== User preferences (stays in main class) ====================
    def get_user_preferences(self):
            """Takes in user input for the download settings"""
            Enhanced_Menu.print_header("Download Settings", "Configure your music conversion preferences")

            # Audio quality
            while True:
                audio_quality_input = Enhanced_Menu.get_input(
                    "What bitrate would you like (enter 'choice' to see options) ",
                    "str", default=self.__audio_quality)
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

            # Audio format
            while True:
                audio_format_input = Enhanced_Menu.get_input(
                    "What format would you like (enter 'choice' to see options) ",
                    "str", default=self.__audio_format)
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

            # Output directory
            output_path = Enhanced_Menu.get_input(f"Enter output directory (default{self.__output_directory}): ", "str").strip()
            if output_path:
                self.__output_directory = Path(output_path)
            else:
                self.__output_directory = Path.home() / "Music" / "SpotifyDownloads"
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
    # ================================================== Core Download Functions ==================================================
    def run_download(self, url: str, output_template: str = None, extra_args: List[str] = None,
                    total_items: int = None, item_desc: str = "item") -> bool:
        """Run spotdl with a custom progress bar, showing errors immediately on failure."""
        cmd = [
            "spotdl", "download", url,
            "--format", self.audio_format,
            "--bitrate", self.audio_quality,
            "--output", output_template,
            "--overwrite", "skip",
            "--print-errors"
        ]
        if extra_args:
            cmd.extend(extra_args)

        # Setup progress bar
        if total_items:
            pbar = tqdm(total=total_items, desc=f"Downloading {item_desc}s", unit=item_desc,
                        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]")
        else:
            pbar = tqdm(desc="Downloading", unit=" steps", total=None,
                        bar_format="{l_bar}{bar}| {n_fmt} steps [{elapsed}]")

        # We'll store all output lines to inspect on failure
        output_lines = []

        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1, universal_newlines=True)

            completed = 0
            last_percent = 0

            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if not line:
                    continue

                # Keep the line for potential error display
                output_lines.append(line)
                # Limit memory – keep only last 1000 lines (adjust as needed)
                if len(output_lines) > 1000:
                    output_lines = output_lines[-200:]   # keep recent 200

                # --- Completion signals ---
                if any(phrase in line for phrase in ["Finished downloading", "Saved", "Download completed"]):
                    completed += 1
                    if total_items:
                        pbar.update(1)
                        pbar.set_description(f"Completed {completed}/{total_items}")
                    else:
                        pbar.update(1)
                        pbar.set_description(f"Processed {completed} items" if completed > 0 else "Processing")
                    last_percent = 0

                # --- Percentage from yt-dlp (if present) ---
                percent_match = re.search(r'(\d+\.?\d*)%', line)
                if percent_match:
                    percent = float(percent_match.group(1))
                    if total_items is None or total_items == 1:
                        pbar.n = percent / 100.0
                        pbar.set_description(f"Downloading {percent:.1f}%")
                        pbar.refresh()

                # --- Speed / ETA (only for single item) ---
                speed_match = re.search(r'at\s+([\d\.]+\s*[KMGT]?i?B/s)', line)
                if speed_match and (total_items is None or total_items == 1):
                    pbar.set_postfix_str(f"Speed: {speed_match.group(1)}")
                eta_match = re.search(r'ETA\s+([\d:]+)', line)
                if eta_match and (total_items is None or total_items == 1):
                    pbar.set_postfix_str(f"ETA: {eta_match.group(1)}")

            process.wait()
            pbar.close()

            if process.returncode == 0:
                if total_items:
                    self.log_manager.log_success(f"Downloaded {completed}/{total_items} {item_desc}s from {url}")
                return True
            else:
                # Extract lines that look like errors (contain 'error', 'downloaderror', etc.)
                error_keywords = ['error', 'fail', 'blocked', 'unavailable', 'private',
                                'forbidden', 'not found', 'quota', 'rate limit']
                error_lines = []
                for line in output_lines:
                    if any(keyword in line.lower() for keyword in error_keywords):
                        error_lines.append(line)

                # If no obvious error lines, show the last few lines
                if not error_lines:
                    error_lines = output_lines[-5:]

                # Display the errors immediately to the console
                print(f"\n{Fore.RED}===== spotdl error output ====={Style.RESET_ALL}")
                for err_line in error_lines:
                    print(f"{Fore.RED}{err_line}{Style.RESET_ALL}")
                print(f"{Fore.RED}==============================={Style.RESET_ALL}\n")

                # Log each error line to error.log (without console output, to avoid duplication)
                for err_line in error_lines:
                    self.log_manager.log_error(f"spotdl: {err_line}", console=False)

                # Also log a summary failure
                self.log_manager.log_failure(f"spotdl failed for {url}")
                return False

        except Exception as e:
            self.log_manager.log_error(f"Download process exception: {e}", console=True)
            pbar.close()
            return False
           
    def _download_with_retry(self, url: str, output_template: str, extra_args: list = None,
                            item_type: str = "item", total_items: int = None) -> bool:
        """Unified retry logic for downloads"""
        for attempt in range(1, self.max_retries + 1):   # ← use instance attribute
            Enhanced_Menu.print_section(f"Downloading {item_type} (Attempt {attempt}/{self.max_retries})")
            if attempt > 1:
                print(f"Waiting {self.retry_delay} seconds before retry...")
                time.sleep(self.retry_delay)

            try:
                success = self.run_download(url, output_template, extra_args,
                                            total_items=total_items, item_desc=item_type)
                if success:
                    self.log_manager.log_success(f"Successfully downloaded {item_type}: {url}")
                    if item_type in ['album', 'playlist', 'artist']:
                        Helpers.cleanup_directory(self.__output_directory, self.log_manager)
                    return True
            except Exception as e:
                self.log_manager.log_error(f"Attempt {attempt} failed: {e}")
                if attempt == self.max_retries:
                    self.log_manager.log_failure(f"Failed after {self.max_retries} attempts: {url}")
        return False
    
    def _download_items_concurrently(self, tasks, max_workers=3, desc="Downloading"):
        """
        tasks: list of (url, output_template, additional_args, archive_path, task_id)
        returns: dict {task_id: success_bool}
        """
        total = len(tasks)
        results = {}
        result_lock = threading.Lock()
        archive_locks = {}
        archive_locks_lock = threading.Lock()
        pbar_lock = threading.Lock()

        with tqdm(total=total, desc=desc, unit="items") as pbar:
            def worker(url, tmpl, args, archive_path, task_id):
                with archive_locks_lock:
                    if archive_path not in archive_locks:
                        archive_locks[archive_path] = threading.Lock()
                    lock = archive_locks[archive_path]

                with lock:
                    # Acquiring the lock ensures that only one spotdl process
                    # writes to this archive file at a time, preventing corruption.
                    success = self._download_with_retry(url, tmpl, args, "item")

                with result_lock:
                    results[task_id] = success
                with pbar_lock:
                    pbar.update(1)
                return success

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for url, tmpl, args, archive_path, tid in tasks:
                    futures.append(executor.submit(worker, url, tmpl, args, archive_path, tid))
                for future in as_completed(futures):
                    pass   # exceptions already handled inside _download_with_retry

        return results
        
    def _download_playlist_direct(self, url: str) -> bool:
        """Direct playlist download (reused by smart download)"""
        # Validate resource
        is_valid, message, metadata = Helpers.validate_spotify_url(url)
        if not is_valid or metadata.get('type') != 'playlist':
            Enhanced_Menu.print_status(f"Validation failed: {message}", "failure")
            return False
        
        playlist_count = metadata.get('playlist_count', 0)
        if playlist_count == 0:
            Enhanced_Menu.print_status("No tracks found in playlist.", "warning")
            return False
        
        playlist_title = metadata.get('title', 'Unknown Playlist')
        Enhanced_Menu.print_status(f"Playlist: {playlist_title} ({playlist_count} tracks)", "success")
        
        if playlist_count > 50:
            if not Enhanced_Menu.get_input(f"This playlist has {playlist_count} tracks. Continue? (y/n)", "yn", default=False):
                Enhanced_Menu.print_status("Download cancelled.", "info")
                return False
        
        if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
            self.get_user_preferences()
        
        items = Helpers.get_spotify_playlist_items(url, self.log_manager)
        if not items:
            Enhanced_Menu.print_status("Failed to retrieve playlist items.", "error")
            return False
        
        order = Enhanced_Menu.get_input("Download order: (t)op-to-bottom or (b)ottom-to-top", "str", default="t")
        if order.lower() == 'b':
            items.reverse()
        
        playlist_id = re.search(r'playlist/([a-zA-Z0-9]+)', url)
        if playlist_id:
            archive_path = self.archives_dir / f"playlist_{playlist_id.group(1)}.spotdl"
        else:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            archive_path = self.archives_dir / f"playlist_{url_hash}.spotdl"
        
        safe_title = Helpers.sanitize_filename(playlist_title)
        playlist_folder = self.__output_directory / safe_title
        playlist_folder.mkdir(parents=True, exist_ok=True)
        output_template = str(playlist_folder / "{artist} - {title}.{output-ext}")
        
        tasks = []
        for idx, item in enumerate(items):
            search_term = f"{item['artist']} - {item['title']}"
            task_id = f"{idx}_{hashlib.md5(search_term.encode()).hexdigest()[:8]}"
            additional_args = ["--save-file", str(archive_path)]
            tasks.append((search_term, output_template, additional_args, archive_path, task_id))
        
        if not tasks:
            Enhanced_Menu.print_status("No tracks to download.", "warning")
            return False
        
        Enhanced_Menu.print_status(f"Starting concurrent download of {len(tasks)} tracks (max 3 at a time)...", "info")
        results = self._download_items_concurrently(tasks, max_workers=3, desc="Playlist Download")
        
        success_count = sum(1 for v in results.values() if v)
        failed_count = len(results) - success_count
        
        print("\n" + "=" * 55)
        Enhanced_Menu.print_header("Playlist Download Complete")
        print(f"  {Fore.GREEN}Successfully downloaded: {success_count}{Style.RESET_ALL}")
        if failed_count > 0:
            print(f"  {Fore.RED}Failed: {failed_count}{Style.RESET_ALL}")
        print("=" * 55)
        
        return failed_count == 0

    def _download_item(self, item_type: str, url_prompt: str, output_template: str,
                       confirm_large: bool = False, use_archive: bool = False,
                       force_url: str = None) -> bool:
        """Unified download function for tracks and albums (playlist handled separately)"""
        while True:
            print("\n" + "=" * 55)
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header(f"Download {item_type.title()}")
            
            if force_url:
                url = force_url
            else:
                url = Enhanced_Menu.get_input(f"Enter Spotify {url_prompt} (or 'back' to return)", "str")
                if url.lower() == 'back':
                    return False
            
            if not url:
                Enhanced_Menu.print_status("No URL provided", "error")
                if force_url:
                    return False
                continue
            
            self.history.add_input(url, item_type)
            
            is_valid, message, metadata = Helpers.validate_resource_spotify(url)
            if not is_valid:
                Enhanced_Menu.print_status(f"Validation failed: {message}", "error")
                if force_url:
                    return False
                continue
            
            Enhanced_Menu.print_status("Resource information:", "success")
            if item_type == "track":
                title = metadata.get('title', 'Unknown')
                artist = metadata.get('artist', 'Unknown Artist')
                album = metadata.get('album', 'Unknown Album')
                print(f"  {Fore.CYAN}Track:{Style.RESET_ALL} {title}")
                print(f"  {Fore.CYAN}Artist:{Style.RESET_ALL} {artist}")
                if album != 'Unknown Album':
                    print(f"  {Fore.CYAN}Album:{Style.RESET_ALL} {album}")
            elif item_type == "album":
                album_title = metadata.get('title', 'Unknown Album')
                album_artist = metadata.get('artist', 'Unknown Artist')
                track_count = metadata.get('playlist_count', '?')
                print(f"  {Fore.CYAN}Album:{Style.RESET_ALL} {album_title}")
                print(f"  {Fore.CYAN}Artist:{Style.RESET_ALL} {album_artist}")
                print(f"  {Fore.CYAN}Tracks:{Style.RESET_ALL} {track_count}")
            
            elif item_type == "artist":
                artist = metadata.get('artist', 'Unknown Artist')
                print(f"  {Fore.CYAN}Artist:{Style.RESET_ALL} {artist}")
            print()
            
            if confirm_large and metadata.get('playlist_count', 0) > 50:
                count = metadata['playlist_count']
                Enhanced_Menu.print_status(f"This {item_type} contains {count} items. This may take a while.", "warning")
                if not Enhanced_Menu.get_input("Continue with download? (y/n)", "yn", default=False):
                    Enhanced_Menu.print_status("Download cancelled", "info")
                    if force_url:
                        return False
                    continue
                
            total = metadata.get('playlist_count', None) if item_type in ['album', 'playlist'] else None
            if use_archive:
                if 'album' in url:
                    album_id = re.search(r'album/([a-zA-Z0-9]+)', url)
                    if album_id:
                        archive_path = self.archives_dir / f"album_{album_id.group(1)}.spotdl"
                    else:
                        archive_path = self.archives_dir / f"album_{hashlib.md5(url.encode()).hexdigest()[:8]}.spotdl"
                else:
                    archive_path = self.archives_dir / f"item_{hashlib.md5(url.encode()).hexdigest()[:8]}.spotdl"
                
                additional_args = ["--save-file", str(archive_path)]
            else:
                additional_args = None
            
            if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
                self.get_user_preferences()
            
            Enhanced_Menu.print_status(f"Starting {item_type} download...", "info")
            success = self._download_with_retry(url, output_template, additional_args, item_type, total_items=total)
            
            if force_url:
                return success
            
            if success:
                time.sleep(0.5)
                another = Enhanced_Menu.get_input(f"\nDownload another {item_type}? (y/n): ", "yn", default=True)
                if another:
                    continue
                else:
                    return True
            else:
                retry = Enhanced_Menu.get_input(f"\nDownload failed. Try another {item_type}? (y/n): ", "yn", default=True)
                if retry:
                    continue
                else:
                    return False

    # ================================================== Download Functions ==================================================
    def download_track(self):
        """Download a single track"""
        return self._download_item(
            item_type="track",
            url_prompt="track URL",
            output_template=str(self.__output_directory / "{artist} - {title}.{output-ext}"),
            confirm_large=False
        )

    def download_album(self):
        """Download an album"""
        return self._download_item(
            item_type="album",
            url_prompt="album URL",
            output_template=str(self.__output_directory / "{artist}/{album}/{artist} - {title}.{output-ext}"),
            confirm_large=True,
            use_archive=True
        )

    def download_playlist(self):
        """Download a playlist (original method)"""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Download Playlist")
        url = Enhanced_Menu.get_input("Enter Spotify playlist URL (or 'back' to return): ", "str")
        if url.lower() == 'back':
            return False
        self.history.add_input(url, "playlist")
        return self._download_playlist_direct(url)
             
    def search_and_download(self):
        """Search for a song by name and download."""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Search & Download")
        song_query = Enhanced_Menu.get_input("Enter song name or search query", "str")
        if not song_query:
            Enhanced_Menu.print_status("No query entered", "error")
            return False
        self.history.add_input(song_query, "search")
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
    
    # Don't use method as issues with spotdl are yet to be resolved
    def download_artist(self):
        """Download an artist"""
        return self._download_item(
            item_type="artist",
            url_prompt="artist URL",
            output_template=str(self.__output_directory / "{artist}.{output-ext}"),
            confirm_large=True,
            use_archive=True
        )
    
    #  ================================= Problem with functions as spotdl login features has been disabled, till better one is writing  =================================
    
    # def download_user_playlist(self):
    #     """Download a user's playlist (requires authentication)"""
    #     Enhanced_Menu.clear_screen()
    #     Enhanced_Menu.print_header("User Playlist Download", "Download your personal playlists")

    #     Enhanced_Menu.print_status("Note: This requires Spotify authentication", "warning")
    #     Enhanced_Menu.print_status("You will be redirected to the Spotify website for authorization", "info")

    #     proceed = Enhanced_Menu.get_input("Continue? (y/n): ", "yn", default=True)
    #     if not proceed:
    #         return False

    #     if Enhanced_Menu.get_input("Configure download settings? (y/n): ", "yn", default=False):
    #         self.get_user_preferences()

    #     output_template = str(self.output_directory / "{playlist}/{artists} - {title}.{output-ext}")

    #     Enhanced_Menu.print_status("Starting download...", "info")

    #     try:
    #         result = subprocess.run([
    #             "spotdl",
    #             "download",
    #             "all-user-playlists",
    #             "--user-auth",
    #             "--output", output_template,
    #             "--overwrite", "skip",
    #             "--bitrate", self.audio_quality,
    #             "--format", self.audio_format,
    #         ],
    #             stdout=subprocess.PIPE,
    #             stderr=subprocess.PIPE,
    #             text=True,
    #             encoding='utf-8',
    #             timeout=self.download_timeout
    #         )

    #         if result.returncode == 0:
    #             self.log_manager.log_success("Successfully downloaded user playlists")
    #             if result.stdout:
    #                 print(f"\n{Fore.CYAN}Output:{Style.RESET_ALL}")
    #                 print(result.stdout[:500])
    #             return True
    #         else:
    #             self.log_manager.log_failure(f"Failed to download user playlists. Return code: {result.returncode}")
    #             if result.stderr:
    #                 self.log_manager.log_error(f"Error: {result.stderr[:500]}")
    #             return False

    #     except Exception as e:
    #         self.log_manager.log_error(f"Unexpected exception: {e}")
    #         return False

    # def download_user_liked_songs(self):
    #     """Download a user's liked songs"""
    #     Enhanced_Menu.clear_screen()
    #     Enhanced_Menu.print_header("Download Liked Songs", "Download your liked songs")

    #     Enhanced_Menu.print_status("Note: This requires Spotify authentication", "warning")
    #     Enhanced_Menu.print_status("You will be redirected to the Spotify website for authorization", "info")

    #     proceed = Enhanced_Menu.get_input("Continue? (y/n): ", "yn", default=True)
    #     if not proceed:
    #         return False

    #     if Enhanced_Menu.get_input("Configure download settings? (y/n): ", "yn", default=False):
    #         self.get_user_preferences()

    #     output_template = str(self.output_directory / "Liked Songs/{artists} - {title}.{output-ext}")
    #     Enhanced_Menu.print_status("Starting download...", "info")

    #     try:
    #         result = subprocess.run([
    #             "spotdl",
    #             "download",
    #             "saved",
    #             "--user-auth",
    #             "--output", output_template,
    #             "--overwrite", "skip",
    #             "--bitrate", self.audio_quality,
    #             "--format", self.audio_format,
    #         ],
    #             stdout=subprocess.PIPE,
    #             stderr=subprocess.PIPE,
    #             text=True,
    #             encoding='utf-8',
    #             timeout=self.download_timeout
    #         )

    #         if result.returncode == 0:
    #             self.log_manager.log_success("Successfully downloaded liked songs")
    #             if result.stdout:
    #                 print(f"\n{Fore.CYAN}Output:{Style.RESET_ALL}")
    #                 print(result.stdout[:500])
    #             return True
    #         else:
    #             self.log_manager.log_failure(f"Failed to download liked songs. Return code: {result.returncode}")
    #             if result.stderr:
    #                 self.log_manager.log_error(f"Error: {result.stderr[:500]}")
    #             return False

    #     except Exception as e:
    #         self.log_manager.log_error(f"Unexpected exception: {e}")
    #         return False

    # def download_user_saved_albums(self):
    #     """Download a user's saved albums"""
    #     Enhanced_Menu.clear_screen()
    #     Enhanced_Menu.print_header("Download Saved albums", "Download your saved albums")

    #     Enhanced_Menu.print_status("Note: This requires Spotify authentication", "warning")
    #     Enhanced_Menu.print_status("You will be redirected to the Spotify website for authorization", "info")

    #     proceed = Enhanced_Menu.get_input("Continue? (y/n): ", "yn", default=True)
    #     if not proceed:
    #         return False

    #     if Enhanced_Menu.get_input("Configure download settings? (y/n): ", "yn", default=False):
    #         self.get_user_preferences()

    #     output_template = str(self.output_directory / "{artists}/{album}/{artists} - {title}.{output-ext}")

    #     Enhanced_Menu.print_status("Starting download...", "info")

    #     try:
    #         result = subprocess.run([
    #             "spotdl",
    #             "download",
    #             "all-user-saved-albums",
    #             "--user-auth",
    #             "--output", output_template,
    #             "--overwrite", "skip",
    #             "--bitrate", self.audio_quality,
    #             "--format", self.audio_format,
    #         ],
    #             stdout=subprocess.PIPE,
    #             stderr=subprocess.PIPE,
    #             text=True,
    #             encoding='utf-8',
    #             timeout=self.download_timeout
    #         )

    #         if result.returncode == 0:
    #             self.log_manager.log_success("Successfully downloaded saved albums")
    #             if result.stdout:
    #                 print(f"\n{Fore.CYAN}Output:{Style.RESET_ALL}")
    #                 print(result.stdout[:500])
    #             return True
    #         else:
    #             self.log_manager.log_failure(f"Failed to download saved albums. Return code: {result.returncode}")
    #             if result.stderr:
    #                 self.log_manager.log_error(f"Error: {result.stderr[:500]}")
    #             return False

    #     except Exception as e:
    #         self.log_manager.log_error(f"Unexpected exception: {e}")
    #         return False

    # ================================================== Helpers ==================================================
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

    def check_spotdl(self):
        return self.utils.check_spotdl()

    def check_ffmpeg(self):
        return self.utils.check_ffmpeg()

    def show_spotdl_help(self):
        return self.utils.show_spotdl_help

    def check_dependencies(self):
        return self.utils.check_dependencies()

    def setup_spotdl(self):
        self.utils.setup_spotdl()

    def program_info(self):
        return self.utils.program_info()

    def troubleshooting(self):
        print("\n" + "=" * 50)
        Enhanced_Menu.print_header("TROUBLESHOOTING", "")
        print("=" * 50)
        print("Hello, this troubleshooter is to help if you're experiencing problem in the program")
        print("Running a simple diagnostic. This might take a while.....")

        Enhanced_Menu.print_status("1. Checking spotdl installation...", "info")
        if not self.check_spotdl():
            Enhanced_Menu.print_status("spotdl not found or not working", "error")
            install = Enhanced_Menu.get_input("Install spotdl now? (y/n)", "yn", default=True)
            if install:
                self.setup_spotdl()

        Enhanced_Menu.print_status("\n2. Checking FFmpeg installation...", "info")
        if not self.check_ffmpeg():
            Enhanced_Menu.print_status("FFmpeg not found (audio conversion might fail)", "error")

        Enhanced_Menu.print_status("\n3. Testing Spotify access...", "info")
        test_url = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
        try:
            test_command = ["spotdl", "--skip-download", "--print-json", test_url]
            result = subprocess.run(
                test_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                Enhanced_Menu.print_status("Can access Spotify", "success")
            else:
                Enhanced_Menu.print_status(f"Cannot access Spotify: {result.stderr[:100]}", "error")
        except Exception as e:
            Enhanced_Menu.print_status(f"Test failed: {e}", "error")

    def reset_to_defaults(self):
        """Reset all settings to default values"""
        self.__output_directory = Path.home() / "Music" / "SpotifyDownloads"
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.use_cookies = False
        self.save_config()
        Enhanced_Menu.print_status("Settings reset to defaults", "success")
