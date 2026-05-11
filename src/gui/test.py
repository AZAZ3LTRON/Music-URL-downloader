"""
YouTube Music Downloader - PySide6 GUI
A sleek, dark-themed interface for the yt-dlp based music downloader.
"""

import sys
import os
import json
import subprocess
import threading
import time
import re
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QCheckBox, QProgressBar,
    QTextEdit, QFileDialog, QFrame, QStackedWidget, QScrollArea,
    QGridLayout, QSizePolicy, QMessageBox, QSpacerItem, QSlider,
    QTabWidget, QListWidget, QListWidgetItem, QGroupBox
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QTimer, QPropertyAnimation, QEasingCurve,
    QSize, QPoint, QRect, QObject, Slot
)
from PySide6.QtGui import (
    QFont, QFontDatabase, QIcon, QPixmap, QPainter, QColor, QPen,
    QBrush, QLinearGradient, QPalette, QCursor, QTextCursor, QKeySequence
)

current_dir = Path(__file__).parent

include_path = (current_dir / ".." / "include").resolve()
interface_path = (current_dir / ".." / "interface").resolve()

sys.path.insert(0, str(include_path))
sys.path.insert(1, str(interface_path))

from YoutubeMusicDownloader import Youtube_Downloader  # type: ignore
from Helpers_Validators import Helpers  # type: ignore
from Interface import DownloaderInterface # type: ignore

# ─── THEME CONSTANTS ──────────────────────────────────────────────────────────
BG_DEEP    = "#0d0d0f"
BG_CARD    = "#141418"
BG_SURFACE = "#1a1a20"
BG_PANEL   = "#111115"
ACCENT     = "#e63946"
ACCENT_DIM = "#8b1a22"
ACCENT_GLOW= "#ff4d5a"
TEXT_PRI   = "#f0f0f2"
TEXT_SEC   = "#888896"
TEXT_MUT   = "#444450"
BORDER     = "#252530"
SUCCESS    = "#2ecc71"
WARNING    = "#f39c12"
ERROR      = "#e74c3c"
GLASS      = "rgba(255,255,255,0.03)"


STYLESHEET = f"""
/* ── Root ────────────────────────────────────────────────── */
QMainWindow, QWidget {{
    background-color: {BG_DEEP};
    color: {TEXT_PRI};
    font-family: "Segoe UI", "SF Pro Display", Helvetica, Arial, sans-serif;
    font-size: 13px;
}}

/* ── Sidebar ─────────────────────────────────────────────── */
#sidebar {{
    background-color: {BG_PANEL};
    border-right: 1px solid {BORDER};
    min-width: 220px;
    max-width: 220px;
}}

#logo_label {{
    color: {ACCENT};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 3px;
    padding: 0 20px;
}}

#logo_sub {{
    color: {TEXT_MUT};
    font-size: 10px;
    letter-spacing: 1px;
    padding: 0 20px;
}}

/* ── Nav Buttons ─────────────────────────────────────────── */
QPushButton#nav_btn {{
    background: transparent;
    border: none;
    color: {TEXT_SEC};
    text-align: left;
    padding: 11px 20px;
    font-size: 12px;
    font-weight: 500;
    border-left: 3px solid transparent;
    border-radius: 0px;
}}
QPushButton#nav_btn:hover {{
    background: rgba(230,57,70,0.08);
    color: {TEXT_PRI};
}}
QPushButton#nav_btn[active="true"] {{
    background: rgba(230,57,70,0.12);
    color: {ACCENT};
    border-left: 3px solid {ACCENT};
    font-weight: 600;
}}

/* ── Section Divider ─────────────────────────────────────── */
#section_label {{
    color: {TEXT_MUT};
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 2px;
    padding: 12px 20px 4px 20px;
}}

/* ── Content Area ────────────────────────────────────────── */
#content_area {{
    background-color: {BG_DEEP};
}}

/* ── Page Header ─────────────────────────────────────────── */
#page_title {{
    font-size: 22px;
    font-weight: 700;
    color: {TEXT_PRI};
    letter-spacing: -0.5px;
}}
#page_subtitle {{
    color: {TEXT_SEC};
    font-size: 12px;
}}

/* ── Cards ───────────────────────────────────────────────── */
QFrame#card {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

/* ── Labels ──────────────────────────────────────────────── */
QLabel#field_label {{
    color: {TEXT_SEC};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}

/* ── Input Fields ────────────────────────────────────────── */
QLineEdit {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 7px;
    color: {TEXT_PRI};
    padding: 9px 14px;
    font-size: 13px;
    selection-background-color: {ACCENT_DIM};
}}
QLineEdit:focus {{
    border: 1px solid {ACCENT};
    background-color: #1e1e26;
}}
QLineEdit::placeholder {{
    color: {TEXT_MUT};
}}

/* ── ComboBox ────────────────────────────────────────────── */
QComboBox {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 7px;
    color: {TEXT_PRI};
    padding: 9px 14px;
    font-size: 13px;
    min-width: 120px;
}}
QComboBox:focus {{
    border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
}}
QComboBox::down-arrow {{
    width: 10px;
    height: 10px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    color: {TEXT_PRI};
    selection-background-color: {ACCENT_DIM};
    padding: 4px;
}}

/* ── Buttons ─────────────────────────────────────────────── */
QPushButton#primary_btn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT_GLOW});
    border: none;
    border-radius: 8px;
    color: white;
    font-size: 13px;
    font-weight: 700;
    padding: 11px 28px;
    letter-spacing: 0.3px;
}}
QPushButton#primary_btn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT_GLOW}, stop:1 #ff6b75);
}}
QPushButton#primary_btn:pressed {{
    background: {ACCENT_DIM};
}}
QPushButton#primary_btn:disabled {{
    background: #333340;
    color: {TEXT_MUT};
}}

QPushButton#secondary_btn {{
    background: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    color: {TEXT_SEC};
    font-size: 12px;
    font-weight: 600;
    padding: 9px 20px;
}}
QPushButton#secondary_btn:hover {{
    border-color: {ACCENT};
    color: {TEXT_PRI};
    background: rgba(230,57,70,0.06);
}}

QPushButton#icon_btn {{
    background: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 7px;
    color: {TEXT_SEC};
    font-size: 13px;
    padding: 9px 14px;
    min-width: 40px;
}}
QPushButton#icon_btn:hover {{
    border-color: {ACCENT};
    color: {ACCENT};
}}

/* ── CheckBox ────────────────────────────────────────────── */
QCheckBox {{
    color: {TEXT_SEC};
    font-size: 12px;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    border: 1.5px solid {BORDER};
    border-radius: 4px;
    background: {BG_SURFACE};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox:hover {{
    color: {TEXT_PRI};
}}

/* ── Progress Bar ────────────────────────────────────────── */
QProgressBar {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 5px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT_GLOW});
    border-radius: 5px;
}}

/* ── Log Output ──────────────────────────────────────────── */
QTextEdit#log_output {{
    background-color: #0a0a0e;
    border: 1px solid {BORDER};
    border-radius: 8px;
    color: #a0f0a0;
    font-family: "Cascadia Code", "JetBrains Mono", "Consolas", monospace;
    font-size: 11px;
    padding: 12px;
    line-height: 1.6;
    selection-background-color: {ACCENT_DIM};
}}

/* ── Scrollbar ───────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{ height: 6px; background: transparent; }}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 3px;
}}

/* ── Status Badge ────────────────────────────────────────── */
QLabel#badge_success {{ color: {SUCCESS}; font-size: 11px; font-weight: 600; }}
QLabel#badge_error   {{ color: {ERROR};   font-size: 11px; font-weight: 600; }}
QLabel#badge_warning {{ color: {WARNING}; font-size: 11px; font-weight: 600; }}
QLabel#badge_info    {{ color: #4aa3f5;   font-size: 11px; font-weight: 600; }}

/* ── Separator ───────────────────────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="HLine"] {{
    color: {BORDER};
    background: {BORDER};
    border: none;
    max-height: 1px;
}}

/* ── Tabs ────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {BG_CARD};
}}
QTabBar::tab {{
    background: {BG_SURFACE};
    color: {TEXT_SEC};
    padding: 8px 18px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    margin-right: 2px;
    font-size: 12px;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    background: {BG_CARD};
    color: {ACCENT};
    border-top: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT_PRI};
}}

/* ── List Widget ─────────────────────────────────────────── */
QListWidget {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    color: {TEXT_PRI};
    font-size: 12px;
    padding: 4px;
    outline: none;
}}
QListWidget::item {{
    padding: 8px 12px;
    border-radius: 5px;
    border-bottom: 1px solid rgba(255,255,255,0.03);
}}
QListWidget::item:selected {{
    background: rgba(230,57,70,0.15);
    color: {ACCENT};
}}
QListWidget::item:hover:!selected {{
    background: rgba(255,255,255,0.04);
}}

/* ── Tooltip ─────────────────────────────────────────────── */
QToolTip {{
    background-color: {BG_CARD};
    color: {TEXT_PRI};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 5px 8px;
    font-size: 11px;
}}
"""


