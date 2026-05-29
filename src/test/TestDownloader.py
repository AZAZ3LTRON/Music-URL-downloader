#!/usr/bin/env python3
"""
spotify_info.py — Retrieve information about Spotify tracks, albums, playlists, or URLs.

Setup:
    pip install spotipy

    Set environment variables (or create a .env file):
        SPOTIPY_CLIENT_ID=your_client_id
        SPOTIPY_CLIENT_SECRET=your_client_secret

    Get credentials at: https://developer.spotify.com/dashboard
"""

import os
import sys
import re
import argparse
import textwrap
from datetime import datetime

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
except ImportError:
    sys.exit("spotipy is not installed. Run: pip install spotipy")


# ─── Helpers ────────────────────────────────────────────────────────────────

def bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"

def green(text: str) -> str:
    return f"\033[92m{text}\033[0m"

def cyan(text: str) -> str:
    return f"\033[96m{text}\033[0m"

def yellow(text: str) -> str:
    return f"\033[93m{text}\033[0m"

def dim(text: str) -> str:
    return f"\033[2m{text}\033[0m"

def separator(char: str = "─", width: int = 60) -> str:
    return dim(char * width)

def ms_to_duration(ms: int) -> str:
    """Convert milliseconds to m:ss format."""
    seconds = ms // 1000
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}"

