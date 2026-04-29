import sys
import builtins
import subprocess
import re
from pathlib import Path
from typing import Callable, Optional
from functools import wraps

current_dir = Path(__file__).parent

include_path = (current_dir / ".." / "include").resolve()
interface_path = (current_dir / ".." / "interface").resolve()

sys.path.insert(0, str(include_path))
sys.path.insert(1, str(interface_path))

from YoutubeMusicDownloader import Youtube_Downloader # type: ignore
from Helpers_Validators import Helpers # type: ignore
from EnhancedMenu import Enhanced_Menu # type: ignore

class DownloaderInterface:
    """ An interface that connect Youtube Downloader to allow GUI Integration"""
    def __init__(self, downloader):
        self._downloader = downloader
        self._gui_mode = False
        self._url = None
        self._query = None
        self._progress_callback: Optional[Callable] = None
        self._cancel_check:  Optional[Callable[[], bool]] = None
        self._original_run_download = None
        
    def _patch_input(self):
        """Replace input functions with GUI versions"""
        self._orginal_enhanced_input = Enhanced_Menu.get_input
        Enhanced_Menu.get_input = self._mocked_enhanced_input
        
    def _restore_input(self):
        """Restore original input functions."""
        builtins.input = self._original_input
        if self._original_enhanced_get_input is not None:
            Enhanced_Menu.get_input = self._original_enhanced_get_input
            
    def _mocked_input(self, prompt=''):
        """Mock input that returns the pre-set URL/query."""
        if self._query is not None:
            return self._query
        return self._url
    
    def _mocked_enhanced_input(self, prompt, input_type="str", min_val=None, max_val=None, default=None):
        # URL / search query
        if "Enter YouTube Music" in prompt or "What is the name of the song" in prompt:
            return self._url if self._url is not None else self._query

        # Configuration questions – always skip
        if "Configure download settings" in prompt:
            return 'n'

        # After download – DO NOT loop
        if "Download another" in prompt or "Try another" in prompt:
            return 'n'

        # Large playlist confirmation – always continue
        if "Continue with download" in prompt:
            return 'y'

        # Order selection (playlist) – default top-to-bottom
        if "Download order" in prompt:
            return 't'

        # Any yes/no question not matched above – answer 'n' to be safe
        if input_type == "yn":
            return default if default is not None else 'n'

        # For any other input, return the default (or empty string)
        return default if default is not None else ""

    def _patch_run_download(self):
        """Replace run_download with a version that supports progress and cancellation."""
        self._original_run_download = self._downloader.run_download
        
        def patched_run_download(url, output_template, additional_args=None):
            # Use the new cancelable version (implemented without touching original class)
            return self._run_download_with_cancel(url, output_template, additional_args)
        
        self._downloader.run_download = patched_run_download
    
    def _restore_run_download(self):
            """Restore original run_download."""
            if self._original_run_download:
                self._downloader.run_download = self._original_run_download

    def _run_download_with_cancel(self, url, output_template, additional_args=None):
        # Build the command (same as before)
        cmd = [
            "yt-dlp", "-x",
            "--audio-format", self._downloader._Youtube_Downloader__audio_format,
            "--audio-quality", self._downloader._Youtube_Downloader__audio_quality,
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
        if self._downloader._Youtube_Downloader__embed_metadata:
            cmd.append("--add-metadata")

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, universal_newlines=True)
        output_lines = []
        try:
            for line in iter(process.stdout.readline, ''):
                # Check cancellation
                if self._cancel_check and self._cancel_check():
                    process.terminate()
                    process.wait(timeout=3)
                    return subprocess.CompletedProcess(
                        args=cmd,
                        returncode=-1,
                        stdout=''.join(output_lines),
                        stderr="Cancelled by user"
                    )
                line = line.strip()
                output_lines.append(line)
                if "[download]" in line:
                    m = re.search(r'(\d+\.?\d*)%', line)
                    if m and self._progress_callback:
                        percent = int(float(m.group(1)))
                        self._progress_callback(percent, f"Downloading.. {percent}%")
            process.wait()
            returncode = process.returncode
            full_output = '\n'.join(output_lines)
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=returncode,
                stdout=full_output,
                stderr=""
            )
        except Exception as e:
            process.terminate()
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=-1,
                stdout='\n'.join(output_lines),
                stderr=str(e)
            )
            
    def download_track(self, url: str, progress_callback=None, cancel_check=None) -> bool:
        """Download a track – patches input and run_download, then calls original method."""
        self._gui_mode = True
        self._url = url
        self._query = None
        self._progress_callback = progress_callback
        self._cancel_check = cancel_check
        self._patch_input()
        self._patch_run_download()
        try:
            return self._downloader.download_track()
        finally:
            self._restore_input()
            self._restore_run_download()
            self._gui_mode = False
            self._url = None
            self._progress_callback = None
            self._cancel_check = None

    def download_album(self, url: str, progress_callback=None, cancel_check=None) -> bool:
        self._gui_mode = True
        self._url = url
        self._progress_callback = progress_callback
        self._cancel_check = cancel_check
        self._patch_input()
        self._patch_run_download()
        try:
            return self._downloader.download_album()
        finally:
            self._restore_input()
            self._restore_run_download()
            self._gui_mode = False
            self._url = None

    def download_playlist(self, url: str, progress_callback=None, cancel_check=None) -> bool:
        self._gui_mode = True
        self._url = url
        self._progress_callback = progress_callback
        self._cancel_check = cancel_check
        self._patch_input()
        self._patch_run_download()
        try:
            return self._downloader.download_playlist()
        finally:
            self._restore_input()
            self._restore_run_download()
            self._gui_mode = False
            self._url = None

    def search_and_download(self, query: str, progress_callback=None, cancel_check=None) -> bool:
        self._gui_mode = True
        self._query = query
        self._url = None
        self._progress_callback = progress_callback
        self._cancel_check = cancel_check
        self._patch_input()
        self._patch_run_download()
        try:
            return self._downloader.search_and_download()
        finally:
            self._restore_input()
            self._restore_run_download()
            self._gui_mode = False
            self._query = None