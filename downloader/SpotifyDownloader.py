import re
import os
import random
import subprocess
import time
import hashlib
import threading

from functools import wraps
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from colorama import init, Fore, Style

from tools.CookieManager import CookieManager
from tools.ConfigManager import DownloaderConfigManager
from tools.BatchFile import BatchFile
from tools.RetryQueue import RetryQueue
from tools.RateLimiter import spotify_limiter, youtube_limiter, looks_throttled
from tools.EnhancedMenu import Enhanced_Menu
from utils.utilities import DownloaderUtils
from utils.logger import Logs_Manager
from utils.validators import Helpers
from utils.history_logger import DownloadHistory
from utils.helpers import DownloadHelpers

init(autoreset=True)
os.makedirs("cookies", exist_ok=True)

class _NullBar:
    """No-op stand-in for tqdm so worker threads don't threads don't render nested bars."""
    total = None
    n = 0
    
    def set_description(self, *args, **kwargs):
        pass

    def set_postfix_str(self, *args, **kwargs):
        pass

    def refresh(self):
        pass

    def close(self):
        pass
    
class Spotify_Downloader:
    """Downloader class that handles the downloading process"""
    
    def __init__(self):
        self.__output_directory = Path.home() / "Music" / "Collection" / "Spotify"
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.__configuration_file = r"config/SpotifyMusicDownloader.json"
        self.use_cookies = False
        self.debug = False

        self.max_retries = 3
        self.retry_delay = 10
        self.download_timeout = 120       
        self.max_concurrent = 2
        self.yt_dlp_sleep_min = 3          
        self.yt_dlp_sleep_max = 7          
        self.rate_limit_backoff = 300      
        self.rate_limit_max_wait = 1800    
        self._last_run_throttled = False

        self.log_manager = Logs_Manager()
        self.cookie_manager = CookieManager()
        self.utils = DownloaderUtils()
        self.history = DownloadHistory()
        self._config = DownloaderConfigManager.for_spotify(self.__configuration_file, on_error=self.log_manager.log_error)
        self.file_helpers = DownloadHelpers(on_error=self.log_manager.log_error)
        self.batch_file = BatchFile(on_error=self.log_manager.log_error, backup_dir="history/backups")
        self.retry_queue = RetryQueue("history/retry_queue_spotify.json", on_error=self.log_manager.log_error)

        try:
            self.load_config()
        except Exception as e:
            self.log_manager.log_error(f"Error loading config: {e}")
            
        self.archives_dir = Path("history/archives")
        self.archives_dir.mkdir(parents=True, exist_ok=True)
        self.__output_directory.mkdir(parents=True, exist_ok=True)

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

    def load_config(self):
        c = self._config.load()
        self.__output_directory = Path(c["output_directory"])
        self.__audio_quality = c["audio_quality"]
        self.__audio_format = c["audio_format"]
        self.use_cookies = c["use_cookies"]
        self.max_retries = c["max_retries"]
        self.retry_delay = c["retry_delay"]
        self.download_timeout = c["download_timeout"]
        self.max_concurrent = c["max_concurrent"]
        self.yt_dlp_sleep_min = c["yt_dlp_sleep_min"]
        self.yt_dlp_sleep_max = c["yt_dlp_sleep_max"]

    def save_config(self):
        self._config.save({
            "output_directory": self.__output_directory,
            "audio_quality": self.__audio_quality,
            "audio_format": self.__audio_format,
            "use_cookies": self.use_cookies,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "download_timeout": self.download_timeout,
            "max_concurrent": self.max_concurrent,
            "yt_dlp_sleep_min": self.yt_dlp_sleep_min,
            "yt_dlp_sleep_max": self.yt_dlp_sleep_max,
        })

    def get_user_preferences(self):
        """Take user input for the download settings."""
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
        output_path = Enhanced_Menu.get_input(
            f"Enter output directory (default: {self.__output_directory}): ", "str")
        output_path = (output_path or "").strip()
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
            Enhanced_Menu.print_status(
                "Note: make sure you have extracted the cookies beforehand - "
                "the Cookie Manager can help you with that.", "info")
        else:
            self.use_cookies = False

        self.save_config()
        Enhanced_Menu.print_status("Settings saved", "success")

    def _get_cookie_file(self) -> Optional[str]:
        """Return a usable cookie-file path if cookies are enabled, else None."""
        if not self.use_cookies:
            return None
        path = getattr(self.cookie_manager, "current_cookie_file", None)
        if path and os.path.exists(path):
            return str(path)
        cookies_dir = Path("cookies")
        if cookies_dir.is_dir():
            candidates = sorted(cookies_dir.glob("*.txt"),
                                key=lambda p: p.stat().st_mtime, reverse=True)
            if candidates:
                return str(candidates[0])
        self.log_manager.log_error(
            "Cookies are enabled but no cookie file was found in cookies/. "
            "Use the Cookie Manager to add one.")
        return None

    def run_download(self, url: str, output_template: str = None, extra_args: List[str] = None,
                        total_items: int = None, item_desc: str = "item", desc: str = None,
                        show_progress: bool = True) -> bool:
        """Run spotdl with a live bar that advances per finished track."""
        # spotdl sources its audio from YouTube, so this shares the YouTube
        # bucket with the other downloader rather than keeping a second,
        # independent stream of requests pointed at the same host.
        youtube_limiter.acquire()

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

                # looks_throttled is the shared definition, so this can't
                # drift from what the YouTube downloader treats as throttling.
                if not rate_limited and looks_throttled(line):
                    rate_limited = True
                    youtube_limiter.penalize(self.retry_delay * 6)
                    self.log_manager.log_error(
                        "Throttling detected - pausing outbound requests", console=False)

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
                    penalty = min(self.rate_limit_backoff * (2 ** (attempt - 2)),
                                  self.rate_limit_max_wait)
                    youtube_limiter.penalize(penalty)
                    if show_progress:
                        Enhanced_Menu.print_status(
                            f"Rate limit detected - holding off {penalty:.0f}s before retrying. "
                            f"Already-downloaded tracks will be skipped.", "warning")
                else:
                    if show_progress:
                        print(f"Waiting {self.retry_delay} seconds before retry...")
                    time.sleep(self.retry_delay)

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

