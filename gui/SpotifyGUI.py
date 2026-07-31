"""
SpotDL Studio — a PySide6 GUI front-end for SpotifyMusicDownloader.

Pages:
  • Home      — URL bar, metadata card (cover + details), track table, progress
  • Batch     — .txt/.csv batch downloads + the retry queue
  • History   — Downloads / Fetches tabs with type filter + text search
  • Settings  — download options (shared with the CLI), cookies, appearance
  • Debug     — live log console with copy / export / clear
  • About     — project + support info

Parity with the CLI backend
---------------------------
This GUI is written to behave like `SpotifyMusicDownloader` rather than merely
call spotdl:

  * settings live in config/SpotifyMusicDownloader.json — the same file the CLI
    reads — so changing a value in either place is visible to the other. Only
    look-and-feel keys go in config/gui_settings.json.
  * download commands are built by `build_download_cmd`, which mirrors
    `run_download`: same flags, same --yt-dlp-args sleep interval, same cookie
    file lookup, same {list-name}/{artist}/{album} output templates, and the
    same history/archives/*.spotdl save files for albums and playlists.
  * failure/throttle detection uses the backend's markers. If tools.RateLimiter
    is importable its `looks_throttled` is used directly so the two can't drift.
  * retries use max_retries with the backend's exponential rate-limit backoff.
  * batch downloads and the retry queue use tools.BatchFile / tools.RetryQueue
    when they are importable, so statuses are written in exactly the format the
    CLI expects. Small local fallbacks keep this file standalone-runnable.

Run:  python spotdl_studio.py
Requires:  pip install PySide6   (and spotdl + ffmpeg on PATH for real downloads)
"""

import os
import re
import csv
import sys
import json
import time
import random
import hashlib
import tempfile
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt, QThread, Signal, QByteArray, QSize, QTimer, QUrl
from PySide6.QtGui import QIcon, QPixmap, QPainter, QFontDatabase, QDesktopServices
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QToolButton, QComboBox, QStackedWidget,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QPlainTextEdit, QFileDialog, QButtonGroup, QScrollArea, QCheckBox,
    QSpinBox, QAbstractItemView, QMessageBox,
)

APP_NAME = "SpotDL Studio"
APP_VERSION = "1.1.0"

CONFIG_DIR = Path("config")
BACKEND_CONFIG = CONFIG_DIR / "SpotifyMusicDownloader.json"   # shared with the CLI
GUI_CONFIG = CONFIG_DIR / "gui_settings.json"                 # appearance only
HISTORY_FILE = CONFIG_DIR / "gui_history.json"
ARCHIVES_DIR = Path("history/archives")
COOKIES_DIR = Path("cookies")
RETRY_QUEUE_FILE = Path("history/retry_queue_spotify.json")

# Same shape checks the backend uses for batch files.
SPOTIFY_LINK = re.compile(
    r"^(?:https?://(?:open|play)\.spotify\.com/\S+|spotify:[a-z]+:[A-Za-z0-9]+)$",
    re.IGNORECASE)
SPOTIFY_URI = re.compile(r"^spotify:([a-z]+):([A-Za-z0-9]+)$", re.IGNORECASE)

# ----------------------------------------------------------------------------
# Optional backend collaborators
# ----------------------------------------------------------------------------
# Importing these keeps the on-disk formats identical to the CLI's. When the GUI
# is run on its own (no tools/ package alongside it) the fallbacks below take
# over, and the only thing lost is byte-for-byte compatibility of the status
# markers with a BatchFile implementation this file cannot see.
try:
    from tools.RateLimiter import looks_throttled as _backend_looks_throttled
except Exception:
    _backend_looks_throttled = None

try:
    from tools.BatchFile import BatchFile as _BackendBatchFile
except Exception:
    _BackendBatchFile = None

try:
    from tools.RetryQueue import RetryQueue as _BackendRetryQueue
except Exception:
    _BackendRetryQueue = None


# spotdl v4's per-track failure lines, copied from run_download so the GUI counts
# a track finished at exactly the same moments the CLI does.
FAIL_MARKERS = ('No results found', 'LookupError', 'AudioProviderError',
                'Error downloading', 'Failed to download')

# Only consulted when tools.RateLimiter is unavailable.
THROTTLE_MARKERS = ('rate-limited by youtube', 'http error 403', 'status 403',
                    'reached a rate/request limit', 'max retries reached',
                    'sign in to confirm', 'too many requests', 'http error 429')


