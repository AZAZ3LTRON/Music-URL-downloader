"""Small filesystem helpers shared by the downloaders.

`safe_name` is pure and stateless, so it stays a static method. The archive
readers touch the disk and therefore need somewhere to report a failure, which
is what the `on_error` sink is for - the same pattern DownloaderConfigManager
already uses, so nothing here has to import the logger directly.
"""

import re
import threading
from pathlib import Path
from typing import Callable, Optional, Set


class DownloadHelpers:
    """Filesystem-safe naming and yt-dlp download-archive bookkeeping."""

    def __init__(self, on_error: Optional[Callable[[str], None]] = None):
        self._on_error = on_error or (lambda message: None)

    # ---------------- Naming ----------------
    @staticmethod
    def safe_name(name, fallback: str = "Playlist") -> str:
        """Turn an arbitrary title into a filesystem-safe folder name."""
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name or "")).strip(" .")
        return cleaned[:120] or fallback

    # ---------------- Archives ----------------
    def load_archive(self, archive_path: Path) -> Set[str]:
        """Return the set of video IDs already recorded in a yt-dlp archive file."""
        ids: Set[str] = set()
        try:
            if Path(archive_path).exists():
                with open(archive_path, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 2:
                            ids.add(parts[-1])
        except OSError as e:
            self._on_error(f"Could not read archive {archive_path}: {e}")
        return ids

    def append_archive(self, archive_path: Path, video_id: str, lock: threading.Lock):
        """Append a finished video ID to the archive, serialised across threads."""
        with lock:
            try:
                with open(archive_path, "a", encoding="utf-8") as f:
                    f.write(f"youtube {video_id}\n")
            except OSError as e:
                self._on_error(f"Could not update archive {archive_path}: {e}")