import re
import os
import random
import subprocess
import time
import hashlib
import threading
import json

from functools import wraps
from pathlib import Path
from typing import Dict, List, Tuple
from tqdm import tqdm
from colorama import init, Fore, Style

from tools.CookieManager import CookieManager
from utils.loaders import DownloaderUtils 
from tools.EnhancedMenu import Enhanced_Menu
from utils.logger import Logs_Manager
from utils.historylogger import DownloadHistory
from utils.validators import Helpers
from utils.helpers import DownloadHelpers
from tools.BatchFile import BatchFile
from tools.RetryQueue import RetryQueue

init(autoreset=True)
os.makedirs("cookies", exist_ok=True)

# Cheap shape check for links read out of a batch file. Running every line past
# Helpers.validate_resource_spotify would be one network round trip per link
# before a single track is fetched, so the real check is left to the download.
SPOTIFY_LINK = re.compile(
    r"^(?:https?://(?:open|play)\.spotify\.com/\S+|spotify:[a-z]+:[A-Za-z0-9]+)$",
    re.IGNORECASE)


class _NullBar:
    """No-op stand-in for tqdm, for batch links that print their own status."""
    total = None
    n = 0

    def update(self, *args, **kwargs):
        pass

    def set_postfix_str(self, *args, **kwargs):
        pass

    def refresh(self):
        pass

    def close(self):
        pass


def rate_limit(calls_per_minute: int = 60):
    def decorator(func):
        last_called = [0.0]
        call_lock = threading.Lock()
        min_interval = 60.0 / calls_per_minute
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            with call_lock:
                now = time.monotonic()
                wait = min_interval - (now - last_called[0])
                last_called[0] = now + max(wait, 0)
                if wait > 0:
                    time.sleep(wait)
            return func(*args, **kwargs)
        return wrapper
    return decorator