def looks_throttled(line: str) -> bool:
    """Throttle detection, deferring to the backend's definition when present."""
    if _backend_looks_throttled is not None:
        try:
            return bool(_backend_looks_throttled(line))
        except Exception:
            pass
    low = (line or "").lower()
    return any(m in low for m in THROTTLE_MARKERS)


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
    "file":     ('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
                 '<polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/>'
                 '<line x1="8" y1="17" x2="13" y2="17"/>'),
    "layers":   ('<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/>'
                 '<polyline points="2 12 12 17 22 12"/>'),
    "stop":     '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    "reset":    '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
    "save":     '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>',
    "trash":    '<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "copy":     '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "check":    '<polyline points="20 6 9 17 4 12"/>',
    "x":        '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
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
    "Emerald": "#1DB954", "Blue": "#3b82f6", "Purple": "#8b5cf6",
    "Rose": "#f43f5e", "Amber": "#f59e0b", "Cyan": "#06b6d4",
}
OK_COLOR = "#22c55e"
WARN_COLOR = "#f59e0b"
BAD_COLOR = "#ef4444"


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
    def __init__(self, mode="Dark", accent="Emerald", font="Segoe UI"):
        self.mode = mode if mode in PALETTES else "Dark"
        self.accent_name = accent if accent in ACCENTS else "Emerald"
        self.font = font or "Segoe UI"

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
        QLabel#Ok {{ color: {OK_COLOR}; font-size: 12px; }}
        QLabel#Warn {{ color: {WARN_COLOR}; font-size: 12px; }}
        QLabel#Bad {{ color: {BAD_COLOR}; font-size: 12px; }}
        QCheckBox {{ background: transparent; spacing: 8px; }}
        QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px;
                     border: 1px solid {c['border']}; background: {c['surface']}; }}
        QCheckBox::indicator:checked {{ background: {accent}; border: 1px solid {accent}; }}
        QFrame[card="true"] {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 14px; }}
        QFrame#Cover {{ background: {c['surface_alt']}; border: 1px solid {c['border']}; border-radius: 12px; }}
        QFrame#Divider {{ background: {c['border']}; max-height: 1px; min-height: 1px; border: 0; }}
        QLineEdit {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px;
                     padding: 10px 12px; selection-background-color: {accent}; selection-color: {on_accent}; }}
        QLineEdit:focus {{ border: 1px solid {accent}; }}
        QLineEdit:disabled {{ color: {c['text_faint']}; }}
        QComboBox, QSpinBox {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px;
                     padding: 8px 12px; min-height: 18px; }}
        QComboBox:hover, QSpinBox:hover {{ border: 1px solid {accent}; }}
        QComboBox::drop-down {{ border: 0; width: 22px; }}
        QSpinBox::up-button, QSpinBox::down-button {{ width: 16px; border: 0; background: transparent; }}
        QComboBox QAbstractItemView {{ background: {c['surface_alt']}; border: 1px solid {c['border']};
                     selection-background-color: {accent}; selection-color: {on_accent}; padding: 4px; }}
        QPushButton {{ background: {c['surface_alt']}; border: 1px solid {c['border']}; border-radius: 10px;
                       padding: 9px 14px; font-weight: 600; }}
        QPushButton:hover {{ background: {c['hover']}; }}
        QPushButton:disabled {{ color: {c['text_faint']}; }}
        QPushButton[variant="accent"] {{ background: {accent}; color: {on_accent}; border: 0; }}
        QPushButton[variant="accent"]:hover {{ background: {accent_hover}; }}
        QPushButton[variant="accent"]:disabled {{ background: {c['surface_alt']}; color: {c['text_faint']}; }}
        QPushButton[variant="danger"] {{ background: transparent; border: 1px solid {BAD_COLOR}; color: {BAD_COLOR}; }}
        QPushButton[variant="danger"]:hover {{ background: {_rgba(BAD_COLOR, 0.14)}; }}
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
# Config
# ----------------------------------------------------------------------------
class Config:
    """
    Download settings live in the backend's own config file, so the GUI and the
    CLI are reading and writing one set of values rather than two that drift.
    Appearance keys are GUI-only and stay out of that file.
    """

    # Mirrors SpotifyMusicDownloader.load_config()'s primary_config.
    BACKEND_DEFAULTS = dict(
        output_directory=str(Path.home() / "Music" / "Collection" / "Spotify"),
        audio_quality="320k",
        audio_format="mp3",
        max_retries=3,
        retry_delay=10,
        use_cookies=False,
        max_concurrent=2,
        yt_dlp_sleep_min=3,
        yt_dlp_sleep_max=7,
    )
    # GUI-only keys. rate_limit_* mirror the backend's hard-coded attributes of
    # the same names; they are kept here so they stay editable without touching
    # the config file the CLI parses.
    GUI_DEFAULTS = dict(theme_mode="Dark", accent="Emerald", font="Segoe UI",
                        spotdl_path="spotdl", use_archive=True,
                        rate_limit_backoff=300, rate_limit_max_wait=1800)

    BACKEND_KEYS = set(BACKEND_DEFAULTS)

    # The backend accepts every one of these; the old GUI offered a subset and
    # would silently rewrite a config the CLI had set to, say, 96k.
    QUALITIES = ["auto", "disable", "8k", "16k", "24k", "32k", "40k", "48k", "64k",
                 "80k", "96k", "112k", "128k", "160k", "192k", "224k", "256k", "320k"]
    FORMATS = ["mp3", "flac", "ogg", "opus", "m4a", "wav"]

    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.data = dict(self.BACKEND_DEFAULTS)
        self.data.update(self.GUI_DEFAULTS)
        self.load()

    def load(self):
        for path, keys in ((BACKEND_CONFIG, None), (GUI_CONFIG, None)):
            if not path.exists():
                continue
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update(loaded)
            except Exception:
                pass
        # A config written by hand can still be out of range; clamp rather than
        # let spotdl reject the command later.
        if self["audio_quality"] not in self.QUALITIES:
            self["audio_quality"] = self.BACKEND_DEFAULTS["audio_quality"]
        if self["audio_format"] not in self.FORMATS:
            self["audio_format"] = self.BACKEND_DEFAULTS["audio_format"]
        for key in ("max_retries", "retry_delay", "max_concurrent",
                    "yt_dlp_sleep_min", "yt_dlp_sleep_max",
                    "rate_limit_backoff", "rate_limit_max_wait"):
            try:
                self[key] = int(self[key])
            except (TypeError, ValueError):
                self[key] = self.BACKEND_DEFAULTS.get(key, self.GUI_DEFAULTS.get(key))
        if self["yt_dlp_sleep_max"] < self["yt_dlp_sleep_min"]:
            self["yt_dlp_sleep_max"] = self["yt_dlp_sleep_min"]

    def __getitem__(self, k):
        if k in self.data:
            return self.data[k]
        return self.BACKEND_DEFAULTS.get(k, self.GUI_DEFAULTS.get(k))

    def __setitem__(self, k, v):
        self.data[k] = v

    def snapshot(self) -> dict:
        """A plain dict for handing to a worker thread."""
        return dict(self.data)

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        # Preserve any backend keys this GUI doesn't know about (a future
        # setting added on the CLI side shouldn't be wiped by pressing Save).
        backend = {}
        if BACKEND_CONFIG.exists():
            try:
                loaded = json.loads(BACKEND_CONFIG.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    backend = loaded
            except Exception:
                backend = {}
        backend.update({k: self[k] for k in self.BACKEND_KEYS})
        backend["output_directory"] = str(backend["output_directory"])
        BACKEND_CONFIG.write_text(json.dumps(backend, indent=2, ensure_ascii=False),
                                  encoding="utf-8")

        gui = {k: self[k] for k in self.GUI_DEFAULTS}
        GUI_CONFIG.write_text(json.dumps(gui, indent=2, ensure_ascii=False), encoding="utf-8")

    def reset(self):
        self.data = dict(self.BACKEND_DEFAULTS)
        self.data.update(self.GUI_DEFAULTS)


class History:
    def __init__(self):
        self.entries = []
        if HISTORY_FILE.exists():
            try:
                loaded = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    self.entries = loaded
            except Exception:
                self.entries = []

    def add(self, category, item_type, title, url, status="", error=""):
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
        try:
            HISTORY_FILE.write_text(json.dumps(self.entries, indent=2, ensure_ascii=False),
                                    encoding="utf-8")
        except OSError:
            pass


# ----------------------------------------------------------------------------
# Batch file + retry queue (backend collaborators, with standalone fallbacks)
# ----------------------------------------------------------------------------
_STATUS_COMMENT = re.compile(r"\s*#\s*(?:spotdl-)?status\s*=\s*(\w+)\s*$", re.IGNORECASE)


class _FallbackBatchFile:
    """
    Minimal stand-in for tools.BatchFile, used only when that module isn't
    importable. Statuses are written as a trailing `# status=success` comment on
    .txt lines and into a `status` column for .csv, and parse() reads back what
    it wrote, so a resume works even without the real implementation.
    """

    def __init__(self, on_error=None, backup_dir="history/backups"):
        self.on_error = on_error or (lambda *_a, **_k: None)
        self.backup_dir = Path(backup_dir)

    def parse(self, path):
        path = Path(path)
        try:
            if path.suffix.lower() == ".csv":
                return self._parse_csv(path)
            return self._parse_txt(path)
        except Exception as e:
            self.on_error(f"Could not read {path}: {e}")
            return []

    def _parse_txt(self, path):
        entries = []
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            status = ""
            m = _STATUS_COMMENT.search(line)
            if m:
                status = m.group(1).lower()
                line = _STATUS_COMMENT.sub("", line).strip()
            if not line:
                continue
            entries.append(dict(url=line, title="", status=status))
        return entries

    @staticmethod
    def _pick(header, *candidates):
        for i, name in enumerate(header):
            low = (name or "").strip().lower()
            if any(c in low for c in candidates):
                return i
        return None

    def _parse_csv(self, path):
        with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            rows = list(csv.reader(fh))
        if not rows:
            return []
        header = rows[0]
        url_col = self._pick(header, "url", "uri", "link")
        if url_col is None:
            # Headerless file: assume the first column holds the links.
            url_col, title_col, status_col, body = 0, None, None, rows
        else:
            title_col = self._pick(header, "track name", "title", "song", "name")
            status_col = self._pick(header, "status")
            body = rows[1:]
        entries = []
        for row in body:
            if len(row) <= url_col:
                continue
            url = (row[url_col] or "").strip()
            if not url:
                continue
            title = (row[title_col].strip() if title_col is not None and len(row) > title_col else "")
            status = (row[status_col].strip().lower()
                      if status_col is not None and len(row) > status_col else "")
            entries.append(dict(url=url, title=title, status=status))
        return entries

    def mark_statuses(self, path, statuses):
        if not statuses:
            return True
        path = Path(path)
        try:
            if path.suffix.lower() == ".csv":
                return self._mark_csv(path, statuses)
            return self._mark_txt(path, statuses)
        except Exception as e:
            self.on_error(f"Could not update {path}: {e}")
            return False

    def _mark_txt(self, path, statuses):
        out = []
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.rstrip("\n")
            bare = _STATUS_COMMENT.sub("", line).strip()
            if bare in statuses:
                out.append(f"{bare}  # status={statuses[bare]}")
            else:
                out.append(line)
        self._backup(path)
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
        return True

    def _mark_csv(self, path, statuses):
        with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            rows = list(csv.reader(fh))
        if not rows:
            return False
        header = rows[0]
        url_col = self._pick(header, "url", "uri", "link")
        if url_col is None:
            return False
        status_col = self._pick(header, "status")
        if status_col is None:
            header.append("status")
            status_col = len(header) - 1
        for row in rows[1:]:
            while len(row) <= status_col:
                row.append("")
            if len(row) > url_col and row[url_col].strip() in statuses:
                row[status_col] = statuses[row[url_col].strip()]
        self._backup(path)
        with path.open("w", encoding="utf-8", newline="") as fh:
            csv.writer(fh).writerows(rows)
        return True

    def _backup(self, path):
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            (self.backup_dir / f"{path.stem}-{stamp}{path.suffix}").write_bytes(path.read_bytes())
        except Exception:
            pass   # a missing backup is not a reason to abandon the run


class _FallbackRetryQueue:
    """Minimal stand-in for tools.RetryQueue, keyed by URL like the real one."""

    def __init__(self, path=RETRY_QUEUE_FILE, on_error=None):
        self.path = Path(path)
        self.on_error = on_error or (lambda *_a, **_k: None)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self):
        if not self.path.exists():
            return {}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, dict) else {}
        except Exception as e:
            self.on_error(f"Could not read retry queue: {e}")
            return {}

    @property
    def count(self):
        return len(self.read())

    def _write(self, queue):
        try:
            self.path.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            self.on_error(f"Could not write retry queue: {e}")

    def add_failure(self, url, title="", error="", source="", throttled=False):
        queue = self.read()
        entry = queue.get(url, dict(url=url, attempts=0))
        entry.update(url=url, title=title or entry.get("title", ""), error=error,
                     source=source or entry.get("source", ""), throttled=bool(throttled),
                     attempts=int(entry.get("attempts", 0)) + 1,
                     last_attempt=datetime.now().isoformat(timespec="seconds"))
        queue[url] = entry
        self._write(queue)

    def clear(self, urls=None):
        queue = self.read()
        if urls is None:
            queue = {}
        else:
            for url in urls:
                queue.pop(url, None)
        self._write(queue)


def make_batch_file(on_error):
    if _BackendBatchFile is not None:
        try:
            return _BackendBatchFile(on_error=on_error, backup_dir="history/backups")
        except Exception:
            pass
    return _FallbackBatchFile(on_error=on_error)


def make_retry_queue(on_error):
    if _BackendRetryQueue is not None:
        try:
            return _BackendRetryQueue(str(RETRY_QUEUE_FILE), on_error=on_error)
        except Exception:
            pass
    return _FallbackRetryQueue(RETRY_QUEUE_FILE, on_error=on_error)


# ----------------------------------------------------------------------------
# spotdl command construction (mirrors SpotifyMusicDownloader.run_download)
# ----------------------------------------------------------------------------
def fmt_dur(sec):
    try:
        m, s = divmod(int(float(sec)), 60)
        return f"{m}:{s:02d}"
    except Exception:
        return "--:--"


def url_kind(url: str) -> str:
    """track / album / playlist / artist, from the URL or URI path segment."""
    low = (url or "").lower()
    for kind in ("playlist", "album", "artist", "track"):
        if f"/{kind}/" in low or f":{kind}:" in low:
            return kind
    return "track"


def to_spotify_url(value: str) -> str:
    """spotify:track:<id> -> https://open.spotify.com/track/<id>; else unchanged."""
    match = SPOTIFY_URI.match((value or "").strip())
    if not match:
        return (value or "").strip()
    kind, spotify_id = match.group(1).lower(), match.group(2)
    return f"https://open.spotify.com/{kind}/{spotify_id}"


def is_spotify_link(url: str) -> bool:
    return bool(SPOTIFY_LINK.match((url or "").strip()))


