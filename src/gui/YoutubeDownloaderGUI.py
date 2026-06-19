"""
YTM Studio — a PySide6 GUI front-end for the YoutubeMusicDownloader backend.

Pages:
  • Home      — URL/fetch bar, metadata card (cover + details), track table, progress
  • History   — Downloads / Fetches tabs with type filter + text search
  • Settings  — bitrate, format, output dir, cookies, metadata, theme/accent/font
  • Debug     — live log console with copy / export / clear
  • About     — project + support info

The GUI talks to yt-dlp via subprocess, using the same flags the CLI backend
(`YoutubeMusicDownloader.run_download`) uses. Metadata is fetched with
`yt-dlp -J --flat-playlist`, so no account is required.

Integration with the existing backend
--------------------------------------
This file is standalone-runnable. If you want it to drive your existing
`YoutubeMusicDownloader` class instead of calling yt-dlp directly, the two
worker classes (`MetadataWorker`, `DownloadWorker`) are the only seams you need
to change — replace their `run()` bodies with calls into your backend and keep
emitting the same signals. (The backend's public methods are interactive — they
prompt via Enhanced_Menu — so the GUI shells out to yt-dlp directly and keeps
config/YoutubeMusicDownloader.json in sync so the CLI stays compatible.)

Run:  python ytm_studio.py
Requires:  pip install PySide6   (and yt-dlp + ffmpeg on PATH for real downloads)
"""

import os
import re
import sys
import json
import hashlib
import subprocess
import urllib.request
from pathlib import Path

from PySide6.QtCore import (Qt, QThread, Signal, QByteArray, QSize, QTimer,
                            QUrl)
from PySide6.QtGui import (QIcon, QPixmap, QPainter, QFontDatabase,
                           QDesktopServices)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QToolButton, QComboBox, QStackedWidget,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QPlainTextEdit, QFileDialog, QScrollArea, QButtonGroup, QAbstractItemView,
)

APP_NAME = "YTM Studio"
APP_VERSION = "1.0.0"
CONFIG_DIR = Path("config")
GUI_CONFIG = CONFIG_DIR / "gui_settings.json"
BACKEND_CONFIG = CONFIG_DIR / "YoutubeMusicDownloader.json"   # kept in sync
HISTORY_FILE = CONFIG_DIR / "gui_history.json"
ARCHIVES_DIR = Path("archives")

# ----------------------------------------------------------------------------
# Icons (inline SVG, recolored at runtime so they follow the theme)
# ----------------------------------------------------------------------------
ICON_PATHS = {
    "home":     '<path d="M3 9.5 12 3l9 6.5V20a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
    "history":  '<path d="M3 3v5h5"/><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8"/><path d="M12 7v5l3 2"/>',
    "settings": ('<path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/>'
                 '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06'
                 'a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09'
                 'A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06'
                 'a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09'
                 'A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06'
                 'a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09'
                 'a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06'
                 'a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09'
                 'a1.65 1.65 0 0 0-1.51 1z"/>'),
    "terminal": '<path d="m4 17 6-6-6-6"/><path d="M12 19h8"/>',
    "grid":     ('<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>'
                 '<rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>'),
    "github":   ('<path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 '
                 '6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 '
                 '0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 '
                 '7A3.37 3.37 0 0 0 9 18.13V22"/>'),
    "alert":    '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
    "coffee":   ('<path d="M17 8h1a4 4 0 1 1 0 8h-1"/><path d="M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4z"/>'
                 '<line x1="6" y1="2" x2="6" y2="4"/><line x1="10" y1="2" x2="10" y2="4"/><line x1="14" y1="2" x2="14" y2="4"/>'),
    "search":   '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
    "fetch":    '<path d="M8 17 12 21l4-4"/><path d="M12 12v9"/><path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29"/>',
    "folder":   '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2z"/>',
    "play":     '<polygon points="6 4 20 12 6 20 6 4"/>',
    "reset":    '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
    "save":     '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>',
    "trash":    '<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "copy":     '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "youtube":  ('<path d="M22.54 6.42a2.78 2.78 0 0 0-1.94-2C18.88 4 12 4 12 4s-6.88 0-8.6.46a2.78 2.78 0 0 0-1.94 2'
                 'A29 29 0 0 0 1 11.75a29 29 0 0 0 .46 5.33A2.78 2.78 0 0 0 3.4 19c1.72.46 8.6.46 8.6.46s6.88 0 8.6-.46'
                 'a2.78 2.78 0 0 0 1.94-2 29 29 0 0 0 .46-5.25 29 29 0 0 0-.46-5.33z"/><polygon points="9.75 15.02 15.5 11.75 9.75 8.48 9.75 15.02"/>'),
}


def make_icon(name: str, color: str, size: int = 22) -> QIcon:
    inner = ICON_PATHS.get(name, "")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
           f'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
           f'{inner}</svg>')
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    return QIcon(pm)


# ----------------------------------------------------------------------------
# Theme
# ----------------------------------------------------------------------------
PALETTES = {
    "Dark": dict(bg="#0a0a0a", sidebar="#0d0d0d", surface="#161616", surface_alt="#1e1e1e",
                 hover="#262626", border="#2a2a2a", text="#ffffff", text_dim="#b3b3b3",
                 text_faint="#707070"),
    "Light": dict(bg="#f4f4f5", sidebar="#ffffff", surface="#ffffff", surface_alt="#f0f0f0",
                  hover="#e8e8e8", border="#e2e2e2", text="#18181b", text_dim="#52525b",
                  text_faint="#a1a1aa"),
}
ACCENTS = {
    "Red": "#ff0033", "Rose": "#f43f5e", "Amber": "#f59e0b",
    "Emerald": "#1DB954", "Blue": "#3b82f6", "Purple": "#8b5cf6", "Cyan": "#06b6d4",
}


