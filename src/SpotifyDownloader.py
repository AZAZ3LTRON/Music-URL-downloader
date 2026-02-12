"""
Interactive Playlist/Album/Track Downloader using SpotDL

With the rise of Artificial Intelligence and the music industry scraping artist work to run in LLMs, Spotify has been the biggest profit from this.
From the support of ICE, promoting AI Artist on the platform without proper regulations, their exploitative subscriptions fees which they have increased once again,
putting out Zionist Advertisement, underpaying artist and Daniel Ek's investment in German military AI company Helsing.

I created this python script to allow you, the user, to download track, albums, personal playlist etc from the Spotify Website. Unfortunately, Spotify have blocked all API request from
being made due to mass web scrape of their platform by Anna's Archive. If you wish to download from them, you can go to

The program function is to allow you to download music from Spotify urls.

Its features a:
- Audio Format choice
- Download Quality choice
- Output Directory Choice
- Metadata Support
- Organizes albums by artist
- Mass download support (from text file)
- Log successful downloads
- Log failed downloads
- Log errors in between downloads
- Retry downloads
- Resource validation

Enjoy!
"""

import sys
import os
import subprocess
import shutil
import time
from pathlib import Path
import logging
import re
import urllib.parse
from urllib.parse import urlparse
from typing import List, Dict, Optional, Tuple
import threading
import json
from tqdm import tqdm
import browser_cookie3
from functools import wraps
from colorama import init, Fore, Style
init(autoreset=True)


""" =========================================== Pre Config ===========================================
This part of the pre-configuration of the downloader, it can be change. Each part is explained below:
* SUCCESS_LOG - Logs the successful downloads (subject to change)
* FAILED_LOG - Logs failed downloads (subject to change)
* ERROR_LOG - Logs error in the download process (subject to change)
* MAX_RETRIES - No of times the downloader can retry on a link (subject to change)
* RETRY_DELAY - The delay between each retry (subject to change)
======================================================================================================= """

SUCCESS_LOG = r"log\success.log"
FAILED_LOG = r"log\failed.log"
ERROR_LOG = r"log\error.log"
MAX_RETRIES = 3
RETRY_DELAY = 10
DOWNLOAD_TIMEOUT = 120
COOKIE_DIRECTORY = r"cookies"

os.makedirs("log", exist_ok=True)
os.makedirs(COOKIE_DIRECTORY, exist_ok=True)

"""==== Logger: Initialize the log fies before write ====  """

logger = logging.getLogger("Spotify Downloader")
log_format = logging.Formatter("SpotDL_Music_Converter - %(asctime)s - %(levelname)s - %(funcName)s - %(message)s")

success_downloads = logging.getLogger("successful downloads")
failed_downloads = logging.getLogger("failed downloads")
error_downloads = logging.getLogger("error in downloads")
console_logger = logging.getLogger("console")

# Create loggers (successful downloads logger) ----------------------------------------------
success_downloads.setLevel(logging.INFO)
success_downloads.propagate = False

success_handler = logging.FileHandler(SUCCESS_LOG, encoding='utf-8')
success_handler.setLevel(logging.INFO)
success_handler.setFormatter(log_format)
success_downloads.addHandler(success_handler)

# Failed download logger ---------------------------------------------------------------
failed_downloads.setLevel(logging.INFO)
failed_downloads.propagate = False

failed_handler = logging.FileHandler(FAILED_LOG, encoding='utf-8')
failed_handler.setLevel(logging.INFO)
failed_handler.setFormatter(log_format)
failed_downloads.addHandler(failed_handler)

# Error in download logger ----------------------------------------------------------
error_downloads.setLevel(logging.INFO)
error_downloads.propagate = False

error_handler = logging.FileHandler(ERROR_LOG, encoding='utf-8')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(log_format)
error_downloads.addHandler(error_handler)

# General console logger (stream handler for console output)
console_logger.setLevel(logging.INFO)
console_logger.propagate = False

console_stream_handler = logging.StreamHandler()
console_stream_handler.setLevel(logging.INFO)
console_stream_handler.setFormatter(log_format)
console_logger.addHandler(console_stream_handler)


class Enhanced_Menu:
    """Coloured, boxed menu system for better interaction."""

    COLORS = {
        "header": f"{Fore.CYAN}{Style.BRIGHT}",
        "title": f"{Fore.MAGENTA}{Style.BRIGHT}",
        "section": f"{Fore.BLUE}{Style.BRIGHT}",
        "menu_item": f"{Fore.YELLOW}",
        "menu_desc": f"{Fore.WHITE}",
        "success": f"{Fore.GREEN}{Style.BRIGHT}",
        "failure": f"{Fore.RED}{Style.BRIGHT}",
        "error": f"{Fore.YELLOW}{Style.BRIGHT}",
        "info": f"{Fore.CYAN}",
        "input": f"{Fore.GREEN}{Style.BRIGHT}",
        "highlight": f"{Fore.YELLOW}{Style.BRIGHT}",
        "dim": f"{Style.DIM}",
    }

    @staticmethod
    def clear_screen():
        """Clear terminal screen."""
        os.system("cls" if os.name == "nt" else "clear")

    @staticmethod
    def print_color(text, color_type="info", bold=False, end="\n"):
        """Print coloured text."""
        color = Enhanced_Menu.COLORS.get(color_type, "")
        if bold and "BRIGHT" not in color:
            text = f"{Style.BRIGHT}{text}"
        print(f"{color}{text}{Style.RESET_ALL}", end=end)

    @staticmethod
    def print_boxed_title(title, width=60):
        """Print a title inside a decorative box."""
        border = "═" * (width - 2)
        print(f"{Enhanced_Menu.COLORS['title']}╔{border}╗")
        padding = width - len(title) - 4
        left_pad = padding // 2
        right_pad = padding - left_pad
        print(f"{Enhanced_Menu.COLORS['title']}║{' ' * left_pad}{title}{' ' * right_pad}║")
        print(f"{Enhanced_Menu.COLORS['title']}╚{border}╝{Style.RESET_ALL}")

    @staticmethod
    def print_header(title, subtitle=""):
        """Print a formatted header."""
        print()
        Enhanced_Menu.print_boxed_title(title)
        if subtitle:
            print(f"\n{Enhanced_Menu.COLORS['info']}{subtitle}{Style.RESET_ALL}")
        print()

    @staticmethod
    def print_section(title, symbol="─"):
        """Print a section header."""
        print(f"\n{Enhanced_Menu.COLORS['section']}{symbol * 60}")
        print(f"  {title}")
        print(f"{symbol * 60}{Style.RESET_ALL}")

    @staticmethod
    def print_menu_item(number, title, description="", indent=2):
        """Print a menu item with number and optional description."""
        indent_str = " " * indent
        print(f"{indent_str}{Enhanced_Menu.COLORS['menu_item']}[{number:2}]{Style.RESET_ALL} "
              f"{Enhanced_Menu.COLORS['menu_item']}{Style.BRIGHT}{title}{Style.RESET_ALL}")
        if description:
            desc_indent = " " * (indent + 5)
            for line in Enhanced_Menu.wrap_text(description, width=50):
                print(f"{desc_indent}{Enhanced_Menu.COLORS['menu_desc']}{line}")

    @staticmethod
    def wrap_text(text, width=50):
        """Wrap text to given width."""
        words = text.split()
        lines = []
        current_line = []
        current_len = 0
        for w in words:
            if current_len + len(w) + 1 <= width:
                current_line.append(w)
                current_len += len(w) + 1
            else:
                lines.append(" ".join(current_line))
                current_line = [w]
                current_len = len(w)
        if current_line:
            lines.append(" ".join(current_line))
        return lines

    @staticmethod
    def print_status(message, status_type="info", icon=""):
        """Print a status message with appropriate colour and icon."""
        icons = {
            "success": "✓",
            "failure": "✗",
            "error": "⚠",
            "info": "ℹ"
        }
        icon_to_use = icon or icons.get(status_type, "")
        color = Enhanced_Menu.COLORS.get(status_type, Enhanced_Menu.COLORS["info"])
        print(f"{color}{icon_to_use} {message}{Style.RESET_ALL}")

    @staticmethod
    def get_input(prompt, input_type="int", min_val=None, max_val=None, default=None):
        """
        Get validated user input.
        input_type: 'int', 'str', 'yn', 'float'
        Returns the value or None if cancelled.
        """
        prompt_color = Enhanced_Menu.COLORS["input"]
        reset = Style.RESET_ALL
        while True:
            try:
                full_prompt = f"{prompt_color}{prompt}{reset}"
                if default is not None:
                    full_prompt += f" [{Fore.YELLOW}{default}{reset}]"
                full_prompt += f"{prompt_color}:{reset} "

                user_input = input(full_prompt).strip()

                if not user_input and default is not None:
                    return default

                if input_type == "int":
                    val = int(user_input)
                    if min_val is not None and val < min_val:
                        raise ValueError(f"Minimum is {min_val}")
                    if max_val is not None and val > max_val:
                        raise ValueError(f"Maximum is {max_val}")
                    return val
                elif input_type == "float":
                    return float(user_input)
                elif input_type == "str":
                    return user_input
                elif input_type == "yn":
                    if user_input.lower() in ("y", "yes"):
                        return True
                    elif user_input.lower() in ("n", "no"):
                        return False
                    else:
                        raise ValueError("Enter 'y' or 'n'")
            except ValueError as e:
                Enhanced_Menu.print_status(str(e), "error")
            except KeyboardInterrupt:
                Enhanced_Menu.print_status("Operation cancelled", "error")
                return None


