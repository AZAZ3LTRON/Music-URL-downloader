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
- Progress bar for downloads
- Batch Processing (with parallel downloads)
- Resource Validation (Check if links are available)

Please use the latest version of YT-DLP, upgrade it using "pip install --upgrade yt-dlp" or "yt-dlp -U" depending on how you installed it
Additionally make sure ffmpeg is installed, as that is necessary to parse the music file's metadata if not you will receive postprocessing error in your output

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
from typing import Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from colorama import init, Fore, Style

from utils.CookieManager import CookieManager
from utils.DownloaderUtils import DownloaderUtils 
from utils.EnhancedMenu import Enhanced_Menu#  <-- new helpers module
from utils.Logs_Handler import Logs_Manager
from utils.Validators import Helpers
from utils.DownloadHistory import DownloadHistory
init(autoreset=True)

# ============================= Pre Config =============================
MAX_RETRIES = 3
RETRY_DELAY = 10
DOWNLOAD_TIMEOUT = 120
COOKIE_DIRECTORY = r"cookies"
os.makedirs(COOKIE_DIRECTORY, exist_ok=True)

class YoutubeMusicDownloader:
    """Downloader Class that handles the downloading process"""
    def __init__(self):
        """Initialize the downloader with default values"""
        if 'MAX_RETRIES' not in globals():
            global MAX_RETRIES, RETRY_DELAY, DOWNLOAD_TIMEOUT
            MAX_RETRIES = 3
            RETRY_DELAY = 5
            DOWNLOAD_TIMEOUT = 300

        self.__output_directory = Path.home() / "Music" / "YouTubeMusicDownloads"
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.__configuration_file = r"config/YoutubeMusicDownloader.json"
        self.cookie_manager = CookieManager()
        self.log_manager = Logs_Manager()          # must be thread‑safe now
        self.utils = DownloaderUtils()
        self.history = DownloadHistory()
        self.use_cookies = False
        self.__embed_metadata = False
        
        self.archives_dir = Path("archives")
        self.archives_dir.mkdir(exist_ok=True)
        self.__output_directory.mkdir(parents=True, exist_ok=True)
        
        try:
            self.load_config()
        except Exception as e:
            self.log_manager.log_error(f"Error loading config: {e}")
    
    # ==================== Configuration Managers ====================
    def load_config(self):
        """Load configuration from json file"""
        primary_config = {
            "output_directory": Path.home() / "Music" / "YouTubeMusicDownloads",
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
            if "embed_metadata" in config:
                self.__embed_metadata = config["embed_metadata"]
                
        except Exception as e:
            self.log_manager.log_error(f"Error loading configuration: {e}")
            self.__output_directory = Path(primary_config["output_directory"])
            self.__audio_quality = primary_config["audio_quality"]
            self.__audio_format = primary_config["audio_format"]
            self.use_cookies = primary_config["use_cookies"]
            self.__embed_metadata = primary_config["embed_metadata"]

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
                    "use_cookies": self.use_cookies,
                    "embed_metadata": self.__embed_metadata
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
                    "What bitrate would you like (enter 'choice' to see options): ",
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
                    "What format would you like (enter 'choice' to see options): ",
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
            output_path = Enhanced_Menu.get_input(f"Enter output directory (default: {self.__output_directory}): ", "str").strip()
            if output_path:
                self.__output_directory = Path(output_path)
            else:
                self.__output_directory = Path.home() / "Music" / "YouTubeMusicDownloads"
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
            
            # Metadata embedding
            metadata_choice = Enhanced_Menu.get_input("Embed metadata (artist, album, cover art) into files? (y/n):- ", "yn", default=self.__embed_metadata)
            self.__embed_metadata = metadata_choice

    # ==================== Core download methods ====================
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
            cookie_args = self.cookie_manager.get_arguments_ytdlp()
            if cookie_args:
                command.extend(cookie_args)
                self.log_manager.log_success("Using cookies for better authentication")
            else:
                self.log_manager.log_error("Error using cookies")

        if additional_args:
            if isinstance(additional_args, list):
                command.extend(additional_args)
            else:
                command.append(additional_args)
        command.append(url)
        
        if self.__embed_metadata:
            command.extend(["--add-metadata"])

        try:
            progress_bar = tqdm(
                desc="Downloading",
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                leave=False,
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]",
                dynamic_ncols=True
            )

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

            output_lines = []
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                output_lines.append(line)
                if "[download]" in line:
                    try:
                        percent_match = re.search(r'(\d+\.?\d*)%', line)
                        if percent_match:
                            percent = float(percent_match.group(1))
                            progress_bar.set_description(f"{Fore.CYAN}Downloading: {percent:.1f}%{Style.RESET_ALL}")

                        size_match = re.search(r'of\s+([\d\.]+\s*[KMGT]?i?B)', line)
                        if size_match and progress_bar.total is None:
                            total_str = size_match.group(1)
                            total_bytes = Helpers.parse_size(total_str)   # FIX: use Helpers
                            if total_bytes:
                                progress_bar.total = total_bytes

                        downloaded_match = (re.search(r'([\d\.]+\s*[KMGT]?i?B)\s+at', line) or
                                            re.search(r'([\d\.]+\s*[KMGT]?i?B)\s+ETA', line) or
                                            re.search(r'([\d\.]+\s*[KMGT]?i?B)\s*\/', line))
                        if downloaded_match:
                            downloaded_str = downloaded_match.group(1)
                            downloaded_bytes = Helpers.parse_size(downloaded_str)
                            if downloaded_bytes:
                                progress_bar.n = downloaded_bytes

                        speed_match = re.search(r'at\s+([\d\.]+\s*[KMGT]?i?B/s)', line)
                        if speed_match:
                            speed = speed_match.group(1)
                            progress_bar.set_postfix_str(f"Speed: {speed}")

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
                    progress_bar.set_description(f"{Fore.GREEN}Downloaded{Style.RESET_ALL}")
                    progress_bar.set_postfix_str("")
                    progress_bar.refresh()

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

    # -------------------- Retry wrapper --------------------
    def _download_with_retry(self, url: str, output_template: str, additional_args: list = None,
                             item_type: str = "item") -> bool:
        """Unified retry logic for downloads"""
        for attempt in range(1, MAX_RETRIES + 1):
            Enhanced_Menu.print_section(f"Downloading {item_type} (Attempt {attempt}/{MAX_RETRIES})")
            if attempt > 1:
                print(f"Waiting {RETRY_DELAY} seconds before retry...")
                time.sleep(RETRY_DELAY)

            try:
                result = self.run_download(url, output_template, additional_args)
                if result and result.returncode == 0:
                    self.log_manager.log_success(f"Successfully downloaded {item_type}: {url}")
                    if item_type in ['album', 'playlist']:
                        Helpers.cleanup_directory(self.__output_directory, self.log_manager)
                    return True
                else:
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

    # -------------------- Concurrent helper --------------------
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

    # -------------------- Unified single‑item download (used by track/album) --------------------
    def _download_item(self, item_type: str, url_prompt: str, output_template: str,
                       additional_args: list = None, confirm_large: bool = False,
                       use_archive: bool = False) -> bool:
        """Unified download function for tracks, albums, and playlists"""
        while True:
            print("\n" + "=" * 55)
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header(f"Download {item_type.title()}")

            url = Enhanced_Menu.get_input(f"Enter YouTube Music {url_prompt} (or 'back' to return)", "str")
            if url.lower() == 'back':
                return False
            self.history.add_input(url, item_type)
            if not url:
                Enhanced_Menu.print_status("No URL provided", "error")
                continue

            # Validate URL format
            if not Helpers.validate_youtube_url(url):
                Enhanced_Menu.print_status("Invalid YouTube URL. Enter a valid YouTube/YouTube Music URL", "error")
                continue

            # Validate resource availability (using YouTube helper)
            is_valid, message, metadata = Helpers.validate_resource_youtube(url)
            
            if not is_valid or not metadata:
                Enhanced_Menu.print_status(f"Validation failed: {message}", "error")
                continue
            
            Enhanced_Menu.print_status("Resource information:", "success")
            if item_type == "track":
                title = metadata.get('title', 'Unknown')
                artist = metadata.get('artist') or metadata.get('uploader', 'Unknown Artist')
                album = metadata.get('album', 'Unknown Album')
                print(f"  {Fore.CYAN}Track:{Style.RESET_ALL} {title}")
                print(f"  {Fore.CYAN}Artist:{Style.RESET_ALL} {artist}")
                if album != 'Unknown Album':
                    print(f"  {Fore.CYAN}Album:{Style.RESET_ALL} {album}")
                
            elif item_type == "album":
                album_title = metadata.get('title', 'Unknown Album')
                album_artist = metadata.get('artist') or metadata.get('uploader', 'Unknown Artist')
                track_count = metadata.get('playlist_count', '?')   # ← use playlist_count
                print(f"  {Fore.CYAN}Album:{Style.RESET_ALL} {album_title}")
                print(f"  {Fore.CYAN}Artist:{Style.RESET_ALL} {album_artist}")
                print(f"  {Fore.CYAN}Tracks:{Style.RESET_ALL} {track_count}")
            print()  # blank line for readability                  
            
            if is_valid and metadata:
                if confirm_large and metadata.get('playlist_count', 0) > 50:
                    count = metadata['playlist_count']
                    Enhanced_Menu.print_status(f"This {item_type} contains {count} items. This may take a while.","warning")
                    if not Enhanced_Menu.get_input("Continue with download? (y/n)", "yn", default=False):
                        Enhanced_Menu.print_status("Download cancelled", "info")
                        continue

                if use_archive:
                    playlist_id = Helpers.extract_youtube_playlist_id(url)
                    if playlist_id:
                        archive_path = self.archives_dir / f"{playlist_id}.txt"
                        if additional_args is None:
                            additional_args = []
                        additional_args.extend(["--download-archive", str(archive_path)])
                        self.log_manager.log_success(f"Using archive: {archive_path}")
                    else:
                        self.log_manager.log_warning(f"Could not extract playlist ID from {url}, archive not used")

            # Ask for configuration if desired
            if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
                self.get_user_preferences()

            Enhanced_Menu.print_status(f"Starting {item_type} download...", "info")
            success = self._download_with_retry(url, output_template, additional_args, item_type)

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

    def _validate_channel_url(self, url: str) -> bool:
        """Check if the URL looks like a YouTube channel."""
        patterns = [
            r"youtube\.com/@[\w-]+",
            r"youtube\.com/channel/[\w-]+",
            r"youtube\.com/c/[\w-]+",
            r"youtube\.com/user/[\w-]+",
        ]
        return any(re.search(p, url) for p in patterns)

    def _extract_channel_id(self, url: str) -> str:
        """Extract channel ID from URL (for archive naming). Returns None if not found."""
        # Try to match /channel/ID
        match = re.search(r"youtube\.com/channel/([\w-]+)", url)
        if match:
            return match.group(1)
        # For @handle or /c/name we cannot get a stable ID without an API call.
        # Fallback to a hash of the handle.
        match = re.search(r"youtube\.com/@([\w-]+)", url)
        if match:
            return f"@{match.group(1)}"
        return None

    def _get_channel_videos(self, channel_url: str, limit: int = 0) -> list:
        """
        Use yt-dlp to extract video entries from a channel.
        Returns a list of dicts with 'id' and optionally 'title'.
        """
        command = [
            "yt-dlp",
            "--flat-playlist",
            "--dump-json",
            "--ignore-errors",
            "--quiet",
            "--no-warnings",
            channel_url
        ]
        if limit > 0:
            command.insert(2, f"--playlist-end={limit}")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=60
            )
            if result.returncode != 0:
                self.log_manager.log_error(f"yt-dlp channel extraction failed: {result.stderr[:200]}")
                return []

            items = []
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                try:
                    info = json.loads(line)
                    # Only video entries have an 'id' (playlist items also appear)
                    if info.get('_type') != 'playlist' and info.get('id'):
                        items.append({
                            'id': info['id'],
                            'title': info.get('title', 'Unknown')
                        })
                except json.JSONDecodeError:
                    continue
            return items
        except subprocess.TimeoutExpired:
            self.log_manager.log_error("Channel video extraction timed out after 60 seconds.")
            return []
        except Exception as e:
            self.log_manager.log_error(f"Unexpected error in _get_channel_videos: {e}")
            return []

    # ==================== Public download methods ====================
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
            confirm_large=True,
            use_archive=True
        )

    def download_playlist(self):
        """Download a playlist with concurrent downloads"""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Download Playlist")

        url = Enhanced_Menu.get_input("Enter YouTube Music playlist URL (or 'back' to return): ", "str")
        if url.lower() == 'back':
            return False
        self.history.add_input(url, "playlist")
        if not url or not Helpers.validate_youtube_url(url):
            Enhanced_Menu.print_status("Invalid YouTube URL.", "error")
            return False

        # Validate resource
        is_valid, message, metadata = Helpers.validate_resource_youtube(url)
        if not is_valid:
            Enhanced_Menu.print_status(f"Validation failed: {message}", "failure")
            return False

        playlist_count = metadata.get('playlist_count', 0) if metadata else 0
        if playlist_count == 0:
            Enhanced_Menu.print_status("No videos found in playlist.", "warning")
            return False

        playlist_title = metadata.get('title', 'Unknown Playlist')
        Enhanced_Menu.print_status(f"Playlist: {playlist_title} ({playlist_count} videos)", "success")

        if playlist_count > 50:
            if not Enhanced_Menu.get_input(f"This playlist has {playlist_count} videos. Continue? (y/n)", "yn", default=False):
                Enhanced_Menu.print_status("Download cancelled.", "info")
                return False

        if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
            self.get_user_preferences()

        # Fetch playlist items
        items = Helpers.get_youtube_playlist_items(url, self.log_manager)
        if not items:
            Enhanced_Menu.print_status("Failed to retrieve playlist items.", "error")
            return False
        
        # Reverse order option
        order = Enhanced_Menu.get_input("Download order: (t)op-to-bottom or (b)ottom-to-top", "str", default="t")
        if order.lower() == 'b':
            items.reverse()

        # Setup archive
        playlist_id = Helpers.extract_youtube_playlist_id(url)
        if playlist_id:
            archive_path = self.archives_dir / f"{playlist_id}.txt"
        else:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            archive_path = self.archives_dir / f"playlist_{url_hash}.txt"

        # Prepare output folder
        safe_title = Helpers.sanitize_filename(playlist_title)
        playlist_folder = self.__output_directory / safe_title
        playlist_folder.mkdir(parents=True, exist_ok=True)
        output_template = str(playlist_folder / "%(artist)s - %(title)s.%(ext)s")

        # Build tasks
        tasks = []
        for item in items:
            video_id = item.get('id')
            if not video_id:
                continue
            video_url = f"https://music.youtube.com/watch?v={video_id}"
            additional_args = ["--download-archive", str(archive_path)]
            tasks.append((video_url, output_template, additional_args, archive_path, video_id))

        if not tasks:
            Enhanced_Menu.print_status("No videos to download.", "warning")
            return False

        Enhanced_Menu.print_status(f"Starting concurrent download of {len(tasks)} videos (max 3 at a time)...", "info")
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

    def download_channel(self):
        """Download all videos from an artist/channel using concurrent downloads."""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Download Channel")

        url = Enhanced_Menu.get_input("Enter YouTube channel/artist URL (or 'back' to return): ", "str")
        if url.lower() == 'back':
            return False
        self.history.add_input(url, "playlisr")
        # Validate URL (you can reuse existing validation)
        if not Helpers.validate_youtube_url(url):
            Enhanced_Menu.print_status("Invalid YouTube URL.", "error")
            return False

        is_valid, message, metadata = Helpers.validate_resource_youtube(url)
        if not is_valid:
            Enhanced_Menu.print_status(f"Validation failed: {message}", "failure")
            return False

        channel_name = metadata.get('channel') or metadata.get('uploader') or "Unknown Channel"
        video_count = metadata.get('playlist_count', 0)
        if video_count == 0:
            Enhanced_Menu.print_status("No videos found in this channel.", "warning")
            return False

        Enhanced_Menu.print_status(f"Channel: {channel_name} ({video_count} videos)", "success")

        if video_count > 50 and not Enhanced_Menu.get_input(
            f"This channel has {video_count} videos. Continue? (y/n)", "yn", default=False
        ):
            return False

        if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
            self.get_user_preferences()

        # Fetch video list
        items = self._get_channel_videos(url)   # you'll need this helper (see below)
        if not items:
            Enhanced_Menu.print_status("Failed to retrieve channel videos.", "error")
            return False

        # Setup archive
        channel_id = self._extract_channel_id(url) or hashlib.md5(url.encode()).hexdigest()[:8]
        archive_path = self.archives_dir / f"channel_{channel_id}.txt"

        safe_name = Helpers.sanitize_filename(channel_name)
        channel_folder = self.__output_directory / safe_name
        channel_folder.mkdir(parents=True, exist_ok=True)
        output_template = str(channel_folder / "%(title)s.%(ext)s")

        # Build tasks for concurrent download
        tasks = []
        for video in items:
            video_url = f"https://music.youtube.com/watch?v={video['id']}"
            additional_args = ["--download-archive", str(archive_path)]
            tasks.append((video_url, output_template, additional_args, archive_path, video['id']))

        results = self._download_items_concurrently(tasks, max_workers=3, desc="Channel Download")
        success = sum(results.values())
        print(f"\nDownloaded {success} of {len(tasks)} videos.")
        return success == len(tasks)

    def search_and_download(self):
        """Search for a song and download it"""
        Enhanced_Menu.print_header("SEARCH & DOWNLOAD")
        song_query = Enhanced_Menu.get_input("What is the name of the song you're looking for: ").strip()
        if not song_query:
            Enhanced_Menu.print_status("No search query provided", "error")
            return False
        self.history.add_input(song_query, "search")
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

    # ==================== Checkers & Helpers ====================
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

    def check_ytdlp(self):
        return self.utils.check_ytdlp()

    def check_ffmpeg(self):
        return self.utils.check_ffmpeg()

    def show_ytdlp_help(self):
        return self.utils.show_ytdlp_help()

    def check_dependencies(self):
        return self.utils.check_dependencies()

    def setup_dependencies(self):
        self.utils.setup_dependencies()

    def program_info(self):
        return self.utils.program_info()

    def troubleshooting(self):
        print("\n" + "=" * 50)
        Enhanced_Menu.print_header("TROUBLESHOOTING", "")
        print("=" * 50)
        print("Hello, this troubleshooter is to help if you're experiencing problem in the program")
        print("Running a simple diagnostic. This might take a while.....")

        Enhanced_Menu.print_status("1. Checking yt-dlp installation...", "info")
        if not self.check_ytdlp():
            Enhanced_Menu.print_status("yt-dlp not found or not working", "error")
            install = Enhanced_Menu.get_input("Install yt-dlp now? (y/n)", "yn", default=True)
            if install:
                self.setup_dependencies()

        Enhanced_Menu.print_status("\n2. Checking FFmpeg installation...", "info")
        if not self.check_ffmpeg():
            Enhanced_Menu.print_status("FFmpeg not found (audio conversion might fail)", "error")

        Enhanced_Menu.print_status("\n3. Testing YouTube access...", "info")
        test_url = "https://music.youtube.com/watch?v=215T8NF93kw"
        try:
            test_command = ["yt-dlp", "--skip-download", "--print-json", test_url]
            result = subprocess.run(
                test_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                Enhanced_Menu.print_status("Can access YouTube", "success")
            else:
                Enhanced_Menu.print_status(f"Cannot access YouTube: {result.stderr[:100]}", "error")
        except Exception as e:
            Enhanced_Menu.print_status(f"Test failed: {e}", "error")

    def reset_to_defaults(self):
        """Reset all settings to default values"""
        self.__output_directory = Path.home() / "Music" / "YouTubeMusicDownloads"
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.use_cookies = False
        self.__embed_metadata = False
        self.save_config()
        Enhanced_Menu.print_status("Settings reset to defaults", "success")