def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _adjust(h, f):
    r, g, b = _hex_rgb(h)
    if f >= 0:
        r, g, b = (int(r + (255 - r) * f), int(g + (255 - g) * f), int(b + (255 - b) * f))
    else:
        f = -f
        r, g, b = (int(r * (1 - f)), int(g * (1 - f)), int(b * (1 - f)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _rgba(h, a):
    r, g, b = _hex_rgb(h)
    return f"rgba({r},{g},{b},{a})"


def _on_accent(h):
    r, g, b = _hex_rgb(h)
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if lum > 0.6 else "#ffffff"


class Theme:
    def __init__(self, mode="Dark", accent="Red", font="Segoe UI"):
        self.mode = mode if mode in PALETTES else "Dark"
        self.accent_name = accent if accent in ACCENTS else "Red"
        self.font = font

    @property
    def c(self):
        return PALETTES[self.mode]

    @property
    def accent(self):
        return ACCENTS[self.accent_name]

    @property
    def on_accent(self):
        return _on_accent(self.accent)

    @property
    def accent_soft(self):
        return _rgba(self.accent, 0.16)

    def qss(self):
        c = self.c
        accent = self.accent
        on_accent = self.on_accent
        accent_hover = _adjust(accent, 0.12 if self.mode == "Dark" else -0.10)
        accent_soft = self.accent_soft
        return f"""
        * {{ font-family: "{self.font}"; color: {c['text']}; outline: 0; }}
        QWidget#Root {{ background: {c['bg']}; }}
        QWidget#Sidebar {{ background: {c['sidebar']}; border-right: 1px solid {c['border']}; }}
        QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: 0; }}
        QLabel {{ background: transparent; }}
        QLabel#H1 {{ font-size: 30px; font-weight: 800; }}
        QLabel#H2 {{ font-size: 22px; font-weight: 700; }}
        QLabel#H3 {{ font-size: 15px; font-weight: 700; }}
        QLabel#Sub {{ color: {c['text_dim']}; font-size: 13px; }}
        QLabel#Faint {{ color: {c['text_faint']}; font-size: 12px; }}
        QLabel#Accent {{ color: {accent}; font-weight: 700; }}
        QFrame[card="true"] {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 14px; }}
        QFrame#Cover {{ background: {c['surface_alt']}; border: 1px solid {c['border']}; border-radius: 12px; }}
        QFrame#Divider {{ background: {c['border']}; max-height: 1px; min-height: 1px; border: 0; }}
        QFrame#Badge {{ background: {accent_soft}; border-radius: 8px; }}
        QLineEdit {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px;
                     padding: 10px 12px; selection-background-color: {accent}; selection-color: {on_accent}; }}
        QLineEdit:focus {{ border: 1px solid {accent}; }}
        QComboBox {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px;
                     padding: 8px 12px; min-height: 18px; }}
        QComboBox:hover {{ border: 1px solid {accent}; }}
        QComboBox::drop-down {{ border: 0; width: 22px; }}
        QComboBox QAbstractItemView {{ background: {c['surface_alt']}; border: 1px solid {c['border']};
                     selection-background-color: {accent}; selection-color: {on_accent}; padding: 4px; }}
        QPushButton {{ background: {c['surface_alt']}; border: 1px solid {c['border']}; border-radius: 10px;
                       padding: 9px 14px; font-weight: 600; }}
        QPushButton:hover {{ background: {c['hover']}; }}
        QPushButton:disabled {{ color: {c['text_faint']}; }}
        QPushButton[variant="accent"] {{ background: {accent}; color: {on_accent}; border: 0; }}
        QPushButton[variant="accent"]:hover {{ background: {accent_hover}; }}
        QPushButton[variant="ghost"] {{ background: transparent; border: 0; }}
        QPushButton[variant="ghost"]:hover {{ background: {c['hover']}; }}
        QPushButton[variant="iconbtn"] {{ background: {c['surface_alt']}; border: 1px solid {c['border']};
                       border-radius: 8px; padding: 6px; }}
        QPushButton[variant="iconbtn"]:hover {{ background: {c['hover']}; }}
        QPushButton[variant="dlbtn"] {{ background: {accent}; border: 0; border-radius: 8px; padding: 6px; }}
        QPushButton[variant="dlbtn"]:hover {{ background: {accent_hover}; }}
        QPushButton[seg="true"] {{ background: transparent; border: 0; border-bottom: 2px solid transparent;
                       border-radius: 0; color: {c['text_dim']}; padding: 8px 6px; font-weight: 700; }}
        QPushButton[seg="true"]:checked {{ color: {c['text']}; border-bottom: 2px solid {accent}; }}
        QToolButton#Nav {{ background: transparent; border: 0; border-radius: 12px; padding: 9px; }}
        QToolButton#Nav:hover {{ background: {c['hover']}; }}
        QToolButton#Nav:checked {{ background: {accent_soft}; }}
        QTableWidget {{ background: transparent; border: 0; }}
        QHeaderView::section {{ background: transparent; color: {c['text_faint']}; border: 0;
                       border-bottom: 1px solid {c['border']}; padding: 8px 6px; font-weight: 700; }}
        QTableWidget::item {{ border-bottom: 1px solid {c['border']}; padding: 8px 6px; }}
        QTableWidget::item:selected {{ background: {accent_soft}; color: {c['text']}; }}
        QProgressBar {{ background: {c['surface_alt']}; border: 0; border-radius: 6px; max-height: 8px;
                       min-height: 8px; text-align: center; color: transparent; }}
        QProgressBar::chunk {{ background: {accent}; border-radius: 6px; }}
        QPlainTextEdit {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px;
                       font-family: "Consolas","DejaVu Sans Mono","monospace"; font-size: 12px; padding: 8px; }}
        QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 5px; min-height: 30px; }}
        QScrollBar::handle:vertical:hover {{ background: {c['text_faint']}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
        QScrollBar:horizontal {{ height: 0; }}
        """


# ----------------------------------------------------------------------------
# Config + history
# ----------------------------------------------------------------------------
class Config:
    DEFAULTS = dict(
        output_directory=str(Path.home() / "Music" / "YouTubeMusicDownloads"),
        audio_quality="320k", audio_format="mp3",
        use_cookies=False, cookie_file="", embed_metadata=False,
        ytdlp_path="yt-dlp",
        theme_mode="Dark", accent="Red", font="Segoe UI",
    )
    QUALITIES = ["auto", "128k", "160k", "192k", "224k", "256k", "320k"]
    FORMATS = ["mp3", "m4a", "flac", "opus", "ogg", "wav"]

    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.data = dict(self.DEFAULTS)
        if GUI_CONFIG.exists():
            try:
                self.data.update(json.loads(GUI_CONFIG.read_text(encoding="utf-8")))
            except Exception:
                pass

    def __getitem__(self, k):
        return self.data.get(k, self.DEFAULTS.get(k))

    def __setitem__(self, k, v):
        self.data[k] = v

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        GUI_CONFIG.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        # Mirror download-relevant keys into the backend config so the CLI stays in sync.
        # Only the keys YoutubeMusicDownloader.load_config reads are touched; existing
        # backend-only keys (max_retries, retry_delay, download_timeout) are preserved.
        backend = {}
        if BACKEND_CONFIG.exists():
            try:
                backend = json.loads(BACKEND_CONFIG.read_text(encoding="utf-8"))
            except Exception:
                backend = {}
        backend.update(dict(
            output_directory=self["output_directory"],
            audio_quality=self["audio_quality"],
            audio_format=self["audio_format"],
            use_cookies=self["use_cookies"],
            embed_metadata=self["embed_metadata"],
        ))
        BACKEND_CONFIG.write_text(json.dumps(backend, indent=2, ensure_ascii=False),
                                  encoding="utf-8")


class History:
    def __init__(self):
        self.entries = []
        if HISTORY_FILE.exists():
            try:
                self.entries = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.entries = []

    def add(self, category, item_type, title, url, status="", error=""):
        from datetime import datetime
        self.entries.insert(0, dict(category=category, type=item_type, title=title,
                                    url=url, status=status, error=error,
                                    time=datetime.now().strftime("%Y-%m-%d %H:%M")))
        self.entries = self.entries[:500]
        self._save()

    def clear(self, category=None):
        if category is None:
            self.entries = []
        else:
            self.entries = [e for e in self.entries if e.get("category") != category]
        self._save()

    def _save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(self.entries, indent=2), encoding="utf-8")


# ----------------------------------------------------------------------------
# URL / format helpers
# ----------------------------------------------------------------------------
def fmt_dur(sec):
    try:
        m, s = divmod(int(float(sec)), 60)
        return f"{m}:{s:02d}"
    except Exception:
        return "--:--"


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name or "")
    name = re.sub(r"\s+", " ", name).strip()
    return name[:120] or "untitled"


