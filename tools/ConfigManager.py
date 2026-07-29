import os
import json
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional


class DownloaderConfigManager:
    """
    Handles loading, defaulting, validating, and saving a downloader's JSON config.
    """

    VALID_FORMATS = ("mp3", "flac", "ogg", "opus", "m4a", "wav")
    VALID_QUALITIES = ("auto", "disable", "8k", "16k", "24k", "32k", "40k", "48k",
                       "64k", "80k", "96k", "112k", "128k", "160k", "192k",
                       "224k", "256k", "320k")

    # Keys that must be positive integers, with their sane bounds.
    _INT_BOUNDS = {
        "max_retries": (1, 10),
        "retry_delay": (0, 3600),
        "download_timeout": (10, 86400),
        "max_concurrent": (1, 16),
        "yt_dlp_sleep_min": (0, 3600),
        "yt_dlp_sleep_max": (0, 3600),
        "max_downloads_per_minute": (1, 600),
        "max_metadata_calls_per_minute": (1, 600),
    }

    _COMMON_DEFAULTS: Dict[str, Any] = {
        "audio_quality": "320k",
        "audio_format": "mp3",
        "max_retries": 3,
        "retry_delay": 10,
        "download_timeout": 120,
        "use_cookies": False,
        "max_concurrent": 2,
        "yt_dlp_sleep_min": 3,
        "yt_dlp_sleep_max": 7,
    }

    def __init__(self, config_file: str, defaults: Dict[str, Any],
                 on_error: Optional[Callable[[str], None]] = None):
        self.config_file = str(config_file)
        # Copy so a caller mutating the dict later can't retroactively change
        # what this manager considers a default.
        self.defaults: Dict[str, Any] = dict(defaults)
        self._on_error = on_error or (lambda msg: None)
        self._lock = threading.Lock()

    # ==================== Named profiles ====================
    @classmethod
    def spotify_defaults(cls) -> Dict[str, Any]:
        return {
            **cls._COMMON_DEFAULTS,
            "output_directory": str(Path.home() / "Music" / "Collection" / "Spotify"),
            "max_downloads_per_minute": 60,
            "max_metadata_calls_per_minute": 30,
        }

    @classmethod
    def youtube_defaults(cls) -> Dict[str, Any]:
        return {
            **cls._COMMON_DEFAULTS,
            "output_directory": str(Path.home() / "Music" / "Collection" / "YouTube"),
        }

    @classmethod
    def for_spotify(cls, config_file: str = "config/SpotifyMusicDownloader.json",
                    on_error: Optional[Callable[[str], None]] = None):
        return cls(config_file, cls.spotify_defaults(), on_error)

    @classmethod
    def for_youtube(cls, config_file: str = "config/YoutubeMusicDownloader.json",
                    on_error: Optional[Callable[[str], None]] = None):
        return cls(config_file, cls.youtube_defaults(), on_error)

    # ==================== Internals ====================
    def _log_error(self, msg: str):
        try:
            self._on_error(msg)
        except Exception:
            pass

    def _validate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Replace any value that would break the downloader with its default.
        A hand-edited config with "audio_format": "mp4" should not propagate
        into a subprocess argument list.
        """
        clean = dict(config)

        fmt = clean.get("audio_format")
        if not isinstance(fmt, str) or fmt.lower() not in self.VALID_FORMATS:
            if fmt is not None:
                self._log_error(f"Invalid audio_format {fmt!r}; using default")
            clean["audio_format"] = self.defaults.get("audio_format", "mp3")
        else:
            clean["audio_format"] = fmt.lower()

        quality = clean.get("audio_quality")
        if not isinstance(quality, str) or quality.lower() not in self.VALID_QUALITIES:
            if quality is not None:
                self._log_error(f"Invalid audio_quality {quality!r}; using default")
            clean["audio_quality"] = self.defaults.get("audio_quality", "320k")
        else:
            clean["audio_quality"] = quality.lower()

        for key, (low, high) in self._INT_BOUNDS.items():
            if key not in clean:
                continue
            fallback = self.defaults.get(key, low)
            try:
                value = int(clean[key])
            except (TypeError, ValueError):
                self._log_error(f"Invalid {key}={clean[key]!r}; using {fallback}")
                clean[key] = fallback
                continue
            if not (low <= value <= high):
                self._log_error(f"{key}={value} out of range [{low}, {high}]; using {fallback}")
                clean[key] = fallback
            else:
                clean[key] = value

        # sleep_min must not exceed sleep_max, or yt-dlp errors out
        smin, smax = clean.get("yt_dlp_sleep_min"), clean.get("yt_dlp_sleep_max")
        if isinstance(smin, int) and isinstance(smax, int) and smin > smax:
            self._log_error(f"yt_dlp_sleep_min ({smin}) > max ({smax}); swapping")
            clean["yt_dlp_sleep_min"], clean["yt_dlp_sleep_max"] = smax, smin

        clean["use_cookies"] = bool(clean.get("use_cookies", False))

        out_dir = clean.get("output_directory")
        if not out_dir or not isinstance(out_dir, str):
            clean["output_directory"] = self.defaults.get("output_directory", str(Path.home()))

        return clean

    # ==================== Public API ====================
    def load(self) -> Dict[str, Any]:
        """
        Load config from disk, merged over the defaults so keys added later
        don't break older config files. Creates the file with defaults if it
        doesn't exist. Falls back to defaults on any read/parse error.
        """
        with self._lock:
            try:
                if os.path.exists(self.config_file):
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        user_config = json.load(f)
                    if not isinstance(user_config, dict):
                        raise ValueError("config root is not a JSON object")
                    return self._validate({**self.defaults, **user_config})
                self._save_unlocked(self.defaults)
                return dict(self.defaults)
            except Exception as e:
                self._log_error(f"Error loading configuration: {e}")
                return dict(self.defaults)

    def save(self, config: Dict[str, Any]):
        """Persist a config dict to disk as JSON, creating parent dirs as needed."""
        with self._lock:
            self._save_unlocked(config)

    def _save_unlocked(self, config: Dict[str, Any]):
        try:
            directory = os.path.dirname(self.config_file) or "."
            os.makedirs(directory, exist_ok=True)

            payload = {**config}
            for key, value in payload.items():
                if isinstance(value, Path):
                    payload[key] = str(value)

            # Write to a temp file in the same directory, then atomically replace.
            # A crash or full disk mid-write would otherwise leave a truncated
            # config that fails to parse on next launch.
            fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.config_file)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            self._log_error(f"Error saving configuration: {e}")

    def update(self, **changes) -> Dict[str, Any]:
        """Load, apply changes, validate, save, and return the merged config."""
        config = self.load()
        config.update(changes)
        config = self._validate(config)
        self.save(config)
        return config

    def reset(self) -> Dict[str, Any]:
        """Overwrite the config file with defaults and return them."""
        defaults = dict(self.defaults)
        self.save(defaults)
        return defaults