# ─── WORKER THREAD ────────────────────────────────────────────────────────────

class DownloadWorker(QThread):
    """Runs yt-dlp in a background thread and emits progress signals."""
    log_signal      = Signal(str, str)   # (message, level)
    progress_signal = Signal(int)        # 0-100
    status_signal   = Signal(str)        # status text
    finished_signal = Signal(bool)       # success

    def __init__(self, url: str, output_template: str, audio_format: str,
                 audio_quality: str, embed_metadata: bool,
                 cookie_file: Optional[str] = None, item_type: str = "item"):
        super().__init__()
        self.url = url
        self.output_template = output_template
        self.audio_format = audio_format
        self.audio_quality = audio_quality
        self.embed_metadata = embed_metadata
        self.cookie_file = cookie_file
        self.item_type = item_type
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        self.terminate()

    def run(self):
        os.makedirs(os.path.dirname(self.output_template) if os.path.dirname(self.output_template) else ".", exist_ok=True)

        command = [
            "yt-dlp",
            "-x",
            "--audio-format", self.audio_format,
            "--audio-quality", self.audio_quality,
            "-o", self.output_template,
            "--no-overwrites",
            "--embed-thumbnail",
            "--newline",
            "--progress",
            "--ignore-errors",
            "--retries", "5",
            "--fragment-retries", "5",
            "--extractor-args", "youtube:player_client=android",
        ]
        if self.embed_metadata:
            command.append("--add-metadata")
        if self.cookie_file and os.path.exists(self.cookie_file):
            command.extend(["--cookies", self.cookie_file])

        command.append(self.url)

        self.log_signal.emit(f"▶ Starting download: {self.url}", "info")
        self.log_signal.emit(f"  Format: {self.audio_format.upper()} @ {self.audio_quality}", "info")

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

            for line in iter(process.stdout.readline, ""):
                if self._cancelled:
                    process.kill()
                    self.finished_signal.emit(False)
                    return

                line = line.strip()
                if not line:
                    continue

                # Parse progress
                if "[download]" in line:
                    m = re.search(r"(\d+\.?\d*)%", line)
                    if m:
                        pct = int(float(m.group(1)))
                        self.progress_signal.emit(pct)
                        self.status_signal.emit(f"Downloading… {pct}%")

                # Classify log lines
                if "ERROR" in line or "error" in line.lower():
                    self.log_signal.emit(line, "error")
                elif "WARNING" in line or "warning" in line.lower():
                    self.log_signal.emit(line, "warning")
                elif "[download]" in line or "[ExtractAudio]" in line or "[Merger]" in line:
                    self.log_signal.emit(line, "info")
                elif line:
                    self.log_signal.emit(line, "debug")

            process.wait()
            success = process.returncode == 0
            if success:
                self.progress_signal.emit(100)
                self.status_signal.emit("✓ Complete")
                self.log_signal.emit(f"✓ Download finished successfully", "success")
            else:
                self.status_signal.emit("✗ Failed")
                self.log_signal.emit(f"✗ Download failed (exit code {process.returncode})", "error")
            self.finished_signal.emit(success)

        except FileNotFoundError:
            self.log_signal.emit("✗ yt-dlp not found. Install it: pip install yt-dlp", "error")
            self.finished_signal.emit(False)
        except Exception as e:
            self.log_signal.emit(f"✗ Unexpected error: {e}", "error")
            self.finished_signal.emit(False)