def cookie_file_for(cfg: dict, log=None):
    """Same lookup order as the backend's _get_cookie_file."""
    if not cfg.get("use_cookies"):
        return None
    if COOKIES_DIR.is_dir():
        candidates = sorted(COOKIES_DIR.glob("*.txt"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            return str(candidates[0])
    if log:
        log("[warn] Cookies are enabled but no cookie file was found in cookies/. "
            "Add one with the Cookie Manager, or turn cookies off in Settings.")
    return None


def output_template(cfg: dict, kind: str) -> str:
    """The backend's per-type templates, verbatim."""
    out = Path(cfg["output_directory"])
    if kind == "playlist":
        return str(out / "{list-name}" / "{artist} - {title}.{output-ext}")
    if kind == "album":
        return str(out / "{artist}" / "{album}" / "{artist} - {title}.{output-ext}")
    if kind == "artist":
        return str(out / "{artist}.{output-ext}")
    return str(out / "{artist} - {title}.{output-ext}")


def archive_path_for(url: str) -> Path:
    """
    history/archives/<type>_<id>.spotdl, matching _download_item's naming so a
    GUI download and a CLI download of the same album share one save file.
    """
    ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    if 'album' in url:
        m = re.search(r'album/([a-zA-Z0-9]+)', url)
        return ARCHIVES_DIR / (f"album_{m.group(1)}.spotdl" if m else f"album_{url_hash}.spotdl")
    if 'playlist' in url:
        m = re.search(r'playlist/([a-zA-Z0-9]+)', url)
        return ARCHIVES_DIR / (f"playlist_{m.group(1)}.spotdl" if m else f"playlist_{url_hash}.spotdl")
    return ARCHIVES_DIR / f"track_{url_hash}.spotdl"


def build_download_cmd(cfg: dict, url: str, kind: str = None, template: str = None,
                       use_archive: bool = False, log=None):
    """
    Build the spotdl argv exactly as run_download does: same flag order, the
    --yt-dlp-args sleep interval that keeps YouTube from throttling, the cookie
    file when enabled, and the album/playlist save file.
    """
    kind = kind or url_kind(url)
    cmd = [
        cfg.get("spotdl_path") or "spotdl", "download", url,
        "--format", cfg["audio_format"],
        "--bitrate", cfg["audio_quality"],
        "--output", template or output_template(cfg, kind),
        "--overwrite", "skip",
        "--print-errors",
        "--threads", str(cfg["max_concurrent"]),
    ]

    sleep_min = int(cfg.get("yt_dlp_sleep_min") or 0)
    sleep_max = int(cfg.get("yt_dlp_sleep_max") or 0)
    if sleep_min:
        sleep_args = f"--sleep-interval {sleep_min}"
        if sleep_max:
            sleep_args += f" --max-sleep-interval {sleep_max}"
        cmd.extend(["--yt-dlp-args", sleep_args])

    cookie_file = cookie_file_for(cfg, log)
    if cookie_file:
        cmd.extend(["--cookie-file", cookie_file])

    if use_archive and cfg.get("use_archive", True):
        cmd.extend(["--save-file", str(archive_path_for(url))])

    return cmd


def run_spotdl(cmd, on_log=None, on_track=None, on_progress=None,
               should_stop=None, total=0, titles=()):
    """
    Run one spotdl invocation and return the backend's stats dict.

    Counting matches run_download: a track is finished on a success, a skip, or
    a failure marker, and 'succeeded' therefore excludes files already on disk.
    """
    on_log = on_log or (lambda _s: None)
    should_stop = should_stop or (lambda: False)
    titles = list(titles or [])
    stats = dict(succeeded=0, skipped=0, failed=0, failed_items=[],
                 rate_limited=False, returncode=-1, cancelled=False)

    def match_title(line):
        low = line.lower()
        for t in titles:
            if t and t.lower()[:30] in low:
                return t
        return None

    try:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace",
                                bufsize=1, env=env)
    except FileNotFoundError:
        on_log(f"[error] '{cmd[0]}' not found. Install spotdl or set its path in Settings.")
        stats["failed"] = total or 1
        stats["failed_items"].append("spotdl executable not found")
        return stats
    except Exception as e:
        on_log(f"[error] could not start spotdl: {e}")
        stats["failed"] = total or 1
        stats["failed_items"].append(str(e))
        return stats

    done = 0
    output_lines = []
    for line in iter(proc.stdout.readline, ""):
        if should_stop():
            stats["cancelled"] = True
            proc.terminate()
            break
        line = line.strip()
        if not line:
            continue
        on_log(line)
        output_lines.append(line)
        if len(output_lines) > 1000:
            output_lines = output_lines[-200:]

        if not stats["rate_limited"] and looks_throttled(line):
            stats["rate_limited"] = True
            on_log("[warn] throttling detected — backing off before the next attempt")

        is_success = 'Downloaded "' in line
        is_skip = 'Skipping ' in line
        is_fail = any(m in line for m in FAIL_MARKERS)
        if not (is_success or is_skip or is_fail):
            continue

        if is_fail:
            stats["failed"] += 1
            stats["failed_items"].append(line)
            status = "failed"
        elif is_skip:
            stats["skipped"] += 1
            status = "skipped"
        else:
            stats["succeeded"] += 1
            status = "downloaded"

        if on_track:
            title = match_title(line)
            if title:
                on_track(title, status)
        if not total or done < total:
            done += 1
            if on_progress:
                on_progress(done, total)

    try:
        proc.wait(timeout=20)
    except Exception:
        proc.kill()
    stats["returncode"] = proc.returncode if proc.returncode is not None else -1

    if total and done < total and not stats["cancelled"]:
        if on_progress:
            on_progress(total, total)

    if not stats["cancelled"] and stats["returncode"] != 0 and not stats["failed_items"]:
        keywords = ('error', 'fail', 'blocked', 'unavailable', 'private',
                    'forbidden', 'not found', 'quota', 'rate limit')
        stats["failed_items"] = [l for l in output_lines
                                 if any(k in l.lower() for k in keywords)][-5:] or output_lines[-3:]
    return stats


def run_succeeded(stats: dict) -> bool:
    """
    run_download's success rule: exit 0 counts, except when nothing downloaded,
    nothing was already on disk, and at least one track failed.
    """
    if stats.get("cancelled") or stats.get("returncode") != 0:
        return False
    if stats.get("failed") and not stats.get("succeeded") and not stats.get("skipped"):
        return False
    return True


def error_summary(stats: dict) -> str:
    """One line worth storing in the retry queue (backend's _last_error_summary)."""
    stats = stats or {}
    if stats.get("rate_limited"):
        return "Rate-limited by YouTube/Spotify - retry later"
    items = stats.get("failed_items") or []
    if items:
        return str(items[-1])[:300]
    return "spotdl reported a failure"


def backoff_seconds(cfg: dict, streak: int) -> float:
    """rate_limit_backoff * 2**(streak-1), capped — the backend's curve."""
    base = float(cfg.get("rate_limit_backoff", 300))
    cap = float(cfg.get("rate_limit_max_wait", 1800))
    return min(base * (2 ** max(streak - 1, 0)), cap)


# ----------------------------------------------------------------------------
# Workers
# ----------------------------------------------------------------------------
class MetadataWorker(QThread):
    """`spotdl save` writes a .spotdl JSON, so no Spotify account is needed."""

    done = Signal(dict)
    error = Signal(str)
    log = Signal(str)

    def __init__(self, url, spotdl_path="spotdl"):
        super().__init__()
        self.url = to_spotify_url(url)
        self.spotdl = spotdl_path or "spotdl"

    def run(self):
        kind = url_kind(self.url)
        tmp = Path(tempfile.gettempdir()) / f"spotdl_studio_meta_{os.getpid()}.spotdl"
        tmp.unlink(missing_ok=True)
        cmd = [self.spotdl, "save", self.url, "--save-file", str(tmp)]
        self.log.emit(f"[meta] fetching metadata for {self.url}")
        try:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", env=env, timeout=180)
            for ln in (proc.stdout or "").splitlines():
                if ln.strip():
                    self.log.emit("[meta] " + ln.strip())
            if not tmp.exists():
                if proc.stderr:
                    self.log.emit("[meta] " + proc.stderr.strip()[:500])
                self.error.emit("Could not fetch metadata. Check the URL, and that spotdl is "
                                "installed and reachable at the path set in Settings.")
                return

            songs = json.loads(tmp.read_text(encoding="utf-8"))
            if isinstance(songs, dict):
                songs = [songs]
            if not songs:
                self.error.emit("No tracks found for this URL.")
                return

            first = songs[0]
            if kind == "playlist":
                title = first.get("list_name") or "Playlist"
                subtitle = first.get("list_publisher") or f"{len(songs)} tracks"
            elif kind == "album":
                title = first.get("album_name") or "Album"
                subtitle = first.get("album_artist") or ", ".join(first.get("artists", []))
            elif kind == "artist":
                title = first.get("artist") or "Artist"
                subtitle = f"{len(songs)} tracks"
            else:
                title = first.get("name") or "Track"
                subtitle = ", ".join(first.get("artists", [])) or first.get("artist", "")

            tracks = []
            for s in songs:
                # Older save files carry song_id instead of a full url; the
                # per-row download button needs one or the other.
                track_url = s.get("url") or ""
                if not track_url and s.get("song_id"):
                    track_url = f"https://open.spotify.com/track/{s['song_id']}"
                tracks.append(dict(
                    name=s.get("name", "Unknown"),
                    artists=", ".join(s.get("artists", [])) or s.get("artist", ""),
                    album=s.get("album_name", ""),
                    duration=fmt_dur(s.get("duration", 0)),
                    url=track_url,
                ))

            self.done.emit(dict(kind=kind, title=title, subtitle=subtitle,
                                cover_url=first.get("cover_url", ""),
                                count=len(songs), tracks=tracks, source_url=self.url))
        except subprocess.TimeoutExpired:
            self.error.emit("Metadata fetch timed out after 3 minutes.")
        except FileNotFoundError:
            self.error.emit(f"'{self.spotdl}' not found. Install spotdl or set its path in Settings.")
        except json.JSONDecodeError:
            self.error.emit("spotdl wrote a save file this build could not parse.")
        except Exception as e:
            self.error.emit(f"Metadata error: {e}")
        finally:
            tmp.unlink(missing_ok=True)


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


class _StoppableThread(QThread):
    """Shared cancel plumbing: a flag the runner polls, plus an interruptible wait."""

    def __init__(self):
        super().__init__()
        self._stop = False

    def stop(self):
        self._stop = True

    def stopped(self):
        return self._stop

    def sleep_interruptible(self, seconds, tick=None):
        """Sleep in 0.25s slices so Cancel doesn't have to wait out a backoff."""
        end = time.monotonic() + max(seconds, 0)
        while not self._stop:
            remaining = end - time.monotonic()
            if remaining <= 0:
                return True
            if tick:
                tick(remaining)
            time.sleep(min(0.25, remaining))
        return False


class DownloadWorker(_StoppableThread):
    """
    One track / album / playlist download, with the backend's retry behaviour:
    max_retries attempts, retry_delay between ordinary failures, and exponential
    rate-limit backoff (rate_limit_backoff * 2**(n-1), capped) after throttling.
    """

    log = Signal(str)
    progress = Signal(int, int)        # done, total
    track_status = Signal(str, str)    # title, downloaded|skipped|failed
    attempt = Signal(int, int)         # attempt, max_retries
    waiting = Signal(float)            # seconds left before the next attempt
    finished_stats = Signal(dict)

    def __init__(self, cfg: dict, url: str, kind: str, total: int, titles,
                 use_archive: bool = False):
        super().__init__()
        self.cfg = cfg
        self.url = url
        self.kind = kind
        self.total = int(total or 0)
        self.titles = list(titles or [])
        self.use_archive = use_archive

    def run(self):
        max_retries = max(int(self.cfg.get("max_retries", 3)), 1)
        stats = dict(succeeded=0, skipped=0, failed=0, failed_items=[],
                     rate_limited=False, returncode=-1, cancelled=False)
        attempts_used = 0

        for attempt in range(1, max_retries + 1):
            if self.stopped():
                stats["cancelled"] = True
                break
            attempts_used = attempt
            self.attempt.emit(attempt, max_retries)

            if attempt > 1:
                if stats.get("rate_limited"):
                    wait = backoff_seconds(self.cfg, attempt - 1)
                    self.log.emit(f"[retry] rate limited — holding off {wait:.0f}s. "
                                  f"Already-downloaded tracks will be skipped.")
                else:
                    wait = float(self.cfg.get("retry_delay", 10))
                    self.log.emit(f"[retry] waiting {wait:.0f}s before attempt {attempt}.")
                if not self.sleep_interruptible(wait, self.waiting.emit):
                    stats["cancelled"] = True
                    break

            cmd = build_download_cmd(self.cfg, self.url, self.kind,
                                     use_archive=self.use_archive, log=self.log.emit)
            self.log.emit(f"[download] {' '.join(cmd)}")
            stats = run_spotdl(cmd,
                               on_log=self.log.emit,
                               on_track=self.track_status.emit,
                               on_progress=self.progress.emit,
                               should_stop=self.stopped,
                               total=self.total, titles=self.titles)
            if stats.get("cancelled") or run_succeeded(stats):
                break

        stats["attempts"] = attempts_used
        stats["succeeded_run"] = run_succeeded(stats)
        self.finished_stats.emit(stats)


class BatchWorker(_StoppableThread):
    """
    Batch downloads, one link at a time, mirroring download_from_file: statuses
    written back per link, failures pushed to the retry queue, and a stop after
    three consecutive rate-limited links rather than burning every retry.
    """

    log = Signal(str)
    item_started = Signal(int, int, str)     # index, total, label
    item_finished = Signal(int, str, str)    # index, status, detail
    finished_stats = Signal(dict)
    waiting = Signal(float)

    def __init__(self, cfg: dict, entries, source_path, template, batch_file, retry_queue,
                 from_queue=False):
        super().__init__()
        self.cfg = cfg
        self.entries = list(entries)
        self.source_path = Path(source_path) if source_path else None
        self.template = template
        self.batch_file = batch_file
        self.retry_queue = retry_queue
        self.from_queue = from_queue

    def _download_one(self, url, label):
        """_download_with_retry for a single link, with progress kept quiet."""
        max_retries = max(int(self.cfg.get("max_retries", 3)), 1)
        stats = {}
        for attempt in range(1, max_retries + 1):
            if self.stopped():
                stats["cancelled"] = True
                break
            if attempt > 1:
                if stats.get("rate_limited"):
                    wait = backoff_seconds(self.cfg, attempt - 1)
                else:
                    wait = float(self.cfg.get("retry_delay", 10))
                self.log.emit(f"[retry] {label}: attempt {attempt}/{max_retries} in {wait:.0f}s")
                if not self.sleep_interruptible(wait, self.waiting.emit):
                    stats["cancelled"] = True
                    break
            cmd = build_download_cmd(self.cfg, to_spotify_url(url), "track",
                                     template=self.template, log=self.log.emit)
            stats = run_spotdl(cmd, on_log=self.log.emit, should_stop=self.stopped,
                               total=1, titles=[label])
            if stats.get("cancelled") or run_succeeded(stats):
                break
        return stats

    def run(self):
        total = len(self.entries)
        succeeded = failed = 0
        pending = {}
        cleared = []
        rate_limit_streak = 0
        throttled_out = False
        per_source = {}
        started = time.monotonic()

        for index, entry in enumerate(self.entries, 1):
            if self.stopped():
                break
            url = entry["url"]
            label = entry.get("title") or url
            self.item_started.emit(index, total, str(label)[:80])

            stats = self._download_one(url, str(label)[:40])
            if stats.get("cancelled"):
                break

            source = entry.get("source") or (str(self.source_path) if self.source_path else "")
            if run_succeeded(stats):
                succeeded += 1
                rate_limit_streak = 0
                cleared.append(url)
                pending[url] = "success"
                if source:
                    per_source.setdefault(source, {})[url] = "success"
                self.item_finished.emit(index, "success", "done")
            else:
                failed += 1
                detail = error_summary(stats)
                pending[url] = "failed"
                self.retry_queue.add_failure(url, entry.get("title", ""), detail, source,
                                             throttled=bool(stats.get("rate_limited")))
                if stats.get("rate_limited"):
                    rate_limit_streak += 1
                    self.item_finished.emit(index, "rate_limited", "rate limited → retry queue")
                else:
                    rate_limit_streak = 0
                    self.item_finished.emit(index, "failed", "failed → retry queue")

            # Flushed per link: an interrupted run should not lose results the
            # screen has already reported.
            if self.source_path and not self.from_queue and pending:
                if self.batch_file.mark_statuses(self.source_path, pending):
                    pending = {}

            if rate_limit_streak >= 3:
                throttled_out = True
                self.log.emit("[stop] three rate-limited links in a row — stopping. Re-run "
                              "later and the finished links will be skipped.")
                break

            if index < total:
                if rate_limit_streak:
                    wait = backoff_seconds(self.cfg, rate_limit_streak)
                    self.log.emit(f"[wait] rate limited — holding off {wait:.0f}s before the next link")
                else:
                    # spotdl's own --sleep-interval only applies within one
                    # invocation, not between them.
                    wait = random.uniform(float(self.cfg.get("yt_dlp_sleep_min", 3)),
                                          float(self.cfg.get("yt_dlp_sleep_max", 7)))
                if not self.sleep_interruptible(wait, self.waiting.emit):
                    break

        if self.source_path and not self.from_queue and pending:
            self.batch_file.mark_statuses(self.source_path, pending)
        if self.from_queue:
            for source, statuses in per_source.items():
                source_path = Path(source)
                if source_path.is_file():
                    self.batch_file.mark_statuses(source_path, statuses)
        if cleared:
            self.retry_queue.clear(cleared)

        self.finished_stats.emit(dict(
            succeeded=succeeded, failed=failed, total=total,
            attempted=succeeded + failed, throttled_out=throttled_out,
            cancelled=self.stopped(), elapsed=time.monotonic() - started))


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


def heading(text, level="H3"):
    lbl = QLabel(text)
    lbl.setObjectName(level)
    return lbl


# ----------------------------------------------------------------------------
# Home
# ----------------------------------------------------------------------------
class HomePage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.meta = None
        self.dl_worker = None
        self.img_worker = None
        self.mw = None
        self._row_of = {}
        self._cur = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 36, 40, 24)
        outer.setSpacing(14)

        outer.addWidget(heading(APP_NAME, "H1"))
        outer.addWidget(heading("Fetch a Spotify track, album, playlist or artist, then download "
                                "it with the same settings the CLI uses.", "Sub"))

        # Search row
        searchrow = QHBoxLayout()
        searchrow.setSpacing(10)
        self.search_icon = QLabel()
        self.search_icon.setFixedWidth(20)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://open.spotify.com/playlist/…  or  spotify:album:…")
        self.url_edit.returnPressed.connect(self.fetch)
        self.fetch_btn = QPushButton("  Fetch")
        self.fetch_btn.setProperty("variant", "accent")
        self.fetch_btn.setCursor(Qt.PointingHandCursor)
        self.fetch_btn.clicked.connect(self.fetch)
        searchrow.addWidget(self.search_icon)
        searchrow.addWidget(self.url_edit, 1)
        searchrow.addWidget(self.fetch_btn)
        outer.addLayout(searchrow)

        # Status / progress / cancel
        statusrow = QHBoxLayout()
        statusrow.setSpacing(10)
        self.status = QLabel("")
        self.status.setObjectName("Faint")
        self.cancel_btn = QPushButton("  Cancel")
        self.cancel_btn.setProperty("variant", "danger")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.cancel_download)
        self.cancel_btn.setVisible(False)
        statusrow.addWidget(self.status, 1)
        statusrow.addWidget(self.cancel_btn)
        outer.addLayout(statusrow)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
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
        self.kind_lbl = heading("", "Accent")
        self.meta_title = heading("—", "H2")
        self.meta_title.setWordWrap(True)
        self.meta_sub = heading("", "Sub")
        self.meta_count = heading("", "Faint")
        self.dest_lbl = heading("", "Faint")
        self.dest_lbl.setWordWrap(True)

        btnrow = QHBoxLayout()
        self.dl_all = QPushButton("  Download All")
        self.dl_all.setProperty("variant", "accent")
        self.dl_all.setCursor(Qt.PointingHandCursor)
        self.dl_all.clicked.connect(self.download_all)
        self.open_btn = QPushButton("Open in Spotify")
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.clicked.connect(self._open_in_spotify)
        self.open_folder_btn = QPushButton("  Open Folder")
        self.open_folder_btn.setCursor(Qt.PointingHandCursor)
        self.open_folder_btn.clicked.connect(self.win.open_output_dir)
        btnrow.addWidget(self.dl_all)
        btnrow.addWidget(self.open_btn)
        btnrow.addWidget(self.open_folder_btn)
        btnrow.addStretch(1)

        for w in (self.kind_lbl, self.meta_title, self.meta_sub, self.meta_count, self.dest_lbl):
            info.addWidget(w)
        info.addStretch(1)
        info.addLayout(btnrow)
        mc.addLayout(info, 1)
        outer.addWidget(self.meta_card)

        # Track table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["#", "Title", "Album", "Length", "Status", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        h = self.table.horizontalHeader()
        for col, mode in ((0, QHeaderView.ResizeToContents), (1, QHeaderView.Stretch),
                          (2, QHeaderView.Stretch), (3, QHeaderView.ResizeToContents),
                          (4, QHeaderView.ResizeToContents), (5, QHeaderView.ResizeToContents)):
            h.setSectionResizeMode(col, mode)
        self.table.setVisible(False)
        outer.addWidget(self.table, 1)

    # -- theming hook
    def refresh_icons(self):
        t = self.win.theme
        self.search_icon.setPixmap(make_icon("search", t.c["text_faint"], 20).pixmap(20, 20))
        self.fetch_btn.setIcon(make_icon("fetch", t.on_accent, 18))
        self.dl_all.setIcon(make_icon("download", t.on_accent, 18))
        self.cancel_btn.setIcon(make_icon("stop", BAD_COLOR, 16))
        self.open_folder_btn.setIcon(make_icon("folder", t.c["text_dim"], 16))
        if self.meta:
            self._fill_table(self.meta["tracks"])

    def _open_in_spotify(self):
        if self.meta:
            QDesktopServices.openUrl(QUrl(self.meta["source_url"]))

    def busy(self):
        return bool(self.dl_worker and self.dl_worker.isRunning())

    # -- fetch
    def fetch(self):
        raw = self.url_edit.text().strip()
        url = to_spotify_url(raw)
        if not is_spotify_link(raw) and not url.startswith("http"):
            self.status.setText("That doesn't look like a Spotify link or URI.")
            return
        if self.mw and self.mw.isRunning():
            return
        self.status.setText("Fetching metadata…")
        self.fetch_btn.setEnabled(False)
        self.mw = MetadataWorker(url, self.win.cfg["spotdl_path"])
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
        self.status.setText("Metadata fetched.")
        self.kind_lbl.setText(meta["kind"].upper())
        self.meta_title.setText(meta["title"])
        self.meta_sub.setText(meta["subtitle"])
        self.meta_count.setText(f"{meta['count']} track{'s' if meta['count'] != 1 else ''}")
        self.dest_lbl.setText("Saves to  " + output_template(self.win.cfg.snapshot(), meta["kind"]))
        self.meta_card.setVisible(True)
        self.cover_img.clear()
        if meta["cover_url"]:
            self.img_worker = ImageWorker(meta["cover_url"])
            self.img_worker.loaded.connect(self._cover_loaded)
            self.img_worker.start()
        self._fill_table(meta["tracks"])

        if meta["kind"] == "artist":
            # Kept in step with the backend's own note on download_artist.
            self.status.setText("Metadata fetched. Note: artist downloads are still unreliable "
                                "in spotdl — album by album is safer.")
        self.win.history.add("fetch", meta["kind"], meta["title"], meta["source_url"], "fetched")
        self.win.refresh_history()

    def _cover_loaded(self, data):
        pm = QPixmap()
        if pm.loadFromData(QByteArray(data)):
            self.cover_img.setPixmap(pm)

    def _fill_table(self, tracks):
        self.table.setRowCount(0)
        self._row_of = {}
        self.table.setVisible(True)
        for i, tr in enumerate(tracks, 1):
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setRowHeight(r, 52)
            self.table.setItem(r, 0, QTableWidgetItem(str(i)))
            self.table.setItem(r, 1, QTableWidgetItem(f"{tr['name']}\n{tr['artists']}"))
            self.table.setItem(r, 2, QTableWidgetItem(tr["album"]))
            self.table.setItem(r, 3, QTableWidgetItem(tr["duration"]))
            self.table.setItem(r, 4, QTableWidgetItem(""))
            btn = QPushButton()
            btn.setProperty("variant", "dlbtn")
            btn.setIcon(make_icon("download", self.win.theme.on_accent, 16))
            btn.setFixedSize(34, 30)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip("Download this track" if tr["url"] else "No direct URL for this track")
            btn.setEnabled(bool(tr["url"]))
            btn.clicked.connect(lambda _=False, u=tr["url"], n=tr["name"]: self.download_one(u, n))
            wrap = QWidget()
            wl = QHBoxLayout(wrap)
            wl.setContentsMargins(4, 0, 8, 0)
            wl.addWidget(btn)
            self.table.setCellWidget(r, 5, wrap)
            self._row_of.setdefault(tr["name"], r)

    # -- downloads
    def download_all(self):
        if not self.meta:
            return
        titles = [t["name"] for t in self.meta["tracks"]]
        # Albums and playlists get a --save-file archive, as in _download_item.
        use_archive = self.meta["kind"] in ("album", "playlist", "artist")
        self._start(self.meta["source_url"], self.meta["kind"], self.meta["count"],
                    titles, self.meta["title"], use_archive)

    def download_one(self, url, name):
        if not url:
            self.status.setText("No direct URL for this track.")
            return
        self._start(url, "track", 1, [name], name, False)

    def _start(self, url, kind, total, titles, title, use_archive):
        if self.busy():
            self.status.setText("A download is already running.")
            return
        if self.win.batch_page.busy():
            self.status.setText("A batch download is running — let it finish or cancel it first.")
            return
        try:
            Path(self.win.cfg["output_directory"]).mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.status.setText(f"Cannot create the output folder: {e}")
            return

        self._cur = dict(kind=kind, title=title, url=url)
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 4)
            if item:
                item.setText("")
        self.status.setText(f"Downloading {title}…")
        self.progress.setVisible(True)
        self.progress.setRange(0, total or 0)
        self.progress.setValue(0)
        self.dl_all.setEnabled(False)
        self.fetch_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)

        self.dl_worker = DownloadWorker(self.win.cfg.snapshot(), url, kind, total, titles,
                                        use_archive=use_archive)
        self.dl_worker.log.connect(self.win.log)
        self.dl_worker.progress.connect(self._on_progress)
        self.dl_worker.track_status.connect(self._on_track_status)
        self.dl_worker.attempt.connect(self._on_attempt)
        self.dl_worker.waiting.connect(self._on_waiting)
        self.dl_worker.finished_stats.connect(self._on_finished)
        self.dl_worker.start()

    def cancel_download(self):
        if self.busy():
            self.dl_worker.stop()
            self.status.setText("Cancelling…")

    def _on_attempt(self, attempt, total):
        if attempt > 1:
            self.win.log(f"[attempt] {attempt}/{total}")

    def _on_waiting(self, remaining):
        self.status.setText(f"Waiting {remaining:.0f}s before the next attempt…")

    def _on_progress(self, done, total):
        if total:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
            self.status.setText(f"Downloading… {done}/{total}")
        else:
            self.progress.setRange(0, 0)
            self.status.setText(f"Downloading… {done} done")

    def _on_track_status(self, title, status):
        row = self._row_of.get(title)
        if row is None:
            return
        item = self.table.item(row, 4)
        if item:
            item.setText({"downloaded": "✓ saved", "skipped": "• on disk",
                          "failed": "✕ failed"}.get(status, status))

    def _on_finished(self, stats):
        self.dl_all.setEnabled(True)
        self.fetch_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)

        if stats.get("cancelled"):
            msg = "Cancelled. Finished tracks stay on disk and will be skipped next time."
            status = "cancelled"
        else:
            ok = stats.get("succeeded_run")
            attempts = int(stats.get("attempts", 1))
            head = "Done" if ok else "Finished with problems"
            msg = (f"{head} — {stats['succeeded']} downloaded, "
                   f"{stats['skipped']} already on disk, {stats['failed']} failed.")
            if attempts > 1:
                msg += f" ({attempts} attempts)"
            if stats.get("rate_limited"):
                msg += " YouTube rate-limit detected — try again later."
            status = "completed" if ok else "partial/failed"
        self.status.setText(msg)

        c = self._cur or {}
        self.win.history.add("download", c.get("kind", "track"), c.get("title", ""),
                             c.get("url", ""), status,
                             error="" if status == "completed" else error_summary(stats))
        self.win.refresh_history()