class CookieManager:
    """ Manages cookies for Spotify authentication"""

    def __init__(self):
        self.cookie_directory = Path(COOKIE_DIRECTORY)
        self.cookie_directory.mkdir(exist_ok=True)
        self.current_cookie_file = None
        self.cookie_sources = {
            'chrome': browser_cookie3.chrome,
            'firefox': browser_cookie3.firefox,
            'edge': browser_cookie3.edge,
            'opera': browser_cookie3.opera,
            'opera_gx': browser_cookie3.opera_gx,
            'brave': browser_cookie3.brave,
            'safari': browser_cookie3.safari
        }

    def get_status(self):
        """Get cookie status"""
        Enhanced_Menu.print_header("Checking available browser cookies...")
        available = []
        for browser, func in self.cookie_sources.items():
            try:
                cookies = list(func(domain_name="https://open.spotify.com/"))
                if cookies:
                    available.append(browser)
                    Enhanced_Menu.print_status(f"{browser}: {len(cookies)} cookies", "success")
                else:
                    Enhanced_Menu.print_status(f"{browser}: no cookies", "failure")
            except Exception as e:
                Enhanced_Menu.print_status(f"{browser}: error – {e}", "error")
        if available:
            Enhanced_Menu.print_status(f"Available from: {', '.join(available)}", "success")
            return True
        else:
            Enhanced_Menu.print_status("No Spotify cookies found in any browser", "error")
            return False

    def extract_cookies(self, browser_name: str = 'brave') -> Optional[Path]:
        """Extract cookies from your browser of choice & saves to files"""
        if browser_name not in self.cookie_sources:
            Enhanced_Menu.print_status("Browser not supported", "error")
            Enhanced_Menu.print_status(f"Available browsers are: {', '.join(self.cookie_sources.keys())}", "info")
            return None

        Enhanced_Menu.print_header(f" Extracting cookies from {browser_name}....")
        # Retrieve cookies from Spotify domains
        domains = ['https://open.spotify.com/']
        all_cookies = []
        try:
            for domain in domains:
                try:
                    cookies = self.cookie_sources[browser_name](domain_name=domain)
                    for cookie in cookies:
                        if cookie not in all_cookies:
                            all_cookies.append(cookie)
                    Enhanced_Menu.print_status(f"Found {len(list(cookies))} cookies for {domain}", "success")
                except Exception as e:
                    Enhanced_Menu.print_status(f" Couldn't get cookies for {domain}: {e}", "error")

            if not all_cookies:
                Enhanced_Menu.print_status(f" No cookies found for Spotify in {browser_name}", "info")
                return None

            cookie_file = self.cookie_directory / f"{browser_name}_cookies.txt"
            with open(cookie_file, "w", encoding='utf-8') as f:
                f.write("# Netscape HTTP cookie file\n")
                f.write("# This file was generated by Spotify Downloader\n")
                f.write("# https://curl.haxx.se/docs/http-cookies.html\n\n")

                for cookie in all_cookies:
                    # Convert to Netscape format
                    netloc = urlparse(cookie.domain).netloc if cookie.domain.startswith('http') else cookie.domain
                    if not netloc:
                        netloc = cookie.domain

                    # Handle secure flag
                    secure = "TRUE" if cookie.secure else "FALSE"

                    # Write cookie in Netscape format
                    f.write(f"{netloc}\t")
                    f.write("TRUE\t")  # Include subdomains
                    f.write(f"{cookie.path}\t")
                    f.write(f"{secure}\t")
                    f.write(f"{int(time.time()) + 3600 * 24 * 365}\t")  # Expiry (1 year from now)
                    f.write(f"{cookie.name}\t")
                    f.write(f"{cookie.value}\n")

            Enhanced_Menu.print_status(f" Successfully extracted {len(all_cookies)} cookies to {cookie_file}", "success")
            Enhanced_Menu.print_status(f"Cookies saved to: {cookie_file}", "info")

            self.current_cookie_file = cookie_file
            return cookie_file

        except Exception as e:
            Enhanced_Menu.print_status(f" Failed to extract cookies from {browser_name}: {e}", "error")
            Enhanced_Menu.print_color(f"Direct cookie extraction failed for {browser_name}")
            Enhanced_Menu.print_color("Try manual cookie export:")
            Enhanced_Menu.print_color("1. Install 'Get cookies.txt' extension for Chrome/Edge")
            Enhanced_Menu.print_color("2. Export cookies from spotify.com")
            Enhanced_Menu.print_color("3. Load the exported file using option 4")
            return None

    def load_cookies(self, cookie_file: str) -> Optional[Path]:
        """Load cookies from an existing file"""
        cookie_path = Path(cookie_file)

        # Check if file exists in cookies directory
        if not cookie_path.exists():
            # Try to find it in the cookie directory
            cookie_path = self.cookie_directory / cookie_file
            if not cookie_path.exists():
                Enhanced_Menu.print_status(f"Cookie file not found: {cookie_file}", "failure")
                return None

        try:
            with open(cookie_path, 'r', encoding='utf-8') as f:
                content = f.read(200)
                if "# Netscape HTTP Cookie File" not in content:
                    Enhanced_Menu.print_status(f" Warning: Cookie file may not be in Netscape format", "error")
            self.current_cookie_file = cookie_path
            Enhanced_Menu.print_status(f"Cookies loaded from:- {cookie_path}", "info")
            return cookie_path
        except Exception as e:
            Enhanced_Menu.print_status(f"Failed to load cookies:- {e}", "failure")
            return None

    def save_cookies(self, name: str = "cookies") -> Optional[Path]:
        """Save current cookie file to persistent storage"""
        if not self.current_cookie_file or not self.current_cookie_file.exists():
            Enhanced_Menu.print_status(f"No active cookie file to save", "error")
            return None

        # Create a text file for the cookies
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        save_path = self.cookie_directory / f"{name}_{timestamp}.txt"

        try:
            shutil.copy2(self.current_cookie_file, save_path)
            Enhanced_Menu.print_status(f"Cookies saved to: {save_path}", "success")
            return save_path
        except Exception as e:
            Enhanced_Menu.print_status(f"Failed to save cookies: {e}", "error")
            return None

    def list_cookies(self) -> List[Path]:
        """List all saved cookie files"""
        cookie_files = sorted(self.cookie_directory.glob("*.txt"))
        if not cookie_files:
            Enhanced_Menu.print_status(f"No saved cookies files found.", "error")
            return []
        Enhanced_Menu.print_status(f"Saved cookie files:", "info")
        for i, cookie_file in enumerate(cookie_files, 1):
            file_size = cookie_file.stat().st_size
            mod_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(cookie_file.stat().st_mtime))
            print(f"{Fore.YELLOW}[{i}]{Style.RESET_ALL} {Fore.CYAN}{cookie_file.name:30}{Style.RESET_ALL}  "
                  f"Size: {file_size} B  Modified: {mod_time}")
        return cookie_files

    def clear_cookies(self):
        """Delete all cookie files from the main cookie directory"""
        cookie_files = list(self.cookie_directory.glob("*.txt"))

        if not cookie_files:
            Enhanced_Menu.print_status("No cookie files to delete", "info")
            return
        Enhanced_Menu.print_color(f"Found {len(cookie_files)} cookie file(s) to delete:-")

        # Go through List files to be deleted
        for cookie_file in cookie_files:
            Enhanced_Menu.print_color(f"  - {cookie_file.name}")

        # Ask for confirmation to delete cookie files
        confirm = Enhanced_Menu.get_input(f"\nAre you sure you want to delete ALL cookie files? (y/n):- ", "yn", default=False)
        if not confirm:
            Enhanced_Menu.print_status("Cookie deletion cancelled.", "failure")
            return

        # Delete the files
        deleted_count = 0
        for cookie_file in cookie_files:
            try:
                cookie_file.unlink()
                deleted_count += 1
            except Exception as e:
                Enhanced_Menu.print_status(f"Failed to delete {cookie_file.name}: {e}", "failure")

        # Clear current cookie file reference if it was deleted
        if self.current_cookie_file and not self.current_cookie_file.exists():
            self.current_cookie_file = None
        Enhanced_Menu.print_status(f"\nSuccessfully deleted {deleted_count} cookie file(s) from {self.cookie_directory}", "success")

    def get_arguments(self) -> List[str]:
        """Get spotdl cookie arguments if cookies are available"""
        if self.current_cookie_file and self.current_cookie_file.exists():
            return ["--cookies", str(self.current_cookie_file)]
        return []

    def interactive_menu(self):
        """Run the cookie manager submenu."""
        while True:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Cookie Manager")
            Enhanced_Menu.print_section("Options")
            Enhanced_Menu.print_menu_item(1, "Check browsers for Spotify cookies")
            Enhanced_Menu.print_menu_item(2, "Extract cookies from a browser")
            Enhanced_Menu.print_menu_item(3, "List saved cookie files")
            Enhanced_Menu.print_menu_item(4, "Load cookies from file")
            Enhanced_Menu.print_menu_item(5, "Save current cookies")
            Enhanced_Menu.print_menu_item(6, "Clear all cookie files")
            Enhanced_Menu.print_menu_item(7, "Show current cookie status")
            Enhanced_Menu.print_menu_item(8, "Return to main menu")

            Enhanced_Menu.print_section("Status")
            if self.current_cookie_file:
                Enhanced_Menu.print_status(f"Active cookie file: {self.current_cookie_file.name}", "success")
            else:
                Enhanced_Menu.print_status("No active cookie file", "error")

            choice = Enhanced_Menu.get_input("Select option (1-8)", "int", 1, 8)
            if choice == 1:
                self.get_status()
                input("Press Enter to continue...")
            elif choice == 2:
                Enhanced_Menu.print_section("Available browsers")
                for i, b in enumerate(self.cookie_sources.keys(), 1):
                    print(f"  {Fore.YELLOW}[{i}]{Style.RESET_ALL} {b}")
                browser_input = Enhanced_Menu.get_input("Browser name or number", "str")
                if browser_input.isdigit():
                    idx = int(browser_input)
                    if 1 <= idx <= len(self.cookie_sources):
                        browser = list(self.cookie_sources.keys())[idx - 1]
                        self.extract_cookies(browser)
                else:
                    self.extract_cookies(browser_input.lower())
                input("Press Enter to continue...")
            elif choice == 3:
                files = self.list_cookies()
                if files:
                    load_choice = Enhanced_Menu.get_input("Load a file? (number or Enter to skip)", "str")
                    if load_choice.isdigit():
                        idx = int(load_choice) - 1
                        if 0 <= idx < len(files):
                            self.load_cookies(files[idx])
                input("Press Enter to continue...")
            elif choice == 4:
                fname = Enhanced_Menu.get_input("Cookie filename or path", "str")
                if fname:
                    self.load_cookies(fname)
                input("Press Enter to continue...")
            elif choice == 5:
                if self.current_cookie_file:
                    name = Enhanced_Menu.get_input("Save as name", "str", default="cookies")
                    self.save_cookies(name)
                else:
                    Enhanced_Menu.print_status("No active cookies", "error")
                input("Press Enter to continue...")
            elif choice == 6:
                self.clear_cookies()
                input("Press Enter to continue...")
            elif choice == 7:
                self.get_status()
                if self.current_cookie_file:
                    Enhanced_Menu.print_status(f"Active: {self.current_cookie_file.name}", "success")
                input("Press Enter to continue...")
            elif choice == 8:
                break


