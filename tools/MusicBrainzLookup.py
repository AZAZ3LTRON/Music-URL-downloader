import time
import threading
import difflib
from typing import Optional, Dict
import requests


class MusicBrainzLookup:
    """Thin client for MusicBrainz's recording search, used to verify/enrich
    track metadata after a download completes."""

    BASE_URL = "https://musicbrainz.org/ws/2"
    USER_AGENT = "SpotifyMusicDownloader/1.0 (contact: your-email-or-repo-url)"
    MIN_INTERVAL = 1.0  # MusicBrainz anonymous rate limit: 1 req/sec

    _last_request_time = 0.0
    _lock = threading.Lock()

    def __init__(self, log_manager=None, min_confidence: float = 0.55):
        self.log_manager = log_manager
        self.min_confidence = min_confidence

    def _throttle(self):
        with self._lock:
            now = time.monotonic()
            wait = self.MIN_INTERVAL - (now - MusicBrainzLookup._last_request_time)
            if wait > 0:
                time.sleep(wait)
            MusicBrainzLookup._last_request_time = time.monotonic()

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        return difflib.SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()

    def lookup_recording(self, artist: str, title: str, album: str = None,
                          timeout: int = 10) -> Optional[Dict]:
        """
        Search MusicBrainz for a recording matching artist/title (+ optional album).
        Returns the best candidate with a confidence score, or None if nothing
        clears the confidence threshold.
        """
        if not artist or not title:
            return None

        query_parts = [f'recording:"{title}"', f'artist:"{artist}"']
        if album:
            query_parts.append(f'release:"{album}"')
        query = " AND ".join(query_parts)

        params = {"query": query, "fmt": "json", "limit": 5}
        headers = {"User-Agent": self.USER_AGENT}

        self._throttle()
        try:
            resp = requests.get(f"{self.BASE_URL}/recording", params=params,
                                 headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            if self.log_manager:
                self.log_manager.log_error(
                    f"MusicBrainz lookup failed for '{artist} - {title}': {e}", console=False)
            return None

        recordings = data.get("recordings", [])
        if not recordings:
            return None

        best, best_score = None, -1.0
        for rec in recordings:
            rec_title = rec.get("title", "")
            rec_artists = ", ".join(
                c.get("name", "") for c in rec.get("artist-credit", []) if isinstance(c, dict)
            )
            title_sim = self._similarity(title, rec_title)
            artist_sim = self._similarity(artist, rec_artists)
            mb_score = rec.get("score", 0) / 100.0
            combined = (title_sim * 0.4) + (artist_sim * 0.4) + (mb_score * 0.2)
            if combined > best_score:
                best_score, best = combined, rec

        if best is None or best_score < self.min_confidence:
            return None

        release_info = None
        releases = best.get("releases") or []
        if releases:
            release_info = {
                "title": releases[0].get("title"),
                "id": releases[0].get("id"),
                "date": releases[0].get("date"),
            }

        return {
            "mbid": best.get("id"),
            "title": best.get("title"),
            "artist": ", ".join(
                c.get("name", "") for c in best.get("artist-credit", []) if isinstance(c, dict)
            ),
            "release": release_info,
            "confidence": round(best_score, 3),
        }