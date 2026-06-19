import re
import os
import subprocess
import time
import hashlib
import threading
import json

from functools import wraps
from pathlib import Path
from typing import Dict, List
from tqdm import tqdm
from colorama import init, Fore, Style

from utils.CookieManager import CookieManager
from utils.DownloaderUtils import DownloaderUtils
from utils.EnhancedMenu import Enhanced_Menu
from utils.Logs_Handler import Logs_Manager
from utils.DownloadHistory import DownloadHistory
from src.utils.Helpers import Helpers

init(autoreset=True)
os.makedirs("cookies", exist_ok=True)


def rate_limit(calls_per_minute: int = 60):
    """Throttle how often the decorated method may be invoked (process-wide)."""
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


class YoutubeMusicDownloader:
    """Downloads music from YouTube / YouTube Music via yt-dlp.

    Mirrors SpotifyMusicDownloader: a single unified download path expands collections
    in one yt-dlp invocation, with rate-limit-aware retries, categorised failure
    tracking, and a categorised summary.
    """

    # Lines in yt-dlp output that mean we're being throttled rather than simply missing a video.
    RATE_LIMIT_MARKERS = ("http error 429", "sign in to confirm", "rate-limited",
                          "too many requests", "rate/request limit")
    # Categories worth a retry round; permanent ones (private/unavailable/...) are not.
    RETRYABLE = ("rate_limited", "network", "conversion", "format", "other")

    _ERR_RE = re.compile(
        r'ERROR:\s*(?:\[[^\]]+\]\s*)?(?P<vid>[A-Za-z0-9_-]{11})?[: ]\s*(?P<reason>.*)', re.IGNORECASE)
    _ITEM_RE = re.compile(r'Downloading (?:item|video) (\d+) of (\d+)', re.IGNORECASE)
    _PCT_RE = re.compile(r'(\d+\.?\d*)%')

    def __init__(self):
        self.__output_directory = Path.home() / "Music" / "YouTubeMusicDownloads"
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.__embed_metadata = False
        self.__configuration_file = r"config/YoutubeMusicDownloader.json"

        self.cookie_manager = CookieManager()
        self.log_manager = Logs_Manager()
        self.utils = DownloaderUtils()
        self.history = DownloadHistory()
        self.use_cookies = False

        self._last_download_stats = {"succeeded": 0, "skipped": 0, "failed": 0,
                                     "failed_items": [], "by_category": {}, "rate_limited": False}

        self.max_retries = 3
        self.retry_delay = 10
        self.download_timeout = 120
        self.max_concurrent = 3            # yt-dlp --concurrent-fragments
        self.rate_limit_backoff = 300      # base wait (s) after a YouTube rate limit
        self.rate_limit_max_wait = 1800    # cap escalating backoff at 30 min
        self.yt_dlp_sleep_min = 3          # min seconds yt-dlp waits between downloads
        self.yt_dlp_sleep_max = 7          # max seconds (random delay in this range)

        self.archives_dir = Path("archives")
        self.archives_dir.mkdir(exist_ok=True)
        self.__output_directory.mkdir(parents=True, exist_ok=True)
        os.makedirs(os.path.dirname(self.__configuration_file), exist_ok=True)

        try:
            self.load_config()
        except Exception as e:
            self.log_manager.log_error(f"Error loading config: {e}")

    # ==================== Public properties ====================
    @property
    def audio_format(self) -> str:
        return self.__audio_format

    @audio_format.setter
    def audio_format(self, value: str):
        if value in ["mp3", "flac", "ogg", "opus", "m4a", "wav"]:
            self.__audio_format = value
        else:
            raise ValueError(f"Unsupported audio format: {value}")

    @property
    def audio_quality(self) -> str:
        return self.__audio_quality

    @audio_quality.setter
    def audio_quality(self, value: str):
        valid = ["auto", "disable", "8k", "16k", "24k", "32k", "40k", "48k", "64k",
                 "80k", "96k", "112k", "128k", "160k", "192k", "224k", "256k", "320k"]
        if value in valid:
            self.__audio_quality = value
        else:
            raise ValueError(f"Unsupported audio quality: {value}")

    @property
    def output_directory(self) -> Path:
        return self.__output_directory

    @output_directory.setter
    def output_directory(self, path: Path):
        self.__output_directory = Path(path)
        self.__output_directory.mkdir(parents=True, exist_ok=True)

    # ==================== Configuration ====================
    def load_config(self):
        """Load configuration from the json file."""
        primary_config = {
            "output_directory": str(Path.home() / "Music" / "YouTubeMusicDownloads"),
            "audio_quality": "320k",
            "audio_format": "mp3",
            "embed_metadata": False,
            "max_retries": 3,
            "retry_delay": 10,
            "download_timeout": 120,
            "max_concurrent": 3,
            "rate_limit_backoff": 300,
            "rate_limit_max_wait": 1800,
            "yt_dlp_sleep_min": 3,
            "yt_dlp_sleep_max": 7,
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
            self.__embed_metadata = config.get("embed_metadata", False)
            self.use_cookies = config.get("use_cookies", False)
            self.max_retries = config.get("max_retries", 3)
            self.retry_delay = config.get("retry_delay", 10)
            self.download_timeout = config.get("download_timeout", 120)
            self.max_concurrent = config.get("max_concurrent", 3)
            self.rate_limit_backoff = config.get("rate_limit_backoff", 300)
            self.rate_limit_max_wait = config.get("rate_limit_max_wait", 1800)
            self.yt_dlp_sleep_min = config.get("yt_dlp_sleep_min", 3)
            self.yt_dlp_sleep_max = config.get("yt_dlp_sleep_max", 7)
        except Exception as e:
            self.log_manager.log_error(f"Error loading configuration: {e}")
            self.__output_directory = Path(primary_config["output_directory"])
            self.__audio_quality = primary_config["audio_quality"]
            self.__audio_format = primary_config["audio_format"]
            self.__embed_metadata = primary_config["embed_metadata"]
            self.use_cookies = primary_config["use_cookies"]

    def save_config(self, config: Dict = None):
        """Save configuration to file."""
        try:
            os.makedirs(os.path.dirname(self.__configuration_file), exist_ok=True)
            if config is None:
                config = {
                    "output_directory": str(self.__output_directory),
                    "audio_quality": self.__audio_quality,
                    "audio_format": self.__audio_format,
                    "embed_metadata": self.__embed_metadata,
                    "max_retries": self.max_retries,
                    "retry_delay": self.retry_delay,
                    "download_timeout": self.download_timeout,
                    "max_concurrent": self.max_concurrent,
                    "rate_limit_backoff": self.rate_limit_backoff,
                    "rate_limit_max_wait": self.rate_limit_max_wait,
                    "yt_dlp_sleep_min": self.yt_dlp_sleep_min,
                    "yt_dlp_sleep_max": self.yt_dlp_sleep_max,
                    "use_cookies": self.use_cookies,
                }
            else:
                config = {**config}
                if "output_directory" in config:
                    config["output_directory"] = str(config["output_directory"])
            with open(self.__configuration_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log_manager.log_error(f"Error saving configuration: {e}")

    # ==================== User preferences ====================
    def get_user_preferences(self):
        """Collect download settings from the user."""
        Enhanced_Menu.print_header("Download Settings", "Configure your music download preferences")

        while True:
            q = Enhanced_Menu.get_input(
                "What bitrate would you like (enter 'choice' to see options): ",
                "str", default=self.__audio_quality)
            if not q:
                self.__audio_quality = "320k"
                break
            if q == 'choice':
                print(f"\n{Fore.CYAN}Available qualities:{Style.RESET_ALL}")
                print("  auto     - Let yt-dlp choose the best")
                print("  320k     - High quality (default)")
                print("  256k     - Very good quality")
                print("  192k     - Good quality")
                print("  128k     - Standard quality")
                print("  8k-160k  - Lower qualities")
                continue
            valid = ["auto", "disable", "8k", "16k", "24k", "32k", "40k", "48k", "64k",
                     "80k", "96k", "112k", "128k", "160k", "192k", "224k", "256k", "320k"]
            if q in valid:
                self.__audio_quality = q.lower()
                break
            Enhanced_Menu.print_status("Invalid bitrate. The downloader doesn't support these values", "error")

        while True:
            fmt = Enhanced_Menu.get_input(
                "What format would you like (enter 'choice' to see options): ",
                "str", default=self.__audio_format)
            if not fmt:
                self.__audio_format = "mp3"
                break
            if fmt == 'choice':
                print(f"\n{Fore.CYAN}Available formats:{Style.RESET_ALL}")
                print("  mp3  - Most compatible (default)")
                print("  m4a  - Apple format, good quality")
                print("  flac - Lossless audio")
                print("  opus - Excellent compression")
                print("  ogg  - Open format")
                print("  wav  - Uncompressed")
                continue
            if fmt in ["mp3", "flac", "ogg", "opus", "m4a", "wav"]:
                self.__audio_format = fmt
                break
            Enhanced_Menu.print_status("Invalid format. Downloader doesn't support this format", "error")

        output_path = Enhanced_Menu.get_input(
            f"Enter output directory (default: {self.__output_directory}): ", "str").strip()
        if output_path:
            self.__output_directory = Path(output_path)
        else:
            self.__output_directory = Path.home() / "Music" / "YouTubeMusicDownloads"
        self.__output_directory.mkdir(parents=True, exist_ok=True)

        self.__embed_metadata = Enhanced_Menu.get_input(
            "Embed metadata (artist, album, cover art) into files? (y/n): ", "yn",
            default=self.__embed_metadata)

        Enhanced_Menu.print_status("Cookie Settings", "info")
        print(f"\n{Fore.CYAN}Cookies can help with:{Style.RESET_ALL}")
        print(" Age-restricted content")
        print(" Region-restricted videos")
        print(" Private playlists")
        self.use_cookies = Enhanced_Menu.get_input(
            "Use cookies for authentication? (y/n): ", "yn", default=self.use_cookies)
        if self.use_cookies:
            if self._get_cookie_file():
                Enhanced_Menu.print_status("Cookies enabled for this download.", "info")
            elif Enhanced_Menu.get_input(
                    "No cookie file found. Open Cookie Manager now? (y/n)", "yn", default=False):
                self.manage_cookies()

    # ==================== Helpers ====================
    def _get_cookie_file(self):
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
                self.cookie_manager.current_cookie_file = candidates[0]
                return str(candidates[0])
        self.log_manager.log_error(
            "Cookies are enabled but no cookie file was found in cookies/. "
            "Use the Cookie Manager to add one.", console=True)
        return None

    def _bitrate_arg(self) -> str:
        """'320k' -> yt-dlp '320K'; 'auto'/'disable'/blank -> best (0)."""
        q = (self.__audio_quality or "").lower().rstrip("k")
        return f"{q}K" if q.isdigit() else "0"

    @staticmethod
    def _classify_ytdlp_error(text: str) -> str:
        """Bucket a yt-dlp failure. Permanent buckets aren't retried; transient ones are."""
        t = (text or "").lower()
        if any(k in t for k in ("http error 429", "sign in to confirm", "rate-limited",
                                "too many requests")):
            return "rate_limited"
        if "private" in t:
            return "private"
        if "age" in t and "restrict" in t:
            return "age_restricted"
        if "copyright" in t:
            return "copyright"
        if any(k in t for k in ("unavailable", "removed", "not available", "deleted")):
            return "unavailable"
        if "ffmpeg" in t:
            return "conversion"
        if "format" in t:
            return "format"
        if any(k in t for k in ("timed out", "timeout", "connection", "network", "temporary failure")):
            return "network"
        return "other"

    @staticmethod
    def _archive_id(url: str) -> str:
        """Stable archive filename stem from a playlist/channel/video URL."""
        pl = Helpers.extract_youtube_playlist_id(url)
        if pl:
            return f"playlist_{pl}"
        m = re.search(r"youtube\.com/channel/([\w-]+)", url)
        if m:
            return f"channel_{m.group(1)}"
        m = re.search(r"youtube\.com/@([\w-]+)", url)
        if m:
            return f"channel_{m.group(1)}"
        return f"url_{hashlib.md5(url.encode()).hexdigest()[:8]}"

    # ==================== Core download ====================
    @rate_limit(calls_per_minute=60)
    def run_download(self, url: str, output_template: str, extra_args: List[str] = None,
                     total_items: int = None, item_desc: str = "item", desc: str = None) -> bool:
        """Run yt-dlp (which expands playlists/channels itself) with a live progress bar.

        Parses yt-dlp output for per-item progress, archive skips, rate limits, and
        categorised failures; populates self._last_download_stats.
        """
        out_dir = os.path.dirname(output_template)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        cmd = [
            "yt-dlp",
            "-x", "--audio-format", self.__audio_format,
            "--audio-quality", self._bitrate_arg(),
            "-o", output_template,
            "--no-overwrites",
            "--embed-thumbnail",
            "--newline", "--progress", "--no-warnings",
            "--ignore-errors",
            "--retries", "10", "--fragment-retries", "10",
            "--concurrent-fragments", str(self.max_concurrent),
            "--sleep-interval", str(self.yt_dlp_sleep_min),
            "--max-sleep-interval", str(self.yt_dlp_sleep_max),
            "--extractor-args", "youtube:player_client=android",
        ]
        if self.__embed_metadata:
            cmd.append("--add-metadata")
        cookie_file = self._get_cookie_file()
        if cookie_file:
            cmd.extend(["--cookies", cookie_file])
        if extra_args:
            cmd.extend(extra_args)
        cmd.append(url)

        label = desc or f"Downloading {item_desc}s"
        if len(label) > 40:
            label = label[:37] + "..."

        if total_items and total_items > 1:
            pbar = tqdm(total=total_items, desc=label, unit=item_desc, colour="green",
                        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]")
        else:
            pbar = tqdm(desc=label, unit="track", total=None, colour="green",
                        bar_format="{l_bar}{bar}| {n_fmt} [{elapsed}]{postfix}")

        output_lines, failures = [], {}
        skipped = completed = 0
        rate_limited = False

        try:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding="utf-8", errors="replace",
                                       bufsize=1, env=env)

            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if not line:
                    continue
                output_lines.append(line)
                if len(output_lines) > 1000:
                    output_lines = output_lines[-200:]
                low = line.lower()

                if any(m in low for m in self.RATE_LIMIT_MARKERS):
                    rate_limited = True

                # Collection progress: "Downloading item N of M"
                im = self._ITEM_RE.search(line)
                if im and total_items and total_items > 1:
                    idx = int(im.group(1))
                    if idx > completed:
                        completed = idx
                        pbar.n = min(idx, total_items)
                        pbar.refresh()
                    continue

                # Archive / already-have skip
                if "has already been downloaded" in low or "recorded in the archive" in low:
                    skipped += 1
                    continue

                # Failure (deduped by video id)
                if "error:" in low:
                    m = self._ERR_RE.search(line)
                    vid = (m.group("vid") if m and m.group("vid") else None) or line
                    reason = (m.group("reason") if m else line) or line
                    if vid not in failures:
                        failures[vid] = {"reason": reason.strip()[:200],
                                         "category": self._classify_ytdlp_error(f"{reason} {line}")}
                    continue

                # Single-item live detail
                if not total_items or total_items == 1:
                    pm = self._PCT_RE.search(line)
                    if pm and "[download]" in low:
                        pbar.set_postfix_str(f"{float(pm.group(1)):.1f}%")
                    sm = re.search(r'at\s+([\d.]+\s*[KMGT]?i?B/s)', line)
                    if sm:
                        pbar.set_postfix_str(sm.group(1))

            process.wait()

            if total_items and total_items > 1:
                pbar.n = total_items
                pbar.refresh()
            pbar.close()

            by_category = {}
            for info in failures.values():
                by_category[info["category"]] = by_category.get(info["category"], 0) + 1

            failed = len(failures)
            if total_items:
                succeeded = max(total_items - failed - skipped, 0)
            else:
                succeeded = 0 if failed else 1

            self._last_download_stats = {
                "succeeded": succeeded, "skipped": skipped, "failed": failed,
                "failed_items": [{"id": k, **v} for k, v in failures.items()],
                "by_category": by_category, "rate_limited": rate_limited,
            }
            return failed == 0

        except FileNotFoundError:
            pbar.close()
            self.log_manager.log_error("yt-dlp not found. Install it with: pip install yt-dlp", console=True)
            raise RuntimeError("yt-dlp not found")
        except Exception as e:
            pbar.close()
            self.log_manager.log_error(f"Download process exception: {e}", console=True)
            self._last_download_stats = {"succeeded": 0, "skipped": skipped, "failed": len(failures),
                                         "failed_items": [{"id": k, **v} for k, v in failures.items()],
                                         "by_category": {}, "rate_limited": rate_limited}
            return False

    def _download_with_retry(self, url: str, output_template: str, extra_args: list = None,
                             item_type: str = "item", total_items: int = None, desc: str = None) -> bool:
        """Retry wrapper with rate-limit-aware backoff (mirrors the Spotify downloader)."""
        for attempt in range(1, self.max_retries + 1):
            Enhanced_Menu.print_section(f"Downloading {item_type} (Attempt {attempt}/{self.max_retries})")
            if attempt > 1:
                if self._last_download_stats.get("rate_limited"):
                    wait = min(self.rate_limit_backoff * (2 ** (attempt - 2)), self.rate_limit_max_wait)
                    Enhanced_Menu.print_status(
                        f"YouTube rate limit detected - backing off {wait}s before retrying. "
                        f"Already-downloaded items will be skipped.", "warning")
                else:
                    wait = self.retry_delay
                    print(f"Waiting {wait} seconds before retry...")
                time.sleep(wait)

            try:
                success = self.run_download(url, output_template, extra_args,
                                            total_items=total_items, item_desc=item_type, desc=desc)
                if success:
                    self.log_manager.log_success(f"Successfully downloaded {item_type}: {url}")
                    if item_type in ('album', 'playlist', 'channel'):
                        Helpers.cleanup_directory(self.__output_directory, self.log_manager)
                    return True
                # If everything that failed is permanent, no point retrying.
                cats = self._last_download_stats.get("by_category", {})
                if cats and all(c not in self.RETRYABLE for c in cats):
                    self.log_manager.log_failure(
                        f"{item_type} failed with only permanent errors, not retrying: {url}")
                    return False
            except Exception as e:
                self.log_manager.log_error(f"Attempt {attempt} failed: {e}")
                if attempt == self.max_retries:
                    self.log_manager.log_failure(f"Failed after {self.max_retries} attempts: {url}")

        if self._last_download_stats.get("rate_limited"):
            self.log_manager.log_failure(
                f"Gave up after {self.max_retries} attempts due to YouTube rate limiting: {url}. "
                f"Re-run later - the --download-archive means finished items are skipped.")
        return False

    # ==================== Unified item download ====================
    def _download_item(self, item_type: str, url_prompt: str, output_template: str,
                       confirm_large: bool = False, use_archive: bool = False,
                       no_playlist: bool = False, force_url: str = None) -> bool:
        """Unified download for track / album / playlist / channel."""
        while True:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header(f"Download {item_type.title()}")

            if force_url:
                url = force_url
            else:
                url = Enhanced_Menu.get_input(f"Enter YouTube Music {url_prompt} (or 'back' to return)", "str")
                if url.lower() == 'back':
                    return False
            if not url:
                Enhanced_Menu.print_status("No URL provided", "error")
                if force_url:
                    return False
                continue

            self.history.add_input(url, item_type)

            if not Helpers.validate_youtube_url(url):
                Enhanced_Menu.print_status("Invalid YouTube/YouTube Music URL", "error")
                if force_url:
                    return False
                continue

            is_valid, message, metadata = Helpers.validate_resource_youtube(url)
            if not is_valid or not metadata:
                Enhanced_Menu.print_status(f"Validation failed: {message}", "error")
                if force_url:
                    return False
                continue

            Enhanced_Menu.print_status("Resource information:", "success")
            if item_type == "track":
                print(f"  {Fore.CYAN}Track:{Style.RESET_ALL} {metadata.get('title', 'Unknown')}")
                print(f"  {Fore.CYAN}Artist:{Style.RESET_ALL} "
                      f"{metadata.get('artist') or metadata.get('uploader', 'Unknown Artist')}")
                album = metadata.get('album', 'Unknown Album')
                if album != 'Unknown Album':
                    print(f"  {Fore.CYAN}Album:{Style.RESET_ALL} {album}")
            else:
                name = metadata.get('title', f'Unknown {item_type.title()}')
                owner = metadata.get('channel') or metadata.get('uploader') or metadata.get('artist', 'Unknown')
                print(f"  {Fore.CYAN}{item_type.title()}:{Style.RESET_ALL} {name}")
                if owner and owner != 'Unknown':
                    print(f"  {Fore.CYAN}By:{Style.RESET_ALL} {owner}")
                print(f"  {Fore.CYAN}Items:{Style.RESET_ALL} {metadata.get('playlist_count', '?')}")
            print()

            total = metadata.get('playlist_count') or None if item_type in ('album', 'playlist', 'channel') else 1

            if confirm_large and (metadata.get('playlist_count', 0) or 0) > 50:
                count = metadata['playlist_count']
                Enhanced_Menu.print_status(f"This {item_type} contains {count} items. This may take a while.", "warning")
                if not Enhanced_Menu.get_input("Continue with download? (y/n)", "yn", default=False):
                    Enhanced_Menu.print_status("Download cancelled", "info")
                    if force_url:
                        return False
                    continue

            extra_args = []
            if no_playlist:
                extra_args.append("--no-playlist")
            if use_archive:
                archive_path = self.archives_dir / f"{self._archive_id(url)}.txt"
                extra_args.extend(["--download-archive", str(archive_path)])

            if not force_url and Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
                self.get_user_preferences()

            Enhanced_Menu.print_status(f"Starting {item_type} download...", "info")
            display_name = metadata.get('title') or item_type.title()
            success = self._download_with_retry(url, output_template, extra_args or None,
                                                item_type, total_items=total, desc=display_name)

            if item_type in ('album', 'playlist', 'channel'):
                self._print_summary(item_type, url, total)

            if force_url:
                return success

            if success:
                time.sleep(0.5)
                if Enhanced_Menu.get_input(f"\nDownload another {item_type}? (y/n): ", "yn", default=True):
                    continue
                return True
            else:
                if Enhanced_Menu.get_input(f"\nDownload failed. Try another {item_type}? (y/n): ", "yn", default=True):
                    continue
                return False

    def _print_summary(self, item_type: str, url: str, total):
        """Categorised summary + clean per-item failed logging (mirrors Spotify)."""
        stats = self._last_download_stats
        failed = stats["failed"]
        failed_items = stats.get("failed_items", [])
        by_category = stats.get("by_category", {})
        succeeded = max(total - failed, 0) if total else stats["succeeded"]

        labels = {
            "rate_limited": "Rate-limited (retry later)", "network": "Network errors",
            "private": "Private", "unavailable": "Unavailable / removed",
            "age_restricted": "Age-restricted", "copyright": "Copyright-blocked",
            "format": "Format unavailable", "conversion": "Conversion (ffmpeg) errors", "other": "Other",
        }

        print()
        Enhanced_Menu.print_status(f"{item_type.title()} download summary:", "info")
        print(f"  {Fore.GREEN}Succeeded:{Style.RESET_ALL} {succeeded}")
        print(f"  {Fore.RED}Failed:{Style.RESET_ALL} {failed}")
        for cat, n in sorted(by_category.items(), key=lambda x: -x[1]):
            print(f"      {labels.get(cat, cat)}: {n}")
        if total:
            print(f"  {Fore.CYAN}Total items:{Style.RESET_ALL} {total}")

        if failed_items:
            print(f"{Fore.RED} Some items failed - see failed.log {Style.RESET_ALL}")
            for it in failed_items:
                vid = it["id"]
                target = f"https://music.youtube.com/watch?v={vid}" if len(str(vid)) == 11 else vid
                self.log_manager.log_failure(
                    f"{item_type} {url} | [{it['category']}] {target} - {it['reason']}", console=False)

    # ==================== Public download methods ====================
    def download_track(self):
        return self._download_item(
            item_type="track", url_prompt="track URL",
            output_template=str(self.__output_directory / "%(artist)s - %(title)s.%(ext)s"),
            confirm_large=False, no_playlist=True)

    def download_album(self):
        return self._download_item(
            item_type="album", url_prompt="album URL",
            output_template=str(self.__output_directory / "%(artist)s/%(album)s/%(artist)s - %(title)s.%(ext)s"),
            confirm_large=True, use_archive=True)

    def download_playlist(self):
        return self._download_item(
            item_type="playlist", url_prompt="playlist URL",
            output_template=str(self.__output_directory / "%(playlist_title)s/%(artist)s - %(title)s.%(ext)s"),
            confirm_large=True, use_archive=True)

    def download_channel(self):
        return self._download_item(
            item_type="channel", url_prompt="channel/artist URL",
            output_template=str(self.__output_directory / "%(channel)s/%(title)s.%(ext)s"),
            confirm_large=True, use_archive=True)

    def search_and_download(self):
        """Search for a song by name and download the top result."""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Search & Download")
        query = Enhanced_Menu.get_input("Enter song name or search query", "str")
        if not query:
            Enhanced_Menu.print_status("No query entered", "error")
            return False
        self.history.add_input(query, "search")
        if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
            self.get_user_preferences()

        output_template = str(self.__output_directory / "%(artist)s - %(title)s.%(ext)s")
        success = self._download_with_retry(f"ytsearch1:{query}", output_template,
                                            ["--no-playlist"], "track", total_items=1, desc=query)
        if success:
            self.log_manager.log_success(f"Successfully downloaded: '{query}'")
        else:
            self.log_manager.log_failure(f"Failed to download after {self.max_retries} attempts: '{query}'")
        return success

    # ==================== Cookies / checkers / utilities ====================
    def manage_cookies(self):
        self.cookie_manager.interactive_menu()
        if self.cookie_manager.current_cookie_file:
            self.use_cookies = Enhanced_Menu.get_input(
                "Enable cookies for future downloads? (y/n)", "yn", default=False)
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
        print("Running a simple diagnostic. This might take a while.....")

        Enhanced_Menu.print_status("1. Checking yt-dlp installation...", "info")
        if not self.check_ytdlp():
            Enhanced_Menu.print_status("yt-dlp not found or not working", "error")
            if Enhanced_Menu.get_input("Install yt-dlp now? (y/n)", "yn", default=True):
                self.setup_dependencies()

        Enhanced_Menu.print_status("\n2. Checking FFmpeg installation...", "info")
        if not self.check_ffmpeg():
            Enhanced_Menu.print_status("FFmpeg not found (audio conversion might fail)", "error")

        Enhanced_Menu.print_status("\n3. Testing YouTube access...", "info")
        test_url = "https://music.youtube.com/watch?v=215T8NF93kw"
        try:
            result = subprocess.run(["yt-dlp", "--skip-download", "--print", "title", test_url],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            if result.returncode == 0:
                Enhanced_Menu.print_status("Can access YouTube", "success")
            else:
                Enhanced_Menu.print_status(f"Cannot access YouTube: {result.stderr[:100]}", "error")
        except Exception as e:
            Enhanced_Menu.print_status(f"Test failed: {e}", "error")

    def reset_to_defaults(self):
        self.__output_directory = Path.home() / "Music" / "YouTubeMusicDownloads"
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.__embed_metadata = False
        self.use_cookies = False
        self.save_config()
        Enhanced_Menu.print_status("Settings reset to defaults", "success")