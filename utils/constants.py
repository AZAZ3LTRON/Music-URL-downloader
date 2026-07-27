PYTHON_DEPENDENCIES = [
    "psutil",
    "colorama",
    "mutagen",
    "schedule",
    "questionary",
]

SYSTEM_DEPENDENCIES = [
    "ffmpeg",
]

# Audio Related

VALID_AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"}

AUDIO_BITRATE_OPTIONS = {
    "64k": "Very low quality (speech/podcasts)",
    "96k": "Low quality (voice focus)",
    "128k": "Medium quality (most music)",
    "192k": "Good quality (balanced size)",
    "256k": "High quality",
    "320k": "Best quality (larger file size)"
}


# Files

FAILED_FILE = "data/failed_downloads.json"
PROGRESS_FILE = "data/download_progress.json"
LOG_FILE = "app.log"