class SpotifyMusicDownloader:
    def __init__(self):
        """Initialize the downloader with default values"""
        self.__output_directory = Path.home() / "Music" / "Collection" / "Spotify"
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.__configuration_file = r"config/SpotifyMusicDownloader.json"
        self.cookie_manager = CookieManager()
        self.log_manager = Logs_Manager()          
        self.utils = DownloaderUtils()
        self.history = DownloadHistory()
        self.helpers = Helpers()
        self.use_cookies = False
        self._last_download_stats = {"succeeded": 0, "skipped": 0, "failed": 0, "failed_items": [], "rate_limited": False}

        self.max_retries = 3
        self.retry_delay = 10
        self.max_concurrent = 2
        self.rate_limit_backoff = 300     # base wait (s) after a YouTube rate limit
        self.rate_limit_max_wait = 1800 
        self.yt_dlp_sleep_min = 3          # min seconds yt-dlp waits between downloads
        self.yt_dlp_sleep_max = 7          # max seconds (random delay in this range)

        self.archives_dir = Path("history/archives")
        self.archives_dir.mkdir(exist_ok=True, parents=True)

        # Batch-download collaborators. `file_helpers` is deliberately not
        # `helpers`, which is already taken above by the validators. The retry
        # queue is kept separate from the YouTube downloader's - a Spotify link
        # is no use to yt-dlp, and vice versa.
        self.file_helpers = DownloadHelpers(on_error=self.log_manager.log_error)
        self.batch_file = BatchFile(on_error=self.log_manager.log_error,
                                    backup_dir="history/backups")
        self.retry_queue = RetryQueue("history/retry_queue_spotify.json",
                                      on_error=self.log_manager.log_error)

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

    @property
    def retry_queue_count(self) -> int:
        """How many failed links are currently waiting in the retry queue."""
        return self.retry_queue.count

    def _log_download(self, url, item_type, status, metadata=None, error=None):
        self.history.add_entry(url, item_type, status, metadata=metadata, error=error)
            
    def load_config(self):
        """Load configuration from json file"""
        primary_config = {
            "output_directory": str(Path.home() / "Music" / "Collection" / "Spotify"),
            "audio_quality": "320k",
            "audio_format": "mp3",
            "max_retries": 3,
            "retry_delay": 10,
            "use_cookies": False,
            "max_concurrent": 2,
            "yt_dlp_sleep_min": 3,
            "yt_dlp_sleep_max": 7,
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
            self.max_concurrent = config.get("max_concurrent", 2)
            
            self.yt_dlp_sleep_min = config.get("yt_dlp_sleep_min", 3)
            self.yt_dlp_sleep_max = config.get("yt_dlp_sleep_max", 7)
            
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
                    "max_concurrent": self.max_concurrent,
                    "use_cookies": self.use_cookies,
                    "yt_dlp_sleep_min": self.yt_dlp_sleep_min,
                    "yt_dlp_sleep_max": self.yt_dlp_sleep_max,
                }
            else:
                config = {**config}
                if "output_directory" in config:
                    config["output_directory"] = str(config["output_directory"])
            with open(self.__configuration_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log_manager.log_error(f"Error saving configuration: {e}")
            
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
            output_path = Enhanced_Menu.get_input(f"Enter output directory (default {self.__output_directory})", "str").strip()
            if output_path:
                self.__output_directory = Path(output_path)
            else:
                self.__output_directory = Path.home() / "Music" / "Collection" / "Spotify"
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
    def _get_cookie_file(self):
        """Return a usable cookie-file path if cookies are enabled, else None."""
        if not self.use_cookies:
            return None
        # Prefer whatever the CookieManager is currently pointing at
        path = getattr(self.cookie_manager, "current_cookie_file", None)
        if path and os.path.exists(path):
            return str(path)
        # Otherwise fall back to the newest .txt in the cookies/ directory
        cookies_dir = Path("cookies")
        if cookies_dir.is_dir():
            candidates = sorted(cookies_dir.glob("*.txt"),
                                key=lambda p: p.stat().st_mtime, reverse=True)
            if candidates:
                return str(candidates[0])
        self.log_manager.log_error(
            "Cookies are enabled but no cookie file was found in cookies/. "
            "Use the Cookie Manager to add one.", console=True)
        return None
                
    @rate_limit(calls_per_minute=60)
    def run_download(self, url: str, output_template: str = None, extra_args: List[str] = None,
                        total_items: int = None, item_desc: str = "item", desc: str = None,
                        show_progress: bool = True) -> bool:
        """Run spotdl with a live bar that advances per finished track."""
        cmd = [
            "spotdl", "download", url,
            "--format", self.audio_format,
            "--bitrate", self.audio_quality,
            "--output", output_template,
            "--overwrite", "skip",
            "--print-errors",
            "--threads", str(self.max_concurrent),
        ]

        # Throttle YouTube requests to avoid rate-limit / 403s
        if self.yt_dlp_sleep_min:
            sleep_args = f"--sleep-interval {self.yt_dlp_sleep_min}"
            if self.yt_dlp_sleep_max:
                sleep_args += f" --max-sleep-interval {self.yt_dlp_sleep_max}"
            cmd.extend(["--yt-dlp-args", sleep_args])
            
        cookie_file = self._get_cookie_file()
        if cookie_file:
            cmd.extend(["--cookie-file", cookie_file])
        if extra_args:
            cmd.extend(extra_args)

        # These are what spotdl v4 actually prints per track:
        FAIL_MARKERS = ('No results found', 'LookupError', 'AudioProviderError',
                        'Error downloading', 'Failed to download')
        # Signals that the failures are YouTube/Spotify throttling, not missing songs:
        RATE_LIMIT_MARKERS = ('rate-limited by YouTube', 'HTTP Error 403',
                            'reached a rate/request limit', 'Max Retries reached',
                            'Sign in to confirm')

        label = desc or f"Downloading {item_desc}s"
        if len(label) > 40:
            label = label[:37] + "..."

        if not show_progress:
            # A batch run prints its own line per link; a bar on top of that
            # just fights it for the terminal.
            pbar = _NullBar()
        elif total_items:
            pbar = tqdm(total=total_items, desc=label, unit=item_desc, colour="green",
                        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]")
        else:
            pbar = tqdm(desc=label, unit="track", total=None, colour="green",
                        bar_format="{l_bar}{bar}| {n_fmt} [{elapsed}]")

        output_lines = []
        failed_items = []
        succeeded = skipped = failed = 0
        rate_limited = False
        try:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace",
                                    bufsize=1, env=env)
            completed = 0

            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if not line:
                    continue

                output_lines.append(line)
                if len(output_lines) > 1000:
                    output_lines = output_lines[-200:]

                if any(m in line for m in RATE_LIMIT_MARKERS):
                    rate_limited = True

                # Advance once per finished track (success, skip, or failure)
                is_success = 'Downloaded "' in line
                is_skip = 'Skipping ' in line
                is_fail = any(m in line for m in FAIL_MARKERS)
                if is_success or is_skip or is_fail:
                    if is_fail:
                        failed += 1
                        failed_items.append(line)
                    elif is_skip:
                        skipped += 1
                    else:
                        succeeded += 1
                    if not total_items or completed < total_items:
                        completed += 1
                        pbar.update(1)
                        if total_items:
                            pbar.set_postfix_str(f"{completed}/{total_items}")
                    continue

                # Single-item live detail only (never for playlist/album bars)
                if total_items is None or total_items == 1:
                    pm = re.search(r'(\d+\.?\d*)%', line)
                    if pm:
                        pbar.set_postfix_str(f"{float(pm.group(1)):.1f}%")
                    sm = re.search(r'at\s+([\d.]+\s*[KMGT]?i?B/s)', line)
                    if sm:
                        pbar.set_postfix_str(sm.group(1))

            process.wait()

            if total_items:
                if pbar.n < total_items:
                    pbar.update(total_items - pbar.n)
                else:
                    pbar.total = pbar.n or completed
                    pbar.refresh()
            pbar.close()

            self._last_download_stats = {
                "succeeded": succeeded, "skipped": skipped, "failed": failed,
                "failed_items": failed_items, "rate_limited": rate_limited,
            }

            if process.returncode == 0:
                # "Nothing succeeded, nothing was already on disk, and at least
                # one track failed" is a failure whatever spotdl exited with.
                # A part-failed album still counts as success - the caller has
                # the stats and prints its own summary.
                if failed and not succeeded and not skipped:
                    self.log_manager.log_failure(
                        f"spotdl exited 0 but no track downloaded for {url}")
                    return False
                return True

            error_keywords = ['error', 'fail', 'blocked', 'unavailable', 'private',
                            'forbidden', 'not found', 'quota', 'rate limit']
            error_lines = [l for l in output_lines if any(k in l.lower() for k in error_keywords)]
            if not error_lines:
                error_lines = output_lines[-5:]
            if show_progress:
                print(f"\n{Fore.RED}===== spotdl error output ====={Style.RESET_ALL}")
                for el in error_lines:
                    print(f"{Fore.RED}{el}{Style.RESET_ALL}")
                print(f"{Fore.RED}==============================={Style.RESET_ALL}\n")
            for el in error_lines:
                self.log_manager.log_error(f"spotdl: {el}", console=False)
            self.log_manager.log_failure(f"spotdl failed for {url}")
            return False

        except Exception as e:
            self.log_manager.log_error(f"Download process exception: {e}", console=True)
            self._last_download_stats = {
                "succeeded": succeeded, "skipped": skipped, "failed": failed,
                "failed_items": failed_items, "rate_limited": rate_limited,
            }
            pbar.close()
            return False               
        
    def _download_with_retry(self, url: str, output_template: str, extra_args: list = None,
                            item_type: str = "item", total_items: int = None, desc: str = None,
                            show_progress: bool = True) -> bool:

        errors_file = None
        if extra_args and "--save-errors" in extra_args:
            idx = extra_args.index("--save-errors")
            if idx + 1 < len(extra_args):
                errors_file = extra_args[idx + 1]

        self.log_manager.reset_session_failures()
        for attempt in range(1, self.max_retries + 1):
            if errors_file:
                try:
                    open(errors_file, "w", encoding="utf-8").close()
                except OSError:
                    pass

            if show_progress:
                Enhanced_Menu.print_section(f"Downloading {item_type} (Attempt {attempt}/{self.max_retries})")

            if attempt > 1:
                if self._last_download_stats.get("rate_limited"):
                    wait = min(self.rate_limit_backoff * (2 ** (attempt - 2)),
                            self.rate_limit_max_wait)
                    if show_progress:
                        Enhanced_Menu.print_status(
                            f"YouTube rate limit detected - backing off {wait}s before retrying. "
                            f"Already-downloaded tracks will be skipped.", "warning")
                else:
                    wait = self.retry_delay
                    if show_progress:
                        print(f"Waiting {wait} seconds before retry...")
                time.sleep(wait)

            try:
                success = self.run_download(url, output_template, extra_args,
                                            total_items=total_items, item_desc=item_type, desc=desc,
                                            show_progress=show_progress)
                if success:
                    self.log_manager.log_success(f"Successfully downloaded {item_type}: {url}")
                    if item_type in ['album', 'playlist', 'artist']:
                        Helpers.cleanup_directory(self.__output_directory, self.log_manager)
                    return True
            except Exception as e:
                self.log_manager.log_error(f"Attempt {attempt} failed: {e}")
                if attempt == self.max_retries:
                    self.log_manager.log_failure(f"Failed after {self.max_retries} attempts: {url}")

        if self._last_download_stats.get("rate_limited"):
            self.log_manager.log_failure(
                f"Gave up after {self.max_retries} attempts due to YouTube rate limiting: {url}. "
                f"Re-run later - the archive (--save-file) means finished tracks are skipped.")
        return False
    
    def _download_item(self, item_type: str, url_prompt: str, output_template: str,
                       confirm_large: bool = False, use_archive: bool = False,
                       force_url: str = None) -> bool:
        """Unified download function for tracks and albums (playlist handled separately)"""
        while True:
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
                
            elif item_type == "playlist":
                playlist_title = metadata.get('title', 'Unknown Playlist')
                playlist_owner = metadata.get('artist', 'Unknown')
                track_count = metadata.get('playlist_count', '?')
                print(f"  {Fore.CYAN}Playlist:{Style.RESET_ALL} {playlist_title}")
                if playlist_owner != 'Unknown':
                    print(f"  {Fore.CYAN}Owner:{Style.RESET_ALL} {playlist_owner}")
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
                
            total = metadata.get('playlist_count') or None if item_type in ['album', 'playlist'] else None
            if use_archive:
                url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                if 'album' in url:
                    album_id = re.search(r'album/([a-zA-Z0-9]+)', url)
                    archive_path = self.archives_dir / (
                        f"album_{album_id.group(1)}.spotdl" if album_id
                        else f"album_{url_hash}.spotdl"
                    )
                elif 'playlist' in url:
                    playlist_id = re.search(r'playlist/([a-zA-Z0-9]+)', url)
                    archive_path = self.archives_dir / (
                        f"playlist_{playlist_id.group(1)}.spotdl" if playlist_id else f"playlist_{url_hash}.spotdl"
                    )
                else:
                    archive_path = self.archives_dir / f"track_{url_hash}.spotdl"

                additional_args = ["--save-file", str(archive_path)]
            else:
                additional_args = None
                            
            if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
                self.get_user_preferences()
            
            Enhanced_Menu.print_status(f"Starting {item_type} download...", "info")
            display_name = metadata.get('title') or item_type.title()
            success = self._download_with_retry(url, output_template, additional_args,
                                                item_type, total_items=total, desc=display_name)
                       
            if item_type == "playlist":
                stats = self._last_download_stats
                failed_count = stats["failed"]
                failed_items = stats["failed_items"]
                
                if total:
                    succeeded_count = max(total - failed_count, 0)     # not-failed == on disk
                else:
                    succeeded_count = self._last_download_stats["succeeded"]  # fallback (no known total)

                for detail in failed_items:
                    self.log_manager.log_track_failure(detail, source_url=url)
                    
                summary = self.log_manager.get_session_summary()
                failed_count = summary["total"]
                succeeded_count = max(total - failed_count, 0) if total else self._last_download_stats["succeeded"]
                
                
                print()
                Enhanced_Menu.print_status("Playlist download summary:", "info")
                print(f"  {Fore.GREEN}Succeeded:{Style.RESET_ALL} {succeeded_count}")
                print(f"  {Fore.RED}Failed:{Style.RESET_ALL} {failed_count}")
                labels = {"not_found": "Not found (won't recover)", "rate_limited": "Rate-limited (retry later)",
                        "download_error": "Download errors"}
                for cat in ("not_found", "rate_limited", "download_error"):
                    if summary[cat]:
                        print(f"      {labels[cat]}: {summary[cat]}")
                if total:
                    print(f"  {Fore.CYAN}Total tracks:{Style.RESET_ALL} {total}")
                if failed_count:
                    print(f"{Fore.RED} Some tracks failed - see failed.log {Style.RESET_ALL}")
                    
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

    # ================================================== Batch download from a file ==================================================
    @staticmethod
    def _is_spotify_link(url: str) -> bool:
        """Shape check only - the download itself is the real validation."""
        return bool(SPOTIFY_LINK.match((url or "").strip()))

    def _last_error_summary(self) -> str:
        """Turn the last run's stats into one line worth storing in the queue."""
        stats = self._last_download_stats or {}
        if stats.get("rate_limited"):
            return "Rate-limited by YouTube/Spotify - retry later"
        items = stats.get("failed_items") or []
        if items:
            return str(items[-1])[:300]
        return "spotdl reported a failure"

    def download_from_file(self, file_path: str = None) -> bool:
        """
        Download every link in a .txt or .csv file, strictly one at a time.

        Sequential by design: a batch file is usually long, and firing several
        requests at once at the same host is what gets you throttled. Every
        success is written back into the source file, so a re-run picks up where
        the last one stopped; every failure lands in the retry queue with its
        error and attempt count.

        Unlike the per-item downloads this does not use a spotdl --save-file
        archive. The status written into the source file is the record of what
        finished, and spotdl's own `--overwrite skip` already covers a track
        that is somehow attempted twice.
        """
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Batch Download", "Download every link in a .txt or .csv file")

        if file_path is None:
            raw = Enhanced_Menu.get_input(
                "Path to the .txt or .csv file (or 'back' to return)", "str")
            raw = (raw or "").strip().strip('"').strip("'")
            if not raw or raw.lower() == "back":
                return False
            file_path = raw

        path = Path(file_path).expanduser()
        if not path.is_file():
            Enhanced_Menu.print_status(f"No such file: {path}", "error")
            return False

        entries = self.batch_file.parse(path)
        if not entries:
            Enhanced_Menu.print_status(f"No links found in {path.name}", "error")
            return False

        # De-duplicate (keeping order), drop non-Spotify links, and skip
        # anything the file already records as downloaded.
        seen = set()
        valid: List[Dict[str, str]] = []
        invalid = already_done = 0
        for entry in entries:
            url = entry["url"]
            if url in seen:
                continue
            seen.add(url)
            if not self._is_spotify_link(url):
                invalid += 1
                continue
            if entry.get("status") == "success":
                already_done += 1
                continue
            valid.append(entry)
        duplicates = len(entries) - len(seen)

        Enhanced_Menu.print_status(f"Read {path.name}:", "success")
        print(f"  {Fore.CYAN}Links found:{Style.RESET_ALL} {len(entries)}")
        if duplicates:
            print(f"  {Fore.YELLOW}Duplicates skipped:{Style.RESET_ALL} {duplicates}")
        if invalid:
            print(f"  {Fore.YELLOW}Not Spotify links, skipped:{Style.RESET_ALL} {invalid}")
        if already_done:
            print(f"  {Fore.CYAN}Already marked success:{Style.RESET_ALL} {already_done}")
        print(f"  {Fore.GREEN}To download:{Style.RESET_ALL} {len(valid)}")
        print()

        if not valid:
            Enhanced_Menu.print_status("Nothing left to download.", "info")
            return True

        if not Enhanced_Menu.get_input(f"Download these {len(valid)} links? (y/n)",
                                       "yn", default=True):
            Enhanced_Menu.print_status("Cancelled", "info")
            return False

        self.history.add_input(str(path), "batch")

        # Output folder: named after the file by default, so a batch stays together.
        folder_name = self.file_helpers.safe_name(path.stem, "Batch")
        if Enhanced_Menu.get_input(f"Save into a subfolder named '{folder_name}'? (y/n)",
                                   "yn", default=True):
            target = self.__output_directory / folder_name
        else:
            target = self.__output_directory
        target.mkdir(parents=True, exist_ok=True)
        output_template = str(target / "{artist} - {title}.{output-ext}")

        if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
            self.get_user_preferences()

        total = len(valid)
        succeeded = failed = 0
        pending: Dict[str, str] = {}          # url -> status, not yet flushed to file
        cleared: List[str] = []               # urls to remove from the retry queue
        failures: List[Tuple[str, str, str]] = []
        interrupted = throttled_out = False
        rate_limit_streak = 0
        started = time.monotonic()

        Enhanced_Menu.print_status(f"Starting batch download of {total} links...", "info")
        print()

        try:
            for index, entry in enumerate(valid, 1):
                url, title = entry["url"], entry.get("title", "")
                label = title or url
                print(f"{Fore.CYAN}[{index}/{total}]{Style.RESET_ALL} {str(label)[:65]}")

                ok = self._download_with_retry(
                    url, output_template, item_type="track",
                    total_items=1, desc=str(label)[:40], show_progress=False)

                if ok:
                    succeeded += 1
                    pending[url] = "success"
                    cleared.append(url)
                    rate_limit_streak = 0
                    print(f"      {Fore.GREEN}done{Style.RESET_ALL}")
                else:
                    failed += 1
                    error = self._last_error_summary()
                    pending[url] = "failed"
                    failures.append((url, title, error))
                    self.retry_queue.add_failure(url, title, error, str(path))
                    if self._last_download_stats.get("rate_limited"):
                        rate_limit_streak += 1
                        print(f"      {Fore.RED}rate limited -> retry queue{Style.RESET_ALL}")
                    else:
                        rate_limit_streak = 0
                        print(f"      {Fore.RED}failed -> retry queue{Style.RESET_ALL}")

                # Written per link rather than in batches: the file should say
                # what the screen just said, and an interrupted run shouldn't
                # lose the last few results.
                if self.batch_file.mark_statuses(path, pending):
                    pending = {}

                # Once throttling starts, every remaining link will fail the
                # same way and burn its retries doing it. Stop and let the file
                # markers make the resume trivial.
                if rate_limit_streak >= 3:
                    throttled_out = True
                    Enhanced_Menu.print_status(
                        "Three rate-limited links in a row - stopping here. Re-run this "
                        "file later and the finished links will be skipped.", "warning")
                    break

                if index < total:
                    if rate_limit_streak:
                        wait = min(self.rate_limit_backoff * (2 ** (rate_limit_streak - 1)),
                                   self.rate_limit_max_wait)
                        Enhanced_Menu.print_status(
                            f"Rate limited - pausing {wait}s before the next link", "warning")
                    else:
                        # spotdl's own --sleep-interval only applies within a
                        # single invocation, not between them.
                        wait = random.uniform(self.yt_dlp_sleep_min, self.yt_dlp_sleep_max)
                    time.sleep(wait)

        except KeyboardInterrupt:
            interrupted = True
            print()
            Enhanced_Menu.print_status(
                "Interrupted. Re-run this file later and finished links will be skipped.",
                "warning")

        # Final flush of statuses, and drop anything that succeeded from the queue.
        self.batch_file.mark_statuses(path, pending)
        self.retry_queue.clear(cleared)

        elapsed = time.monotonic() - started
        stopped = interrupted or throttled_out
        print()
        Enhanced_Menu.print_header("Batch Download Complete" if not stopped
                                   else "Batch Download Stopped")
        print(f"  {Fore.GREEN}Succeeded:{Style.RESET_ALL} {succeeded}")
        if failed:
            print(f"  {Fore.RED}Failed:{Style.RESET_ALL} {failed}")
            for url, title, _ in failures[:10]:
                print(f"      {Fore.RED}- {str(title or url)[:60]}{Style.RESET_ALL}")
            if len(failures) > 10:
                print(f"      {Fore.RED}...and {len(failures) - 10} more{Style.RESET_ALL}")
            print(f"  {Fore.YELLOW}Queued for retry in:{Style.RESET_ALL} {self.retry_queue.path}")
        if stopped:
            print(f"  {Fore.YELLOW}Not attempted:{Style.RESET_ALL} {total - succeeded - failed}")
        print(f"  {Fore.CYAN}Statuses written to:{Style.RESET_ALL} {path}")
        print(f"  {Fore.CYAN}Elapsed:{Style.RESET_ALL} {elapsed / 60:.1f} min")

        if succeeded:
            Helpers.cleanup_directory(self.__output_directory, self.log_manager)

        return failed == 0 and not stopped

    def download_from_retry_queue(self) -> bool:
        """Re-attempt every link sitting in the retry queue."""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Retry Queue", "Re-attempt previously failed links")

        queue = self.retry_queue.read()
        if not queue:
            Enhanced_Menu.print_status("The retry queue is empty.", "info")
            return True

        items = sorted(queue.values(), key=lambda e: int(e.get("attempts", 0)))
        print(f"  {Fore.CYAN}Queued links:{Style.RESET_ALL} {len(items)}")
        for entry in items[:10]:
            print(f"      - {str(entry.get('title') or entry['url'])[:55]} "
                  f"{Fore.YELLOW}({entry.get('attempts', 0)} attempts){Style.RESET_ALL}")
        if len(items) > 10:
            print(f"      ...and {len(items) - 10} more")
        print()

        if not Enhanced_Menu.get_input(f"Retry these {len(items)} links? (y/n)",
                                       "yn", default=True):
            Enhanced_Menu.print_status("Cancelled", "info")
            return False

        target = self.__output_directory / "Retries"
        target.mkdir(parents=True, exist_ok=True)
        output_template = str(target / "{artist} - {title}.{output-ext}")

        succeeded = failed = 0
        per_source: Dict[str, Dict[str, str]] = {}
        cleared: List[str] = []
        rate_limit_streak = 0
        total = len(items)

        try:
            for index, entry in enumerate(items, 1):
                url = entry["url"]
                label = entry.get("title") or url
                print(f"{Fore.CYAN}[{index}/{total}]{Style.RESET_ALL} {str(label)[:65]}")

                ok = self._download_with_retry(
                    url, output_template, item_type="track",
                    total_items=1, desc=str(label)[:40], show_progress=False)

                source = entry.get("source")
                if ok:
                    succeeded += 1
                    cleared.append(url)
                    rate_limit_streak = 0
                    if source:
                        per_source.setdefault(source, {})[url] = "success"
                    print(f"      {Fore.GREEN}done{Style.RESET_ALL}")
                else:
                    failed += 1
                    self.retry_queue.add_failure(url, entry.get("title", ""),
                                                 self._last_error_summary(), source or "")
                    if self._last_download_stats.get("rate_limited"):
                        rate_limit_streak += 1
                    else:
                        rate_limit_streak = 0
                    print(f"      {Fore.RED}still failing{Style.RESET_ALL}")

                if rate_limit_streak >= 3:
                    Enhanced_Menu.print_status(
                        "Three rate-limited links in a row - stopping here. The rest stay "
                        "queued.", "warning")
                    break

                if index < total:
                    if rate_limit_streak:
                        wait = min(self.rate_limit_backoff * (2 ** (rate_limit_streak - 1)),
                                   self.rate_limit_max_wait)
                        Enhanced_Menu.print_status(
                            f"Rate limited - pausing {wait}s before the next link", "warning")
                    else:
                        wait = random.uniform(self.yt_dlp_sleep_min, self.yt_dlp_sleep_max)
                    time.sleep(wait)

        except KeyboardInterrupt:
            print()
            Enhanced_Menu.print_status("Interrupted - remaining links stay queued.", "warning")

        self.retry_queue.clear(cleared)
        # Mirror the successes back into whichever file each link came from.
        for source, statuses in per_source.items():
            source_path = Path(source)
            if source_path.is_file():
                self.batch_file.mark_statuses(source_path, statuses)

        print()
        Enhanced_Menu.print_header("Retry Complete")
        print(f"  {Fore.GREEN}Recovered:{Style.RESET_ALL} {succeeded}")
        if failed:
            print(f"  {Fore.RED}Still queued:{Style.RESET_ALL} {failed}")

        if succeeded:
            Helpers.cleanup_directory(self.__output_directory, self.log_manager)
        return failed == 0

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
        """Download a playlist"""
        return self._download_item(
            item_type ="playlist",
            url_prompt="playlist URL",
            output_template=str(self.__output_directory/"{list-name}"/"{artist} - {title}.{output-ext}"),
            confirm_large=True,
            use_archive=True
        )

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

        output_template = str(self.__output_directory/"Searches"/"{artists} - {title}.{output-ext}")
        for attempt in range(1, self.max_retries + 1):
            Enhanced_Menu.print_status(f"Attempt {attempt}/{self.max_retries}", "info")
            if attempt > 1:
                if self._last_download_stats.get("rate_limited"):
                    wait = min(self.rate_limit_backoff * (2 ** (attempt - 2)),
                            self.rate_limit_max_wait)
                    Enhanced_Menu.print_status(f"Rate limit detected - backing off {wait}s...", "warning")
                else:
                    wait = self.retry_delay
                    Enhanced_Menu.print_status(f"Waiting {wait}s before retry...", "info")
                time.sleep(wait)
            try:
                if self.run_download(f":{song_query}", output_template):
                    self.log_manager.log_success(f"Successfully downloaded: '{song_query}'")
                    return True
            except Exception as e:
                self.log_manager.log_error(f"Unexpected error: {e}")

        # Previously fell out of the loop returning None, so a failed search
        # looked neither successful nor failed to the caller.
        self.log_manager.log_failure(f"Failed after {self.max_retries} attempts: '{song_query}'")
        return False
    
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
        return self.utils.show_spotdl_help()

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
        self.__output_directory = Path.home() / "Music" / "Collection" / "Spotify"
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.use_cookies = False
        self.save_config()
        Enhanced_Menu.print_status("Settings reset to defaults", "success")