# ----------------------------------------------------------------------------
# Batch + retry queue
# ----------------------------------------------------------------------------
class BatchPage(QWidget):
    """
    The GUI half of download_from_file / download_from_retry_queue: pick a .txt
    or .csv, see what will actually be attempted after de-duplication, then run
    the links one at a time with statuses written back to the source file.
    """

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.path = None
        self.entries = []
        self.rows = []
        self.worker = None
        self.mode = "file"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 36, 40, 24)
        outer.setSpacing(14)
        outer.addWidget(heading("Batch & Retry", "H1"))
        outer.addWidget(heading("Download a file of links one at a time, or re-attempt everything "
                                "sitting in the retry queue.", "Sub"))

        tabs = QHBoxLayout()
        tabs.setSpacing(18)
        self.tab_file = QPushButton("From File")
        self.tab_queue = QPushButton("Retry Queue")
        for b, mode in ((self.tab_file, "file"), (self.tab_queue, "queue")):
            b.setProperty("seg", "true")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, m=mode: self.switch(m))
        self.tab_file.setChecked(True)
        grp = QButtonGroup(self)
        grp.setExclusive(True)
        grp.addButton(self.tab_file)
        grp.addButton(self.tab_queue)
        tabs.addWidget(self.tab_file)
        tabs.addWidget(self.tab_queue)
        tabs.addStretch(1)
        outer.addLayout(tabs)

        # File picker row
        pickrow = QHBoxLayout()
        pickrow.setSpacing(10)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Path to a .txt or .csv of Spotify links…")
        self.path_edit.returnPressed.connect(lambda: self.load_file(self.path_edit.text()))
        self.browse_btn = QPushButton("  Browse")
        self.browse_btn.setCursor(Qt.PointingHandCursor)
        self.browse_btn.clicked.connect(self.pick_file)
        self.reload_btn = QPushButton("  Reload")
        self.reload_btn.setCursor(Qt.PointingHandCursor)
        self.reload_btn.clicked.connect(self.reload)
        pickrow.addWidget(self.path_edit, 1)
        pickrow.addWidget(self.browse_btn)
        pickrow.addWidget(self.reload_btn)
        self.pickrow_host = QWidget()
        self.pickrow_host.setLayout(pickrow)
        outer.addWidget(self.pickrow_host)

        # Summary + controls
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)
        self.summary = heading("No file loaded.", "Faint")
        self.subfolder = QCheckBox("Save into a subfolder named after the file")
        self.subfolder.setChecked(True)
        self.start_btn = QPushButton("  Start")
        self.start_btn.setProperty("variant", "accent")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start)
        self.cancel_btn = QPushButton("  Cancel")
        self.cancel_btn.setProperty("variant", "danger")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self.cancel)
        self.clear_queue_btn = QPushButton("  Empty Queue")
        self.clear_queue_btn.setCursor(Qt.PointingHandCursor)
        self.clear_queue_btn.setVisible(False)
        self.clear_queue_btn.clicked.connect(self.clear_queue)
        ctrl.addWidget(self.summary, 1)
        ctrl.addWidget(self.subfolder)
        ctrl.addWidget(self.clear_queue_btn)
        ctrl.addWidget(self.start_btn)
        ctrl.addWidget(self.cancel_btn)
        outer.addLayout(ctrl)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        outer.addWidget(self.progress)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "Link / Title", "State", "Detail"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        outer.addWidget(self.table, 1)

    def refresh_icons(self):
        t = self.win.theme
        self.browse_btn.setIcon(make_icon("file", t.c["text_dim"], 16))
        self.reload_btn.setIcon(make_icon("reset", t.c["text_dim"], 16))
        self.start_btn.setIcon(make_icon("download", t.on_accent, 16))
        self.cancel_btn.setIcon(make_icon("stop", BAD_COLOR, 16))
        self.clear_queue_btn.setIcon(make_icon("trash", t.c["text_dim"], 16))

    def busy(self):
        return bool(self.worker and self.worker.isRunning())

    # -- mode
    def switch(self, mode):
        if self.busy():
            self.tab_file.setChecked(self.mode == "file")
            self.tab_queue.setChecked(self.mode == "queue")
            return
        self.mode = mode
        is_file = mode == "file"
        self.pickrow_host.setVisible(is_file)
        self.subfolder.setVisible(is_file)
        self.clear_queue_btn.setVisible(not is_file)
        if is_file:
            self.reload()
        else:
            self.load_queue()

    # -- file mode
    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a batch file", "",
                                              "Link lists (*.txt *.csv);;All files (*)")
        if path:
            self.load_file(path)

    def reload(self):
        if self.mode != "file":
            return
        text = self.path_edit.text().strip()
        if text:
            self.load_file(text)
        else:
            self.entries = []
            self._render([])
            self.summary.setText("No file loaded.")
            self.start_btn.setEnabled(False)

    def load_file(self, raw, render=True):
        path = Path(str(raw or "").strip().strip('"').strip("'")).expanduser()
        self.path_edit.setText(str(path))
        if not path.is_file():
            self.summary.setText(f"No such file: {path}")
            self.start_btn.setEnabled(False)
            self._render([])
            return
        self.path = path

        parsed = self.win.batch_file.parse(path) or []
        # Same filtering as download_from_file: de-duplicate keeping order, drop
        # non-Spotify links, skip anything already marked success.
        seen, valid = set(), []
        invalid = already = 0
        for entry in parsed:
            url = (entry.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            if not is_spotify_link(url):
                invalid += 1
                continue
            if (entry.get("status") or "").lower() == "success":
                already += 1
                continue
            valid.append(dict(url=url, title=entry.get("title", "")))
        duplicates = max(len(parsed) - len(seen), 0)

        self.entries = valid
        self.start_btn.setEnabled(bool(valid))
        if not render:
            # Called straight after a run: the table is showing per-link
            # outcomes worth keeping, so only the entry list is refreshed.
            return
        bits = [f"{len(parsed)} links read"]
        if duplicates:
            bits.append(f"{duplicates} duplicate")
        if invalid:
            bits.append(f"{invalid} not Spotify")
        if already:
            bits.append(f"{already} already done")
        bits.append(f"{len(valid)} to download")
        self.summary.setText("  •  ".join(bits))
        self._render(valid)

    # -- queue mode
    def load_queue(self, render=True):
        queue = self.win.retry_queue.read() or {}
        items = sorted(queue.values(), key=lambda e: int(e.get("attempts", 0)))
        self.entries = [dict(url=e["url"], title=e.get("title", ""), source=e.get("source", ""))
                        for e in items if e.get("url")]
        self.start_btn.setEnabled(bool(self.entries))
        if not render:
            return
        self.summary.setText(f"{len(self.entries)} link(s) queued for retry."
                             if self.entries else "The retry queue is empty.")
        self._render(self.entries, details=[e.get("error", "") for e in items])

    def clear_queue(self):
        if self.busy():
            return
        self.win.retry_queue.clear(None)
        self.win.log("[queue] retry queue emptied.")
        self.load_queue()

    def _render(self, entries, details=None):
        self.table.setRowCount(0)
        self.rows = []
        for i, entry in enumerate(entries, 1):
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setRowHeight(r, 40)
            self.table.setItem(r, 0, QTableWidgetItem(str(i)))
            self.table.setItem(r, 1, QTableWidgetItem(entry.get("title") or entry["url"]))
            self.table.setItem(r, 2, QTableWidgetItem("waiting"))
            detail = (details[i - 1] if details and i <= len(details) else "")
            self.table.setItem(r, 3, QTableWidgetItem(str(detail)[:120]))
            self.rows.append(r)

    # -- run
    def start(self):
        if self.busy() or not self.entries:
            return
        if self.win.home.busy():
            self.summary.setText("A download is running on the Home page — finish or cancel it first.")
            return
        cfg = self.win.cfg.snapshot()
        target = Path(cfg["output_directory"])
        if self.mode == "queue":
            target = target / "Retries"
        elif self.subfolder.isChecked() and self.path is not None:
            safe = re.sub(r'[<>:"/\\|?*]+', "_", self.path.stem).strip() or "Batch"
            target = target / safe
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.summary.setText(f"Cannot create {target}: {e}")
            return

        template = str(target / "{artist} - {title}.{output-ext}")
        self.win.log(f"[batch] {len(self.entries)} link(s) → {target}")
        self.progress.setVisible(True)
        self.progress.setRange(0, len(self.entries))
        self.progress.setValue(0)
        self.start_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.tab_file.setEnabled(False)
        self.tab_queue.setEnabled(False)

        self.worker = BatchWorker(cfg, self.entries,
                                  None if self.mode == "queue" else self.path,
                                  template, self.win.batch_file, self.win.retry_queue,
                                  from_queue=self.mode == "queue")
        self.worker.log.connect(self.win.log)
        self.worker.item_started.connect(self._item_started)
        self.worker.item_finished.connect(self._item_finished)
        self.worker.waiting.connect(self._waiting)
        self.worker.finished_stats.connect(self._done)
        self.worker.start()

    def cancel(self):
        if self.busy():
            self.worker.stop()
            self.summary.setText("Cancelling after the current link…")

    def _item_started(self, index, total, label):
        row = index - 1
        if 0 <= row < self.table.rowCount():
            self.table.setItem(row, 2, QTableWidgetItem("downloading"))
            self.table.scrollToItem(self.table.item(row, 1))
        self.summary.setText(f"[{index}/{total}] {label}")

    def _item_finished(self, index, status, detail):
        row = index - 1
        if 0 <= row < self.table.rowCount():
            self.table.setItem(row, 2, QTableWidgetItem(status))
            self.table.setItem(row, 3, QTableWidgetItem(detail))
        self.progress.setValue(index)

    def _waiting(self, remaining):
        if remaining > 2:
            self.summary.setText(f"Waiting {remaining:.0f}s before the next link…")

    def _done(self, stats):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.progress.setVisible(False)
        self.tab_file.setEnabled(True)
        self.tab_queue.setEnabled(True)

        parts = [f"{stats['succeeded']} succeeded", f"{stats['failed']} failed"]
        if stats["attempted"] < stats["total"]:
            parts.append(f"{stats['total'] - stats['attempted']} not attempted")
        parts.append(f"{stats['elapsed'] / 60:.1f} min")
        tail = ""
        if stats.get("cancelled"):
            tail = " — cancelled; re-run and finished links are skipped."
        elif stats.get("throttled_out"):
            tail = " — stopped after three rate-limited links; try again later."
        elif stats["failed"]:
            tail = " — failures are in the retry queue."
        self.summary.setText("  •  ".join(parts) + tail)

        label = (self.path.name if self.path and self.mode == "file" else "Retry queue")
        self.win.history.add("download", "batch", label,
                             str(self.path) if self.path and self.mode == "file" else "",
                             "completed" if not stats["failed"] and not stats.get("cancelled")
                             else "partial/failed")
        self.win.refresh_history()
        # Re-read what is left to attempt, but leave the table showing this
        # run's per-link outcomes; Reload redraws it when the user wants that.
        if self.mode == "queue":
            self.load_queue(render=False)
        elif self.path is not None:
            self.load_file(self.path, render=False)


# ----------------------------------------------------------------------------
# History
# ----------------------------------------------------------------------------
class HistoryPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.category = "download"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 36, 40, 24)
        outer.setSpacing(14)
        outer.addWidget(heading("History", "H1"))

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
        self.type_filter.addItems(["All types", "Track", "Album", "Playlist", "Artist", "Batch"])
        self.type_filter.currentIndexChanged.connect(self.render)
        self.type_filter.setFixedWidth(160)
        filt.addWidget(self.search, 1)
        filt.addWidget(self.type_filter)
        outer.addLayout(filt)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Type", "Title", "Status", "Detail", "When"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.itemDoubleClicked.connect(self._open_row)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        outer.addWidget(self.table, 1)

        self.empty = heading("No history yet. Your activity will appear here.", "Faint")
        self.empty.setAlignment(Qt.AlignCenter)
        outer.addWidget(self.empty)

    def refresh_icons(self):
        self.clear_btn.setIcon(make_icon("trash", self.win.theme.c["text_dim"], 16))

    def switch(self, cat):
        self.category = cat
        self.render()

    def clear(self):
        self.win.history.clear(self.category)
        self.render()

    def _open_row(self, item):
        row = item.row()
        if 0 <= row < len(self._visible):
            url = self._visible[row].get("url", "")
            if url.startswith("http"):
                QDesktopServices.openUrl(QUrl(url))

    def render(self):
        q = self.search.text().lower().strip()
        tf = self.type_filter.currentText().lower()
        rows = [e for e in self.win.history.entries if e.get("category") == self.category]
        if tf != "all types":
            rows = [e for e in rows if (e.get("type") or "").lower() == tf]
        if q:
            rows = [e for e in rows
                    if q in (str(e.get("title", "")) + str(e.get("url", ""))).lower()]
        self._visible = rows

        self.table.setRowCount(0)
        self.empty.setVisible(not rows)
        self.table.setVisible(bool(rows))
        for e in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setRowHeight(r, 44)
            self.table.setItem(r, 0, QTableWidgetItem(str(e.get("type", "")).title()))
            title_item = QTableWidgetItem(e.get("title", ""))
            title_item.setToolTip(e.get("url", ""))
            self.table.setItem(r, 1, title_item)
            self.table.setItem(r, 2, QTableWidgetItem(e.get("status", "")))
            self.table.setItem(r, 3, QTableWidgetItem(str(e.get("error", ""))[:120]))
            self.table.setItem(r, 4, QTableWidgetItem(e.get("time", "")))


