import os
import re
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import urllib.parse

class Helpers:
    @staticmethod
    def validate_youtube_url(url: str) -> bool:
        patterns = [
            r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$',
            r'^(https?://)?music\.youtube\.com/.+$',
            r'^(https?://)?youtube\.com/watch\?v=[\w-]+(&.*)?$',
            r'^(https?://)?youtube\.com/playlist\?list=[\w-]+(&.*)?$',
            r'^(https?://)?youtu\.be/[\w-]+$'
        ]
        for pattern in patterns:
            if re.match(pattern, url, re.IGNORECASE):
                try:
                    parsed = urllib.parse.urlparse(url)
                    if parsed.scheme in ('http', 'https', '') or parsed.netloc:
                        return True
                except:
                    continue
        return False

    @staticmethod
    def validate_spotify_url(url: str) -> Tuple[bool, Optional[str]]:
        patterns = [
            (r'^https://open\.spotify\.com/track/[A-Za-z0-9]+', 'track'),
            (r'^https://open\.spotify\.com/album/[A-Za-z0-9]+', 'album'),
            (r'^https://open\.spotify\.com/playlist/[A-Za-z0-9]+', 'playlist'),
            (r'^https://open\.spotify\.com/artist/[A-Za-z0-9]+', 'artist'),
            (r'^spotify:track:[A-Za-z0-9]+$', 'track'),
            (r'^spotify:album:[A-Za-z0-9]+$', 'album'),
            (r'^spotify:playlist:[A-Za-z0-9]+$', 'playlist'),
            (r'^spotify:artist:[A-Za-z0-9]+$', 'artist')
        ]
        for pattern, typ in patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True, typ
        return False, None

    @staticmethod
    def extract_spotify_id(url: str) -> str:
        patterns = [
            r'spotify\.com/(track|album|playlist)/([A-Za-z0-9]+)',
            r'spotify:(track|album|playlist):([A-Za-z0-9]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(2)
        return None

    @staticmethod
    def extract_youtube_id(url: str) -> str:
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)',
            r'youtube\.com/playlist\?list=([\w-]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def extract_youtube_playlist_id(url: str) -> Optional[str]:
        patterns = [
            r'[?&]list=([^&]+)',
            r'/playlist\?list=([^&]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def get_youtube_playlist_items(url: str, log_manager) -> List[Dict]:
        """Fetch all video entries from a playlist"""
        command = ["yt-dlp", "--flat-playlist", "--dump-json", "--no-warnings", url]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
            if result.returncode != 0:
                log_manager.log_error(f"Failed to fetch playlist items: {result.stderr}")
                return []
            items = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        items.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return items
        except Exception as e:
            log_manager.log_error(f"Error fetching playlist items: {e}")
            return []

    @staticmethod
    def cleanup_directory(output_directory: Path, log_manager) -> None:
        """Remove empty directories under output_directory."""
        removed_count = 0
        for root, dirs, files in os.walk(output_directory, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    if not os.listdir(dir_path):
                        os.rmdir(dir_path)
                        removed_count += 1
                except OSError:
                    pass
        if removed_count > 0:
            log_manager.log_success("Cleaned up empty directories")

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Remove invalid characters for file/folder names."""
        return re.sub(r'[<>:"/\\|?*]', '_', name)

    @staticmethod
    def validate_resource_youtube(url: str, timeout=30) -> Tuple[bool, str, Optional[Dict]]:
        """Validate YouTube URL and return metadata."""
        command = ["yt-dlp", "--skip-download", "--flat-playlist", "--dump-json", "--no-warnings", url]
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, timeout=timeout, check=False)
            if result.returncode == 0:
                try:
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            metadata = json.loads(line)
                            if metadata.get('availability') == 'unavailable':
                                return False, "Video unavailable", metadata
                            return True, f"Available - {metadata.get('title', 'Unknown')}", metadata
                    return True, "Resource available", None
                except json.JSONDecodeError:
                    return True, "Resource available", None
            else:
                err = result.stderr.lower()
                if "unavailable" in err:
                    return False, "Resource unavailable", None
                elif "private" in err:
                    return False, "Restricted access", None
                elif "age restriction" in err:
                    return False, "Age restricted video", None
                elif "not found" in err:
                    return False, "Resource not found", None
                else:
                    return False, f"Validation failed: {err[:100]}", None
        except subprocess.TimeoutExpired:
            return False, "Validation timeout", None
        except Exception as e:
            return False, f"Validation error: {str(e)[:100]}", None

    @staticmethod
    def validate_resource_spotify(url: str, timeout=30) -> Tuple[bool, str, Optional[dict]]:
        """Validate Spotify URL using spotdl."""
        cmd = ["spotdl", url, "--skip-download", "--print-json", "--no-warnings"]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, timeout=timeout, check=False)
            if result.returncode == 0 and result.stdout.strip():
                try:
                    metadata = json.loads(result.stdout.strip())
                    if not metadata.get("name") and not metadata.get("title"):
                        return False, "Missing title metadata", metadata
                    typ = metadata.get("type", "")
                    if typ in ("playlist", "album"):
                        tracks = metadata.get("tracks", [])
                        available = sum(1 for t in tracks if t.get("available", True))
                        total = len(tracks)
                        if available == 0:
                            return False, f"No available tracks in this {typ}", metadata
                        return True, f"{typ} available ({available}/{total} tracks)", metadata
                    else:  # track
                        if metadata.get("duration", 0) <= 0:
                            return False, "Invalid duration", metadata
                        return True, "Track available", metadata
                except json.JSONDecodeError:
                    return False, "Invalid JSON response", None
            else:
                err = result.stderr.lower()
                if "not found" in err:
                    return False, "Resource not found on Spotify", None
                elif "private" in err or "access" in err:
                    return False, "Private resource – requires authentication", None
                elif "unavailable" in err:
                    return False, "Resource unavailable in your region", None
                elif "quota" in err or "rate limit" in err:
                    return False, "Rate limit exceeded, try later", None
                else:
                    return False, f"{err[:100]}", None
        except subprocess.TimeoutExpired:
            return False, "Validation timeout", None
        except FileNotFoundError:
            return False, "spotdl not found – please install it first", None
        except Exception as e:
            return False, f"Validation error: {str(e)[:100]}", None

    @staticmethod
    def parse_size(size_str: str) -> Optional[int]:
        if not size_str:
            return None
        size_str = size_str.strip().upper()
        units = {
            'B': 1, 'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4,
            'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4,
            'KIB': 1024, 'MIB': 1024**2, 'GIB': 1024**3, 'TIB': 1024**4
        }
        match = re.match(r'([\d\.]+)\s*(\w*)', size_str)
        if not match:
            return None
        value, unit = match.groups()
        try:
            value = float(value)
            if not unit:
                return int(value)
            if unit in units:
                return int(value * units[unit])
        except ValueError:
            return None
        return None