class Spotify_Downloader:
    def __init__(self):
        """Initialize the downloader with default settings."""
        # Retry & timeout settings
        self.max_retries = MAX_RETRIES
        self.retry_delay = RETRY_DELAY
        self.download_timeout = DOWNLOAD_TIMEOUT

        # Private configuration attributes
        self._output_directory = Path("Albums")
        self._audio_quality = "320k"
        self._audio_format = "mp3"
        self._filepath = Path("links/spotify_links.txt")
        self._configuration_file = Path("config/spotify_downloader.json")

        self.cookie_manager = CookieManager()
        self.use_cookies = False

        # Create necessary directories
        self._output_directory.mkdir(parents=True, exist_ok=True)
        Path("links").mkdir(parents=True, exist_ok=True)
        Path("log").mkdir(parents=True, exist_ok=True)

        # Load configuration
        self.load_config()

    # -----------------------------------------------------------------
    # Properties for public access to settings
    # -----------------------------------------------------------------
    @property
    def output_directory(self) -> Path:
        return self._output_directory

    @output_directory.setter
    def output_directory(self, value):
        self._output_directory = Path(value)
        self._output_directory.mkdir(parents=True, exist_ok=True)

    @property
    def audio_quality(self) -> str:
        return self._audio_quality

    @audio_quality.setter
    def audio_quality(self, value):
        self._audio_quality = value

    @property
    def audio_format(self) -> str:
        return self._audio_format

    @audio_format.setter
    def audio_format(self, value):
        self._audio_format = value

    # -----------------------------------------------------------------
    # Configuration management
    # -----------------------------------------------------------------
    def load_config(self):
        """Load configuration from json file"""
        primary_config = {
            "output_directory": "Albums",
            "audio_quality": "320k",
            "audio_format": "mp3",
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "download_timeout": self.download_timeout,
            "use_cookies": False
        }

        try:
            if self._configuration_file.exists():
                with open(self._configuration_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    config = {**primary_config, **user_config}
            else:
                config = primary_config
                self.save_config(config)

            # Apply configuration safely
            if "output_directory" in config:
                self.output_directory = config["output_directory"]
            if "audio_quality" in config:
                self.audio_quality = config["audio_quality"]
            if "audio_format" in config:
                self.audio_format = config["audio_format"]
            if "max_retries" in config:
                self.max_retries = config["max_retries"]
            if "retry_delay" in config:
                self.retry_delay = config["retry_delay"]
            if "download_timeout" in config:
                self.download_timeout = config["download_timeout"]
            if "use_cookies" in config:
                self.use_cookies = config["use_cookies"]

        except Exception as e:
            self.log_error(f"Error loading configuration: {e}")
            # Use defaults
            self.output_directory = Path(primary_config["output_directory"])
            self.audio_quality = primary_config["audio_quality"]
            self.audio_format = primary_config["audio_format"]
            self.use_cookies = primary_config["use_cookies"]

    def save_config(self, config: Dict = None):
        """Save configuration to file"""
        try:
            if config is None:
                config = {
                    "output_directory": str(self.output_directory),
                    "audio_quality": self.audio_quality,
                    "audio_format": self.audio_format,
                    "max_retries": self.max_retries,
                    "retry_delay": self.retry_delay,
                    "download_timeout": self.download_timeout,
                    "use_cookies": self.use_cookies
                }

            # Ensure config directory exists
            self._configuration_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self._configuration_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.log_error(f"Error saving configuration: {e}")

    def reset_config(self):
        """Reset all settings to default values"""
        self.output_directory = Path("Albums")
        self.audio_quality = "320k"
        self.audio_format = "mp3"
        self.max_retries = MAX_RETRIES
        self.retry_delay = RETRY_DELAY
        self.download_timeout = DOWNLOAD_TIMEOUT
        self.use_cookies = False
        self.save_config()
        Enhanced_Menu.print_status("Configuration reset to defaults", "success")

    # ====================================
    # Logger Functions
    # ===================================
    def log_success(self, message: str):
        """Logs only successful downloads (to success log)"""
        success_downloads.info(message)
        console_logger.info(f"{Fore.GREEN}{message}{Style.RESET_ALL}")

    def log_failure(self, message: str):
        """Logs only failed downloads (to failed log)"""
        failed_downloads.info(message)
        console_logger.info(f"{Fore.RED}{message}{Style.RESET_ALL}")

    def log_error(self, message: str, exc_info=False):
        """Logs only error in download process (to error log)"""
        error_downloads.error(message, exc_info=exc_info)
        console_logger.info(f"{Fore.YELLOW}{message}{Style.RESET_ALL}")

    # ====================================
    # Preference & Other Helpers
    # ===================================
    def get_user_preferences(self):
        """Takes in user input for the download settings"""
        Enhanced_Menu.print_header("DOWNLOAD SETTINGS", "Configure your music conversion preferenced")

        # Handle choice of bitrate/audio quality inputs
        while True:
            audio_quality_input = Enhanced_Menu.get_input(
                "What bitrate would you like (enter 'choice' to see options):- ",
                "str", default=self.audio_quality)

            if not audio_quality_input:
                self.audio_quality = "320k"
                break

            if audio_quality_input == 'choice':
                print(f"\n{Fore.CYAN}Available qualities:{Style.RESET_ALL}")
                print("  auto     - Let yt-dlp choose the best")
                print("  320k     - High quality (default)")
                print("  256k     - Very good quality")
                print("  192k     - Good quality")
                print("  128k     - Standard quality")
                print("  8k-160k  - Lower qualities")
                continue

            valid_bitrates = ["auto", "disable", "8k", "16k", "24k", "32k", "40k", "48k", "64k",
                              "80k", "96k", "112k", "128k", "160k", "192k", "224k", "256k", "320k"]

            if audio_quality_input in valid_bitrates:
                self.audio_quality = audio_quality_input.lower()
                break
            Enhanced_Menu.print_status("Invalid bitrate. The downloader doesn't support these values", "error")

        # Handle choice of audio format
        while True:
            audio_format_input = Enhanced_Menu.get_input(
                "What format would you like(enter 'choice' to see options):- ",
                "str", default=self.audio_format)

            if not audio_format_input:
                self.audio_format = "mp3"
                break

            if audio_format_input == 'choice':
                print(f"\n{Fore.CYAN}Available formats:{Style.RESET_ALL}")
                print("  mp3  - Most compatible (default)")
                print("  m4a  - Apple format, good quality")
                print("  flac - Lossless audio")
                print("  opus - Excellent compression")
                print("  ogg  - Open format")
                print("  wav  - Uncompressed")
                continue

            if audio_format_input in ["mp3", "flac", "ogg", "opus", "m4a", "wav"]:
                self.audio_format = audio_format_input
                break
            Enhanced_Menu.print_status("Invalid format. Downloader doesn't support this format", "error")

        # Handle choice of output directory
        output_path = Enhanced_Menu.get_input("Enter output directory (default: Albums):- ", "str").strip()
        if output_path:
            self.output_directory = Path(output_path)
        else:
            self.output_directory = Path("Albums")

        # Handles choice for cookies
        Enhanced_Menu.print_status("Cookie Settings", "info")
        print(f"\n{Fore.CYAN}Cookies can help with:{Style.RESET_ALL}")
        print(" Age-restricted content")
        print(" Region-restricted videos")
        print(" Private playlists")

        cookie_choice = Enhanced_Menu.get_input("Use cookies for authentication? (y/n):- ", "yn", default=True)
        self.use_cookies = cookie_choice  # cookie_choice is boolean
        if self.use_cookies:
            Enhanced_Menu.print_status("Note: Make sure you have extracted the cookies beforehand, if make use of Cookie Manager to help you", "info")

    @staticmethod
    def validate_spotify_url(url: str) -> Tuple[bool, Optional[str]]:
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

    def cleanup_directory(self):
        """Removes empty directories after download"""
        removed_count = 0
        for root, dirs, files in os.walk(self.output_directory, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    if not os.listdir(dir_path):
                        os.rmdir(dir_path)
                        removed_count += 1
                except OSError:
                    pass

        if removed_count > 0:
            self.log_success("Cleaned up empty directories")

    def extract_spotify_id(self, url: str) -> str:
        """ Extract Spotify ID from URL """
        patterns = [
            r'spotify\.com/(track|album|playlist)/([A-Za-z0-9]+)',
            r'spotify:(track|album|playlist):([A-Za-z0-9]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(2)
        return None

    def validate_resource(self, url: str) -> Tuple[bool, str, Optional[dict]]:
        """ Validate if a resource is available before downloading to the device """
        print(f"Validating resource: {url}")

        cmd = [
            "spotdl",
            url,
            "--skip-download",
            "--print-json",
            "--no-warnings"
        ]
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.download_timeout,
                check=False
            )
            if result.returncode == 0 and result.stdout.strip():
                try:
                    metadata = json.loads(result.stdout.strip())
                    # Basic sanity checks
                    if not metadata.get("name") and not metadata.get("title"):
                        return False, "Missing title metadata", metadata
                    typ = metadata.get("type", "")

                    # If a playlist or album link is provided, check if there are any tracks in it
                    if typ in ("playlist", "album"):
                        tracks = metadata.get("tracks", [])
                        available = sum(1 for t in tracks if t.get("available", True))
                        total = len(tracks)
                        if available == 0:
                            return False, f"No available tracks in this {typ}", metadata
                        return True, f"{typ} available ({available}/{total} tracks)", metadata
                    else:  # track
                        duration = metadata.get("duration", 0)
                        if duration <= 0:
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
                    return False, f"Validation failed: {err[:100]}", None
        except subprocess.TimeoutExpired:
            return False, "Validation timeout", None
        except FileNotFoundError:
            return False, "spotdl not found – please install it first", None
        except Exception as e:
            return False, f"Validation error: {str(e)[:100]}", None

    def parse_size(self, size_str: str) -> Optional[int]:
        """Parse size string to bytes"""
        size_str = size_str.strip().upper()

        units = {
            'B': 1, 'K': 1024, 'M': 1024 ** 2, 'G': 1024 ** 3, 'T': 1024 ** 4,
            'KB': 1024, 'MB': 1024 ** 2, 'GB': 1024 ** 3, 'TB': 1024 ** 4,
            'KIB': 1024, 'MIB': 1024 ** 2, 'GIB': 1024 ** 3, 'TIB': 1024 ** 4
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

    # ==================================== The Download Function ===================================
    @staticmethod
    def rate_limit(calls_per_minute=60):
        """Rate limit decorator to avoid blockage from (Improved)"""
        def decorator(func):
            last_called = [0.0]
            call_lock = threading.Lock()

            @wraps(func)
            def wrapper(*args, **kwargs):
                with call_lock:
                    elapsed_time = time.time() - last_called[0]
                    wait_time = (60.0 / calls_per_minute) - elapsed_time

                    if wait_time > 0:
                        time.sleep(wait_time)
                    last_called[0] = time.time()

                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_called[0] = time.time() - (60.0 / calls_per_minute)
                        raise
            return wrapper
        return decorator

    @rate_limit(calls_per_minute=30)
    def run_download(self, url: str, output_template: str, additional_args=None):
        """ Run spotdl download with modern syntax """
        command = [
            "spotdl",
            "download",
            url,
            "--output", output_template,
            "--overwrite", "skip",
            "--bitrate", self.audio_quality,
            "--format", self.audio_format
        ]

        if self.use_cookies:
            cookie_args = self.cookie_manager.get_arguments()
            if cookie_args:
                command.extend(cookie_args)
                self.log_success("Using cookies from authentication")
            else:
                self.log_error("No active cookies found")

        if additional_args:
            command.extend(additional_args)

        # Initialize progress bar
        with tqdm(
            desc="Downloading",
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            leave=False,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]",
            dynamic_ncols=True
        ) as pbar:
            try:
                # Start the subprocess
                result = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    encoding='utf-8',
                    errors='replace'
                )

                # Parse output in real-time
                for line in iter(result.stdout.readline, ''):
                    line = line.strip()

                    if "[download]" in line:
                        # Parse percentage
                        percent_match = re.search(r'(\d+\.?\d*)%', line)
                        if percent_match:
                            percent = float(percent_match.group(1))
                            pbar.set_description(f"{Fore.CYAN}Downloading: {percent:.1f}%{Style.RESET_ALL}")

                        # Parse total size
                        size_match = re.search(r'of\s+([\d\.]+\s*[KMGT]?i?B)', line)
                        if size_match and pbar.total is None:
                            total_str = size_match.group(1)
                            total_bytes = self.parse_size(total_str)
                            if total_bytes:
                                pbar.total = total_bytes

                        # Parse downloaded size
                        downloaded_match = re.search(r'([\d\.]+\s*[KMGT]?i?B)\s+at', line) or \
                                           re.search(r'([\d\.]+\s*[KMGT]?i?B)\s+ETA', line) or \
                                           re.search(r'([\d\.]+\s*[KMGT]?i?B)\s*\/', line)
                        if downloaded_match:
                            downloaded_str = downloaded_match.group(1)
                            downloaded_bytes = self.parse_size(downloaded_str)
                            if downloaded_bytes:
                                pbar.n = downloaded_bytes
                                pbar.refresh()

                        # Speed & ETA (fixed)
                        speed_match = re.search(r'at\s+([\d\.]+\s*[KMGT]?i?B/s)', line)
                        eta_match = re.search(r'ETA\s+([\d:]+)', line)
                        if speed_match or eta_match:
                            postfix = []
                            if speed_match:
                                postfix.append(f"Speed: {speed_match.group(1)}")
                            if eta_match:
                                postfix.append(f"ETA: {eta_match.group(1)}")
                            pbar.set_postfix_str(" ".join(postfix))

                    # When finished
                    if "100%" in line or "already been downloaded" in line or "[Merger]" in line:
                        if pbar.total and pbar.n < pbar.total:
                            pbar.n = pbar.total
                        pbar.set_description(f"{Fore.GREEN}Downloaded{Style.RESET_ALL}")
                        pbar.set_postfix_str("")

                # Wait for process to finish with timeout
                result.wait(timeout=self.download_timeout)
                if result.returncode == 0:
                    self.log_success(f"Downloaded: {url}")
                    return True
                else:
                    self.log_failure(f"Download failed (code {result.returncode}): {url}")
                    return False
            except subprocess.TimeoutExpired:
                result.kill()
                self.log_error(f"Timeout downloading {url}")
                return False
            except Exception as e:
                self.log_error(f"Unexpected error: {e}", exc_info=True)
                return False

    # ====================================
    # Main Download Functions
    # ===================================
    @rate_limit(calls_per_minute=30)
    def download_track(self):
        """Download a single track"""
        while True:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Download Track")
            url = Enhanced_Menu.get_input("Enter Spotify track URL (or 'back')", "str")
            if url and url.lower() == "back":
                return False
            if not url:
                Enhanced_Menu.print_status("No URL provided", "error")
                continue

            valid, typ = self.validate_spotify_url(url)
            if not valid:
                Enhanced_Menu.print_status("Invalid Spotify URL", "error")
                continue
            if typ != "track":
                Enhanced_Menu.print_status(f"URL is a {typ}, not a track", "error")
                proceed = Enhanced_Menu.get_input("Continue anyway?", "yn", default=False)
                if not proceed:
                    continue

            # Validate
            Enhanced_Menu.print_status("Validating resource...", "info")
            available, msg, meta = self.validate_resource(url)
            if not available:
                Enhanced_Menu.print_status(f"Validation failed: {msg}", "error")
                retry = Enhanced_Menu.get_input("Try to download anyway?", "yn", default=True)
                if not retry:
                    continue
            else:
                Enhanced_Menu.print_status(msg, "success")
                if meta:
                    print(f"\n{Fore.CYAN}Track details:{Style.RESET_ALL}")
                    print(f"  Title:  {Fore.YELLOW}{meta.get('name', 'Unknown')}{Style.RESET_ALL}")
                    artists = meta.get('artists', [{}])
                    if artists:
                        print(f"  Artist: {Fore.YELLOW}{artists[0].get('name', 'Unknown')}{Style.RESET_ALL}")
                    duration = meta.get('duration', 0)
                    if duration:
                        print(f"  Duration: {Fore.YELLOW}{duration // 60}:{duration % 60:02d}{Style.RESET_ALL}")

            # Optional config
            if Enhanced_Menu.get_input("Configure download settings?", "yn", default=False):
                self.get_user_preferences()

            output_template = str(self.output_directory / "{artists} - {title}.{output-ext}")
            success = False
            for attempt in range(1, self.max_retries + 1):
                Enhanced_Menu.print_status(f"Attempt {attempt}/{self.max_retries}", "info")
                if attempt > 1:
                    Enhanced_Menu.print_status(f"Waiting {self.retry_delay} seconds before retry...", "info")
                    time.sleep(self.retry_delay)
                if self.run_download(url, output_template):
                    success = True
                    break
            if success:
                self.log_success(f"Successfully downloaded {url}")
                another = Enhanced_Menu.get_input("Download another track?", "yn", default=True)
                if another:
                    continue
                else:
                    return True
            else:
                self.log_failure(f"Failed to download after {self.max_retries} attempts: {url}")
                return False

    @rate_limit(calls_per_minute=30)
    def download_album(self):
        """Download an album"""
        while True:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Download Album")
            url = Enhanced_Menu.get_input("Enter Spotify album URL (or 'back')", "str")
            if url and url.lower() == "back":
                return False
            if not url:
                Enhanced_Menu.print_status("No URL provided", "error")
                continue

            valid, typ = self.validate_spotify_url(url)
            if not valid:
                Enhanced_Menu.print_status("Invalid Spotify URL", "error")
                continue
            if typ != "album":
                Enhanced_Menu.print_status(f"URL is a {typ}, not an album", "error")
                proceed = Enhanced_Menu.get_input("Continue anyway?", "yn", default=False)
                if not proceed:
                    continue

            Enhanced_Menu.print_status("Validating album...", "info")
            available, msg, meta = self.validate_resource(url)
            if not available:
                Enhanced_Menu.print_status(f"Validation failed: {msg}", "error")
                retry = Enhanced_Menu.get_input("Try to download anyway?", "yn", default=True)
                if not retry:
                    continue
            else:
                Enhanced_Menu.print_status(msg, "success")
                if meta:
                    print(f"\n{Fore.CYAN}Album details:{Style.RESET_ALL}")
                    print(f"  Album:  {Fore.YELLOW}{meta.get('name', 'Unknown')}{Style.RESET_ALL}")
                    artists = meta.get('artists', [{}])
                    if artists:
                        print(f"  Artist: {Fore.YELLOW}{artists[0].get('name', 'Unknown')}{Style.RESET_ALL}")
                    tracks = meta.get('tracks', [])
                    if tracks:
                        avail = sum(1 for t in tracks if t.get('available', True))
                        print(f"  Tracks: {Fore.YELLOW}{avail}/{len(tracks)} available{Style.RESET_ALL}")

            if Enhanced_Menu.get_input("Configure download settings?", "yn", default=False):
                self.get_user_preferences()

            output_template = str(self.output_directory / "{artists}/{album}/{artist} - {title}.{output-ext}")
            success = False
            for attempt in range(1, self.max_retries + 1):
                Enhanced_Menu.print_status(f"Attempt {attempt}/{self.max_retries}", "info")
                if attempt > 1:
                    Enhanced_Menu.print_status(f"Waiting {self.retry_delay} seconds before retry...", "info")
                    time.sleep(self.retry_delay)
                if self.run_download(url, output_template):
                    success = True
                    break
            if success:
                self.log_success(f"Successfully downloaded {url}")
                another = Enhanced_Menu.get_input("Download another album?", "yn", default=True)
                if another:
                    continue
                else:
                    return True
            else:
                self.log_failure(f"Failed to download after {self.max_retries} attempts: {url}")
                return False

    @rate_limit(calls_per_minute=30)
    def download_playlist(self):
        """Download a playlist"""
        while True:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Download Playlist")
            url = Enhanced_Menu.get_input("Enter Spotify playlist URL (or 'back')", "str")
            if url and url.lower() == "back":
                return False
            if not url:
                Enhanced_Menu.print_status("No URL provided", "error")
                continue

            valid, typ = self.validate_spotify_url(url)
            if not valid:
                Enhanced_Menu.print_status("Invalid Spotify URL", "error")
                continue
            if typ != "playlist":
                Enhanced_Menu.print_status(f"URL is a {typ}, not a playlist", "error")
                proceed = Enhanced_Menu.get_input("Continue anyway?", "yn", default=False)
                if not proceed:
                    continue

            Enhanced_Menu.print_status("Validating playlist...", "info")
            available, msg, meta = self.validate_resource(url)
            if not available:
                Enhanced_Menu.print_status(f"Validation failed: {msg}", "error")
                retry = Enhanced_Menu.get_input("Try to download anyway?", "yn", default=True)
                if not retry:
                    continue
            else:
                Enhanced_Menu.print_status(msg, "success")
                if meta:
                    print(f"\n{Fore.CYAN}Playlist details:{Style.RESET_ALL}")
                    print(f"  Playlist: {Fore.YELLOW}{meta.get('name', 'Unknown')}{Style.RESET_ALL}")
                    tracks = meta.get('tracks', [])
                    if tracks:
                        avail = sum(1 for t in tracks if t.get('available', True))
                        print(f"  Tracks: {Fore.YELLOW}{avail}/{len(tracks)} available{Style.RESET_ALL}")

            if Enhanced_Menu.get_input("Configure download settings?", "yn", default=False):
                self.get_user_preferences()

            output_template = str(self.output_directory / "{playlist}/{artists} - {title}.{output-ext}")
            extra = ["--playlist-numbering", "--playlist-retain-track-cover"]
            success = False
            for attempt in range(1, self.max_retries + 1):
                Enhanced_Menu.print_status(f"Attempt {attempt}/{self.max_retries}", "info")
                if attempt > 1:
                    Enhanced_Menu.print_status(f"Waiting {self.retry_delay} seconds before retry...", "info")
                    time.sleep(self.retry_delay)
                if self.run_download(url, output_template, additional_args=extra):
                    success = True
                    break
            if success:
                self.log_success(f"Successfully downloaded {url}")
                another = Enhanced_Menu.get_input("Download another playlist?", "yn", default=True)
                if another:
                    continue
                else:
                    return True
            else:
                self.log_failure(f"Failed to download after {self.max_retries} attempts: {url}")
                return False

    @rate_limit(calls_per_minute=30)
    def download_from_file(self) -> bool:
        """Batch download from a text file containing one URL per line."""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Batch Download", "Download multiple URLs from a file")
        default_file = "links/spotify_links.txt"
        Path("links").mkdir(exist_ok=True)

        filepath = Enhanced_Menu.get_input(
            f"Path to text file (default: {default_file})",
            "str", default=default_file
        )
        filepath = Path(filepath)
        if not filepath.exists():
            Enhanced_Menu.print_status(f"File not found: {filepath}", "error")
            return False

        # Validation options
        Enhanced_Menu.print_section("Validation Options")
        Enhanced_Menu.print_menu_item(1, "Validate all resources before downloading", "Recommended")
        Enhanced_Menu.print_menu_item(2, "Skip validation (faster, may fail more)")
        Enhanced_Menu.print_menu_item(3, "Validate without cache (fresh check)")
        val_choice = Enhanced_Menu.get_input("Choose (1-3)", "int", 1, 3, default=1)

        if Enhanced_Menu.get_input("Configure download settings for this batch?", "yn", default=False):
            self.get_user_preferences()

        # Read file, strip comments, skip empty lines
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = [line.rstrip() for line in f if line.strip()]
        except Exception as e:
            self.log_failure(f"Cannot read file: {e}")
            return False

        urls_to_process = []
        for line in lines:
            if "# DOWNLOADED" in line or "# FAILED" in line:
                continue
            url_part = line.split("#")[0].strip()
            if url_part:
                urls_to_process.append(url_part)

        if not urls_to_process:
            Enhanced_Menu.print_status("No new URLs to process", "info")
            return True

        # Validate if chosen
        validation_results = {}
        if val_choice in (1, 3):
            Enhanced_Menu.print_status(f"Validating {len(urls_to_process)} URLs...", "info")
            skip_cache = (val_choice == 3)
            for i, url in enumerate(urls_to_process, 1):
                print(f"  {i}/{len(urls_to_process)}: {url[:60]}...")
                available, msg, _ = self.validate_resource(url)
                validation_results[url] = (available, msg)
            available_count = sum(1 for v in validation_results.values() if v[0])
            Enhanced_Menu.print_section("Validation Summary")
            Enhanced_Menu.print_status(f"Available: {available_count}/{len(urls_to_process)}", "success")
            Enhanced_Menu.print_status(f"Unavailable: {len(urls_to_process) - available_count}",
                                       "failure" if available_count < len(urls_to_process) else "info")

            # Ask how to proceed
            Enhanced_Menu.print_section("Download Options")
            Enhanced_Menu.print_menu_item(1, "Download only available resources")
            Enhanced_Menu.print_menu_item(2, "Download all resources (may fail)")
            Enhanced_Menu.print_menu_item(3, "Cancel")
            dl_choice = Enhanced_Menu.get_input("Choose (1-3)", "int", 1, 3, default=1)
            if dl_choice == 3:
                Enhanced_Menu.print_status("Cancelled", "info")
                return False
            if dl_choice == 1:
                urls_to_download = [url for url in urls_to_process if validation_results[url][0]]
            else:
                urls_to_download = urls_to_process
        else:
            urls_to_download = urls_to_process

        Enhanced_Menu.print_status(f"Downloading {len(urls_to_download)} item(s)...", "info")

        success_count = 0
        failed_count = 0

        # We'll rewrite the file after download with status markers
        updated_lines = lines[:]  # copy

        for i, url in enumerate(urls_to_download, 1):
            Enhanced_Menu.print_section(f"Processing {i}/{len(urls_to_download)}")
            print(f"URL: {url[:80]}...")

            # Determine output template based on URL type
            valid, typ = self.validate_spotify_url(url)
            if valid and typ == "playlist":
                out_tmpl = str(self.output_directory / "{playlist}/{artists} - {title}.{output-ext}")
                extra = ["--playlist-numbering", "--playlist-retain-track-cover"]
            elif valid and typ == "album":
                out_tmpl = str(self.output_directory / "{artists}/{album}/{artist} - {title}.{output-ext}")
                extra = None
            else:
                out_tmpl = str(self.output_directory / "{artists} - {title}.{output-ext}")
                extra = None

            success = False
            for attempt in range(1, self.max_retries + 1):
                if attempt > 1:
                    Enhanced_Menu.print_status(f"Retry {attempt}/{self.max_retries}", "info")
                    time.sleep(self.retry_delay)
                if self.run_download(url, out_tmpl, additional_args=extra):
                    success = True
                    break
            if success:
                success_count += 1
                self.log_success(f"Downloaded: {url}")
                # Mark as DOWNLOADED in file
                for idx, line in enumerate(updated_lines):
                    if line.strip().startswith(url.split("#")[0].strip()):
                        if "#" in line:
                            base = line.split("#")[0].strip()
                            updated_lines[idx] = f"{base} # DOWNLOADED"
                        else:
                            updated_lines[idx] = f"{line} # DOWNLOADED"
                        break
            else:
                failed_count += 1
                self.log_failure(f"Failed: {url}")
                for idx, line in enumerate(updated_lines):
                    if line.strip().startswith(url.split("#")[0].strip()):
                        if "#" in line:
                            base = line.split("#")[0].strip()
                            updated_lines[idx] = f"{base} # FAILED"
                        else:
                            updated_lines[idx] = f"{line} # FAILED"
                        break

        # Write updated file
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(updated_lines))
        except Exception as e:
            self.log_failure(f"Could not update file: {e}")

        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Batch Download Summary")
        Enhanced_Menu.print_status(f"Successful: {success_count}", "success")
        Enhanced_Menu.print_status(f"Failed: {failed_count}", "failure" if failed_count > 0 else "info")
        Enhanced_Menu.print_status(f"Total: {len(urls_to_download)}", "info")
        return failed_count == 0

    @rate_limit(calls_per_minute=30)
    def search_and_download(self) -> bool:
        """Search for a song by name and download."""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Search & Download")
        song_query = Enhanced_Menu.get_input("Enter song name or search query", "str")
        if not song_query:
            Enhanced_Menu.print_status("No query entered", "error")
            return False

        if Enhanced_Menu.get_input("Configure download settings?", "yn", default=False):
            self.get_user_preferences()

        output_template = str(self.output_directory / "{artists} - {title}.{output-ext}")
        success = False
        for attempt in range(1, self.max_retries + 1):
            Enhanced_Menu.print_status(f"Attempt {attempt}/{self.max_retries}", "info")
            if attempt > 1:
                Enhanced_Menu.print_status(f"Waiting {self.retry_delay} seconds before retry...", "info")
                time.sleep(self.retry_delay)
            try:
                if self.run_download(f":{song_query}", output_template):
                    success = True
                    break
            except Exception as e:
                self.log_error(f"Unexpected error: {e}")
        if success:
            self.log_success(f"Successfully downloaded: '{song_query}'")
            return True
        else:
            self.log_failure(f"Failed to download after {self.max_retries} attempts: '{song_query}'")
            return False

    # ====================================
    # Special Download Functions
    # ===================================
    @rate_limit(calls_per_minute=30)
    def download_user_playlist(self):
        """Download a user's playlist (requires authentication)"""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("User Playlist Download", "Download your personal playlists")

        Enhanced_Menu.print_status("Note: This requires Spotify authentication", "warning")
        Enhanced_Menu.print_status("You will be redirected to the Spotify website for authorization", "info")

        proceed = Enhanced_Menu.get_input("Continue? (y/n): ", "yn", default=True)
        if not proceed:
            return False

        if Enhanced_Menu.get_input("Configure download settings? (y/n): ", "yn", default=False):
            self.get_user_preferences()

        output_template = str(self.output_directory / "{playlist}/{artists} - {title}.{output-ext}")

        Enhanced_Menu.print_status("Starting download...", "info")

        try:
            result = subprocess.run([
                "spotdl",
                "download",
                "all-user-playlists",
                "--user-auth",
                "--output", output_template,
                "--overwrite", "skip",
                "--bitrate", self.audio_quality,
                "--format", self.audio_format,
            ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                timeout=self.download_timeout
            )

            if result.returncode == 0:
                self.log_success("Successfully downloaded user playlists")
                if result.stdout:
                    print(f"\n{Fore.CYAN}Output:{Style.RESET_ALL}")
                    print(result.stdout[:500])
                return True
            else:
                self.log_failure(f"Failed to download user playlists. Return code: {result.returncode}")
                if result.stderr:
                    self.log_error(f"Error: {result.stderr[:500]}")
                return False

        except Exception as e:
            self.log_error(f"Unexpected exception: {e}")
            return False

    @rate_limit(calls_per_minute=30)
    def download_user_liked_songs(self):
        """Download a user's liked songs"""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Download Liked Songs", "Download your liked songs")

        Enhanced_Menu.print_status("Note: This requires Spotify authentication", "warning")
        Enhanced_Menu.print_status("You will be redirected to the Spotify website for authorization", "info")

        proceed = Enhanced_Menu.get_input("Continue? (y/n): ", "yn", default=True)
        if not proceed:
            return False

        if Enhanced_Menu.get_input("Configure download settings? (y/n): ", "yn", default=False):
            self.get_user_preferences()

        output_template = str(self.output_directory / "Liked Songs/{artists} - {title}.{output-ext}")
        Enhanced_Menu.print_status("Starting download...", "info")

        try:
            result = subprocess.run([
                "spotdl",
                "download",
                "saved",
                "--user-auth",
                "--output", output_template,
                "--overwrite", "skip",
                "--bitrate", self.audio_quality,
                "--format", self.audio_format,
            ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                timeout=self.download_timeout
            )

            if result.returncode == 0:
                self.log_success("Successfully downloaded liked songs")
                if result.stdout:
                    print(f"\n{Fore.CYAN}Output:{Style.RESET_ALL}")
                    print(result.stdout[:500])
                return True
            else:
                self.log_failure(f"Failed to download liked songs. Return code: {result.returncode}")
                if result.stderr:
                    self.log_error(f"Error: {result.stderr[:500]}")
                return False

        except Exception as e:
            self.log_error(f"Unexpected exception: {e}")
            return False

    @rate_limit(calls_per_minute=30)
    def download_user_saved_albums(self):
        """Download a user's saved albums"""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Download Saved Albums", "Download your saved albums")

        Enhanced_Menu.print_status("Note: This requires Spotify authentication", "warning")
        Enhanced_Menu.print_status("You will be redirected to the Spotify website for authorization", "info")

        proceed = Enhanced_Menu.get_input("Continue? (y/n): ", "yn", default=True)
        if not proceed:
            return False

        if Enhanced_Menu.get_input("Configure download settings? (y/n): ", "yn", default=False):
            self.get_user_preferences()

        output_template = str(self.output_directory / "{artists}/{album}/{artists} - {title}.{output-ext}")

        Enhanced_Menu.print_status("Starting download...", "info")

        try:
            result = subprocess.run([
                "spotdl",
                "download",
                "all-user-saved-albums",
                "--user-auth",
                "--output", output_template,
                "--overwrite", "skip",
                "--bitrate", self.audio_quality,
                "--format", self.audio_format,
            ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                timeout=self.download_timeout
            )

            if result.returncode == 0:
                self.log_success("Successfully downloaded saved albums")
                if result.stdout:
                    print(f"\n{Fore.CYAN}Output:{Style.RESET_ALL}")
                    print(result.stdout[:500])
                return True
            else:
                self.log_failure(f"Failed to download saved albums. Return code: {result.returncode}")
                if result.stderr:
                    self.log_error(f"Error: {result.stderr[:500]}")
                return False

        except Exception as e:
            self.log_error(f"Unexpected exception: {e}")
            return False

    # ====================================
    # Check Spotdl Functions
    # ===================================
    @staticmethod
    def check_spotdl() -> bool:
        """Verify spotdl is installed and print version."""
        spotdl = shutil.which("spotdl")
        if not spotdl:
            Enhanced_Menu.print_status("spotdl not found in PATH", "error")
            return False
        try:
            result = subprocess.run(
                ["spotdl", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=False
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                Enhanced_Menu.print_status(f"spotdl version: {version}", "success")
                return True
            else:
                Enhanced_Menu.print_status("spotdl --version failed", "error")
                return False
        except Exception as e:
            Enhanced_Menu.print_status(f"Error checking spotdl: {e}", "error")
            return False

    @staticmethod
    def show_spotdl_help():
        """Display spotdl help."""
        try:
            result = subprocess.run(
                ["spotdl", "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            if result.returncode == 0:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("SpotDL Help")
                print(result.stdout)
            else:
                Enhanced_Menu.print_status("Could not get spotdl help", "error")
        except Exception as e:
            Enhanced_Menu.print_status(f"Error: {e}", "error")
        input("Press Enter to continue...")

    @staticmethod
    def check_ffmpeg() -> bool:
        """Check if ffmpeg is installed."""
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            Enhanced_Menu.print_status("ffmpeg not found – audio conversion may fail", "error")
            return False
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=False
            )
            if result.returncode == 0:
                version = result.stdout.splitlines()[0]
                Enhanced_Menu.print_status(f"ffmpeg: {version[:60]}...", "success")
                return True
            else:
                Enhanced_Menu.print_status("ffmpeg not working", "error")
                return False
        except Exception as e:
            Enhanced_Menu.print_status(f"ffmpeg check failed: {e}", "error")
            return False

    @staticmethod
    def check_dependencies() -> bool:
        """Check for required Python packages."""
        missing = []
        for pkg in ["browser_cookie3", "colorama", "tqdm", "spotdl"]:
            try:
                __import__(pkg.replace("-", "_"))
            except ImportError:
                missing.append(pkg)
        if missing:
            Enhanced_Menu.print_status(f"Missing packages: {', '.join(missing)}", "error")
            print("Install with: pip install " + " ".join(missing))
            return False
        return True

    @staticmethod
    def setup_dependencies():
        """Attempt to install missing dependencies."""
        for pkg in ["spotdl", "browser_cookie3", "tqdm", "colorama"]:
            try:
                __import__(pkg.replace("-", "_"))
                Enhanced_Menu.print_status(f"{pkg} already installed", "success")
            except ImportError:
                Enhanced_Menu.print_status(f"Installing {pkg}...", "info")
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

    def troubleshooting(self):
        """Run a diagnostic and suggest fixes."""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Troubleshooting")
        print("Running diagnostics...\n")

        # spotdl
        Enhanced_Menu.print_status("1. Checking spotdl...", "info")
        if not self.check_spotdl():
            if Enhanced_Menu.get_input("Install spotdl now?", "yn", default=True):
                subprocess.check_call([sys.executable, "-m", "pip", "install", "spotdl"])
        # ffmpeg
        Enhanced_Menu.print_status("\n2. Checking ffmpeg...", "info")
        self.check_ffmpeg()
        # network test
        Enhanced_Menu.print_status("\n3. Testing Spotify access...", "info")
        test_url = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"  # public track
        available, msg, _ = self.validate_resource(test_url)
        if available:
            Enhanced_Menu.print_status("Spotify accessible", "success")
        else:
            Enhanced_Menu.print_status(f"Spotify access issue: {msg}", "error")
        # directories
        Enhanced_Menu.print_status("\n4. Checking directories...", "info")
        for d in ["log", "Albums", "links", "cookies"]:
            p = Path(d)
            if p.exists():
                Enhanced_Menu.print_status(f"  {d}/ exists", "success")
            else:
                Enhanced_Menu.print_status(f"  {d}/ missing (will be created)", "warning")
        input("\nPress Enter to continue...")
        return True

    @staticmethod
    def program_info():
        """Display program information"""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Spotify Downloader", "Interactive Spotify Music Downloader")

        print(f"""
                {Fore.CYAN}Description:{Style.RESET_ALL}
                A comprehensive tool for downloading music from Spotify with support for 
                albums, playlists, and individual tracks.

                {Fore.CYAN}Features:{Style.RESET_ALL}
                • Download single tracks from Spotify
                • Download complete albums from Spotify
                • Download playlists with metadata preservation
                • Batch download from text files
                • Search and download songs by name
                • Download personal playlists, liked songs, and saved albums (with authentication)
                • Customizable audio format and quality
                • Progress tracking with visual feedback

                {Fore.CYAN}Supported Bitrates:{Style.RESET_ALL}
                320k, 256k, 128k, etc.

                {Fore.CYAN}Supported Audio Formats:{Style.RESET_ALL}
                MP3, M4A, FLAC, OGG, OPUS, WAV

                {Fore.CYAN}Usage Tips:{Style.RESET_ALL}
                • Use authentication for personal content
                • Configure settings before large downloads
                • Use batch files for multiple downloads
                • Monitor disk space for large downloads
        """)


def main():
    """Main menu loop."""
    Enhanced_Menu.clear_screen()

    # ASCII art header
    print(f"{Fore.CYAN}{'=' * 80}{Style.RESET_ALL}")
    print(f"""{Fore.GREEN}{Style.BRIGHT}
    ███╗   ███╗██╗   ██╗███████╗██╗ ██████╗     ██████╗ ██████╗ ███╗   ██╗██╗   ██╗███████╗██████╗ ████████╗███████╗██████╗ 
    ████╗ ████║██║   ██║██╔════╝██║██╔════╝    ██╔════╝██╔═══██╗████╗  ██║██║   ██║██╔════╝██╔══██╗╚══██╔══╝██╔════╝██╔══██╗
    ██╔████╔██║██║   ██║███████╗██║██║         ██║     ██║   ██║██╔██╗ ██║██║   ██║█████╗  ██████╔╝   ██║   █████╗  ██████╔╝
    ██║╚██╔╝██║██║   ██║╚════██║██║██║         ██║     ██║   ██║██║╚██╗██║╚██╗ ██╔╝██╔══╝  ██╔══██╗   ██║   ██╔══╝  ██╔══██╗
    ██║ ╚═╝ ██║╚██████╔╝███████║██║╚██████╗    ╚██████╗╚██████╔╝██║ ╚████║ ╚████╔╝ ███████╗██║  ██║   ██║   ███████╗██║  ██║
    ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝ ╚═════╝     ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝                                                                                                 
    {Style.RESET_ALL}""")
    print(f"{Fore.CYAN}{'=' * 80}{Style.RESET_ALL}")

    # Initialise downloader
    if not Spotify_Downloader.check_dependencies():
        print("\nMissing dependencies. Please install them and restart.")
        sys.exit(1)

    downloader = Spotify_Downloader()

    # Menu actions
    def settings_menu():
        """Submenu for program settings."""
        while True:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Program Settings")
            Enhanced_Menu.print_section("Audio Settings")
            Enhanced_Menu.print_menu_item(1, f"Audio Format (current: {downloader.audio_format.upper()})")
            Enhanced_Menu.print_menu_item(2, f"Audio Quality (current: {downloader.audio_quality})")
            Enhanced_Menu.print_section("Output")
            Enhanced_Menu.print_menu_item(3, f"Output Directory (current: {downloader.output_directory})")
            Enhanced_Menu.print_section("Configuration")
            Enhanced_Menu.print_menu_item(4, "Save Settings")
            Enhanced_Menu.print_menu_item(5, "Load Settings")
            Enhanced_Menu.print_menu_item(6, "Reset to Defaults")
            Enhanced_Menu.print_section("Navigation")
            Enhanced_Menu.print_menu_item(7, "Back to Main Menu")

            choice = Enhanced_Menu.get_input("Select option", "int", 1, 7)
            if choice == 1:
                fmt = Enhanced_Menu.get_input("Enter format (mp3, flac, m4a, opus, ogg, wav)", "str",
                                              default=downloader.audio_format)
                if fmt:
                    downloader.audio_format = fmt
            elif choice == 2:
                q = Enhanced_Menu.get_input("Enter bitrate (e.g., 320k, 192k, auto)", "str",
                                            default=downloader.audio_quality)
                if q:
                    downloader.audio_quality = q
            elif choice == 3:
                d = Enhanced_Menu.get_input("Enter output directory", "str", default=str(downloader.output_directory))
                if d:
                    downloader.output_directory = d
            elif choice == 4:
                downloader.save_config()
                Enhanced_Menu.print_status("Settings saved", "success")
                time.sleep(1)
            elif choice == 5:
                downloader.load_config()
                Enhanced_Menu.print_status("Settings loaded", "success")
                time.sleep(1)
            elif choice == 6:
                if Enhanced_Menu.get_input("Reset all settings to defaults?", "yn", default=False):
                    downloader.reset_config()
                    Enhanced_Menu.print_status("Settings reset", "success")
                    time.sleep(1)
            elif choice == 7:
                break
            input("Press Enter to continue...")

    def exit_program():
        """Clean shutdown."""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Thank you for using Spotify Downloader!")
        print("\nGoodbye!\n")
        downloader.cleanup_directory()
        sys.exit(0)

    actions = {
        1: downloader.download_track,
        2: downloader.download_album,
        3: downloader.download_playlist,
        4: downloader.download_from_file,
        5: downloader.search_and_download,
        6: downloader.download_user_playlist,
        7: downloader.download_user_liked_songs,
        8: downloader.download_user_saved_albums,
        9: Spotify_Downloader.check_spotdl,
        10: Spotify_Downloader.show_spotdl_help,
        11: settings_menu,
        12: downloader.troubleshooting,
        13: lambda: downloader.cookie_manager.interactive_menu(),
        14: Spotify_Downloader.program_info,
        15: exit_program
    }

    # Main loop
    while True:
        try:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Main Menu", "Select an option")

            Enhanced_Menu.print_section("📥 Download")
            Enhanced_Menu.print_menu_item(1, "Download Track")
            Enhanced_Menu.print_menu_item(2, "Download Album")
            Enhanced_Menu.print_menu_item(3, "Download Playlist")
            Enhanced_Menu.print_menu_item(4, "Batch Download (from file)")
            Enhanced_Menu.print_menu_item(5, "Search & Download")

            Enhanced_Menu.print_section("👤 Personal (requires login)")
            Enhanced_Menu.print_menu_item(6, "Download Your Playlists")
            Enhanced_Menu.print_menu_item(7, "Download Liked Songs")
            Enhanced_Menu.print_menu_item(8, "Download Saved Albums")

            Enhanced_Menu.print_section("🛠️ Tools")
            Enhanced_Menu.print_menu_item(9, "Check spotdl Installation")
            Enhanced_Menu.print_menu_item(10, "Show spotdl Help")
            Enhanced_Menu.print_menu_item(11, "Settings")
            Enhanced_Menu.print_menu_item(12, "Troubleshooting")
            Enhanced_Menu.print_menu_item(13, "Cookie Manager")

            Enhanced_Menu.print_section("ℹ️ Info")
            Enhanced_Menu.print_menu_item(14, "About")
            Enhanced_Menu.print_menu_item(15, "Exit")

            print(
                f"\n{Style.DIM}Current settings: {downloader.audio_format.upper()} / {downloader.audio_quality} / {downloader.output_directory}{Style.RESET_ALL}")

            choice = Enhanced_Menu.get_input("Enter choice", "int", 1, 15)
            if choice == 15:
                exit_program()
            action = actions.get(choice)
            if action:
                Enhanced_Menu.clear_screen()
                try:
                    result = action()
                    if result is False:  # explicit failure
                        Enhanced_Menu.print_status("Operation failed", "failure")
                    elif result is None:  # cancelled etc.
                        Enhanced_Menu.print_status("Operation cancelled", "info")
                except KeyboardInterrupt:
                    Enhanced_Menu.print_status("Interrupted", "warning")
                except Exception as e:
                    logger.error(f"Menu action error: {e}", exc_info=True)
                    Enhanced_Menu.print_status(f"Unexpected error: {e}", "error")
            else:
                Enhanced_Menu.print_status("Invalid choice", "error")

            if choice != 15:
                if Enhanced_Menu.get_input("Return to main menu?", "yn", default=True):
                    continue
                else:
                    exit_program()
        except KeyboardInterrupt:
            print("\nInterrupted by user")
            exit_program()
        except Exception as e:
            logger.error(f"Main loop error: {e}", exc_info=True)
            if Enhanced_Menu.get_input("Continue?", "yn", default=True):
                continue
            else:
                exit_program()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting... Goodbye!")
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)