class ValidateWorker(QThread):
    """Fetches metadata for a URL without downloading."""
    result_signal = Signal(dict)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            result = subprocess.run(
                ["yt-dlp", "--dump-single-json", "--no-warnings",
                 "--flat-playlist", "--playlist-items", "1", self.url],
                capture_output=True, text=True, timeout=20, encoding="utf-8"
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                self.result_signal.emit(data)
            else:
                self.result_signal.emit({})
        except Exception:
            self.result_signal.emit({})


# ─── REUSABLE WIDGETS ──────────────────────────────────────────────────────────

def make_separator():
    sep = QFrame()
    sep.setFrameShape(QFrame.HLine)
    return sep


def make_card():
    frame = QFrame()
    frame.setObjectName("card")
    return frame


def field_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("field_label")
    return lbl


class StatusDot(QLabel):
    """Coloured dot for connection/status indicators."""
    def __init__(self, color=SUCCESS):
        super().__init__("●")
        self.setStyleSheet(f"color: {color}; font-size: 10px;")


class LogConsole(QTextEdit):
    """Auto-scrolling colour log console."""
    COLORS = {
        "info":    "#4aa3f5",
        "success": "#2ecc71",
        "warning": "#f39c12",
        "error":   "#e74c3c",
        "debug":   "#666680",
    }

    def __init__(self):
        super().__init__()
        self.setObjectName("log_output")
        self.setReadOnly(True)
        self.setMinimumHeight(180)

    def append_log(self, msg: str, level: str = "info"):
        color = self.COLORS.get(level, self.COLORS["info"])
        ts = time.strftime("%H:%M:%S")
        html = (
            f'<span style="color:{TEXT_MUT};">[{ts}]</span> '
            f'<span style="color:{color};">{msg}</span><br>'
        )
        self.moveCursor(QTextCursor.End)
        self.insertHtml(html)
        self.moveCursor(QTextCursor.End)

    def clear_log(self):
        self.clear()
        self.append_log("Console cleared.", "debug")


# ─── DOWNLOAD PAGE (shared base) ───────────────────────────────────────────────

class BaseDownloadPage(QWidget):
    """Shared layout for Track / Album / Playlist pages."""

    def __init__(self, title: str, subtitle: str,
                 url_placeholder: str, item_type: str,
                 output_subfmt: str, confirm_large: bool = False):
        super().__init__()
        self.item_type = item_type
        self.output_subfmt = output_subfmt
        self.confirm_large = confirm_large
        self._worker: Optional[DownloadWorker] = None
        self._validator: Optional[ValidateWorker] = None

        # ── Main layout ──────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(20)

        # Header
        hdr = QVBoxLayout()
        t = QLabel(title)
        t.setObjectName("page_title")
        s = QLabel(subtitle)
        s.setObjectName("page_subtitle")
        hdr.addWidget(t)
        hdr.addWidget(s)
        root.addLayout(hdr)
        root.addWidget(make_separator())

        # ── URL Card ─────────────────────────────────────────────────
        url_card = make_card()
        url_layout = QVBoxLayout(url_card)
        url_layout.setContentsMargins(20, 18, 20, 18)
        url_layout.setSpacing(10)
        url_layout.addWidget(field_label("YouTube / YouTube Music URL"))

        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(url_placeholder)
        self.url_input.returnPressed.connect(self._on_validate)
        url_row.addWidget(self.url_input)

        self.validate_btn = QPushButton("Validate")
        self.validate_btn.setObjectName("secondary_btn")
        self.validate_btn.setFixedWidth(88)
        self.validate_btn.clicked.connect(self._on_validate)
        url_row.addWidget(self.validate_btn)
        url_layout.addLayout(url_row)

        # Meta info row
        self.meta_label = QLabel("Paste a URL above and click Validate")
        self.meta_label.setObjectName("badge_info")
        self.meta_label.setWordWrap(True)
        url_layout.addWidget(self.meta_label)

        root.addWidget(url_card)

        # ── Settings Card ─────────────────────────────────────────────
        set_card = make_card()
        set_layout = QGridLayout(set_card)
        set_layout.setContentsMargins(20, 18, 20, 18)
        set_layout.setSpacing(12)
        set_layout.setColumnStretch(1, 1)
        set_layout.setColumnStretch(3, 1)

        set_layout.addWidget(field_label("FORMAT"), 0, 0)
        self.fmt_combo = QComboBox()
        for fmt in ["mp3", "flac", "m4a", "opus", "ogg", "wav"]:
            self.fmt_combo.addItem(fmt.upper(), fmt)
        set_layout.addWidget(self.fmt_combo, 0, 1)

        set_layout.addWidget(field_label("QUALITY"), 0, 2)
        self.qual_combo = QComboBox()
        for q in ["320k", "256k", "192k", "128k", "auto", "disable"]:
            self.qual_combo.addItem(q, q)
        set_layout.addWidget(self.qual_combo, 0, 3)

        set_layout.addWidget(field_label("OUTPUT DIRECTORY"), 1, 0)
        dir_row = QHBoxLayout()
        self.dir_input = QLineEdit()
        self.dir_input.setText(str(Path("Albums")))
        dir_row.addWidget(self.dir_input)
        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("icon_btn")
        browse_btn.setFixedWidth(72)
        browse_btn.clicked.connect(self._browse_dir)
        dir_row.addWidget(browse_btn)
        dir_container = QWidget()
        dir_container.setLayout(dir_row)
        set_layout.addWidget(dir_container, 1, 1, 1, 3)

        self.meta_check = QCheckBox("Embed metadata (artist, album, cover art)")
        self.meta_check.setChecked(True)
        self.cookie_check = QCheckBox("Use cookies (for restricted content)")
        set_layout.addWidget(self.meta_check, 2, 0, 1, 2)
        set_layout.addWidget(self.cookie_check, 2, 2, 1, 2)

        root.addWidget(set_card)

        # ── Download Button + Progress ────────────────────────────────
        ctrl_row = QHBoxLayout()
        self.download_btn = QPushButton(f"  ▶  Download {title}")
        self.download_btn.setObjectName("primary_btn")
        self.download_btn.setMinimumHeight(44)
        self.download_btn.clicked.connect(self._on_download)
        self.cancel_btn = QPushButton("✕  Cancel")
        self.cancel_btn.setObjectName("secondary_btn")
        self.cancel_btn.setMinimumHeight(44)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        ctrl_row.addWidget(self.download_btn, 3)
        ctrl_row.addWidget(self.cancel_btn, 1)
        root.addLayout(ctrl_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(8)
        root.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setObjectName("badge_info")
        self.status_label.setVisible(False)
        root.addWidget(self.status_label)

        # ── Log Console ───────────────────────────────────────────────
        log_hdr = QHBoxLayout()
        log_hdr.addWidget(field_label("CONSOLE OUTPUT"))
        log_hdr.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("secondary_btn")
        clear_btn.setFixedWidth(60)
        log_hdr.addWidget(clear_btn)
        root.addLayout(log_hdr)

        self.log = LogConsole()
        root.addWidget(self.log)
        clear_btn.clicked.connect(self.log.clear_log)

    # ── Internals ────────────────────────────────────────────────────

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory",
                                              self.dir_input.text())
        if d:
            self.dir_input.setText(d)

    def _on_validate(self):
        url = self.url_input.text().strip()
        if not url:
            self.meta_label.setText("Please enter a URL first.")
            return
        self.validate_btn.setEnabled(False)
        self.meta_label.setObjectName("badge_info")
        self.meta_label.setText("⟳ Fetching metadata…")
        self.meta_label.setStyleSheet(f"color: #4aa3f5; font-size: 11px; font-weight: 600;")
        self._validator = ValidateWorker(url)
        self._validator.result_signal.connect(self._on_validate_result)
        self._validator.start()

    @Slot(dict)
    def _on_validate_result(self, data: dict):
        self.validate_btn.setEnabled(True)
        if not data:
            self.meta_label.setStyleSheet(f"color: {ERROR}; font-size: 11px; font-weight: 600;")
            self.meta_label.setText("✗ Could not fetch metadata. Check the URL or your connection.")
            return
        title  = data.get("title") or data.get("webpage_url_basename", "Unknown")
        upl    = data.get("uploader") or data.get("artist") or data.get("channel", "Unknown")
        count  = data.get("playlist_count", "")
        count_str = f"  ·  {count} tracks" if count else ""
        self.meta_label.setStyleSheet(f"color: {SUCCESS}; font-size: 11px; font-weight: 600;")
        self.meta_label.setText(f"✓  {title}  ·  {upl}{count_str}")

    def _build_output_template(self) -> str:
        base = Path(self.dir_input.text().strip() or "Albums")
        return str(base / self.output_subfmt)

    def _on_download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "No URL", "Please enter a YouTube URL first.")
            return
        if not url.startswith("http"):
            url = f"ytsearch1:{url}"

        out_tmpl   = self._build_output_template()
        fmt        = self.fmt_combo.currentData()
        qual       = self.qual_combo.currentData()
        embed_meta = self.meta_check.isChecked()

        # Create output dir
        out_dir = os.path.dirname(out_tmpl)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        self.download_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setVisible(True)
        self.status_label.setText("Starting…")

        self._worker = DownloadWorker(
            url=url, output_template=out_tmpl,
            audio_format=fmt, audio_quality=qual,
            embed_metadata=embed_meta,
            item_type=self.item_type
        )
        self._worker.log_signal.connect(self.log.append_log)
        self._worker.progress_signal.connect(self.progress_bar.setValue)
        self._worker.status_signal.connect(self.status_label.setText)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _on_cancel(self):
        if self._worker:
            self._worker.cancel()
            self.log.append_log("⚠ Download cancelled by user.", "warning")
        self._reset_ui()

    @Slot(bool)
    def _on_finished(self, success: bool):
        self._reset_ui()
        if success:
            self.status_label.setStyleSheet(f"color: {SUCCESS}; font-size: 11px; font-weight: 600;")
            self.status_label.setText("✓ Download complete!")
        else:
            self.status_label.setStyleSheet(f"color: {ERROR}; font-size: 11px; font-weight: 600;")
            self.status_label.setText("✗ Download failed — see console for details.")

    def _reset_ui(self):
        self.download_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)