def extract_list_id(url: str):
    m = re.search(r"[?&]list=([\w-]+)", url or "")
    return m.group(1) if m else None


def url_kind(url: str) -> str:
    u = (url or "").lower()
    if any(p in u for p in ("/channel/", "/@", "/c/", "/user/", "/artist/")):
        return "artist"
    lid = extract_list_id(url)
    if lid:
        # Auto-generated album playlists from YouTube Music start with OLAK5uy.
        return "album" if lid.startswith("OLAK5uy") else "playlist"
    if "/playlist" in u:
        return "playlist"
    return "track"


def best_thumb(obj) -> str:
    if not obj:
        return ""
    thumbs = obj.get("thumbnails")
    if isinstance(thumbs, list) and thumbs:
        return thumbs[-1].get("url", "") or ""
    return obj.get("thumbnail", "") or ""


# ----------------------------------------------------------------------------
# Workers
# ----------------------------------------------------------------------------
class MetadataWorker(QThread):
    done = Signal(dict)
    error = Signal(str)
    log = Signal(str)

    def __init__(self, url, ytdlp_path="yt-dlp", cookie_file="", use_cookies=False):
        super().__init__()
        self.url = url.strip()
        self.ytdlp = ytdlp_path or "yt-dlp"
        self.cookie_file = cookie_file
        self.use_cookies = use_cookies

    def run(self):
        kind = url_kind(self.url)
        cmd = [self.ytdlp, "-J", "--flat-playlist", "--no-warnings", "--ignore-errors",
               "--extractor-args", "youtube:player_client=android"]
        if self.use_cookies and self.cookie_file and Path(self.cookie_file).exists():
            cmd += ["--cookies", self.cookie_file]
        cmd.append(self.url)

        self.log.emit(f"[meta] fetching metadata for {self.url}")
        try:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", env=env, timeout=180)
            out = (proc.stdout or "").strip()
            if not out:
                self.error.emit("Could not fetch metadata. Is the URL valid and yt-dlp installed?")
                if proc.stderr:
                    self.log.emit("[meta] " + proc.stderr.strip()[:500])
                return

            data = json.loads(out)
            entries = data.get("entries")

            if entries is not None:                       # playlist / album / channel
                tracks = []
                for e in entries:
                    if not e:
                        continue
                    vid = e.get("id")
                    tracks.append(dict(
                        name=e.get("title") or "Unknown",
                        artists=(e.get("artist") or e.get("uploader")
                                 or e.get("channel") or ""),
                        album=data.get("title", "") if kind == "album" else "",
                        duration=fmt_dur(e.get("duration") or 0),
                        cover_url=best_thumb(e),
                        url=e.get("url") or (f"https://music.youtube.com/watch?v={vid}" if vid else ""),
                    ))
                if not tracks:
                    self.error.emit("No videos found for this URL.")
                    return
                title = data.get("title") or kind.title()
                if kind == "album":
                    subtitle = (data.get("channel") or data.get("uploader")
                                or tracks[0]["artists"] or "")
                else:
                    subtitle = f"{len(tracks)} tracks"
                cover = best_thumb(data) or tracks[0]["cover_url"]
                count = len(tracks)
            else:                                         # single video
                title = data.get("title") or "Track"
                subtitle = (data.get("artist") or data.get("uploader")
                            or data.get("channel") or "")
                cover = best_thumb(data)
                tracks = [dict(
                    name=title, artists=subtitle, album=data.get("album", "") or "",
                    duration=fmt_dur(data.get("duration") or 0), cover_url=cover,
                    url=data.get("webpage_url") or self.url,
                )]
                count = 1

            self.done.emit(dict(kind=kind, title=title, subtitle=subtitle,
                                cover_url=cover, count=count, tracks=tracks,
                                source_url=self.url))
        except subprocess.TimeoutExpired:
            self.error.emit("Metadata fetch timed out.")
        except FileNotFoundError:
            self.error.emit(f"'{self.ytdlp}' not found. Install yt-dlp or set its path in Settings.")
        except json.JSONDecodeError:
            self.error.emit("Could not parse metadata from yt-dlp output.")
        except Exception as e:
            self.error.emit(f"Metadata error: {e}")


class ImageWorker(QThread):
    loaded = Signal(bytes)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        if not self.url:
            return
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                self.loaded.emit(r.read())
        except Exception:
            pass


