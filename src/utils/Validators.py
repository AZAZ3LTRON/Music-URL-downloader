import os
import re
import spotipy
from dotenv import load_dotenv
load_dotenv()
from spotipy.oauth2 import SpotifyClientCredentials
from spotdl.utils.spotify import SpotifyClient
from spotdl.types.song import Song
from spotdl.types.album import Album
from spotdl.types.playlist import Playlist
from spotdl.types.artist import Artist
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import urllib.parse


class Helpers:
    # ========================================= Youtube Functions =========================================
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

    # ========================================= Spotify Functions =========================================
    @staticmethod
    def validate_spotify_url(url: str):
        """ Validate if the URL input is a proper URL and return type"""
        spotify_patterns = [
            (r'^https://open\.spotify\.com/track/[A-Za-z0-9]+', 'track'),
            (r'^https://open\.spotify\.com/album/[A-Za-z0-9]+', 'album'),
            (r'^https://open\.spotify\.com/playlist/[A-Za-z0-9]+', 'playlist'),
            (r'^https://open\.spotify\.com/artist/[A-Za-z0-9]+', 'artist'),
            (r'^spotify:track:[A-Za-z0-9]+$', 'track'),
            (r'^spotify:album:[A-Za-z0-9]+$', 'album'),
            (r'^spotify:playlist:[A-Za-z0-9]+$', 'playlist'),
            (r'^spotify:artist:[A-Za-z0-9]+$', 'artist')
        ]

        for pattern, typ in spotify_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True, typ
        return False, None
    
    @staticmethod
    def get_spotify_playlist_items(url: str) -> List[Dict]:
        """Fetch track list from a Spotify playlist using spotdl internals."""
        try:
            SpotifyClient.init(
                client_id=os.getenv("SPOTIPY_CLIENT_ID"),
                client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
            )
        except Exception:
            pass

        playlist = Playlist.from_url(url)

        items = []
        for track in playlist.tracks:
            items.append({
                'title':  getattr(track, 'name', 'Unknown'),
                'artist': getattr(track, 'artist', 'Unknown Artist'),
                'url':    getattr(track, 'url', None),
                'track':  track,  
            })

        return items
    
    @staticmethod
    def validate_resource_spotify(url: str, timeout: int = 30) -> Tuple[bool, str, Optional[Dict]]:
        """Validate and fetch Spotify metadata via spotdl internals (no Premium required)."""

        TYPE_PATTERNS = {
            'track':    r'spotify\.com/track/([A-Za-z0-9]+)',
            'album':    r'spotify\.com/album/([A-Za-z0-9]+)',
            'playlist': r'spotify\.com/playlist/([A-Za-z0-9]+)',
            'artist':   r'spotify\.com/artist/([A-Za-z0-9]+)',
        }

        resource_type = None
        for rtype, pattern in TYPE_PATTERNS.items():
            if re.search(pattern, url):
                resource_type = rtype
                break

        if not resource_type:
            return False, "Invalid or unrecognised Spotify URL", {}

        try:
            # Initialise spotdl's Spotify client if not already done.
            # Uses the same credentials spotdl uses internally for downloads.
            try:
                SpotifyClient.init(
                    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
                    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
                )
            except Exception:
                pass  # Already initialised — SpotifyClient is a singleton

            if resource_type == 'track':
                track = Song.from_url(url)
                metadata = {
                    'type':   'track',
                    'title':  getattr(track, 'name', 'Unknown Track'),
                    'artist': getattr(track, 'artist', None) or getattr(track, 'artists', ['Unknown Artist'])[0],
                    'album':  getattr(track, 'album_name', None) or getattr(track, 'album', 'Unknown Album'),
                }
                message = f"Track: {metadata['artist']} – {metadata['title']}"

            elif resource_type == 'album':
                album = Album.from_url(url)
                metadata = {
                    'type':           'album',
                    'title':          album.name,
                    'artist':         album.artist,
                    'playlist_count': len(album.tracks),
                }
                message = f"Album: {metadata['artist']} – {metadata['title']} ({metadata['playlist_count']} tracks)"

            elif resource_type == 'playlist':
                playlist = Playlist.from_url(url)
                metadata = {
                    'type':           'playlist',
                    'title':          playlist.name,
                    'playlist_count': len(playlist.tracks),
                    'tracks':         playlist.tracks,
                }
                message = f"Playlist: {metadata['title']} ({metadata['playlist_count']} tracks)"
 
            elif resource_type == 'artist':
                artist = Artist.from_url(url)
                metadata = {
                    'type':   'artist',
                    'title':  artist.name,
                    'artist': artist.name,
                }
                message = f"Artist: {metadata['artist']}"

            return True, message, metadata

        except Exception as e:
            return False, f"spotdl metadata error: {e}", {}
        
    # ========================================= Other functions =========================================
    @staticmethod
    def cleanup_directory(output_directory: Path, log_manager) -> None:
        """Remove empty directories under output_directory."""
        removed = 0
        for dir_path in sorted(output_directory.rglob('*'), reverse=True):
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                dir_path.rmdir()
                removed += 1
        if removed:
            log_manager.log_success(f"Removed {removed} empty director{'y' if removed==1 else 'ies'}")

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Remove invalid characters for file/folder names."""
        name = re.sub(r'[<>:"/\\|?*]', '_', name).strip('. ')
        return name if name else "_"

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