# ─── INDIVIDUAL PAGES ─────────────────────────────────────────────────────────

class TrackPage(BaseDownloadPage):
    def __init__(self):
        super().__init__(
            title="Track",
            subtitle="Download a single song from YouTube Music",
            url_placeholder="https://music.youtube.com/watch?v=…",
            item_type="track",
            output_subfmt="%(artist)s - %(title)s.%(ext)s",
        )


class AlbumPage(BaseDownloadPage):
    def __init__(self):
        super().__init__(
            title="Album",
            subtitle="Download a full album or playlist as an organised collection",
            url_placeholder="https://music.youtube.com/playlist?list=…",
            item_type="album",
            output_subfmt="%(artist)s/%(album)s/%(artist)s - %(title)s.%(ext)s",
            confirm_large=True,
        )


class PlaylistPage(BaseDownloadPage):
    def __init__(self):
        super().__init__(
            title="Playlist",
            subtitle="Download all tracks from a YouTube Music playlist",
            url_placeholder="https://music.youtube.com/playlist?list=…",
            item_type="playlist",
            output_subfmt="%(playlist_title)s/%(artist)s - %(title)s.%(ext)s",
            confirm_large=True,
        )


class SearchPage(QWidget):
    """Search & Download by song name."""

    def __init__(self):
        super().__init__()
        self._worker: Optional[DownloadWorker] = None
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(20)

        t = QLabel("Search & Download")
        t.setObjectName("page_title")
        s = QLabel("Find a song by name and download directly from YouTube")
        s.setObjectName("page_subtitle")
        root.addWidget(t)
        root.addWidget(s)
        root.addWidget(make_separator())

        # Search card
        card = make_card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 18, 20, 18)
        cl.setSpacing(12)
        cl.addWidget(field_label("SONG NAME / SEARCH QUERY"))
        row = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("e.g.  Bohemian Rhapsody Queen  or  Lose Yourself Eminem")
        self.query_input.returnPressed.connect(self._on_download)
        row.addWidget(self.query_input)
        self.search_btn = QPushButton("Search & Download")
        self.search_btn.setObjectName("primary_btn")
        self.search_btn.clicked.connect(self._on_download)
        row.addWidget(self.search_btn)
        cl.addLayout(row)
        root.addWidget(card)

        # Settings card (inline simple)
        scard = make_card()
        sl = QGridLayout(scard)
        sl.setContentsMargins(20, 18, 20, 18)
        sl.setSpacing(12)
        sl.setColumnStretch(1, 1)
        sl.setColumnStretch(3, 1)
        sl.addWidget(field_label("FORMAT"), 0, 0)
        self.fmt_combo = QComboBox()
        for fmt in ["mp3", "flac", "m4a", "opus", "ogg", "wav"]:
            self.fmt_combo.addItem(fmt.upper(), fmt)
        sl.addWidget(self.fmt_combo, 0, 1)
        sl.addWidget(field_label("QUALITY"), 0, 2)
        self.qual_combo = QComboBox()
        for q in ["320k", "256k", "192k", "128k", "auto"]:
            self.qual_combo.addItem(q, q)
        sl.addWidget(self.qual_combo, 0, 3)
        sl.addWidget(field_label("OUTPUT DIR"), 1, 0)
        dir_row = QHBoxLayout()
        self.dir_input = QLineEdit("Albums")
        dir_row.addWidget(self.dir_input)
        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("icon_btn")
        browse_btn.setFixedWidth(72)
        browse_btn.clicked.connect(self._browse_dir)
        dir_row.addWidget(browse_btn)
        dc = QWidget(); dc.setLayout(dir_row)
        sl.addWidget(dc, 1, 1, 1, 3)
        self.meta_check = QCheckBox("Embed metadata")
        self.meta_check.setChecked(True)
        sl.addWidget(self.meta_check, 2, 0, 1, 4)
        root.addWidget(scard)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(8)
        root.addWidget(self.progress_bar)
        self.status_label = QLabel("")
        self.status_label.setObjectName("badge_info")
        self.status_label.setVisible(False)
        root.addWidget(self.status_label)

        log_hdr = QHBoxLayout()
        log_hdr.addWidget(field_label("CONSOLE OUTPUT"))
        log_hdr.addStretch()
        clr = QPushButton("Clear"); clr.setObjectName("secondary_btn"); clr.setFixedWidth(60)
        log_hdr.addWidget(clr)
        root.addLayout(log_hdr)
        self.log = LogConsole()
        root.addWidget(self.log)
        clr.clicked.connect(self.log.clear_log)

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.dir_input.text())
        if d:
            self.dir_input.setText(d)

    def _on_download(self):
        query = self.query_input.text().strip()
        if not query:
            return
        url = f"ytsearch1:{query}"
        fmt  = self.fmt_combo.currentData()
        qual = self.qual_combo.currentData()
        base = Path(self.dir_input.text().strip() or "Albums")
        out  = str(base / "%(artist)s - %(title)s.%(ext)s")
        os.makedirs(str(base), exist_ok=True)

        self.search_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setVisible(True)
        self.status_label.setText("Searching…")

        self._worker = DownloadWorker(url, out, fmt, qual, self.meta_check.isChecked())
        self._worker.log_signal.connect(self.log.append_log)
        self._worker.progress_signal.connect(self.progress_bar.setValue)
        self._worker.status_signal.connect(self.status_label.setText)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    @Slot(bool)
    def _on_finished(self, ok: bool):
        self.search_btn.setEnabled(True)
        if ok:
            self.status_label.setStyleSheet(f"color: {SUCCESS}; font-size: 11px; font-weight: 600;")
            self.status_label.setText("✓ Download complete!")
        else:
            self.status_label.setStyleSheet(f"color: {ERROR}; font-size: 11px; font-weight: 600;")
            self.status_label.setText("✗ Download failed — see console.")