class DownloadWorker(QThread):
    log = Signal(str)
    progress = Signal(int, int)          # done, total
    track_status = Signal(str, str)      # title, status (downloaded/skipped/failed)
    finished_stats = Signal(dict)

    # yt-dlp signals (NOTE: we deliberately do NOT pass --quiet, otherwise these
    # lines are suppressed and progress/counting break).
    RATE = ("Sign in to confirm", "HTTP Error 429", "Too Many Requests",
            "rate-limit", "rate/request limit", "429:")
    SKIP = ("has already been downloaded", "already been recorded in the archive")
    SUCCESS = ("[ExtractAudio] Destination:", "Not converting audio")

    def __init__(self, cmd, total, titles):
        super().__init__()
        self.cmd = cmd
        self.total = total or 0
        self.titles = list(titles or [])
        self._stop = False
        self._lastdest = ""

    def stop(self):
        self._stop = True

    def _match(self, text):
        if not text:
            return None
        low = text.lower()
        for t in self.titles:
            if t and t.lower()[:30] in low:
                return t
        return None

    def run(self):
        succeeded = skipped = failed = 0
        pct_re = re.compile(r"(\d+\.?\d*)%")
        item_re = re.compile(r"Downloading (?:item|video) (\d+) of (\d+)")
        dest_re = re.compile(r"Destination:\s*(.+)$")

        try:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace",
                                    bufsize=1, env=env)
        except FileNotFoundError:
            self.log.emit("[error] yt-dlp not found. Install it or set its path in Settings.")
            self.finished_stats.emit(dict(succeeded=0, skipped=0, failed=self.total,
                                          rate_limited=False, returncode=-1))
            return
        except Exception as e:
            self.log.emit(f"[error] could not start download: {e}")
            self.finished_stats.emit(dict(succeeded=0, skipped=0, failed=self.total,
                                          rate_limited=False, returncode=-1))
            return

        for line in iter(proc.stdout.readline, ""):
            if self._stop:
                proc.terminate()
                break
            line = line.rstrip()
            if not line:
                continue
            self.log.emit(line)

            if any(m in line for m in self.RATE):
                rate_seen = True  # noqa: F841 (kept for readability)
                rate = True
            else:
                rate = locals().get("rate", False)

            # discover/refresh total from the playlist counter
            m = item_re.search(line)
            if m:
                if not self.total:
                    self.total = int(m.group(2))
                continue

            # remember most recent destination filename for title matching
            dm = dest_re.search(line)
            if dm:
                self._lastdest = os.path.basename(dm.group(1).strip())

            # within-file percentage → keep the bar alive without advancing count
            if "[download]" in line and "%" in line and "of" in line:
                done = succeeded + skipped + failed
                self.progress.emit(min(done, self.total) if self.total else done, self.total)
                continue

            outcome = None
            if line.startswith("ERROR:"):
                failed += 1
                outcome = "failed"
            elif any(s in line for s in self.SKIP):
                skipped += 1
                outcome = "skipped"
            elif any(s in line for s in self.SUCCESS):
                succeeded += 1
                outcome = "downloaded"

            if outcome:
                title = self._match(self._lastdest) or self._match(line)
                if title:
                    self.track_status.emit(title, outcome)
                done = succeeded + skipped + failed
                self.progress.emit(min(done, self.total) if self.total else done, self.total)

        proc.wait()
        done = succeeded + skipped + failed
        if self.total and done < self.total:
            self.progress.emit(self.total, self.total)
        self.finished_stats.emit(dict(succeeded=succeeded, skipped=skipped, failed=failed,
                                      rate_limited=locals().get("rate", False),
                                      returncode=proc.returncode))


# ----------------------------------------------------------------------------
# Reusable widgets
# ----------------------------------------------------------------------------
class NavButton(QToolButton):
    def __init__(self, icon_name, tooltip, win):
        super().__init__()
        self.icon_name = icon_name
        self.win = win
        self.setObjectName("Nav")
        self.setCheckable(True)
        self.setToolTip(tooltip)
        self.setIconSize(QSize(22, 22))
        self.setCursor(Qt.PointingHandCursor)
        self.toggled.connect(self.refresh)

    def refresh(self, *_):
        t = self.win.theme
        color = t.accent if self.isChecked() else t.c["text_dim"]
        self.setIcon(make_icon(self.icon_name, color, 22))


class Card(QFrame):
    def __init__(self):
        super().__init__()
        self.setProperty("card", True)