# ----------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------
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
        head.addWidget(heading("Settings", "H1"))
        head.addStretch(1)
        self.check_btn = QPushButton("  Check Dependencies")
        self.check_btn.setCursor(Qt.PointingHandCursor)
        self.check_btn.clicked.connect(self.check_deps)
        self.open_cfg = QPushButton("  Config Folder")
        self.open_cfg.setCursor(Qt.PointingHandCursor)
        self.open_cfg.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(CONFIG_DIR.resolve()))))
        self.reset_btn = QPushButton("  Reset")
        self.reset_btn.setCursor(Qt.PointingHandCursor)
        self.reset_btn.clicked.connect(self.reset)
        self.save_btn = QPushButton("  Save Changes")
        self.save_btn.setProperty("variant", "accent")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self.save)
        for b in (self.check_btn, self.open_cfg, self.reset_btn, self.save_btn):
            head.addWidget(b)
        outer.addLayout(head)

        outer.addWidget(heading("These are the same values config/SpotifyMusicDownloader.json "
                                "holds, so the CLI picks them up too.", "Sub"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(40)
        grid.setVerticalSpacing(14)
        outer.addLayout(grid)

        cfg = self.win.cfg
        row = 0
        grid.addWidget(heading("Download Path"), row, 0)
        row += 1
        pathrow = QHBoxLayout()
        self.path_edit = QLineEdit(str(cfg["output_directory"]))
        self.browse = QPushButton("  Browse")
        self.browse.setProperty("variant", "accent")
        self.browse.setCursor(Qt.PointingHandCursor)
        self.browse.clicked.connect(self.pick_dir)
        pathrow.addWidget(self.path_edit, 1)
        pathrow.addWidget(self.browse)
        pw = QWidget()
        pw.setLayout(pathrow)
        grid.addWidget(pw, row, 0)
        row += 1

        grid.addWidget(heading("Bitrate"), row, 0)
        row += 1
        self.bitrate = QComboBox()
        self.bitrate.addItems(Config.QUALITIES)
        self.bitrate.setCurrentText(cfg["audio_quality"])
        grid.addWidget(self.bitrate, row, 0)
        row += 1

        grid.addWidget(heading("Conversion Format"), row, 0)
        row += 1
        self.fmt = QComboBox()
        self.fmt.addItems(Config.FORMATS)
        self.fmt.setCurrentText(cfg["audio_format"])
        grid.addWidget(self.fmt, row, 0)
        row += 1

        grid.addWidget(heading("Concurrent Downloads (spotdl --threads)"), row, 0)
        row += 1
        self.threads = QSpinBox()
        self.threads.setRange(1, 8)
        self.threads.setValue(int(cfg["max_concurrent"]))
        grid.addWidget(self.threads, row, 0)
        row += 1

        grid.addWidget(heading("spotdl Executable"), row, 0)
        row += 1
        self.spotdl_edit = QLineEdit(cfg["spotdl_path"])
        grid.addWidget(self.spotdl_edit, row, 0)
        row += 1

        # Right column
        rrow = 0
        grid.addWidget(heading("Retries & Throttling"), rrow, 1)
        rrow += 1
        retryrow = QHBoxLayout()
        self.retries = QSpinBox()
        self.retries.setRange(1, 10)
        self.retries.setValue(int(cfg["max_retries"]))
        self.retries.setToolTip("Attempts per item before giving up (max_retries)")
        self.retry_delay = QSpinBox()
        self.retry_delay.setRange(0, 600)
        self.retry_delay.setSuffix(" s")
        self.retry_delay.setValue(int(cfg["retry_delay"]))
        self.retry_delay.setToolTip("Wait between ordinary retries (retry_delay)")
        retryrow.addWidget(self.retries, 1)
        retryrow.addWidget(self.retry_delay, 1)
        rw = QWidget()
        rw.setLayout(retryrow)
        grid.addWidget(rw, rrow, 1)
        rrow += 1

        grid.addWidget(heading("yt-dlp Sleep Interval (min / max)"), rrow, 1)
        rrow += 1
        sleeprow = QHBoxLayout()
        self.sleep_min = QSpinBox()
        self.sleep_min.setRange(0, 120)
        self.sleep_min.setSuffix(" s")
        self.sleep_min.setValue(int(cfg["yt_dlp_sleep_min"]))
        self.sleep_max = QSpinBox()
        self.sleep_max.setRange(0, 300)
        self.sleep_max.setSuffix(" s")
        self.sleep_max.setValue(int(cfg["yt_dlp_sleep_max"]))
        self.sleep_min.valueChanged.connect(
            lambda v: self.sleep_max.setValue(max(v, self.sleep_max.value())))
        sleeprow.addWidget(self.sleep_min, 1)
        sleeprow.addWidget(self.sleep_max, 1)
        sw = QWidget()
        sw.setLayout(sleeprow)
        grid.addWidget(sw, rrow, 1)
        rrow += 1

        grid.addWidget(heading("Rate-limit Backoff (base / cap)"), rrow, 1)
        rrow += 1
        backrow = QHBoxLayout()
        self.backoff = QSpinBox()
        self.backoff.setRange(0, 3600)
        self.backoff.setSuffix(" s")
        self.backoff.setValue(int(cfg["rate_limit_backoff"]))
        self.backoff_cap = QSpinBox()
        self.backoff_cap.setRange(0, 7200)
        self.backoff_cap.setSuffix(" s")
        self.backoff_cap.setValue(int(cfg["rate_limit_max_wait"]))
        backrow.addWidget(self.backoff, 1)
        backrow.addWidget(self.backoff_cap, 1)
        bw = QWidget()
        bw.setLayout(backrow)
        grid.addWidget(bw, rrow, 1)
        rrow += 1

        self.cookies = QCheckBox("Use cookies from cookies/ (age- and region-locked audio)")
        self.cookies.setChecked(bool(cfg["use_cookies"]))
        self.cookies.stateChanged.connect(self._cookie_hint)
        grid.addWidget(self.cookies, rrow, 1)
        rrow += 1
        self.cookie_note = heading("", "Faint")
        self.cookie_note.setWordWrap(True)
        grid.addWidget(self.cookie_note, rrow, 1)
        rrow += 1

        self.archive = QCheckBox("Keep a .spotdl save file per album/playlist")
        self.archive.setChecked(bool(cfg["use_archive"]))
        self.archive.setToolTip(f"Written to {ARCHIVES_DIR}, shared with the CLI")
        grid.addWidget(self.archive, rrow, 1)
        rrow += 1

        # Appearance
        outer.addWidget(heading("Appearance", "H2"))
        appearance = QGridLayout()
        appearance.setHorizontalSpacing(40)
        appearance.setVerticalSpacing(14)
        outer.addLayout(appearance)

        appearance.addWidget(heading("Theme Mode"), 0, 0)
        self.mode = QComboBox()
        self.mode.addItems(list(PALETTES.keys()))
        self.mode.setCurrentText(cfg["theme_mode"])
        self.mode.currentTextChanged.connect(self.preview)
        appearance.addWidget(self.mode, 1, 0)

        appearance.addWidget(heading("Accent"), 0, 1)
        self.accent = QComboBox()
        self.accent.addItems(list(ACCENTS.keys()))
        self.accent.setCurrentText(cfg["accent"])
        self.accent.currentTextChanged.connect(self.preview)
        appearance.addWidget(self.accent, 1, 1)

        appearance.addWidget(heading("Font"), 0, 2)
        self.font = QComboBox()
        fams = sorted(set(QFontDatabase.families()))
        common = ["Segoe UI", "Inter", "Roboto", "Arial", "Helvetica Neue"]
        self._fonts = [f for f in common if f in fams] + [f for f in fams if f not in common]
        self.font.addItems(self._fonts or ["Segoe UI"])
        if cfg["font"] in self._fonts:
            self.font.setCurrentText(cfg["font"])
        self.font.currentTextChanged.connect(self.preview)
        appearance.addWidget(self.font, 1, 2)

        self.note = heading("Appearance previews instantly. Save Changes writes download settings "
                            "to config/SpotifyMusicDownloader.json and appearance to "
                            "config/gui_settings.json.", "Faint")
        self.note.setWordWrap(True)
        outer.addWidget(self.note)
        outer.addStretch(1)
        self._cookie_hint()

    def refresh_icons(self):
        t = self.win.theme
        self.check_btn.setIcon(make_icon("check", t.c["text_dim"], 16))
        self.open_cfg.setIcon(make_icon("folder", t.c["text_dim"], 16))
        self.reset_btn.setIcon(make_icon("reset", t.c["text_dim"], 16))
        self.save_btn.setIcon(make_icon("save", t.on_accent, 16))
        self.browse.setIcon(make_icon("folder", t.on_accent, 16))

    def _cookie_hint(self, *_):
        if not self.cookies.isChecked():
            self.cookie_note.setText("")
            return
        found = cookie_file_for(dict(use_cookies=True))
        self.cookie_note.setText(f"Using {found}" if found else
                                 "No .txt cookie file found in cookies/ — export one with the "
                                 "CLI's Cookie Manager first.")

    def pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Choose download folder", self.path_edit.text())
        if d:
            self.path_edit.setText(d)

    def preview(self):
        self.win.theme.mode = self.mode.currentText()
        self.win.theme.accent_name = self.accent.currentText()
        self.win.theme.font = self.font.currentText()
        self.win.apply_theme()

    def check_deps(self):
        """A quick spotdl/ffmpeg probe, the GUI counterpart of troubleshooting()."""
        lines = []
        for name, args in ((self.spotdl_edit.text() or "spotdl", ["--version"]),
                           ("ffmpeg", ["-version"])):
            try:
                proc = subprocess.run([name] + args, capture_output=True, text=True,
                                      encoding="utf-8", errors="replace", timeout=30)
                first = (proc.stdout or proc.stderr or "").strip().splitlines()
                lines.append(f"{name}: {'ok — ' + first[0][:60] if first else 'ok'}")
            except FileNotFoundError:
                lines.append(f"{name}: NOT FOUND on PATH")
            except Exception as e:
                lines.append(f"{name}: {e}")
        for ln in lines:
            self.win.log("[deps] " + ln)
        QMessageBox.information(self, "Dependencies", "\n".join(lines))

    def save(self):
        cfg = self.win.cfg
        cfg["output_directory"] = self.path_edit.text().strip() or \
            Config.BACKEND_DEFAULTS["output_directory"]
        cfg["audio_quality"] = self.bitrate.currentText()
        cfg["audio_format"] = self.fmt.currentText()
        cfg["max_concurrent"] = self.threads.value()
        cfg["max_retries"] = self.retries.value()
        cfg["retry_delay"] = self.retry_delay.value()
        cfg["yt_dlp_sleep_min"] = self.sleep_min.value()
        cfg["yt_dlp_sleep_max"] = max(self.sleep_max.value(), self.sleep_min.value())
        cfg["use_cookies"] = self.cookies.isChecked()
        cfg["use_archive"] = self.archive.isChecked()
        cfg["rate_limit_backoff"] = self.backoff.value()
        cfg["rate_limit_max_wait"] = max(self.backoff_cap.value(), self.backoff.value())
        cfg["spotdl_path"] = self.spotdl_edit.text().strip() or "spotdl"
        cfg["theme_mode"] = self.mode.currentText()
        cfg["accent"] = self.accent.currentText()
        cfg["font"] = self.font.currentText()
        cfg.save()
        try:
            Path(cfg["output_directory"]).mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.win.log(f"[warn] could not create output directory: {e}")
        self.win.log("[config] settings saved to " + str(BACKEND_CONFIG))
        self.save_btn.setText("  Saved!")
        QTimer.singleShot(1400, lambda: self.save_btn.setText("  Save Changes"))
        self._cookie_hint()

    def reset(self):
        self.win.cfg.reset()
        self.win.cfg.save()
        d = self.win.cfg
        self.path_edit.setText(str(d["output_directory"]))
        self.bitrate.setCurrentText(d["audio_quality"])
        self.fmt.setCurrentText(d["audio_format"])
        self.threads.setValue(int(d["max_concurrent"]))
        self.retries.setValue(int(d["max_retries"]))
        self.retry_delay.setValue(int(d["retry_delay"]))
        self.sleep_min.setValue(int(d["yt_dlp_sleep_min"]))
        self.sleep_max.setValue(int(d["yt_dlp_sleep_max"]))
        self.backoff.setValue(int(d["rate_limit_backoff"]))
        self.backoff_cap.setValue(int(d["rate_limit_max_wait"]))
        self.cookies.setChecked(bool(d["use_cookies"]))
        self.archive.setChecked(bool(d["use_archive"]))
        self.spotdl_edit.setText(d["spotdl_path"])
        self.mode.setCurrentText(d["theme_mode"])
        self.accent.setCurrentText(d["accent"])
        if d["font"] in self._fonts:
            self.font.setCurrentText(d["font"])
        self.preview()


# ----------------------------------------------------------------------------
# Debug + About
# ----------------------------------------------------------------------------
class DebugPage(QWidget):
    MAX_LINES = 5000

    def __init__(self, win):
        super().__init__()
        self.win = win
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 36, 40, 24)
        outer.setSpacing(14)
        head = QHBoxLayout()
        head.addWidget(heading("Debug Logs", "H1"))
        head.addStretch(1)
        self.follow = QCheckBox("Follow output")
        self.follow.setChecked(True)
        head.addWidget(self.follow)
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
        self.console.setMaximumBlockCount(self.MAX_LINES)
        self.console.setPlaceholderText("no logs yet…")
        outer.addWidget(self.console, 1)

    def refresh_icons(self):
        t = self.win.theme
        self.export_btn.setIcon(make_icon("download", t.c["text_dim"], 16))
        self.copy_btn.setIcon(make_icon("copy", t.c["text_dim"], 16))
        self.clear_btn.setIcon(make_icon("trash", t.c["text_dim"], 16))

    def append(self, text):
        stamp = datetime.now().strftime("%H:%M:%S")
        bar = self.console.verticalScrollBar()
        at_end = bar.value() >= bar.maximum() - 4
        self.console.appendPlainText(f"{stamp}  {text}")
        if self.follow.isChecked() and at_end:
            bar.setValue(bar.maximum())

    def export(self):
        default = f"spotdl-studio-{datetime.now():%Y%m%d-%H%M%S}.log"
        path, _ = QFileDialog.getSaveFileName(self, "Export logs", default,
                                              "Log files (*.log *.txt)")
        if path:
            try:
                Path(path).write_text(self.console.toPlainText(), encoding="utf-8")
            except OSError as e:
                QMessageBox.warning(self, "Export failed", str(e))

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
        outer.setSpacing(14)
        outer.addWidget(heading("About", "H1"))

        tabs = QHBoxLayout()
        tabs.setSpacing(18)
        self.tab_proj = QPushButton("Project")
        self.tab_supp = QPushButton("Support Me")
        for b in (self.tab_proj, self.tab_supp):
            b.setProperty("seg", "true")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
        self.tab_proj.setChecked(True)
        grp = QButtonGroup(self)
        grp.setExclusive(True)
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
            "PySide6 front-end for the SpotifyMusicDownloader CLI. Shares its config file, "
            "output templates, save-file archives, retry queue and throttling rules.",
            ["Python", "PySide6", "spotdl"]))
        pl.addWidget(self._project_card(
            "SpotifyMusicDownloader", "CLI",
            "The backend: menu-driven downloads, batch files, retry queue, cookie manager and "
            "shared rate limiting across the Spotify and YouTube tools.",
            ["Python", "spotdl", "yt-dlp"]))
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
        c1l.addWidget(heading("Support via Ko-fi"))
        d = heading("Enjoying the project? You can support ongoing development by buying me a "
                    "coffee.", "Sub")
        d.setWordWrap(True)
        c1l.addWidget(d)
        self.kofi = QPushButton("  Support me on Ko-fi")
        self.kofi.setProperty("variant", "accent")
        self.kofi.setCursor(Qt.PointingHandCursor)
        self.kofi.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://ko-fi.com/")))
        c1l.addStretch(1)
        c1l.addWidget(self.kofi)
        c1.setFixedWidth(360)

        c2 = Card()
        c2l = QVBoxLayout(c2)
        c2l.setContentsMargins(20, 24, 20, 24)
        c2l.setSpacing(10)
        c2l.addWidget(heading("Crypto (USDT TRC20)"))
        d2 = heading("Crypto donations are also accepted. Copy the address below.", "Sub")
        d2.setWordWrap(True)
        c2l.addWidget(d2)
        addr_row = QHBoxLayout()
        self.addr = QLineEdit("YOUR-USDT-ADDRESS-HERE")
        self.addr.setReadOnly(True)
        copy_btn = QPushButton("Copy")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.addr.text()))
        addr_row.addWidget(self.addr, 1)
        addr_row.addWidget(copy_btn)
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
        top.addWidget(heading(name))
        top.addStretch(1)
        top.addWidget(heading(version, "Accent"))
        d = heading(desc, "Sub")
        d.setWordWrap(True)
        l.addLayout(top)
        l.addWidget(d)
        l.addStretch(1)
        l.addWidget(heading("  •  ".join(tags), "Faint"))
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
        self.batch_file = make_batch_file(on_error=lambda m: self.log("[batch] " + str(m)))
        self.retry_queue = make_retry_queue(on_error=lambda m: self.log("[queue] " + str(m)))

        self.setWindowTitle(APP_NAME)
        self.resize(1200, 780)
        self.setMinimumSize(900, 600)

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(64)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(8, 16, 8, 16)
        sb.setSpacing(8)

        self.nav_buttons = []
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        nav_defs = [("home", "Home"), ("layers", "Batch & Retry"), ("history", "History"),
                    ("settings", "Settings"), ("terminal", "Debug Logs"), ("grid", "About")]
        for i, (icon, tip) in enumerate(nav_defs):
            btn = NavButton(icon, tip, self)
            btn.clicked.connect(lambda _=False, idx=i: self.stack.setCurrentIndex(idx))
            self.nav_group.addButton(btn)
            self.nav_buttons.append(btn)
            sb.addWidget(btn, alignment=Qt.AlignHCenter)
        sb.addStretch(1)

        for icon, tip, url in [("folder", "Open download folder", None),
                               ("github", "GitHub", "https://github.com/"),
                               ("alert", "Report an issue", "https://github.com/"),
                               ("coffee", "Buy me a coffee", "https://ko-fi.com/")]:
            b = NavButton(icon, tip, self)
            b.setCheckable(False)
            if url is None:
                b.clicked.connect(self.open_output_dir)
            else:
                b.clicked.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            self.nav_buttons.append(b)
            sb.addWidget(b, alignment=Qt.AlignHCenter)
        layout.addWidget(sidebar)

        # Pages. Debug is built first so anything logged during construction of
        # the others has somewhere to go.
        self.stack = QStackedWidget()
        self.debug_page = DebugPage(self)
        self.home = HomePage(self)
        self.batch_page = BatchPage(self)
        self.history_page = HistoryPage(self)
        self.settings_page = SettingsPage(self)
        self.about_page = AboutPage(self)
        self.pages = [self.home, self.batch_page, self.history_page,
                      self.settings_page, self.debug_page, self.about_page]
        for p in self.pages:
            self.stack.addWidget(p)
        layout.addWidget(self.stack, 1)

        self.nav_buttons[0].setChecked(True)
        self.apply_theme()
        self.history_page.render()
        self.batch_page.switch("file")

        self.log(f"{APP_NAME} v{APP_VERSION} ready.")
        self.log(f"[config] settings from {BACKEND_CONFIG} — output {self.cfg['output_directory']}")
        if _BackendBatchFile is None or _BackendRetryQueue is None:
            self.log("[note] tools.BatchFile / tools.RetryQueue not importable — using the "
                     "built-in fallbacks. Run this file from the project root to share the "
                     "CLI's exact batch formats.")
        queued = 0
        try:
            queued = self.retry_queue.count
        except Exception:
            pass
        if queued:
            self.log(f"[queue] {queued} link(s) waiting in the retry queue.")

    # -- helpers
    def log(self, text):
        self.debug_page.append(str(text))

    def refresh_history(self):
        self.history_page.render()

    def open_output_dir(self):
        path = Path(self.cfg["output_directory"])
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.log(f"[warn] {e}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def apply_theme(self):
        QApplication.instance().setStyleSheet(self.theme.qss())
        for b in self.nav_buttons:
            b.refresh()
        for page in self.pages:
            if hasattr(page, "refresh_icons"):
                page.refresh_icons()

    def closeEvent(self, event):
        running = [w for w in (getattr(self.home, "dl_worker", None),
                               getattr(self.batch_page, "worker", None))
                   if w is not None and w.isRunning()]
        if running:
            answer = QMessageBox.question(
                self, "Quit?",
                "A download is still running. Stop it and quit?\n\n"
                "Finished tracks stay on disk and will be skipped next time.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            for w in running:
                w.stop()
                w.wait(5000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()