# ─── SETTINGS PAGE ─────────────────────────────────────────────────────────────

class SettingsPage(QWidget):
    def __init__(self, config_file: str = "config/youtube_downloader.json"):
        super().__init__()
        self.config_file = config_file
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(20)

        t = QLabel("Settings")
        t.setObjectName("page_title")
        s = QLabel("Persistent configuration saved to disk")
        s.setObjectName("page_subtitle")
        root.addWidget(t)
        root.addWidget(s)
        root.addWidget(make_separator())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(16)

        # ── Default Download ──────────────────────────────────────────
        dl_card = make_card()
        dl_l = QGridLayout(dl_card)
        dl_l.setContentsMargins(20, 18, 20, 18)
        dl_l.setSpacing(12)
        dl_l.setColumnStretch(1, 1)
        dl_l.setColumnStretch(3, 1)

        lbl = QLabel("Default Download Settings")
        lbl.setStyleSheet(f"color: {TEXT_PRI}; font-size: 14px; font-weight: 700;")
        dl_l.addWidget(lbl, 0, 0, 1, 4)

        dl_l.addWidget(field_label("DEFAULT FORMAT"), 1, 0)
        self.fmt_combo = QComboBox()
        for fmt in ["mp3", "flac", "m4a", "opus", "ogg", "wav"]:
            self.fmt_combo.addItem(fmt.upper(), fmt)
        dl_l.addWidget(self.fmt_combo, 1, 1)

        dl_l.addWidget(field_label("DEFAULT QUALITY"), 1, 2)
        self.qual_combo = QComboBox()
        for q in ["320k", "256k", "192k", "128k", "auto", "disable"]:
            self.qual_combo.addItem(q, q)
        dl_l.addWidget(self.qual_combo, 1, 3)

        dl_l.addWidget(field_label("DEFAULT OUTPUT DIR"), 2, 0)
        dir_row = QHBoxLayout()
        self.dir_input = QLineEdit("Albums")
        dir_row.addWidget(self.dir_input)
        br = QPushButton("Browse"); br.setObjectName("icon_btn"); br.setFixedWidth(72)
        br.clicked.connect(self._browse_dir)
        dir_row.addWidget(br)
        dc = QWidget(); dc.setLayout(dir_row)
        dl_l.addWidget(dc, 2, 1, 1, 3)
        inner_layout.addWidget(dl_card)

        # ── Auth ──────────────────────────────────────────────────────
        auth_card = make_card()
        auth_l = QVBoxLayout(auth_card)
        auth_l.setContentsMargins(20, 18, 20, 18)
        auth_l.setSpacing(10)
        auth_title = QLabel("Authentication & Cookies")
        auth_title.setStyleSheet(f"color: {TEXT_PRI}; font-size: 14px; font-weight: 700;")
        auth_l.addWidget(auth_title)

        self.use_cookies_check = QCheckBox("Use cookies for authentication (age/region restricted content)")
        auth_l.addWidget(self.use_cookies_check)

        cookie_row = QHBoxLayout()
        cookie_row.addWidget(field_label("COOKIE FILE PATH"))
        self.cookie_input = QLineEdit()
        self.cookie_input.setPlaceholderText("cookies/cookies.txt")
        cookie_row.addWidget(self.cookie_input)
        cookie_br = QPushButton("Browse"); cookie_br.setObjectName("icon_btn"); cookie_br.setFixedWidth(72)
        cookie_br.clicked.connect(self._browse_cookie)
        cookie_row.addWidget(cookie_br)
        auth_l.addLayout(cookie_row)

        info_lbl = QLabel("Export cookies using a browser extension like 'Get cookies.txt LOCALLY'")
        info_lbl.setStyleSheet(f"color: {TEXT_MUT}; font-size: 11px; font-style: italic;")
        auth_l.addWidget(info_lbl)
        inner_layout.addWidget(auth_card)

        # ── Metadata ──────────────────────────────────────────────────
        meta_card = make_card()
        meta_l = QVBoxLayout(meta_card)
        meta_l.setContentsMargins(20, 18, 20, 18)
        meta_l.setSpacing(10)
        meta_title = QLabel("Metadata & Tagging")
        meta_title.setStyleSheet(f"color: {TEXT_PRI}; font-size: 14px; font-weight: 700;")
        meta_l.addWidget(meta_title)
        self.embed_meta_check = QCheckBox("Embed metadata (artist, album, track number, cover art)")
        self.embed_meta_check.setChecked(True)
        meta_l.addWidget(self.embed_meta_check)
        inner_layout.addWidget(meta_card)

        # ── Advanced ──────────────────────────────────────────────────
        adv_card = make_card()
        adv_l = QGridLayout(adv_card)
        adv_l.setContentsMargins(20, 18, 20, 18)
        adv_l.setSpacing(12)
        adv_l.setColumnStretch(1, 1)
        adv_l.setColumnStretch(3, 1)
        adv_title = QLabel("Advanced")
        adv_title.setStyleSheet(f"color: {TEXT_PRI}; font-size: 14px; font-weight: 700;")
        adv_l.addWidget(adv_title, 0, 0, 1, 4)

        adv_l.addWidget(field_label("MAX RETRIES"), 1, 0)
        self.retries_combo = QComboBox()
        for r in ["1", "2", "3", "5", "10"]:
            self.retries_combo.addItem(r, int(r))
        self.retries_combo.setCurrentIndex(2)
        adv_l.addWidget(self.retries_combo, 1, 1)

        adv_l.addWidget(field_label("RETRY DELAY (s)"), 1, 2)
        self.delay_combo = QComboBox()
        for d in ["5", "10", "15", "30"]:
            self.delay_combo.addItem(d, int(d))
        self.delay_combo.setCurrentIndex(1)
        adv_l.addWidget(self.delay_combo, 1, 3)
        inner_layout.addWidget(adv_card)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)

        # Save / Reset row
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("primary_btn")
        save_btn.clicked.connect(self._save_config)
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setObjectName("secondary_btn")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addStretch()
        btn_row.addWidget(reset_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

        self._load_config()

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Output Directory", self.dir_input.text())
        if d: self.dir_input.setText(d)

    def _browse_cookie(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Cookie File", "", "Text Files (*.txt);;All Files (*)")
        if f: self.cookie_input.setText(f)

    def _save_config(self):
        os.makedirs(os.path.dirname(self.config_file) or ".", exist_ok=True)
        cfg = {
            "output_directory": self.dir_input.text(),
            "audio_quality": self.qual_combo.currentData(),
            "audio_format": self.fmt_combo.currentData(),
            "use_cookies": self.use_cookies_check.isChecked(),
            "embed_metadata": self.embed_meta_check.isChecked(),
            "max_retries": int(self.retries_combo.currentData()),
            "retry_delay": int(self.delay_combo.currentData()),
            "cookie_file": self.cookie_input.text(),
        }
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            QMessageBox.information(self, "Saved", "Settings saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save settings:\n{e}")

    def _load_config(self):
        if not os.path.exists(self.config_file):
            return
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if "output_directory" in cfg:
                self.dir_input.setText(cfg["output_directory"])
            if "audio_format" in cfg:
                idx = self.fmt_combo.findData(cfg["audio_format"])
                if idx >= 0: self.fmt_combo.setCurrentIndex(idx)
            if "audio_quality" in cfg:
                idx = self.qual_combo.findData(cfg["audio_quality"])
                if idx >= 0: self.qual_combo.setCurrentIndex(idx)
            if "use_cookies" in cfg:
                self.use_cookies_check.setChecked(cfg["use_cookies"])
            if "embed_metadata" in cfg:
                self.embed_meta_check.setChecked(cfg["embed_metadata"])
            if "cookie_file" in cfg:
                self.cookie_input.setText(cfg.get("cookie_file", ""))
        except Exception:
            pass

    def _reset_defaults(self):
        self.dir_input.setText("Albums")
        self.fmt_combo.setCurrentIndex(0)
        self.qual_combo.setCurrentIndex(0)
        self.use_cookies_check.setChecked(False)
        self.embed_meta_check.setChecked(True)
        self.retries_combo.setCurrentIndex(2)
        self.delay_combo.setCurrentIndex(1)
        self.cookie_input.clear()


# ─── ABOUT / DIAGNOSTICS PAGE ─────────────────────────────────────────────────

class AboutPage(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(20)

        t = QLabel("About & Diagnostics")
        t.setObjectName("page_title")
        s = QLabel("System status and application information")
        s.setObjectName("page_subtitle")
        root.addWidget(t)
        root.addWidget(s)
        root.addWidget(make_separator())

        # Status card
        stat_card = make_card()
        stat_l = QVBoxLayout(stat_card)
        stat_l.setContentsMargins(20, 18, 20, 18)
        stat_l.setSpacing(10)
        heading = QLabel("Dependency Status")
        heading.setStyleSheet(f"color: {TEXT_PRI}; font-size: 14px; font-weight: 700;")
        stat_l.addWidget(heading)

        self.ytdlp_row = self._make_dep_row("yt-dlp", "Checking…")
        self.ffmpeg_row = self._make_dep_row("FFmpeg", "Checking…")
        stat_l.addLayout(self.ytdlp_row[0])
        stat_l.addLayout(self.ffmpeg_row[0])

        refresh_btn = QPushButton("Re-check Dependencies")
        refresh_btn.setObjectName("secondary_btn")
        refresh_btn.setFixedWidth(200)
        refresh_btn.clicked.connect(self._check_deps)
        stat_l.addWidget(refresh_btn)
        root.addWidget(stat_card)

        # Log path info
        info_card = make_card()
        info_l = QVBoxLayout(info_card)
        info_l.setContentsMargins(20, 18, 20, 18)
        info_l.setSpacing(6)
        info_title = QLabel("Application Info")
        info_title.setStyleSheet(f"color: {TEXT_PRI}; font-size: 14px; font-weight: 700;")
        info_l.addWidget(info_title)
        for label, val in [
            ("Version", "GUI 1.0 (PySide6)"),
            ("Config file", "config/youtube_downloader.json"),
            ("Archive dir", "archives/"),
            ("Default output", "Albums/"),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label + ":")
            lbl.setFixedWidth(120)
            lbl.setStyleSheet(f"color: {TEXT_SEC}; font-size: 12px;")
            val_lbl = QLabel(val)
            val_lbl.setStyleSheet(f"color: {TEXT_PRI}; font-size: 12px;")
            row.addWidget(lbl)
            row.addWidget(val_lbl)
            row.addStretch()
            info_l.addLayout(row)
        root.addWidget(info_card)

        # Install hints
        hint_card = make_card()
        hint_l = QVBoxLayout(hint_card)
        hint_l.setContentsMargins(20, 18, 20, 18)
        hint_l.setSpacing(6)
        hint_title = QLabel("Quick Install Commands")
        hint_title.setStyleSheet(f"color: {TEXT_PRI}; font-size: 14px; font-weight: 700;")
        hint_l.addWidget(hint_title)
        for cmd in [
            "pip install yt-dlp       # Install yt-dlp",
            "pip install --upgrade yt-dlp  # Upgrade yt-dlp",
            "# FFmpeg: https://ffmpeg.org/download.html",
            "# macOS:  brew install ffmpeg",
            "# Ubuntu: sudo apt install ffmpeg",
        ]:
            lbl = QLabel(cmd)
            lbl.setStyleSheet(f"color: #a0f0a0; font-family: 'Consolas', monospace; font-size: 11px;")
            hint_l.addWidget(lbl)
        root.addWidget(hint_card)
        root.addStretch()

        self._check_deps()

    def _make_dep_row(self, name: str, status: str):
        row = QHBoxLayout()
        name_lbl = QLabel(name)
        name_lbl.setFixedWidth(100)
        name_lbl.setStyleSheet(f"color: {TEXT_PRI}; font-size: 12px; font-weight: 600;")
        dot = QLabel("⬤")
        dot.setFixedWidth(20)
        dot.setStyleSheet(f"color: {TEXT_MUT}; font-size: 10px;")
        status_lbl = QLabel(status)
        status_lbl.setStyleSheet(f"color: {TEXT_SEC}; font-size: 12px;")
        row.addWidget(name_lbl)
        row.addWidget(dot)
        row.addWidget(status_lbl)
        row.addStretch()
        return row, dot, status_lbl

    def _check_deps(self):
        # yt-dlp
        try:
            r = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                ver = r.stdout.strip()
                self.ytdlp_row[1].setStyleSheet(f"color: {SUCCESS}; font-size: 10px;")
                self.ytdlp_row[2].setText(f"Installed  ·  v{ver}")
                self.ytdlp_row[2].setStyleSheet(f"color: {SUCCESS}; font-size: 12px;")
            else:
                raise RuntimeError
        except Exception:
            self.ytdlp_row[1].setStyleSheet(f"color: {ERROR}; font-size: 10px;")
            self.ytdlp_row[2].setText("Not found  ·  pip install yt-dlp")
            self.ytdlp_row[2].setStyleSheet(f"color: {ERROR}; font-size: 12px;")

        # ffmpeg
        try:
            r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                line = r.stdout.split("\n")[0]
                self.ffmpeg_row[1].setStyleSheet(f"color: {SUCCESS}; font-size: 10px;")
                self.ffmpeg_row[2].setText(f"Installed  ·  {line[:40]}")
                self.ffmpeg_row[2].setStyleSheet(f"color: {SUCCESS}; font-size: 12px;")
            else:
                raise RuntimeError
        except Exception:
            self.ffmpeg_row[1].setStyleSheet(f"color: {WARNING}; font-size: 10px;")
            self.ffmpeg_row[2].setText("Not found  ·  Audio conversion will fail")
            self.ffmpeg_row[2].setStyleSheet(f"color: {WARNING}; font-size: 12px;")


# ─── SIDEBAR NAV BUTTON ────────────────────────────────────────────────────────

class NavButton(QPushButton):
    def __init__(self, icon: str, text: str):
        super().__init__(f"  {icon}  {text}")
        self.setObjectName("nav_btn")
        self.setCheckable(False)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(40)

    def set_active(self, active: bool):
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)


# ─── MAIN WINDOW ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Music Downloader")
        self.setMinimumSize(960, 680)
        self.resize(1100, 740)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 24, 0, 20)
        side_layout.setSpacing(2)

        # Logo
        logo_area = QWidget()
        la = QVBoxLayout(logo_area)
        la.setContentsMargins(20, 0, 20, 8)
        la.setSpacing(2)
        logo_icon = QLabel("▶")
        logo_icon.setStyleSheet(f"color: {ACCENT}; font-size: 26px; font-weight: 900;")
        logo_lbl = QLabel("MUSIC CONVERTER")
        logo_lbl.setObjectName("logo_label")
        logo_sub = QLabel("yt-dlp powered")
        logo_sub.setObjectName("logo_sub")
        la.addWidget(logo_icon)
        la.addWidget(logo_lbl)
        la.addWidget(logo_sub)
        side_layout.addWidget(logo_area)
        side_layout.addSpacing(10)
        side_layout.addWidget(make_separator())
        side_layout.addSpacing(6)

        # Nav sections
        def section(text):
            lbl = QLabel(text)
            lbl.setObjectName("section_label")
            side_layout.addWidget(lbl)

        section("DOWNLOAD")
        self.nav_track    = NavButton("♪", "Track")
        self.nav_album    = NavButton("💿", "Album")
        self.nav_playlist = NavButton("≡", "Playlist")
        self.nav_search   = NavButton("⌕", "Search & Download")

        section("TOOLS")
        self.nav_settings = NavButton("⚙", "Settings")
        self.nav_about    = NavButton("ℹ", "About & Diagnostics")

        self._nav_buttons = [
            self.nav_track, self.nav_album, self.nav_playlist,
            self.nav_search, self.nav_settings, self.nav_about,
        ]
        for btn in self._nav_buttons:
            side_layout.addWidget(btn)

        side_layout.addStretch()
        side_layout.addWidget(make_separator())
        ver = QLabel("v1.0  ·  PySide6 GUI")
        ver.setStyleSheet(f"color: {TEXT_MUT}; font-size: 10px; padding: 8px 20px 0 20px;")
        side_layout.addWidget(ver)
        main_layout.addWidget(sidebar)

        # ── Content Stack ─────────────────────────────────────────────
        self.stack = QStackedWidget()
        self.stack.setObjectName("content_area")

        self.page_track    = TrackPage()
        self.page_album    = AlbumPage()
        self.page_playlist = PlaylistPage()
        self.page_search   = SearchPage()
        self.page_settings = SettingsPage()
        self.page_about    = AboutPage()

        for page in [self.page_track, self.page_album, self.page_playlist,
                     self.page_search, self.page_settings, self.page_about]:
            self.stack.addWidget(page)

        main_layout.addWidget(self.stack)

        # Connect nav
        self.nav_track.clicked.connect(lambda: self._switch(0))
        self.nav_album.clicked.connect(lambda: self._switch(1))
        self.nav_playlist.clicked.connect(lambda: self._switch(2))
        self.nav_search.clicked.connect(lambda: self._switch(3))
        self.nav_settings.clicked.connect(lambda: self._switch(4))
        self.nav_about.clicked.connect(lambda: self._switch(5))

        self._switch(0)

    def _switch(self, idx: int):
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_buttons):
            btn.set_active(i == idx)


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("YouTube Music Downloader")
    app.setOrganizationName("MusicConverter")
    app.setStyleSheet(STYLESHEET)

    # High-DPI
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()