# ----------------------------------------------------------------------------
# Pages
# ----------------------------------------------------------------------------
class HomePage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.meta = None
        self.dl_worker = None
        self.img_worker = None
        self.mw = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 36, 40, 24)
        outer.setSpacing(18)

        title = QLabel(APP_NAME)
        title.setObjectName("H1")
        sub = QLabel("Fetch YouTube / YouTube Music metadata and download tracks, "
                     "albums, playlists & channels with yt-dlp.")
        sub.setObjectName("Sub")
        outer.addWidget(title)
        outer.addWidget(sub)

        # Search row
        searchrow = QHBoxLayout()
        searchrow.setSpacing(10)
        self.search_icon = QLabel()
        self.search_icon.setFixedWidth(20)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://music.youtube.com/playlist?list=...")
        self.url_edit.returnPressed.connect(self.fetch)
        self.fetch_btn = QPushButton("  Fetch")
        self.fetch_btn.setProperty("variant", "accent")
        self.fetch_btn.setCursor(Qt.PointingHandCursor)
        self.fetch_btn.clicked.connect(self.fetch)
        searchrow.addWidget(self.search_icon)
        searchrow.addWidget(self.url_edit, 1)
        searchrow.addWidget(self.fetch_btn)
        outer.addLayout(searchrow)

        # Status / progress
        self.status = QLabel("")
        self.status.setObjectName("Faint")
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        outer.addWidget(self.status)
        outer.addWidget(self.progress)

        # Metadata card
        self.meta_card = Card()
        self.meta_card.setVisible(False)
        mc = QHBoxLayout(self.meta_card)
        mc.setContentsMargins(18, 18, 18, 18)
        mc.setSpacing(18)
        self.cover = QFrame()
        self.cover.setObjectName("Cover")
        self.cover.setFixedSize(150, 150)
        cov_l = QVBoxLayout(self.cover)
        cov_l.setContentsMargins(0, 0, 0, 0)
        self.cover_img = QLabel()
        self.cover_img.setAlignment(Qt.AlignCenter)
        self.cover_img.setScaledContents(True)
        cov_l.addWidget(self.cover_img)
        mc.addWidget(self.cover)

        info = QVBoxLayout()
        info.setSpacing(4)
        self.kind_lbl = QLabel("PLAYLIST")
        self.kind_lbl.setObjectName("Accent")
        self.meta_title = QLabel("—")
        self.meta_title.setObjectName("H2")
        self.meta_title.setWordWrap(True)
        self.meta_sub = QLabel("")
        self.meta_sub.setObjectName("Sub")
        self.meta_count = QLabel("")
        self.meta_count.setObjectName("Faint")
        btnrow = QHBoxLayout()
        self.dl_all = QPushButton("  Download All")
        self.dl_all.setProperty("variant", "accent")
        self.dl_all.setCursor(Qt.PointingHandCursor)
        self.dl_all.clicked.connect(self.download_all)
        self.open_btn = QPushButton("Open on YouTube")
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(self.meta["source_url"])) if self.meta else None)
        btnrow.addWidget(self.dl_all)
        btnrow.addWidget(self.open_btn)
        btnrow.addStretch(1)
        info.addWidget(self.kind_lbl)
        info.addWidget(self.meta_title)
        info.addWidget(self.meta_sub)
        info.addWidget(self.meta_count)
        info.addStretch(1)
        info.addLayout(btnrow)
        mc.addLayout(info, 1)
        outer.addWidget(self.meta_card)

        # Track table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["#", "Title", "Album", "Duration", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setVisible(False)
        outer.addWidget(self.table, 1)
        outer.addStretch(1)

    # -- theming hook
    def refresh_icons(self):
        t = self.win.theme
        self.search_icon.setPixmap(make_icon("search", t.c["text_faint"], 20).pixmap(20, 20))
        self.fetch_btn.setIcon(make_icon("fetch", t.on_accent, 18))
        self.dl_all.setIcon(make_icon("download", t.on_accent, 18))

    # -- actions
    def fetch(self):
        url = self.url_edit.text().strip()
        if not url.startswith("http"):
            self.status.setText("Enter a valid YouTube / YouTube Music URL.")
            return
        self.status.setText("Fetching metadata…")
        self.fetch_btn.setEnabled(False)
        self.win.log(f"[meta] requested: {url}")
        cfg = self.win.cfg
        self.mw = MetadataWorker(url, cfg["ytdlp_path"], cfg["cookie_file"], cfg["use_cookies"])
        self.mw.log.connect(self.win.log)
        self.mw.done.connect(self._meta_done)
        self.mw.error.connect(self._meta_err)
        self.mw.start()

    def _meta_err(self, msg):
        self.fetch_btn.setEnabled(True)
        self.status.setText(msg)
        self.win.log("[error] " + msg)

    def _meta_done(self, meta):
        self.fetch_btn.setEnabled(True)
        self.meta = meta
        self.status.setText("Metadata fetched successfully.")
        self.kind_lbl.setText(meta["kind"].upper())
        self.meta_title.setText(meta["title"])
        self.meta_sub.setText(meta["subtitle"])
        self.meta_count.setText(f"{meta['count']} tracks")
        self.meta_card.setVisible(True)
        self.cover_img.clear()
        if meta["cover_url"]:
            self.img_worker = ImageWorker(meta["cover_url"])
            self.img_worker.loaded.connect(self._cover_loaded)
            self.img_worker.start()
        self._fill_table(meta["tracks"])
        self.win.history.add("fetch", meta["kind"], meta["title"], meta["source_url"], "fetched")
        self.win.refresh_history()

    def _cover_loaded(self, data):
        pm = QPixmap()
        if pm.loadFromData(QByteArray(data)):
            self.cover_img.setPixmap(pm)

    def _fill_table(self, tracks):
        self.table.setRowCount(0)
        self.table.setVisible(True)
        for i, tr in enumerate(tracks, 1):
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setRowHeight(r, 52)
            self.table.setItem(r, 0, QTableWidgetItem(str(i)))
            title_item = QTableWidgetItem(f"{tr['name']}\n{tr['artists']}")
            self.table.setItem(r, 1, title_item)
            self.table.setItem(r, 2, QTableWidgetItem(tr["album"]))
            self.table.setItem(r, 3, QTableWidgetItem(tr["duration"]))
            btn = QPushButton()
            btn.setProperty("variant", "dlbtn")
            btn.setIcon(make_icon("download", self.win.theme.on_accent, 16))
            btn.setFixedSize(34, 30)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, u=tr["url"], n=tr["name"]: self.download_one(u, n))
            wrap = QWidget()
            wl = QHBoxLayout(wrap)
            wl.setContentsMargins(4, 0, 8, 0)
            wl.addWidget(btn)
            self.table.setCellWidget(r, 4, wrap)

    def _build_cmd(self, url, kind, title):
        """Build a yt-dlp command mirroring YoutubeMusicDownloader.run_download."""
        cfg = self.win.cfg
        out = cfg["output_directory"]
        if kind == "playlist":
            tmpl = str(Path(out) / sanitize_filename(title or "Playlist") /
                       "%(artist)s - %(title)s.%(ext)s")
        elif kind == "album":
            tmpl = str(Path(out) / "%(artist)s" / "%(album)s" /
                       "%(artist)s - %(title)s.%(ext)s")
        elif kind == "artist":
            tmpl = str(Path(out) / sanitize_filename(title or "Channel") /
                       "%(title)s.%(ext)s")
        else:  # track
            tmpl = str(Path(out) / "%(artist)s - %(title)s.%(ext)s")

        cmd = [cfg["ytdlp_path"], "-x",
               "--audio-format", cfg["audio_format"],
               "-o", tmpl,
               "--no-overwrites", "--embed-thumbnail",
               "--newline", "--no-warnings", "--ignore-errors",
               "--retries", "10", "--fragment-retries", "10",
               "--extractor-args", "youtube:player_client=android"]
        if cfg["audio_quality"] not in ("auto", "disable", ""):
            cmd += ["--audio-quality", cfg["audio_quality"]]
        if cfg["embed_metadata"]:
            cmd += ["--add-metadata"]
        if cfg["use_cookies"] and cfg["cookie_file"] and Path(cfg["cookie_file"]).exists():
            cmd += ["--cookies", cfg["cookie_file"]]

        # Per-collection archive so resumed downloads skip what's already grabbed.
        if kind in ("playlist", "album", "artist"):
            ARCHIVES_DIR.mkdir(exist_ok=True)
            key = extract_list_id(url) or hashlib.md5(url.encode()).hexdigest()[:8]
            key = re.sub(r"[^\w@-]", "_", key)
            cmd += ["--download-archive", str(ARCHIVES_DIR / f"{kind}_{key}.txt")]

        cmd.append(url)
        return cmd

    def download_all(self):
        if not self.meta:
            return
        titles = [t["name"] for t in self.meta["tracks"]]
        self._start_download(
            self._build_cmd(self.meta["source_url"], self.meta["kind"], self.meta["title"]),
            self.meta["count"], titles,
            self.meta["kind"], self.meta["title"], self.meta["source_url"])

    def download_one(self, url, name):
        if not url:
            self.status.setText("No direct URL for this track.")
            return
        self._start_download(self._build_cmd(url, "track", name), 1, [name], "track", name, url)

    def _start_download(self, cmd, total, titles, kind, title, url):
        if self.dl_worker and self.dl_worker.isRunning():
            self.status.setText("A download is already running.")
            return
        self.status.setText(f"Downloading {title}…")
        self.progress.setVisible(True)
        self.progress.setRange(0, total if total else 0)
        self.progress.setValue(0)
        self.dl_all.setEnabled(False)
        self.win.log(f"[download] {' '.join(cmd)}")
        self._cur = dict(kind=kind, title=title, url=url)
        self.dl_worker = DownloadWorker(cmd, total, titles)
        self.dl_worker.log.connect(self.win.log)
        self.dl_worker.progress.connect(self._on_progress)
        self.dl_worker.finished_stats.connect(self._on_finished)
        self.dl_worker.start()

    def _on_progress(self, done, total):
        if total:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
            self.status.setText(f"Downloading… {done}/{total}")
        else:
            self.status.setText(f"Downloading… {done} done")

    def _on_finished(self, stats):
        self.dl_all.setEnabled(True)
        msg = (f"Done — {stats['succeeded']} downloaded, {stats['skipped']} skipped, "
               f"{stats['failed']} failed.")
        if stats["rate_limited"]:
            msg += " (YouTube rate-limit detected — try cookies or retry later.)"
        self.status.setText(msg)
        self.progress.setVisible(False)
        c = self._cur
        status = "completed" if stats["returncode"] == 0 else "partial/failed"
        self.win.history.add("download", c["kind"], c["title"], c["url"], status,
                             error="" if stats["returncode"] == 0 else msg)
        self.win.refresh_history()


class HistoryPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.category = "download"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 36, 40, 24)
        outer.setSpacing(16)
        title = QLabel("History")
        title.setObjectName("H1")
        outer.addWidget(title)

        tabs = QHBoxLayout()
        tabs.setSpacing(18)
        self.tab_dl = QPushButton("Downloads")
        self.tab_ft = QPushButton("Fetches")
        for b, cat in ((self.tab_dl, "download"), (self.tab_ft, "fetch")):
            b.setProperty("seg", "true")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=cat: self.switch(c))
        self.tab_dl.setChecked(True)
        grp = QButtonGroup(self)
        grp.setExclusive(True)
        grp.addButton(self.tab_dl)
        grp.addButton(self.tab_ft)
        tabs.addWidget(self.tab_dl)
        tabs.addWidget(self.tab_ft)
        tabs.addStretch(1)
        self.clear_btn = QPushButton("  Clear")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear)
        tabs.addWidget(self.clear_btn)
        outer.addLayout(tabs)

        filt = QHBoxLayout()
        filt.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search history…")
        self.search.textChanged.connect(self.render)
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All types", "Track", "Album", "Playlist", "Artist"])
        self.type_filter.currentIndexChanged.connect(self.render)
        self.type_filter.setFixedWidth(160)
        filt.addWidget(self.search, 1)
        filt.addWidget(self.type_filter)
        outer.addLayout(filt)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Type", "Title", "Status", "When"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        outer.addWidget(self.table, 1)

        self.empty = QLabel("No history yet. Your activity will appear here.")
        self.empty.setObjectName("Faint")
        self.empty.setAlignment(Qt.AlignCenter)
        outer.addWidget(self.empty)
        outer.addStretch(1)          # same fix

    def refresh_icons(self):
        self.clear_btn.setIcon(make_icon("trash", self.win.theme.c["text_dim"], 16))

    def switch(self, cat):
        self.category = cat
        self.render()

    def clear(self):
        self.win.history.clear(self.category)
        self.render()

    def render(self):
        q = self.search.text().lower().strip()
        tf = self.type_filter.currentText().lower()
        rows = [e for e in self.win.history.entries if e.get("category") == self.category]
        if tf != "all types":
            rows = [e for e in rows if e.get("type") == tf]
        if q:
            rows = [e for e in rows if q in (e.get("title", "") + e.get("url", "")).lower()]
        self.table.setRowCount(0)
        self.empty.setVisible(not rows)
        self.table.setVisible(bool(rows))
        for e in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setRowHeight(r, 44)
            self.table.setItem(r, 0, QTableWidgetItem(e.get("type", "").title()))
            self.table.setItem(r, 1, QTableWidgetItem(e.get("title", "")))
            self.table.setItem(r, 2, QTableWidgetItem(e.get("status", "")))
            self.table.setItem(r, 3, QTableWidgetItem(e.get("time", "")))


class SettingsPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        scroll.setWidget(host)
        wrap = QVBoxLayout(self)
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.addWidget(scroll)

        outer = QVBoxLayout(host)
        outer.setContentsMargins(40, 36, 40, 30)
        outer.setSpacing(18)

        head = QHBoxLayout()
        title = QLabel("Settings")
        title.setObjectName("H1")
        head.addWidget(title)
        head.addStretch(1)
        self.open_cfg = QPushButton("  Open Config Folder")
        self.open_cfg.setCursor(Qt.PointingHandCursor)
        self.open_cfg.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(CONFIG_DIR.resolve()))))
        self.reset_btn = QPushButton("  Reset to Default")
        self.reset_btn.setCursor(Qt.PointingHandCursor)
        self.reset_btn.clicked.connect(self.reset)
        self.save_btn = QPushButton("  Save Changes")
        self.save_btn.setProperty("variant", "accent")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self.save)
        head.addWidget(self.open_cfg)
        head.addWidget(self.reset_btn)
        head.addWidget(self.save_btn)
        outer.addLayout(head)

        grid = QGridLayout()
        grid.setHorizontalSpacing(40)
        grid.setVerticalSpacing(16)
        outer.addLayout(grid)

        def field(label):
            l = QLabel(label)
            l.setObjectName("H3")
            return l

        cfg = self.win.cfg

        # Left column — download settings
        grid.addWidget(field("Download Path"), 0, 0)
        pathrow = QHBoxLayout()
        self.path_edit = QLineEdit(cfg["output_directory"])
        self.browse = QPushButton("  Browse")
        self.browse.setProperty("variant", "accent")
        self.browse.setCursor(Qt.PointingHandCursor)
        self.browse.clicked.connect(self.pick_dir)
        pathrow.addWidget(self.path_edit, 1)
        pathrow.addWidget(self.browse)
        pw = QWidget()
        pw.setLayout(pathrow)
        grid.addWidget(pw, 1, 0)

        grid.addWidget(field("Bitrate"), 2, 0)
        self.bitrate = QComboBox()
        self.bitrate.addItems(Config.QUALITIES)
        self.bitrate.setCurrentText(cfg["audio_quality"])
        grid.addWidget(self.bitrate, 3, 0)

        grid.addWidget(field("Conversion Format"), 4, 0)
        self.fmt = QComboBox()
        self.fmt.addItems(Config.FORMATS)
        self.fmt.setCurrentText(cfg["audio_format"])
        grid.addWidget(self.fmt, 5, 0)

        grid.addWidget(field("yt-dlp Executable"), 6, 0)
        self.ytdlp_edit = QLineEdit(cfg["ytdlp_path"])
        grid.addWidget(self.ytdlp_edit, 7, 0)

        grid.addWidget(field("Cookie File (cookies.txt)"), 8, 0)
        cookrow = QHBoxLayout()
        self.cookie_edit = QLineEdit(cfg["cookie_file"])
        self.cookie_edit.setPlaceholderText("optional — for age/region-restricted content")
        self.cookie_browse = QPushButton("  Browse")
        self.cookie_browse.setCursor(Qt.PointingHandCursor)
        self.cookie_browse.clicked.connect(self.pick_cookie)
        cookrow.addWidget(self.cookie_edit, 1)
        cookrow.addWidget(self.cookie_browse)
        cw = QWidget()
        cw.setLayout(cookrow)
        grid.addWidget(cw, 9, 0)

        # Right column — toggles + appearance
        grid.addWidget(field("Use Cookies"), 0, 1)
        self.use_cookies = QComboBox()
        self.use_cookies.addItems(["No", "Yes"])
        self.use_cookies.setCurrentText("Yes" if cfg["use_cookies"] else "No")
        grid.addWidget(self.use_cookies, 1, 1)

        grid.addWidget(field("Embed Metadata"), 2, 1)
        self.embed = QComboBox()
        self.embed.addItems(["No", "Yes"])
        self.embed.setCurrentText("Yes" if cfg["embed_metadata"] else "No")
        grid.addWidget(self.embed, 3, 1)

        grid.addWidget(field("Theme Mode"), 4, 1)
        self.mode = QComboBox()
        self.mode.addItems(list(PALETTES.keys()))
        self.mode.setCurrentText(cfg["theme_mode"])
        self.mode.currentTextChanged.connect(self.preview)
        grid.addWidget(self.mode, 5, 1)

        grid.addWidget(field("Accent"), 6, 1)
        self.accent = QComboBox()
        self.accent.addItems(list(ACCENTS.keys()))
        self.accent.setCurrentText(cfg["accent"])
        self.accent.currentTextChanged.connect(self.preview)
        grid.addWidget(self.accent, 7, 1)

        grid.addWidget(field("Font"), 8, 1)
        self.font = QComboBox()
        fams = sorted(set(QFontDatabase.families()))
        common = ["Segoe UI", "Arial", "Roboto", "Inter", "Google Sans"]
        ordered = [f for f in common if f in fams] + [f for f in fams if f not in common]
        self.font.addItems(ordered or ["Segoe UI"])
        if cfg["font"] in ordered:
            self.font.setCurrentText(cfg["font"])
        self.font.currentTextChanged.connect(self.preview)
        grid.addWidget(self.font, 9, 1)

        note = QLabel("Mode, accent and font preview instantly. Click Save Changes to persist all "
                      "settings — download options are also mirrored into the backend config "
                      "(config/YoutubeMusicDownloader.json) so the CLI stays in sync.")
        note.setObjectName("Faint")
        note.setWordWrap(True)
        outer.addWidget(note)

        outer.addStretch(1)

    def refresh_icons(self):
        t = self.win.theme
        self.open_cfg.setIcon(make_icon("folder", t.c["text_dim"], 16))
        self.reset_btn.setIcon(make_icon("reset", t.c["text_dim"], 16))
        self.save_btn.setIcon(make_icon("save", t.on_accent, 16))
        self.browse.setIcon(make_icon("folder", t.on_accent, 16))
        self.cookie_browse.setIcon(make_icon("folder", t.c["text_dim"], 16))

    def pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Choose download folder", self.path_edit.text())
        if d:
            self.path_edit.setText(d)

    def pick_cookie(self):
        f, _ = QFileDialog.getOpenFileName(self, "Choose cookies file",
                                           self.cookie_edit.text(), "Text files (*.txt);;All files (*)")
        if f:
            self.cookie_edit.setText(f)

    def preview(self):
        self.win.theme.mode = self.mode.currentText()
        self.win.theme.accent_name = self.accent.currentText()
        self.win.theme.font = self.font.currentText()
        self.win.apply_theme()

    def save(self):
        cfg = self.win.cfg
        cfg["output_directory"] = self.path_edit.text()
        cfg["audio_quality"] = self.bitrate.currentText()
        cfg["audio_format"] = self.fmt.currentText()
        cfg["ytdlp_path"] = self.ytdlp_edit.text() or "yt-dlp"
        cfg["cookie_file"] = self.cookie_edit.text()
        cfg["use_cookies"] = (self.use_cookies.currentText() == "Yes")
        cfg["embed_metadata"] = (self.embed.currentText() == "Yes")
        cfg["theme_mode"] = self.mode.currentText()
        cfg["accent"] = self.accent.currentText()
        cfg["font"] = self.font.currentText()
        cfg.save()
        try:
            Path(cfg["output_directory"]).mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self.save_btn.setText("  Saved!")
        QTimer.singleShot(1400, lambda: self.save_btn.setText("  Save Changes"))

    def reset(self):
        self.win.cfg.data = dict(Config.DEFAULTS)
        self.win.cfg.save()
        d = Config.DEFAULTS
        self.path_edit.setText(d["output_directory"])
        self.bitrate.setCurrentText(d["audio_quality"])
        self.fmt.setCurrentText(d["audio_format"])
        self.ytdlp_edit.setText(d["ytdlp_path"])
        self.cookie_edit.setText(d["cookie_file"])
        self.use_cookies.setCurrentText("Yes" if d["use_cookies"] else "No")
        self.embed.setCurrentText("Yes" if d["embed_metadata"] else "No")
        self.mode.setCurrentText(d["theme_mode"])
        self.accent.setCurrentText(d["accent"])
        self.preview()


class DebugPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 36, 40, 24)
        outer.setSpacing(16)
        head = QHBoxLayout()
        title = QLabel("Debug Logs")
        title.setObjectName("H1")
        head.addWidget(title)
        head.addStretch(1)
        self.export_btn = QPushButton("  Export")
        self.copy_btn = QPushButton("  Copy")
        self.clear_btn = QPushButton("  Clear")
        for b, fn in ((self.export_btn, self.export), (self.copy_btn, self.copy),
                      (self.clear_btn, self.clear)):
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            head.addWidget(b)
        outer.addLayout(head)
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(5000)
        self.console.setPlaceholderText("no logs yet…")
        outer.addWidget(self.console, 1)

    def refresh_icons(self):
        t = self.win.theme
        self.export_btn.setIcon(make_icon("download", t.c["text_dim"], 16))
        self.copy_btn.setIcon(make_icon("copy", t.c["text_dim"], 16))
        self.clear_btn.setIcon(make_icon("trash", t.c["text_dim"], 16))

    def append(self, text):
        self.console.appendPlainText(text)

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export logs", "debug.log",
                                              "Log files (*.log *.txt)")
        if path:
            Path(path).write_text(self.console.toPlainText(), encoding="utf-8")

    def copy(self):
        QApplication.clipboard().setText(self.console.toPlainText())

    def clear(self):
        self.console.clear()


class AboutPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 36, 40, 24)
        outer.setSpacing(16)
        title = QLabel("About")
        title.setObjectName("H1")
        outer.addWidget(title)

        tabs = QHBoxLayout()
        tabs.setSpacing(18)
        self.tab_proj = QPushButton("Other Projects")
        self.tab_supp = QPushButton("Support Me")
        for b in (self.tab_proj, self.tab_supp):
            b.setProperty("seg", "true")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
        self.tab_proj.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self.tab_proj)
        grp.addButton(self.tab_supp)
        self.tab_proj.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.tab_supp.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        tabs.addWidget(self.tab_proj)
        tabs.addWidget(self.tab_supp)
        tabs.addStretch(1)
        outer.addLayout(tabs)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        proj = QWidget()
        pl = QHBoxLayout(proj)
        pl.setSpacing(16)
        pl.setAlignment(Qt.AlignTop)
        pl.addWidget(self._project_card(
            APP_NAME, f"v{APP_VERSION}",
            "A PySide6 GUI for downloading YouTube / YouTube Music tracks, albums, "
            "playlists and channels via yt-dlp. Built around the YoutubeMusicDownloader backend.",
            ["Python", "PySide6", "yt-dlp"]))
        pl.addWidget(self._project_card(
            "Your Other Project", "v1.0",
            "Describe another tool of yours here — edit AboutPage to customise.",
            ["Edit", "me"]))
        pl.addStretch(1)
        self.stack.addWidget(proj)

        supp = QWidget()
        sl = QHBoxLayout(supp)
        sl.setSpacing(16)
        sl.setAlignment(Qt.AlignTop)
        c1 = Card()
        c1l = QVBoxLayout(c1)
        c1l.setContentsMargins(20, 24, 20, 24)
        c1l.setSpacing(10)
        h = QLabel("Support via Ko-fi")
        h.setObjectName("H3")
        d = QLabel("Enjoying the project? You can support ongoing development by buying me a coffee.")
        d.setObjectName("Sub")
        d.setWordWrap(True)
        self.kofi = QPushButton("  Support me on Ko-fi")
        self.kofi.setProperty("variant", "accent")
        self.kofi.setCursor(Qt.PointingHandCursor)
        self.kofi.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://ko-fi.com/")))
        c1l.addWidget(h)
        c1l.addWidget(d)
        c1l.addStretch(1)
        c1l.addWidget(self.kofi)
        c1.setFixedWidth(360)

        c2 = Card()
        c2l = QVBoxLayout(c2)
        c2l.setContentsMargins(20, 24, 20, 24)
        c2l.setSpacing(10)
        h2 = QLabel("Crypto (USDT TRC20)")
        h2.setObjectName("H3")
        d2 = QLabel("Crypto donations are also accepted. Copy the address below.")
        d2.setObjectName("Sub")
        d2.setWordWrap(True)
        addr_row = QHBoxLayout()
        self.addr = QLineEdit("YOUR-USDT-ADDRESS-HERE")
        self.addr.setReadOnly(True)
        copy = QPushButton("Copy")
        copy.setCursor(Qt.PointingHandCursor)
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.addr.text()))
        addr_row.addWidget(self.addr, 1)
        addr_row.addWidget(copy)
        c2l.addWidget(h2)
        c2l.addWidget(d2)
        c2l.addStretch(1)
        c2l.addLayout(addr_row)
        c2.setFixedWidth(360)

        sl.addWidget(c1)
        sl.addWidget(c2)
        sl.addStretch(1)
        self.stack.addWidget(supp)

    def _project_card(self, name, version, desc, tags):
        card = Card()
        card.setFixedWidth(340)
        l = QVBoxLayout(card)
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(10)
        top = QHBoxLayout()
        nm = QLabel(name)
        nm.setObjectName("H3")
        ver = QLabel(version)
        ver.setObjectName("Accent")
        top.addWidget(nm)
        top.addStretch(1)
        top.addWidget(ver)
        d = QLabel(desc)
        d.setObjectName("Sub")
        d.setWordWrap(True)
        tagrow = QLabel("  •  ".join(tags))
        tagrow.setObjectName("Faint")
        l.addLayout(top)
        l.addWidget(d)
        l.addStretch(1)
        l.addWidget(tagrow)
        return card

    def refresh_icons(self):
        self.kofi.setIcon(make_icon("coffee", self.win.theme.on_accent, 16))


# ----------------------------------------------------------------------------
# Main window
# ----------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = Config()
        self.history = History()
        self.theme = Theme(self.cfg["theme_mode"], self.cfg["accent"], self.cfg["font"])
        ARCHIVES_DIR.mkdir(exist_ok=True)

        self.setWindowTitle(APP_NAME)
        self.resize(1180, 760)

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(64)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(8, 16, 8, 16)
        sb.setSpacing(8)

        self.nav_buttons = []
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        nav_defs = [("home", "Home"), ("history", "History"),
                    ("settings", "Settings"), ("terminal", "Debug Logs"), ("grid", "About")]
        for i, (icon, tip) in enumerate(nav_defs):
            btn = NavButton(icon, tip, self)
            btn.clicked.connect(lambda _=False, idx=i: self.stack.setCurrentIndex(idx))
            self.nav_group.addButton(btn)
            self.nav_buttons.append(btn)
            sb.addWidget(btn, alignment=Qt.AlignHCenter)
        sb.addStretch(1)
        for icon, tip, url in [("github", "GitHub", "https://github.com/"),
                               ("alert", "Report an issue", "https://github.com/"),
                               ("coffee", "Buy me a coffee", "https://ko-fi.com/")]:
            b = NavButton(icon, tip, self)
            b.setCheckable(False)
            b.clicked.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            self.nav_buttons.append(b)
            sb.addWidget(b, alignment=Qt.AlignHCenter)
        layout.addWidget(sidebar)

        # Pages
        self.stack = QStackedWidget()
        self.home = HomePage(self)
        self.history_page = HistoryPage(self)
        self.settings_page = SettingsPage(self)
        self.debug_page = DebugPage(self)
        self.about_page = AboutPage(self)
        for p in (self.home, self.history_page, self.settings_page, self.debug_page, self.about_page):
            self.stack.addWidget(p)
        layout.addWidget(self.stack, 1)

        self.nav_buttons[0].setChecked(True)
        self.apply_theme()
        self.history_page.render()
        self.log(f"{APP_NAME} v{APP_VERSION} ready.")

    # -- helpers
    def log(self, text):
        self.debug_page.append(text)

    def refresh_history(self):
        self.history_page.render()

    def apply_theme(self):
        QApplication.instance().setStyleSheet(self.theme.qss())
        for b in self.nav_buttons:
            b.refresh()
        for page in (self.home, self.history_page, self.settings_page,
                     self.debug_page, self.about_page):
            if hasattr(page, "refresh_icons"):
                page.refresh_icons()
        if self.home.meta:
            self.home._fill_table(self.home.meta["tracks"])


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()