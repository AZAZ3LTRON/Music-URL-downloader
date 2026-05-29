import sys
import subprocess
import re
import threading
from pathlib import Path
from typing import Callable, Optional
from unittest.mock import patch

current_dir = Path(__file__).parent
include_path = (current_dir / ".." / "include").resolve()
sys.path.insert(0, str(include_path))

from core.SpotifyMusicDownloader import SpotifyMusicDownloader   #type: ignore
from utils.Validators import Helpers  #type: ignore
from utils.EnhancedMenu import Enhanced_Menu #type: ignore

# Needs change

class DownloaderInterface:
    """
    Adapter that runs Youtube_Downloader methods without user interaction.
    Provides progress callbacks and safe cancellation.
    """

    def __init__(self, downloader: SpotifyMusicDownloader):
        self._downloader = downloader
        self._progress_callback: Optional[Callable[[int, str], None]] = None
        self._cancel_event: Optional[threading.Event] = None
        self._url_prompt_count = 0

        # Store references to the original methods we need to wrap
        self._original_get_input = Enhanced_Menu.get_input

    # ------------------------------------------------------------
    # Public API – same signatures as before
    # ------------------------------------------------------------
    def download_track(self, url: str,
                       progress_callback: Optional[Callable[[int, str], None]] = None,
                       cancel_event: Optional[threading.Event] = None) -> bool:
        self._url = url
        return self._run_download("track", "track URL", progress_callback, cancel_event)

    def download_album(self, url: str,
                       progress_callback=None, cancel_event=None) -> bool:
        self._url = url
        return self._run_download("album", "album URL", progress_callback, cancel_event)

    def download_playlist(self, url: str,
                          progress_callback=None, cancel_event=None) -> bool:
        self._url = url
        return self._run_download("playlist", "playlist URL", progress_callback, cancel_event)

    def download_artist(self, url: str,
                          progress_callback=None, cancel_event=None) -> bool:
        self._url = url
        return self._run_download("artist", "artist URL", progress_callback, cancel_event)
    
    def search_and_download(self, query: str,
                            progress_callback=None, cancel_event=None) -> bool:
        self._query = query
        self._url = None
        return self._run_download("search", "song name", progress_callback, cancel_event)

    # ------------------------------------------------------------
    # Internal runner
    # ------------------------------------------------------------
    def _run_download(self, item_type: str, prompt_hint: str,
                      progress_callback, cancel_event) -> bool:
        self._progress_callback = progress_callback
        self._cancel_event = cancel_event or threading.Event()
        self._url_prompt_count = 0

        # Safely mock Enhanced_Menu.get_input only during the call
        with patch.object(Enhanced_Menu, 'get_input', new=self._mocked_get_input):
            # Also temporarily replace run_download to inject cancellation + progress
            original_run = self._downloader.run_download
            self._downloader.run_download = self._run_download_with_monitoring
            try:
                if item_type == "track":
                    return self._downloader.download_track()
                elif item_type == "album":
                    return self._downloader.download_album()
                elif item_type == "playlist":
                    return self._downloader.download_playlist()
                elif item_type == "artist":
                    return self._downloader.download_artist()
                elif item_type == "search":
                    return self._downloader.search_and_download()
                else:
                    return False
            finally:
                self._downloader.run_download = original_run
                self._progress_callback = None
                self._cancel_event = None

    # ------------------------------------------------------------
    # Mock for Enhanced_Menu.get_input – answers all prompts
    # ------------------------------------------------------------
    def _mocked_get_input(self, prompt, input_type="str",
                        min_val=None, max_val=None, default=None):
        # 1) After download – break the loop with boolean False
        if "Download another" in prompt or "Try another" in prompt:
            return False                # ⚡ was 'n'

        # 2) Configuration prompt – skip
        if "Configure download settings" in prompt:
            return False

        # 3) Large playlist confirmation – continue
        if "Continue with download" in prompt:
            return True

        # 4) Playlist order – default to top‑to‑bottom
        if "Download order" in prompt:
            return 't'

        # 5) First URL / search query – return the stored URL/query exactly once
        if "Enter YouTube Music" in prompt or "What is the name of the song" in prompt:
            if self._url_prompt_count == 0:
                self._url_prompt_count += 1
                return self._url if self._url else (self._query or "")
            # Safety: second unexpected URL prompt → force exit
            return ""

        # 6) All other yes/no questions → safe default
        if input_type == "yn":
            return False                # ⚡ return Boolean, not string
        return default if default is not None else ""

    # ------------------------------------------------------------
    # Replaces the downloader’s run_download with monitoring + cancel
    # ------------------------------------------------------------
    def _run_download_with_monitoring(self, url, output_template, additional_args=None):
        # Build the yt-dlp command exactly as the original does (duplicated here
        # for independence; keep in sync with Youtube_Downloader.run_download)
        cmd = [
            "yt-dlp", "-x",
            "--audio-format", self._downloader._YoutubeMusicDownloader__audio_format,
            "--audio-quality", self._downloader._YoutubeMusicDownloader__audio_quality,
            "-o", output_template,
            "--no-overwrites", "--embed-thumbnail",
            "--newline", "--progress", "--quiet", "--no-warnings", "--ignore-errors",
            "--retries", "10", "--fragment-retries", "10",
            "--buffer-size", "16K", "--http-chunk-size", "10M",
            "--extractor-args", "youtube:player_client=android",
        ]
        if self._downloader.use_cookies and self._downloader.cookie_manager.current_cookie_file:
            cookie_args = self._downloader.cookie_manager.get_arguments_ytdlp()
            if cookie_args:
                cmd.extend(cookie_args)
        if additional_args:
            cmd.extend(additional_args if isinstance(additional_args, list) else [additional_args])
        cmd.append(url)
        if self._downloader._YoutubeMusicDownloader__embed_metadata:
            cmd.append("--add-metadata")

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, universal_newlines=True
        )
        output_lines = []

        try:
            for line in iter(process.stdout.readline, ''):
                # Check cancellation before each line
                if self._cancel_event and self._cancel_event.is_set():
                    self._terminate_process(process)
                    return subprocess.CompletedProcess(
                        args=cmd, returncode=-1,
                        stdout=''.join(output_lines),
                        stderr="Download cancelled by user"
                    )

                line = line.strip()
                output_lines.append(line)

                # Parse progress and call callback
                if "[download]" in line and self._progress_callback:
                    percent_match = re.search(r'(\d+\.?\d*)%', line)
                    if percent_match:
                        percent = int(float(percent_match.group(1)))
                        # Build a nice status message
                        speed = eta = ""
                        speed_match = re.search(r'at\s+([\d.]+\s*[KMGT]?i?B/s)', line)
                        if speed_match:
                            speed = f" at {speed_match.group(1)}"
                        eta_match = re.search(r'ETA\s+([\d:]+)', line)
                        if eta_match:
                            eta = f", ETA {eta_match.group(1)}"
                        self._progress_callback(percent, f"Downloading... {percent}%{speed}{eta}")

            process.wait()
            return subprocess.CompletedProcess(
                args=cmd, returncode=process.returncode,
                stdout='\n'.join(output_lines), stderr=""
            )

        except Exception as e:
            self._terminate_process(process)
            return subprocess.CompletedProcess(
                args=cmd, returncode=-1,
                stdout='\n'.join(output_lines), stderr=str(e)
            )

    @staticmethod
    def _terminate_process(process):
        """Gracefully terminate a subprocess, then kill if necessary."""
        try:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        except (ProcessLookupError, OSError):
            pass   # already dead