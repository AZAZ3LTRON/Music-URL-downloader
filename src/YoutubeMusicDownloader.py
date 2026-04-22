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
import time
from functools import wraps
from pathlib import Path
import re
from urllib.parse import urlparse
from typing import Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import json
from tqdm import tqdm
from colorama import init, Fore, Style

from CookieManager import CookieManager
from EnhancedMenu import Enhanced_Menu
from Logs_Handler import Logs_Manager
from Downloader_Utils import DownloaderUtils
from Helpers_Validators import Helpers   # <-- new helpers module

init(autoreset=True)

# ============================= Pre Config =============================
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
        self.log_manager = Logs_Manager()          # must be thread‑safe now
        self.utils = DownloaderUtils()
        self.use_cookies = False
        self.__embed_metadata = False
        
        self.archives_dir = Path("archives")
        self.archives_dir.mkdir(exist_ok=True)
        self.__output_directory.mkdir(parents=True, exist_ok=True)
        Path("links").mkdir(parents=True, exist_ok=True)
        
        try:
            self.load_config()
        except Exception as e:
            self.log_manager.log_error(f"Error loading config: {e}")

    # ==================== Configuration Managers ====================
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
        
        # Metadata embedding
        metadata_choice = Enhanced_Menu.get_input("Embed metadata (artist, album, cover art) into files? (y/n):- ", "yn", default=self.__embed_metadata)
        self.__embed_metadata = metadata_choice

    # ==================== Core download methods ====================
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
            if not url:
                Enhanced_Menu.print_status("No URL provided", "error")
                continue

            # Validate URL format
            if not Helpers.validate_youtube_url(url):
                Enhanced_Menu.print_status("Invalid YouTube URL. Enter a valid YouTube/YouTube Music URL", "error")
                continue

            # Validate resource availability (using YouTube helper)
            Enhanced_Menu.print_status("Validating resource...", "info")
            is_valid, message, metadata = Helpers.validate_resource_youtube(url)

            if is_valid and metadata:
                if confirm_large and metadata.get('playlist_count', 0) > 50:
                    count = metadata['playlist_count']
                    Enhanced_Menu.print_status(
                        f"This {item_type} contains {count} items. This may take a while.",
                        "warning"
                    )
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

        url = Enhanced_Menu.get_input("Enter YouTube Music playlist URL (or 'back' to return)", "str")
        if url.lower() == 'back':
            return False
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

        # Setup archive
        playlist_id = Helpers.extract_youtube_playlist_id(url)
        if playlist_id:
            archive_path = self.archives_dir / f"{playlist_id}.txt"
        else:
            import hashlib
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

        Enhanced_Menu.print_status("\n4. Checking directories...", "info")
        directories = ["Albums", "links"]
        for directory in directories:
            if os.path.exists(directory):
                Enhanced_Menu.print_status(f"{directory}/ exists", "success")
            else:
                Enhanced_Menu.print_status(f"{directory}/ missing", "warning")
        input("\nPress Enter to continue...")
        return True

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
            
            # New metadata option
            metadata_status = "ENABLED" if downloader._Youtube_Downloader__embed_metadata else "DISABLED"
            metadata_color = Fore.GREEN if downloader._Youtube_Downloader__embed_metadata else Fore.YELLOW
            Enhanced_Menu.print_menu_item(4, "Metadata Embedding", f"Current: {metadata_color}{metadata_status}{Style.RESET_ALL}")
            
            Enhanced_Menu.print_section("🌐 COOKIE SETTINGS")
            cookie_status = "ENABLED" if downloader.use_cookies else "DISABLED"
            cookie_color = Fore.GREEN if downloader.use_cookies else Fore.YELLOW
            Enhanced_Menu.print_menu_item(5, "Cookie Authentication", f"Current: {cookie_color}{cookie_status}{Style.RESET_ALL}")
            
            Enhanced_Menu.print_section("💾 Download Configuration")
            Enhanced_Menu.print_menu_item(6, "Save Configuration")
            Enhanced_Menu.print_menu_item(7, "Load Configuration")
            Enhanced_Menu.print_menu_item(8, "Reset to Defaults")
            Enhanced_Menu.print_section("↩️  NAVIGATION")
            Enhanced_Menu.print_menu_item(9, "Back to Main Menu")
            print()
            
            choice = Enhanced_Menu.get_input("Select option", "int", 1, 9)
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
                Enhanced_Menu.print_header("METADATA EMBEDDING",  "Control metadata in downloaded files")
                print(f"{Fore.WHITE}Embedding metadata adds:{Style.RESET_ALL}")
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Artist and title tags")
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Album name")
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Track number")
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Cover art (thumbnail)")
                print()
                print(f"{Fore.YELLOW}Current status:{Style.RESET_ALL} ", end="")
                if downloader._Youtube_Downloader__embed_metadata:
                    print(f"{Fore.GREEN}ENABLED{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}DISABLED{Style.RESET_ALL}")
                print()
                new_setting = Enhanced_Menu.get_input(
                    "Enable metadata embedding? (y/n)",
                    "yn",
                    default=downloader._Youtube_Downloader__embed_metadata
                )
                if new_setting is not None:
                    downloader._Youtube_Downloader__embed_metadata = new_setting
                    status = "enabled" if new_setting else "disabled"
                    Enhanced_Menu.print_status(f"Metadata embedding {status}", "success")
                
            elif choice == 5:
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
                    
            elif choice == 6:
                try:
                    downloader.save_config()
                    Enhanced_Menu.print_status("Settings saved successfully", "success")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Error saving settings: {e}", "error")
                    
            elif choice == 7:
                try:
                    downloader.load_config()
                    Enhanced_Menu.print_status("Settings loaded successfully", "success")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Error loading settings: {e}", "error")
                    
            elif choice == 8:
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
            elif choice == 9:
                break
            if choice != 9:
                input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")

    # Define actions as lambdas to ensure they're called only when selected
    actions = {
        1: lambda: downloader.download_track(),
        2: lambda: downloader.download_album(),
        3: lambda: downloader.download_playlist(),
        4: lambda: downloader.search_a_song(),
        5: lambda: downloader.manage_cookies(),
        6: lambda: downloader.check_dependencies(),
        7: lambda: handle_settings(),
        8: lambda: downloader.program_info(),
        9: lambda: downloader.troubleshooting(),
        10: lambda: downloader.show_ytdlp_help(),
        11: lambda: downloader.log_manager.interactive_menu(),
        12: lambda: handle_exit()
    }

    while True:
        try:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Main Menu", "Select an option below:")
            Enhanced_Menu.print_section("📥 DOWNLOAD OPTIONS")
            Enhanced_Menu.print_menu_item(1, "Download Track")
            Enhanced_Menu.print_menu_item(2, "Download Album")
            Enhanced_Menu.print_menu_item(3, "Download Playlist")
            Enhanced_Menu.print_menu_item(4, "Search & Download a Song")
            
            Enhanced_Menu.print_section("⚙️  TOOLS & SETTINGS")
            Enhanced_Menu.print_menu_item(5, "Manage Cookies (for restricted content)")
            Enhanced_Menu.print_menu_item(6, "Check Dependencies")
            Enhanced_Menu.print_menu_item(7, "Program Settings")
            
            Enhanced_Menu.print_section("❓ HELP & INFORMATION")
            Enhanced_Menu.print_menu_item(8, "Show Program Info")
            Enhanced_Menu.print_menu_item(9, "Troubleshooting")
            Enhanced_Menu.print_menu_item(10, "Show yt-dlp Help")
            
            Enhanced_Menu.print_section("📊 LOG MANAGEMENT")
            Enhanced_Menu.print_menu_item(11, "Log Manager")
            
            Enhanced_Menu.print_section("🚪 EXIT")
            Enhanced_Menu.print_menu_item(12, "Exit Program")
            print(f"\n{Style.DIM}{'─' * 60}{Style.RESET_ALL}")
            Enhanced_Menu.print_status("Current Settings:", "info", "⚙️")
            
            settings = [
                ("Format", downloader._Youtube_Downloader__audio_format),
                ("Quality", downloader._Youtube_Downloader__audio_quality),
                ("Output", str(downloader._Youtube_Downloader__output_directory)),
                ("Metadata", "Enabled" if downloader._Youtube_Downloader__embed_metadata else "Disabled"),  # new line
            ]
            
            for setting_name, setting_value in settings:
                print(f"  {Fore.CYAN}{setting_name}:{Style.RESET_ALL} {Fore.YELLOW}{setting_value}{Style.RESET_ALL}")
            cookie_status = "Enabled" if downloader.use_cookies else "Disabled"
            cookie_color = Fore.GREEN if downloader.use_cookies else Fore.YELLOW
            print(f"  {Fore.CYAN}Cookies:{Style.RESET_ALL} {cookie_color}{cookie_status}{Style.RESET_ALL}")
            print(f"{Style.DIM}{'─' * 60}{Style.RESET_ALL}")
            
            choice = Enhanced_Menu.get_input("\nEnter your choice (1-12)", "int", 1, 12)
            action = actions.get(choice)
            
            if action:
                Enhanced_Menu.clear_screen()
                try:
                    # Call the lambda function
                    result = action()
                    
                    # Handle the result if needed
                    if result is False and choice not in [1,2,3,4,5,6,7,8,9,10,11,12]:
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
        print("\nProgram interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        print("Please check the error log for details.")