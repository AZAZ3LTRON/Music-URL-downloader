#!/usr/bin/env python3
"""
spotify_info.py — Retrieve Spotify metadata for tracks, albums, playlists, and artists.

Setup:
    pip install spotipy

    Get credentials at: https://developer.spotify.com/dashboard
"""

import os
import re
import sys

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
except ImportError:
    sys.exit("spotipy not found. Run: pip install spotipy")


# ── Configure here ────────────────────────────────────────────────────────────

CLIENT_ID     = "your_client_id"
CLIENT_SECRET = "your_client_secret"

# Set the type: "track", "album", "playlist", or "artist"
# Set the value to a Spotify ID or full Spotify URL/URI
TYPE  = "track"
VALUE = "4uLU6hMCjMI75M1A2tKUQC"

# ─────────────────────────────────────────────────────────────────────────────


def ms_to_duration(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


def print_metadata(label: str, data: dict) -> None:
    print(f"\n[ {label} ]")
    for key, value in data.items():
        print(f"  {key:<20} {value}")


def get_track(sp, track_id):
    t = sp.track(track_id)
    print_metadata("Track", {
        "Name":         t["name"],
        "Artist(s)":    ", ".join(a["name"] for a in t["artists"]),
        "Album":        t["album"]["name"],
        "Release Date": t["album"]["release_date"],
        "Duration":     ms_to_duration(t["duration_ms"]),
        "Track #":      f"{t['track_number']} / {t['album']['total_tracks']}",
        "Explicit":     "Yes" if t["explicit"] else "No",
        "Popularity":   f"{t['popularity']} / 100",
        "Spotify URL":  t["external_urls"].get("spotify", "N/A"),
    })


def get_album(sp, album_id):
    a = sp.album(album_id)
    print_metadata("Album", {
        "Name":         a["name"],
        "Artist(s)":    ", ".join(x["name"] for x in a["artists"]),
        "Type":         a["album_type"].title(),
        "Release Date": a["release_date"],
        "Total Tracks": a["total_tracks"],
        "Label":        a.get("label", "N/A"),
        "Genres":       ", ".join(a.get("genres", [])) or "N/A",
        "Popularity":   f"{a['popularity']} / 100",
        "Spotify URL":  a["external_urls"].get("spotify", "N/A"),
    })


def get_playlist(sp, playlist_id):
    p = sp.playlist(playlist_id)
    description = re.sub(r"<[^>]+>", "", p.get("description", "") or "")
    print_metadata("Playlist", {
        "Name":         p["name"],
        "Owner":        p["owner"].get("display_name") or p["owner"]["id"],
        "Total Tracks": p["tracks"]["total"],
        "Followers":    p.get("followers", {}).get("total", "N/A"),
        "Public":       "Yes" if p.get("public") else "No",
        "Description":  description or "N/A",
        "Spotify URL":  p["external_urls"].get("spotify", "N/A"),
    })


def get_artist(sp, artist_id):
    a = sp.artist(artist_id)
    print_metadata("Artist", {
        "Name":        a["name"],
        "Genres":      ", ".join(a.get("genres", [])) or "N/A",
        "Followers":   f"{a['followers']['total']:,}",
        "Popularity":  f"{a['popularity']} / 100",
        "Spotify URL": a["external_urls"].get("spotify", "N/A"),
    })


def parse_url(url: str) -> tuple[str, str]:
    for pattern in [
        r"open\.spotify\.com/(track|album|playlist|artist)/([A-Za-z0-9]+)",
        r"spotify:(track|album|playlist|artist):([A-Za-z0-9]+)",
    ]:
        m = re.search(pattern, url)
        if m:
            return m.group(1), m.group(2)
    raise ValueError(f"Could not parse Spotify URL: {url}")


handlers = {
    "track":    get_track,
    "album":    get_album,
    "playlist": get_playlist,
    "artist":   get_artist,
}

if __name__ == "__main__":
    if not CLIENT_ID or CLIENT_ID == "your_client_id":
        sys.exit("Set CLIENT_ID and CLIENT_SECRET at the top of the file.")

    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET
    ))

    try:
        # Auto-detect if VALUE is a URL/URI
        if VALUE.startswith("http") or VALUE.startswith("spotify:"):
            kind, spotify_id = parse_url(VALUE)
        else:
            kind, spotify_id = TYPE, VALUE

        if kind not in handlers:
            sys.exit(f"Unsupported type: '{kind}'. Use track, album, playlist, or artist.")

        handlers[kind](sp, spotify_id)

    except spotipy.SpotifyException as e:
        sys.exit(f"Spotify API error: {e}")
    except ValueError as e:
        sys.exit(str(e))