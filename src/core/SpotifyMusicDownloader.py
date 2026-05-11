"""
Interactive Playlist/Album/Track Downloader using spotdl

While Spotify faces ethical challenges, YouTube remains a massive platform for music discovery.
This program allows you to download music directly from YouTube and YouTube Music.

Its features include:
- Audio Format choice
- Download Quality choice
- Output Directory Choice
- Zip Downloads choice
- Metadata Support
- Organizes albums by artist
- Mass download support (from text file)
- Log successful downloads
- Log failed downloads
- Log errors in between downloads
- Retry downloads
- Progress bar for downloads
- Batch Processing (with parallel downloads)
- Resource Validation (Check if links are available)

Please use the latest version of YT-DLP, upgrade it using "pip install --upgrade yt-dlp" or "yt-dlp -U" depending on how you installed it
Additionally make sure ffmpeg is installed, as that is necessary to parse the music file's metadata if not you will receive postprocessing error in your output

Enjoy!
"""

import re
import sys
import os
import subprocess
import time
import hashlib
import threading
import json

from functools import wraps
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from colorama import init, Fore, Style

from src.utils.CookieManager import CookieManager
from src.utils.DownloaderUtils import DownloaderUtils 
from src.utils.EnhancedMenu import Enhanced_Menu#  <-- new helpers module
from src.utils.Logs_Handler import Logs_Manager
from src.utils.Validators import Helpers 