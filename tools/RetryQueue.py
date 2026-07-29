"""A JSON-backed record of links that failed to download.

The queue owns its own lock rather than borrowing one from the caller, so a
concurrent caller can't forget to hold it. Reads never raise: a queue file that
has been hand-edited into invalid JSON reports the problem and comes back empty
rather than taking a download run down with it.
"""

import datetime
import json
import os
import threading
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional


class RetryQueue:
    """Failed links, keyed by URL, persisted to history/retry_queue.json."""

    def __init__(self, path="history/retry_queue.json",
                 on_error: Optional[Callable[[str], None]] = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._on_error = on_error or (lambda message: None)
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self.read())

    @property
    def count(self) -> int:
        """How many links are currently waiting."""
        return len(self.read())

    # ---------------- Storage ----------------
    def read(self) -> Dict[str, dict]:
        """Load the queue as {url: entry}. Never raises."""
        try:
            if not self.path.exists():
                return {}
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
            self._on_error(f"Could not read retry queue: {e}")
            return {}

        items = data.get("items") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return {}
        return {e["url"]: e for e in items if isinstance(e, dict) and e.get("url")}

    def _write(self, queue: Dict[str, dict]) -> None:
        payload = {
            "updated": datetime.datetime.now().isoformat(timespec="seconds"),
            "count": len(queue),
            "items": sorted(queue.values(), key=lambda e: e.get("last_failed", "")),
        }
        tmp_path = self.path.with_name(self.path.name + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.path)
        except OSError as e:
            self._on_error(f"Could not write retry queue: {e}")

    # ---------------- Mutations ----------------
    def add_failure(self, url: str, title: str, error: str, source: str) -> None:
        """Add or update one failed link. Attempts accumulate across runs."""
        now = datetime.datetime.now().isoformat(timespec="seconds")
        with self._lock:
            queue = self.read()
            entry = queue.get(url, {
                "url": url,
                "title": title,
                "source": source,
                "attempts": 0,
                "first_failed": now,
            })
            entry["title"] = title or entry.get("title", "")
            entry["source"] = source
            entry["attempts"] = int(entry.get("attempts", 0)) + 1
            entry["last_failed"] = now
            entry["last_error"] = (error or "")[:300]
            queue[url] = entry
            self._write(queue)

    def clear(self, urls: Iterable[str]) -> None:
        """Drop links that have since succeeded."""
        urls = set(urls)
        if not urls:
            return
        with self._lock:
            queue = self.read()
            remaining = {u: e for u, e in queue.items() if u not in urls}
            if len(remaining) != len(queue):
                self._write(remaining)