def parse_spotify_url(url: str) -> tuple[str, str]:
    """
    Parse a Spotify URL or URI and return (type, id).
    Supports:
      - https://open.spotify.com/track/...
      - spotify:track:...
    """
    patterns = [
        r"open\.spotify\.com/(track|album|playlist)/([A-Za-z0-9]+)",
        r"spotify:(track|album|playlist):([A-Za-z0-9]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2)
    raise ValueError(f"Cannot parse Spotify URL/URI: {url}")


# ─── Display functions ───────────────────────────────────────────────────────

def display_track(sp: spotipy.Spotify, track_id: str) -> None:
    track = sp.track(track_id)
    features = sp.audio_features([track_id])[0]

    artists = ", ".join(a["name"] for a in track["artists"])
    album = track["album"]["name"]
    release_date = track["album"]["release_date"]
    duration = ms_to_duration(track["duration_ms"])
    popularity = track["popularity"]
    explicit = "Yes" if track["explicit"] else "No"
    preview = track.get("preview_url") or "Not available"
    external_url = track["external_urls"].get("spotify", "N/A")

    print(f"\n{separator()}")
    print(f"  {green('🎵 TRACK')}  {bold(track['name'])}")
    print(separator())
    print(f"  {'Artist(s)':<16} {artists}")
    print(f"  {'Album':<16} {album}")
    print(f"  {'Released':<16} {release_date}")
    print(f"  {'Duration':<16} {duration}")
    print(f"  {'Popularity':<16} {popularity}/100")
    print(f"  {'Explicit':<16} {explicit}")
    print(f"  {'Track #':<16} {track['track_number']} (disc {track['disc_number']})")
    print(f"  {'Spotify URL':<16} {cyan(external_url)}")
    print(f"  {'Preview':<16} {cyan(preview)}")

    if features:
        print(f"\n  {bold('Audio Features')}")
        print(separator("·"))
        af_keys = [
            ("Tempo",        f"{features['tempo']:.1f} BPM"),
            ("Key",          _key_name(features["key"], features["mode"])),
            ("Time Sig.",    f"{features['time_signature']}/4"),
            ("Danceability", f"{features['danceability']:.2f}"),
            ("Energy",       f"{features['energy']:.2f}"),
            ("Valence",      f"{features['valence']:.2f}  (0=sad, 1=happy)"),
            ("Acousticness", f"{features['acousticness']:.2f}"),
            ("Instrumentalness", f"{features['instrumentalness']:.2f}"),
            ("Liveness",     f"{features['liveness']:.2f}"),
            ("Loudness",     f"{features['loudness']:.1f} dB"),
            ("Speechiness",  f"{features['speechiness']:.2f}"),
        ]
        for label, value in af_keys:
            print(f"  {label:<18} {value}")

    print(separator())


def display_album(sp: spotipy.Spotify, album_id: str) -> None:
    album = sp.album(album_id)

    artists = ", ".join(a["name"] for a in album["artists"])
    total_tracks = album["total_tracks"]
    release_date = album["release_date"]
    label = album.get("label", "N/A")
    genres = ", ".join(album.get("genres", [])) or "N/A"
    popularity = album["popularity"]
    external_url = album["external_urls"].get("spotify", "N/A")
    copyrights = "; ".join(c["text"] for c in album.get("copyrights", [])) or "N/A"

    print(f"\n{separator()}")
    print(f"  {green('💿 ALBUM')}  {bold(album['name'])}")
    print(separator())
    print(f"  {'Artist(s)':<16} {artists}")
    print(f"  {'Type':<16} {album['album_type'].title()}")
    print(f"  {'Released':<16} {release_date}")
    print(f"  {'Tracks':<16} {total_tracks}")
    print(f"  {'Label':<16} {label}")
    print(f"  {'Genres':<16} {genres}")
    print(f"  {'Popularity':<16} {popularity}/100")
    print(f"  {'Spotify URL':<16} {cyan(external_url)}")
    print(f"  {'Copyright':<16} {copyrights}")

    # Tracklist
    print(f"\n  {bold('Tracklist')}")
    print(separator("·"))
    tracks = album["tracks"]["items"]
    for t in tracks:
        num = str(t["track_number"]).rjust(2)
        dur = ms_to_duration(t["duration_ms"])
        explicit = " [E]" if t["explicit"] else ""
        print(f"  {dim(num)}.  {t['name']}{yellow(explicit)}  {dim(dur)}")

    print(separator())


def display_playlist(sp: spotipy.Spotify, playlist_id: str) -> None:
    playlist = sp.playlist(playlist_id)

    owner = playlist["owner"]["display_name"] or playlist["owner"]["id"]
    total = playlist["tracks"]["total"]
    description = playlist.get("description", "") or "—"
    followers = playlist.get("followers", {}).get("total", "N/A")
    public = "Yes" if playlist.get("public") else "No"
    external_url = playlist["external_urls"].get("spotify", "N/A")

    # Clean HTML from description
    description = re.sub(r"<[^>]+>", "", description)

    print(f"\n{separator()}")
    print(f"  {green('📋 PLAYLIST')}  {bold(playlist['name'])}")
    print(separator())
    print(f"  {'Owner':<16} {owner}")
    print(f"  {'Tracks':<16} {total}")
    print(f"  {'Followers':<16} {followers:,}" if isinstance(followers, int) else f"  {'Followers':<16} {followers}")
    print(f"  {'Public':<16} {public}")
    print(f"  {'Spotify URL':<16} {cyan(external_url)}")
    if description and description != "—":
        wrapped = textwrap.fill(description, width=50, subsequent_indent="  " + " " * 18)
        print(f"  {'Description':<16} {wrapped}")

    # Tracks (up to 50 shown; playlist may have more)
    print(f"\n  {bold('Tracks')} {dim('(showing up to 50)')}")
    print(separator("·"))

    items = playlist["tracks"]["items"][:50]
    for idx, item in enumerate(items, start=1):
        t = item.get("track")
        if not t:
            continue
        num = str(idx).rjust(3)
        artists = ", ".join(a["name"] for a in t["artists"])
        dur = ms_to_duration(t["duration_ms"])
        explicit = yellow(" [E]") if t.get("explicit") else ""
        print(f"  {dim(num)}.  {t['name']}{explicit}")
        print(f"       {dim(artists)}  {dim(dur)}")

    if total > 50:
        print(f"\n  {dim(f'… and {total - 50} more tracks')}")

    print(separator())


# ─── Key / mode helper ───────────────────────────────────────────────────────

_KEY_NAMES = ["C", "C♯/D♭", "D", "D♯/E♭", "E", "F",
              "F♯/G♭", "G", "G♯/A♭", "A", "A♯/B♭", "B"]

def _key_name(key: int, mode: int) -> str:
    if key < 0:
        return "Unknown"
    name = _KEY_NAMES[key]
    mode_str = "Major" if mode == 1 else "Minor"
    return f"{name} {mode_str}"


# ─── Auth ────────────────────────────────────────────────────────────────────

def create_client() -> spotipy.Spotify:
    client_id = os.environ.get("SPOTIPY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET")

    if not client_id or not client_secret:
        sys.exit(
            "\n❌  Missing Spotify credentials.\n"
            "    Set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET environment variables.\n"
            "    Get them at: https://developer.spotify.com/dashboard\n"
        )

    auth_manager = SpotifyClientCredentials(
        client_id=client_id,
        client_secret=client_secret,
    )
    return spotipy.Spotify(auth_manager=auth_manager)


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Retrieve Spotify info for a track, album, or playlist.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        Examples:
          python spotify_info.py --track 4uLU6hMCjMI75M1A2tKUQC
          python spotify_info.py --album 1DFixLWuPkv3KT3TnV35m3
          python spotify_info.py --playlist 37i9dQZF1DXcBWIGoYBM5M
          python spotify_info.py --url https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC
          python spotify_info.py --url spotify:album:1DFixLWuPkv3KT3TnV35m3
        """),
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--track",    metavar="ID", help="Spotify track ID")
    group.add_argument("--album",    metavar="ID", help="Spotify album ID")
    group.add_argument("--playlist", metavar="ID", help="Spotify playlist ID")
    group.add_argument("--url",      metavar="URL", help="Any Spotify URL or URI")

    args = parser.parse_args()
    sp = create_client()

    try:
        if args.url:
            kind, spotify_id = parse_spotify_url(args.url)
        elif args.track:
            kind, spotify_id = "track", args.track
        elif args.album:
            kind, spotify_id = "album", args.album
        elif args.playlist:
            kind, spotify_id = "playlist", args.playlist

        dispatch = {
            "track":    display_track,
            "album":    display_album,
            "playlist": display_playlist,
        }

        if kind not in dispatch:
            sys.exit(f"❌  Unsupported Spotify type: '{kind}'")

        dispatch[kind](sp, spotify_id)

    except spotipy.SpotifyException as e:
        sys.exit(f"\n❌  Spotify API error: {e}\n")
    except ValueError as e:
        sys.exit(f"\n❌  {e}\n")


if __name__ == "__main__":
    main()