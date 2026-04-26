#!/usr/bin/env python3
"""
Tidal Music Downloader using the 'tiddl' Python library.
Requires: pip install tiddl

Usage examples:
    python tidal_downloader.py "https://tidal.com/browse/track/123456789"
    python tidal_downloader.py "https://tidal.com/browse/album/987654321" -q MASTER -o "./MyMusic"
    python tidal_downloader.py "https://tidal.com/browse/playlist/abc123-456" --type playlist
"""

import os
import sys
import re
import argparse
import logging
from pathlib import Path

try:
    from tiddl import TidalAPI, Downloader
    from tiddl.exceptions import AuthenticationError, TrackNotFoundError
except ImportError:
    print("Error: 'tiddl' library not found. Install it with: pip install tiddl")
    sys.exit(1)


def setup_logging(verbose: bool) -> None:
    """Configure logging level and format."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=level,
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def login_tidal(quality: str, output_dir: str) -> TidalAPI:
    """
    Authenticate with Tidal using environment variables or interactive login.
    Returns an authenticated TidalAPI instance.
    """
    api = TidalAPI()
    try:
        # Prefer credentials from environment variables (safer than hardcoding)
        username = os.getenv("TIDAL_USERNAME")
        password = os.getenv("TIDAL_PASSWORD")
        if username and password:
            logging.info("Logging in with provided credentials...")
            api.login(username, password)
        else:
            # Fallback: interactive login (will prompt for username/password)
            logging.info("No credentials in environment. Starting interactive login...")
            api.login()  # tiddl will ask for username/password

        logging.info("Login successful")
        api.set_quality(quality)      # e.g., 'LOSSLESS', 'HIGH', 'MASTER'
        api.set_output_dir(output_dir)
        return api
    except AuthenticationError as e:
        logging.error(f"Authentication failed: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error during login: {e}")
        sys.exit(1)


def download_track(api: TidalAPI, track_id: str, output_dir: str) -> None:
    """Download a single track by its ID."""
    try:
        track = api.get_track(track_id)
        logging.info(f"Downloading: {track.title} - {track.artist}")
        downloader = Downloader(api)
        downloader.download_track(track, output_dir)
        logging.info("Track download completed.")
    except TrackNotFoundError:
        logging.error(f"Track with ID {track_id} not found.")
    except Exception as e:
        logging.error(f"Failed to download track {track_id}: {e}")


def download_album(api: TidalAPI, album_id: str, output_dir: str) -> None:
    """Download all tracks from an album."""
    try:
        album = api.get_album(album_id)
        logging.info(f"Downloading album: {album.title} by {album.artist}")
        tracks = album.tracks
        for idx, track in enumerate(tracks, start=1):
            logging.info(f"Track {idx}/{len(tracks)}: {track.title}")
            downloader = Downloader(api)
            downloader.download_track(track, output_dir)
        logging.info("Album download completed.")
    except Exception as e:
        logging.error(f"Failed to download album {album_id}: {e}")


def download_playlist(api: TidalAPI, playlist_id: str, output_dir: str) -> None:
    """Download all tracks from a playlist."""
    try:
        playlist = api.get_playlist(playlist_id)
        logging.info(f"Downloading playlist: {playlist.name} ({playlist.track_count} tracks)")
        for idx, track in enumerate(playlist.tracks, start=1):
            logging.info(f"Track {idx}/{playlist.track_count}: {track.title}")
            downloader = Downloader(api)
            downloader.download_track(track, output_dir)
        logging.info("Playlist download completed.")
    except Exception as e:
        logging.error(f"Failed to download playlist {playlist_id}: {e}")


def extract_id_from_url(url: str):
    """
    Parse a Tidal URL and return (content_type, id).
    Recognises tracks, albums, and playlists.
    If no pattern matches, assume raw numeric ID and default to 'track'.
    """
    patterns = {
        "track": r"track[/](\d+)",
        "album": r"album[/](\d+)",
        "playlist": r"playlist[/]([a-fA-F0-9-]+)"   # playlist IDs often contain hyphens
    }
    for typ, pattern in patterns.items():
        match = re.search(pattern, url)
        if match:
            return typ, match.group(1)

    # If input is just a number, treat as track ID
    if url.strip().isdigit():
        return "track", url.strip()

    return None, url


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Tidal Music Downloader using the tiddl library."
    )
    parser.add_argument("url", nargs="?", help="Tidal URL or ID (track, album, playlist)")
    parser.add_argument(
        "-q", "--quality",
        default="LOSSLESS",
        choices=["LOW", "HIGH", "LOSSLESS", "MASTER"],
        help="Audio quality (default: LOSSLESS)"
    )
    parser.add_argument(
        "-o", "--output",
        default="./Downloads/Tidal",
        help="Output directory (default: ./Downloads/Tidal)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "-t", "--type",
        choices=["track", "album", "playlist"],
        help="Manually specify content type (auto‑detected from URL if omitted)"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    setup_logging(args.verbose)

    if not args.url:
        logging.error("No URL or ID provided. See --help for usage.")
        sys.exit(1)

    # Determine content type and ID
    content_type, content_id = extract_id_from_url(args.url)
    if args.type:
        content_type = args.type   # manual override

    if not content_type:
        logging.error("Could not detect content type from URL. Please specify --type (track/album/playlist)")
        sys.exit(1)

    # Create output directory
    Path(args.output).mkdir(parents=True, exist_ok=True)

    # Authenticate and set quality / output
    api = login_tidal(args.quality, args.output)

    # Dispatch to the appropriate downloader
    if content_type == "track":
        download_track(api, content_id, args.output)
    elif content_type == "album":
        download_album(api, content_id, args.output)
    elif content_type == "playlist":
        download_playlist(api, content_id, args.output)
    else:
        logging.error(f"Unsupported content type: {content_type}")
        sys.exit(1)


if __name__ == "__main__":
    main()