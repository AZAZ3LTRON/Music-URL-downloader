#!/usr/bin/env python3
"""
Interactive Playlist/Album/Track Downloader using yt-dlp

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

Now Improved with
- Progress bar for downloads
- Batch Processing (with parallel downloads)
- Resource Validation (Check if links are available)

Please use the latest version of YT-DLP, upgrade it using "pip install --upgrade yt-dlp" or "yt-dlp -U" depending on how you installed it
Additionally make sure ffmpeg is installed, as that is necessary to parse the music file's metadata if not you will receive postprocessing error in your output

Enjoy!
"""
import sys
import os
import subprocess
import shutil
import time
from functools import wraps
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
from colorama import init, Fore, Back, Style

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

"""==== Logger: Initialize the log files before write ==== """
# Basic Logger info
logger = logging.getLogger("YouTube Downloader")
log_format = logging.Formatter("YT-DLP %(asctime)s - %(levelname)s - %(funcName)s - %(lineno)d - %(message)s")
error_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

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
    """An enhanced menu system for better program interaction"""
    def __init__(self):
        self.current_theme = 'default'

    # Predefined color combinations
    COLORS = {
        'header': f"{Fore.CYAN}{Style.BRIGHT}",
        'title': f"{Fore.MAGENTA}{Style.BRIGHT}",
        'section': f"{Fore.BLUE}{Style.BRIGHT}",
        'menu_item': f"{Fore.YELLOW}",
        'menu_desc': f"{Fore.WHITE}",
        'success': f"{Fore.GREEN}{Style.BRIGHT}",
        'failure': f"{Fore.RED}{Style.BRIGHT}",
        'error': f"{Fore.YELLOW}{Style.BRIGHT}",
        'info': f"{Fore.CYAN}",
        'input': f"{Fore.GREEN}{Style.BRIGHT}",
        'highlight': f"{Fore.YELLOW}{Style.BRIGHT}",
        'dim': f"{Style.DIM}",
    }

    @staticmethod
    def clear_screen():
        """Clear the terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def print_color(text, color_type='info', bold=False, end='\n'):
        """Print colored text"""
        color_code = Enhanced_Menu.COLORS.get(color_type, Enhanced_Menu.COLORS['info'])
        if bold and 'BRIGHT' not in color_code:
            text = f"{Style.BRIGHT}{text}"
        print(f"{color_code}{text}{Style.RESET_ALL}", end=end)

    @staticmethod
    def print_boxed_title(title, width=60):
        """Print a title in a decorative box"""
        border = "═" * (width - 2)
        print(f"{Enhanced_Menu.COLORS['title']}╔{border}╗")
        padding = width - len(title) - 4
        left_pad = padding // 2
        right_pad = padding - left_pad
        print(f"{Enhanced_Menu.COLORS['title']}║{' ' * left_pad}{title}{' ' * right_pad}║")
        print(f"{Enhanced_Menu.COLORS['title']}╚{border}╝{Style.RESET_ALL}")

    @staticmethod
    def print_header(title, subtitle=""):
        """Print a formatted header"""
        print()
        Enhanced_Menu.print_boxed_title(title)
        if subtitle:
            print(f"\n{Enhanced_Menu.COLORS['info']}{subtitle}{Style.RESET_ALL}")
        print()

    @staticmethod
    def print_section(title, symbol="─"):
        """Print a section header"""
        print(f"\n{Enhanced_Menu.COLORS['section']}{symbol * 60}")
        print(f"  {title}")
        print(f"{symbol * 60}{Style.RESET_ALL}")

    @staticmethod
    def print_menu_item(number, title, description="", indent=2):
        """Print a menu item with number and description"""
        indent_str = " " * indent
        print(f"{indent_str}{Enhanced_Menu.COLORS['menu_item']}[{number:2}]{Style.RESET_ALL} "
              f"{Enhanced_Menu.COLORS['menu_item']}{Style.BRIGHT}{title}{Style.RESET_ALL}")
        if description:
            desc_indent = " " * (indent + 5)
            wrapped_desc = Enhanced_Menu.wrap_text(description, width=50)
            for line in wrapped_desc:
                print(f"{desc_indent}{Enhanced_Menu.COLORS['menu_desc']}{line}{Style.RESET_ALL}")

    @staticmethod
    def wrap_text(text, width=50):
        """Wrap text to specified width"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        for word in words:
            if current_length + len(word) + 1 <= width:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_length = len(word)
        if current_line:
            lines.append(" ".join(current_line))
        return lines

    @staticmethod
    def print_status(message, status_type="info", icon=""):
        """Print a status message with appropriate color and icon"""
        status_config = {
            "success": {"color": "success", "default_icon": "✓"},
            "failure": {"color": "failure", "default_icon": "✗"},
            "error": {"color": "error", "default_icon": "⚠"},
            "info": {"color": "info", "default_icon": "ℹ"}
        }
        config = status_config.get(status_type, status_config["info"])
        icon_to_use = icon or config["default_icon"]
        print(f"{Enhanced_Menu.COLORS[config['color']]}{icon_to_use} {message}{Style.RESET_ALL}")

    @staticmethod
    def get_input(prompt, input_type="int", min_val=None, max_val=None, default=None):
        """Get validated user input with colored prompt"""
        prompt_color = Enhanced_Menu.COLORS['input']
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
                    value = int(user_input)
                    if min_val is not None and value < min_val:
                        raise ValueError(f"Value must be at least {min_val}")
                    if max_val is not None and value > max_val:
                        raise ValueError(f"Value must be at most {max_val}")
                    return value
                elif input_type == "str":
                    return user_input
                elif input_type == "yn":
                    if user_input.lower() in ['y', 'yes', '']:
                        return True
                    elif user_input.lower() in ['n', 'no']:
                        return False
                    else:
                        raise ValueError("Please enter 'y' or 'n'")
                elif input_type == "float":
                    return float(user_input)
                else:
                    return user_input
            except ValueError as e:
                Enhanced_Menu.print_status(str(e), "error")
                continue
            except KeyboardInterrupt:
                Enhanced_Menu.print_status("Operation cancelled by user", "error")
                return None

class CookieManager:
    """Manages cookies for authentication"""
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
        Enhanced_Menu.print_header("Checking available browser cookies....")
        available_browsers = []
        failed_browsers = []
        for browser, cookie_func in self.cookie_sources.items():
            try:
                cookies = cookie_func(domain_name="music.youtube.com")
                if cookies and len(list(cookies)) > 0:
                    available_browsers.append(browser)
                    Enhanced_Menu.print_color("Cookies found")
                else:
                    Enhanced_Menu.print_status("No cookies found", "failure")
            except Exception as e:
                failed_browsers.append(browser)
                Enhanced_Menu.print_status(f"{browser}: Error - {e}", "failure")
        if available_browsers:
            Enhanced_Menu.print_status(f"Available cookies from {', '.join(available_browsers)}", "success")
            return True
        else:
            Enhanced_Menu.print_status("No browser cookies found for Youtube Music", "error")
            return False

    def extract_cookies(self, browser_name: str = 'brave') -> Optional[Path]:
        """Extract cookies from your browser of choice & saves to files"""
        if browser_name not in self.cookie_sources:
            Enhanced_Menu.print_status("Browser not supported", "error")
            Enhanced_Menu.print_status(f"Available browsers are: {', '.join(self.cookie_sources.keys())}", "info")
            return None
        Enhanced_Menu.print_header(f"Extracting cookies from {browser_name}....")
        try:
            domains = ['music.youtube.com', 'youtube.com']
            all_cookies = []
            for domain in domains:
                try:
                    cookies = self.cookie_sources[browser_name](domain_name=domain)
                    for cookie in cookies:
                        if cookie not in all_cookies:
                            all_cookies.append(cookie)
                    Enhanced_Menu.print_status(f"Found {len(list(cookies))} cookies for {domain}", "success")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Couldn't get cookies for {domain}: {e}", "error")
            if not all_cookies:
                Enhanced_Menu.print_status(f"No cookies found for Youtube Music in {browser_name}", "info")
                return None
            cookie_file = self.cookie_directory / f"{browser_name}_cookies.txt"
            with open(cookie_file, "w", encoding='utf-8') as f:
                f.write("# Netscape HTTP cookie file\n")
                f.write("# This file was generated by Youtube Downloader\n")
                f.write("# https://curl.haxx.se/docs/http-cookies.html\n\n")
                for cookie in all_cookies:
                    netloc = urlparse(cookie.domain).netloc if cookie.domain.startswith('http') else cookie.domain
                    if not netloc:
                        netloc = cookie.domain
                    secure = "TRUE" if cookie.secure else "FALSE"
                    f.write(f"{netloc}\t")
                    f.write("TRUE\t")
                    f.write(f"{cookie.path}\t")
                    f.write(f"{secure}\t")
                    f.write(f"{int(time.time()) + 3600*24*365}\t")
                    f.write(f"{cookie.name}\t")
                    f.write(f"{cookie.value}\n")
            Enhanced_Menu.print_status(f"Successfully extracted {len(all_cookies)} cookies to {cookie_file}", "success")
            Enhanced_Menu.print_status(f"Cookies saved to: {cookie_file}", "info")
            self.current_cookie_file = cookie_file
            return cookie_file
        except Exception as e:
            Enhanced_Menu.print_status(f"Failed to extract cookies from {browser_name}: {e}", "error")
            Enhanced_Menu.print_color("Direct cookie extraction failed for {}".format(browser_name))
            Enhanced_Menu.print_color("Try manual cookie export:")
            Enhanced_Menu.print_color("1. Install 'Get cookies.txt' extension for Chrome/Edge")
            Enhanced_Menu.print_color("2. Export cookies from music.youtube.com")
            Enhanced_Menu.print_color("3. Load the exported file using option 4")
            return None

    def load_cookies(self, cookie_file: str) -> Optional[Path]:
        """Load cookies from an existing file"""
        cookie_path = Path(cookie_file)
        if not cookie_path.exists():
            cookie_path = self.cookie_directory / cookie_file
            if not cookie_path.exists():
                cookie_path = Path(cookie_file)
                if not cookie_path.exists():
                    Enhanced_Menu.print_status(f"Cookie file not found: {cookie_file}", "failure")
                    return None
        try:
            with open(cookie_path, 'r', encoding='utf-8') as f:
                content = f.read(200)
                if "# Netscape HTTP Cookie File" not in content:
                    Enhanced_Menu.print_status(f"Warning: Cookie file may not be in Netscape format", "error")
            self.current_cookie_file = cookie_path
            Enhanced_Menu.print_status(f"Cookies loaded from: {cookie_path}", "info")
            return cookie_path
        except Exception as e:
            Enhanced_Menu.print_status(f"Failed to load cookies: {e}", "failure")
            return None

    def save_cookies(self, name: str = "cookies") -> Optional[Path]:
        """Save current cookie file to persistent storage"""
        
        # Checks for cookies to save
        if not self.current_cookie_file or not self.current_cookie_file.exists():
            Enhanced_Menu.print_status("No active cookie file to save", "error")
            return None
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_path = self.cookie_directory / f"{name}_{timestamp}.txt"
            shutil.copy2(self.current_cookie_file, save_path)
            Enhanced_Menu.print_status(f"Cookies saved to: {save_path}", "success")
            return save_path
        except Exception as e:
            Enhanced_Menu.print_status(f"Failed to save cookies: {e}", "error")
            return None

    def list_cookies(self) -> List[Path]:
        """List all saved cookie files"""
        cookie_files = list(self.cookie_directory.glob("*.txt"))
        if not cookie_files:
            Enhanced_Menu.print_status("No saved cookies files found.", "error")
            return []
        Enhanced_Menu.print_status("Saved cookie files:", "info")
        
        # Goes through the file
        for i, cookie_file in enumerate(cookie_files, 1):
            file_size = cookie_file.stat().st_size
            mod_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(cookie_file.stat().st_mtime))
            print(f"{Fore.YELLOW}[{i}]{Style.RESET_ALL} {Fore.CYAN}{cookie_file.name:30}{Style.RESET_ALL}")
            print(f"     Size: {file_size} bytes | Modified: {mod_time}")
        return cookie_files

    def clear_cookies(self):
        """Delete all cookie files from the main cookie directory if any"""
        try:
            deleted_count = 0
            cookie_files = list(self.cookie_directory.glob("*.txt"))
            if not cookie_files:
                Enhanced_Menu.print_color("No cookie files found in {}".format(self.cookie_directory))
                return
            Enhanced_Menu.print_color("Found {} cookie file(s) to delete:".format(len(cookie_files)))
            for cookie_file in cookie_files:
                Enhanced_Menu.print_color("  - {}".format(cookie_file.name))
            confirm = input("\nAre you sure you want to delete ALL {} cookie files? (y/n): ".format(len(cookie_files))).strip().lower()
            if confirm not in ['y', 'yes']:
                Enhanced_Menu.print_status("Cookie deletion cancelled.", "failure")
                return
            for cookie_file in cookie_files:
                try:
                    cookie_file.unlink()
                    deleted_count += 1
                    Enhanced_Menu.print_status(f"Deleted: {cookie_file.name}", "success")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Failed to delete {cookie_file.name}: {e}", "failure")
            if self.current_cookie_file and not self.current_cookie_file.exists():
                self.current_cookie_file = None
            Enhanced_Menu.print_status(f"\nSuccessfully deleted {deleted_count} cookie file(s) from {self.cookie_directory}", "success")
        except Exception as e:
            Enhanced_Menu.print_status(f"Error clearing cookies: {e}", "error")

    # Gets cookie arguments for yt-dlp
    def get_arguments(self) -> List[str]:
        """Get yt-dlp cookie arguments if cookies are available"""
        if self.current_cookie_file and self.current_cookie_file.exists():
            return ["--cookies", str(self.current_cookie_file)]
        return []

    def interactive_menu(self):
        """Interactive cookie setup menu"""
        while True:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_color('=' * 50)
            Enhanced_Menu.print_header("Cookie Manager Menu")
            Enhanced_Menu.print_color('=' * 50)
            Enhanced_Menu.print_header("A simple program to help manager")
            Enhanced_Menu.print_section("Choices:- ")
            Enhanced_Menu.print_menu_item(1, "Check available browser for cookies")
            Enhanced_Menu.print_menu_item(2, "Extract cookies from browser")
            Enhanced_Menu.print_menu_item(3, "List saved cookie files")
            Enhanced_Menu.print_menu_item(4, "Load cookies from file")
            Enhanced_Menu.print_menu_item(5, "Save current cookies")
            Enhanced_Menu.print_menu_item(6, "Clear all cookie files")
            Enhanced_Menu.print_menu_item(7, "Show current cookie status")
            Enhanced_Menu.print_menu_item(8, "Return to main menu")
            Enhanced_Menu.print_section("STATUS")
            if self.current_cookie_file:
                Enhanced_Menu.print_status(f"Your active cookie files are: {self.current_cookie_file}", "success")
            else:
                Enhanced_Menu.print_status("You have no cookie files", "error")
            choice = input("Select option (1-8): ").strip()
            
            # Get cookie status
            if choice == "1":
                self.get_status()
                input("\nPress Enter to continue... ")
                
            # Get cookies from browser (Make sure to run browser in administration mode)
            elif choice == "2":
                print(f"\n====={Fore.CYAN}Available Browsers:{Style.RESET_ALL}======")
                for i, browser in enumerate(self.cookie_sources.keys(), 1):
                    Enhanced_Menu.print_color(f"{i}. {browser}")
                browser_choice = Enhanced_Menu.get_input("\nSelect browser (name or number): ", "str").strip()
                if browser_choice.isdigit():
                    browser_num = int(browser_choice)
                    if 1 <= browser_num <= len(self.cookie_sources):
                        browser_name = list(self.cookie_sources.keys())[browser_num - 1]
                        self.extract_cookies(browser_name)
                else:
                    self.extract_cookies(browser_choice)
                if self.current_cookie_file:
                    save = Enhanced_Menu.get_input("Save these cookies for future use? (y/n): ", "yn", default=True)
                    if save:
                        name = Enhanced_Menu.get_input("Enter name for cookie file (optional): ", "str").strip()
                        if not name:
                            name = "cookies"
                        self.save_cookies(name)
                
            # List cookies to choose from 
            elif choice == "3":
                cookie_files = self.list_cookies()
                if cookie_files:
                    load_choice = Enhanced_Menu.get_input("\nEnter number to load cookie file (or press Enter to skip): ", "str")
                    if load_choice.isdigit():
                        idx = int(load_choice) - 1
                        if 0 <= idx < len(cookie_files):
                            self.load_cookies(str(cookie_files[idx]))
                input("\nPress Enter to continue...")
                
            # Load cookes from chosen file path
            elif choice == "4":
                cookie_file = Enhanced_Menu.get_input("Enter cookie filename or path: ", "str").strip()
                if cookie_file:
                    self.load_cookies(cookie_file)
                input("\nPress Enter to continue... ")
                
            # Save cookies f
            elif choice == "5":
                if self.current_cookie_file:
                    name = Enhanced_Menu.get_input("Enter name for cookie file (optional): ", "str", default="cookies")
                    if not name:
                        name = "cookies"
                    self.save_cookies(name)
                else:
                    Enhanced_Menu.print_status("No active cookies to save", "info")
                input("\nPress Enter to continue...")
            
            # Delete all cookies 
            elif choice == "6":
                self.clear_cookies()
                input("\nPress Enter to continue")
            
            # Show current cookie status
            elif choice == "7":
                status = self.get_status()
                if self.current_cookie_file:
                    Enhanced_Menu.print_status(f"Active cookie file: {self.current_cookie_file.name}", "success")
                else:
                    Enhanced_Menu.print_status("No active cookie file", "info")
                input("\nPress Enter to continue...")
                
            # Stop cookie manager
            elif choice == "8":
                break
            
            else:
                Enhanced_Menu.print_status("Invalid choice", "info")
                input("\nPress Enter to continue...")


class Youtube_Downloader:
    """Downloader Class that handles the downloading process"""
    def __init__(self):
        """Initialize the downloader with default values"""
        if 'MAX_RETRIES' not in globals():
            global MAX_RETRIES, RETRY_DELAY, DOWNLOAD_TIMEOUT
            MAX_RETRIES = 3
            RETRY_DELAY = 5
            DOWNLOAD_TIMEOUT = 300
            
        self.__output_directory = Path("Albums")
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.__filepath = r"links/youtube_links.txt"
        self.__configuration_file = r"config/youtube_downloader.json"
        self.cookie_manager = CookieManager()
        self.use_cookies = False
        self.__output_directory.mkdir(parents=True, exist_ok=True)
        Path("links").mkdir(parents=True, exist_ok=True)
        Path("log").mkdir(parents=True, exist_ok=True)
        try:
            self.load_config()
        except Exception as e:
            self.log_error(f"Error loading config: {e}")

    # ============================================= Configuration Managers ===========================================
    def load_config(self):
        """Load configuration from json file"""
        primary_config = {
            "output_directory": "Albums",
            "audio_quality": "320k",
            "audio_format": "mp3",
            "max_retries": MAX_RETRIES,
            "retry_delay": RETRY_DELAY,
            "download_timeout": DOWNLOAD_TIMEOUT,
            "use_cookies": False
        }
        try:
            if os.path.exists(self.__configuration_file):
                with open(self.__configuration_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    config = {**primary_config, **user_config}
            else:
                config = primary_config
                self.save_config(config)
            if "output_directory" in config:
                self.__output_directory = Path(config["output_directory"])
            if "audio_quality" in config:
                self.__audio_quality = config["audio_quality"]
            if "audio_format" in config:
                self.__audio_format = config["audio_format"]
            if "use_cookies" in config:
                self.use_cookies = config["use_cookies"]
        except Exception as e:
            self.log_error(f"Error loading configuration: {e}")
            self.__output_directory = Path(primary_config["output_directory"])
            self.__audio_quality = primary_config["audio_quality"]
            self.__audio_format = primary_config["audio_format"]
            self.use_cookies = primary_config["use_cookies"]

    def save_config(self, config: Dict = None):
        """Save configuration to file"""
        try:
            if config is None:
                config = {
                    "output_directory": str(self.__output_directory),
                    "audio_quality": self.__audio_quality,
                    "audio_format": self.__audio_format,
                    "max_retries": MAX_RETRIES,
                    "retry_delay": RETRY_DELAY,
                    "download_timeout": DOWNLOAD_TIMEOUT,
                    "use_cookies": self.use_cookies
                }
            with open(self.__configuration_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log_error(f"Error saving configuration: {e}")

    # ============================================= Logger Functions ===========================================
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

    #  ============================================= Helper Functions & Resource Validation Functions =============================================
    def get_user_preferences(self):
        """Takes in user input for the download settings"""
        Enhanced_Menu.print_header("Download Settings", "Configure your music conversion preferences")
        
        # Handles audio quality of music conversion       
        while True:
            audio_quality_input = Enhanced_Menu.get_input("What bitrate would you like (enter 'choice' to see options): ", "str", default=self.__audio_quality)
            if not audio_quality_input:
                self.__audio_quality = "320k"
                break
            if audio_quality_input == 'choice':
                print(f"\n{Fore.CYAN}Available qualities:{Style.RESET_ALL}")
                print("  auto     - Let yt-dlp choose the best")
                print("  320k     - High quality (default)")
                print("  256k     - Very good quality")
                print("  192k     - Good quality")
                print("  128k     - Standard quality")
                print("  8k-160k  - Lower qualities")
            valid_bitrates = ["auto", "disable", "8k", "16k", "24k", "32k", "40k", "48k", "64k",
                              "80k", "96k", "112k", "128k", "160k", "192k", "224k", "256k", "320k"]
            if audio_quality_input in valid_bitrates:
                self.__audio_quality = audio_quality_input.lower()
                break
            Enhanced_Menu.print_status("Invalid bitrate. The downloader doesn't support these values", "error")
            
        # Handles audio format from the user
        while True:
            audio_format_input = Enhanced_Menu.get_input("What format would you like (enter 'choice' to see options): ", "str", default=self.__audio_format)
            if not audio_format_input:
                self.__audio_format = "mp3"
                break
            if audio_format_input == 'choice':
                print(f"\n{Fore.CYAN}Available formats:{Style.RESET_ALL}")
                print("  mp3  - Most compatible (default)")
                print("  m4a  - Apple format, good quality")
                print("  flac - Lossless audio")
                print("  opus - Excellent compression")
                print("  ogg  - Open format")
                print("  wav  - Uncompressed")
            if audio_format_input in ["mp3", "flac", "ogg", "opus", "m4a", "wav"]:
                self.__audio_format = audio_format_input
                break
            Enhanced_Menu.print_status("Invalid format. Downloader doesn't support this format", "error")
            
        # Choose your output directory
        output_path = Enhanced_Menu.get_input("Enter output directory (default: Albums): ", "str").strip()
        if output_path:
            self.__output_directory = Path(output_path)
        else:
            self.__output_directory = Path("Albums")
        self.__output_directory.mkdir(parents=True, exist_ok=True)
        
        # Cookie choice
        Enhanced_Menu.print_status("Cookie Settings", "info")
        print(f"\n{Fore.CYAN}Cookies can help with:{Style.RESET_ALL}")
        print(" Age-restricted content")
        print(" Region-restricted videos")
        print(" Private playlists")
        cookie_choice = Enhanced_Menu.get_input("Use cookies for authentication? (y/n): ", "yn", default=True)
        if cookie_choice:
            self.use_cookies = True
            Enhanced_Menu.print_status("Note: Make sure you have extracted the cookies beforehand, if make use of Cookie Mnager to help you", "info")
        else:
            self.use_cookies = False

    def validate_youtube_url(self, url: str) -> bool:
        """Validate if the URL input is a proper YouTube URL"""
        
        # Subject to edit
        youtube_patterns = [
            r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$',
            r'^(https?://)?music\.youtube\.com/.+$',
            r'^(https?://)?youtube\.com/watch\?v=[\w-]+(&.*)?$',
            r'^(https?://)?youtube\.com/playlist\?list=[\w-]+(&.*)?$',
            r'^(https?://)?youtu\.be/[\w-]+$'
        ]
        for pattern in youtube_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                try:
                    parsed = urllib.parse.urlparse(url)
                    if parsed.scheme in ['http', 'https', ''] or parsed.netloc:
                        return True
                except:
                    continue
        return False

    def cleanup_directory(self):
        """Removes empty directories after download"""
        removed_count = 0
        for root, dirs, files in os.walk(self.__output_directory, topdown=False):
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

    def extract_youtube_id(self, url: str) -> str:
        """Extract YouTube ID from URL"""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)',
            r'youtube\.com/playlist\?list=([\w-]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def validate_resource(self, url: str) -> Tuple[bool, str, Optional[Dict]]:
        """Validate if a resource is available before downloading to the device"""
        try:
            # Run a small command 
            command = ["yt-dlp",
                       "--skip-download",
                       "--print-json",        # <-- Added to get JSON metadata
                       "--no-warnings",
                       url]
            result = subprocess.run(
                command, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
                timeout=30, check=False
            )
            
            # Check on output and get metadata
            if result.returncode == 0:
                try:
                    metadata = json.loads(result.stdout)
                    title = metadata.get('title', 'Unknown')
                    duration = metadata.get('duration', 0)
                    if metadata.get('availability') == 'unavailable':
                        return False, "Video unavailable", metadata
                    return True, f"Available - {title}", metadata
                except json.JSONDecodeError:
                    return True, "Music Resource Available - Complication in Metadata", None
            
            # If result or output contains errors
            else:
                error_message = result.stderr.lower()
                if "unavailable" in error_message:
                    return False, "Resource unavailable", None
                elif "private" in error_message:
                    return False, "Restricted Access", None
                elif "age restriction" in error_message:
                    return False, "Age restricted video", None
                elif "not found" in error_message:
                    return False, "Resource not found", None
                else:
                    return False, f"Validation failed: {error_message[:100]}", None
        except subprocess.TimeoutExpired:
            return False, "Validation timeout", None
        except Exception as e:
            return False, f"Validation error: {str(e)[:100]}", None

    def parse_size(self, size_str: str) -> Optional[int]:
        """Parse size string to bytes"""
        if not size_str:
            return None
        size_str = size_str.strip().upper()
        
        # Convert string of download size,
        units = {
            'B': 1, 'K': 1024, 'M': 1024 ** 2, 'G': 1024 ** 3, 'T': 1024 ** 4,
            'KB': 1024, 'MB': 1024 ** 2, 'GB': 1024 ** 3, 'TB': 1024 ** 4,
            'KIB': 1024, 'MIB': 1024 ** 2, 'GIB': 1024 ** 3, 'TIB': 1024 ** 4
        }
        
        # Match with regex
        match = re.match(r'([\d\.]+)\s*(\w*)', size_str)
        if not match:
            return None
        
        # Check for value in units
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



    #  ============================================= Download Functions =============================================
    def run_download(self, url: str, output_template: str, additional_args=None):
        """Run yt-dlp download with modern syntax & tqdm progress bar"""
        
        # Ensure output directory exists
        output_directory = os.path.dirname(output_template)
        if output_directory:
            os.makedirs(output_directory, exist_ok=True)
            
        command = [
            "yt-dlp",
            "-x",
            "--audio-format", self.__audio_format,
            "--audio-quality", self.__audio_quality,
            "-o", output_template,
            "--no-overwrites",
            "--add-metadata",
            "--embed-thumbnail",
            "--newline",
            "--progress",
            "--console-title",
            "--quiet",
            "--no-warnings",
            "--ignore-errors",
            "--retries", "10",
            "--fragment-retries", "10",
            "--buffer-size", "16K",
            "--http-chunk-size", "10M",
            "--extractor-args", "youtube:player_client=android",
        ]
        
        # For cookie options
        if self.use_cookies and self.cookie_manager.current_cookie_file:
            cookie_args = self.cookie_manager.get_arguments()
            if cookie_args:
                command.extend(cookie_args)
                self.log_success("Using cookies from authentication")
            else:
                self.log_error("Error using cookies")
                
        # Additional arguments for specific downloads
        if additional_args:
            if isinstance(additional_args, list):
                command.extend(additional_args)
            else:
                command.append(additional_args)
        command.append(url)
        
        try:
            # Initialize progress bar with tqdm
            progress_bar = tqdm(
                desc="Downloading",
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                leave=False,
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]",
                dynamic_ncols=True
            )
            
            # Start the subprocess
            process = subprocess.Popen(
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
            output_lines = []  # capture all output for error analysis
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                output_lines.append(line)
                if "[download]" in line:
                    try:
                        # Parse percentage
                        percent_match = re.search(r'(\d+\.?\d*)%', line)
                        if percent_match:
                            percent = float(percent_match.group(1))
                            progress_bar.set_description(f"{Fore.CYAN}Downloading: {percent:.1f}%{Style.RESET_ALL}")
                        
                        # Parse possible total download sixe
                        size_match = re.search(r'of\s+([\d\.]+\s*[KMGT]?i?B)', line)
                        if size_match and progress_bar.total is None:
                            total_str = size_match.group(1)
                            total_bytes = self.parse_size(total_str)
                            if total_bytes:
                                progress_bar.total = total_bytes
                                
                        # Parse downloaded size
                        downloaded_match = re.search(r'([\d\.]+\s*[KMGT]?i?B)\s+at', line) or \
                                           re.search(r'([\d\.]+\s*[KMGT]?i?B)\s+ETA', line) or \
                                           re.search(r'([\d\.]+\s*[KMGT]?i?B)\s*\/', line)
                        if downloaded_match:
                            downloaded_str = downloaded_match.group(1)
                            downloaded_bytes = self.parse_size(downloaded_str)
                            if downloaded_bytes:
                                progress_bar.n = downloaded_bytes
                                
                        # Parse download speed
                        speed_match = re.search(r'at\s+([\d\.]+\s*[KMGT]?i?B/s)', line)
                        if speed_match:
                            speed = speed_match.group(1)
                            progress_bar.set_postfix_str(f"Speed: {speed}")
                            
                        # Parse Estimated download time
                        eta_match = re.search(r'ETA\s+([\d:]+)', line)
                        if eta_match:
                            eta = eta_match.group(1)
                            progress_bar.set_postfix_str(f"ETA: {eta}")
                        progress_bar.refresh()
                    except Exception:
                        continue
                    
                # If the download is completed or file already exists
                if "100%" in line or "already been downloaded" in line or "[Merger]" in line:
                    if progress_bar.total and progress_bar.n < progress_bar.total:
                        progress_bar.n = progress_bar.total
                    progress_bar.set_description(f"{Fore.GREEN}Downloaded{Style.RESET_ALL}")
                    progress_bar.set_postfix_str("")
                    progress_bar.refresh()
            
            # Close progress bar and check command output
            process.wait()
            progress_bar.close()
            full_output = "\n".join(output_lines)
            if process.returncode == 0:
                self.log_success(f"Successfully downloaded: {url}")
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=full_output,
                    stderr=""
                )
            else:
                error_msg = f"Download failed for {url} with code {process.returncode}"
                if "unavailable" in full_output.lower():
                    error_msg += " - Video is unavailable"
                elif "private" in full_output.lower():
                    error_msg += " - Video is private"
                elif "age restriction" in full_output.lower():
                    error_msg += " - Age restricted"
                elif "copyright" in full_output.lower():
                    error_msg += " - Copyright restriction"
                elif "format" in full_output.lower():
                    error_msg += " - Format not available"
                elif "ffmpeg" in full_output.lower():
                    error_msg += " - FFmpeg conversion error"
                else:
                    # extract first 200 chars of error
                    error_msg += f" - Error: {full_output[-200:] if full_output else 'Unknown'}"
                self.log_failure(error_msg)
                raise subprocess.CalledProcessError(
                    process.returncode,
                    command,
                    output=full_output,
                    stderr=""
                )
        except FileNotFoundError:
            error_msg = "yt-dlp not found. Please install it with: pip install yt-dlp"
            self.log_error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error in run_download: {e}"
            self.log_error(error_msg)
            if 'progress_bar' in locals():
                progress_bar.close()
            raise

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

    #  ============================================= Main Download functions =============================================
    @rate_limit(calls_per_minute=30)
    def download_track(self):
        """Download a single track (same syntax for most download functions)"""
        # Added outer loop for URL input retry
        while True:
            print("\n" + "=" * 55)
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Track Download")
            url = Enhanced_Menu.get_input("Enter YouTube Music URL (or 'back' to return)", "str")
            
            # Back to menu
            if url.lower() == 'back':
                return False
            
            # Go back and ask for URL again
            if not url:
                Enhanced_Menu.print_status("No URL provided", "error")
                continue
            
            # Check if url is a valid youtube url
            if not self.validate_youtube_url(url):
                Enhanced_Menu.print_status("Invalid YouTube URL. Enter a valid YouTube/YouTube Music URL", "error")
                continue
            
            # Checks for internet connection and if resource is valid
            Enhanced_Menu.print_status("Validating resource...", "info")
            is_valid, message, _ = self.validate_resource(url)
            if not is_valid:
                Enhanced_Menu.print_status(f"Resource validation failed, Please try a different URL.", "failure")
                self.log_failure(f"Resource validation failed for {url}: {message}")
                continue  
            else:
                Enhanced_Menu.print_status(f"Resource validated successfully: {message}", "success")
                break
        
        # Get user preferences, if not use default config 
        if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
            self.get_user_preferences()
            
        Enhanced_Menu.print_status(f"Starting Track download: {url}. This may take a few minutes...", "info")
        output_template = str(self.__output_directory / "%(artist)s - %(title)s.%(ext)s")
        for attempt in range(1, MAX_RETRIES + 1):
            Enhanced_Menu.print_section(f"Downloading Track")
            if attempt > 1:
                print(f"Waiting {RETRY_DELAY} seconds before retry...")
                time.sleep(RETRY_DELAY)
            try:
                result = self.run_download(url, output_template)
                if result.returncode == 0:
                    self.log_success(f"Successfully downloaded track: {url}")
                    
                    # Ask if the user wishes to download another music file
                    another = Enhanced_Menu.get_input("Download another track? (y/n): ", "yn")
                    if another in ['y', 'yes']:
                        continue
                    else:
                        return True
                    
            except subprocess.CalledProcessError as e:
                if attempt < MAX_RETRIES:
                    Enhanced_Menu.print_status(f"Download failed, retrying....", "error")
                    self.log_error(f"Attempt {attempt} failed: {e}")
                else:
                    self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                    return False
            except Exception as e:
                self.log_error(f"Unexpected error: {e}")
                if attempt < MAX_RETRIES:
                    continue
                else:
                    return False
        return False

    @rate_limit(calls_per_minute=30)
    def download_album(self):
        """Download an album"""
        while True:
            print("\n" + "=" * 50)
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Album Download")
            url = Enhanced_Menu.get_input("Enter YouTube Music album URL (or 'back' to return to menu): ", "str")
            if url.lower() == 'back':
                return False
            if not url:
                print("No URL provided")
                continue
            if not self.validate_youtube_url(url):
                print("Invalid YouTube URL. Please enter a valid YouTube Music URL")
                continue
            Enhanced_Menu.print_status("Validating resource...", "info")
            is_valid, message, _ = self.validate_resource(url)
            if not is_valid:
                Enhanced_Menu.print_status(f"Resource validation failed, Please try a different URL.", "failure")
                self.log_failure(f"Resource validation failed for {url}: {message}")
                continue
            else:
                Enhanced_Menu.print_status(f"Resource validated successfully: {message}", "success")
                break
        if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
            self.get_user_preferences()
        Enhanced_Menu.print_status(f"Starting Album download: {url}. This may take a few minutes...", "info")
        output_template = str(self.__output_directory / "%(artist)s/%(album)s/%(artist)s - %(title)s.%(ext)s")
        for attempt in range(1, MAX_RETRIES + 1):
            Enhanced_Menu.print_status(f"Downloading Album...", "info")
            if attempt > 1:
                print(f"Waiting {RETRY_DELAY} seconds before retry...")
                time.sleep(RETRY_DELAY)
            try:
                result = self.run_download(url, output_template)
                if result.returncode == 0:
                    self.log_success(f"Successfully downloaded album: {url}")
                    another = input("Download another album? (y/n): ").strip().lower()
                    if another in ['y', 'yes']:
                        continue
                    else:
                        return True
            except subprocess.CalledProcessError as e:
                if attempt < MAX_RETRIES:
                    error_msg = f"Download failed (attempt {attempt}/{MAX_RETRIES}). Error: {e}"
                    self.log_error(error_msg)
                else:
                    self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                    return False
            except Exception as e:
                self.log_error(f"Unexpected error: {e}")
                if attempt < MAX_RETRIES:
                    continue
                else:
                    return False
        return False

    @rate_limit(calls_per_minute=30)
    def download_playlist(self):
        """Download a playlist"""
        while True:
            print("\n" + "=" * 55)
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Download Playlist")
            url = Enhanced_Menu.get_input("Enter YouTube Music URL (or 'back' to return)", "str")
            if url.lower() == 'back':
                return False
            if not url:
                Enhanced_Menu.print_status("No URL provided", "error")
                continue
            if not self.validate_youtube_url(url):
                Enhanced_Menu.print_status("Invalid YouTube URL. Enter a valid YouTube/YouTube Music URL", "error")
                return False
            Enhanced_Menu.print_status("Validating resource...", "info")
            is_valid, message, _ = self.validate_resource(url)
            if not is_valid:
                Enhanced_Menu.print_status(f"Resource validation failed, Please try a different URL.", "failure")
                self.log_failure(f"Resource validation failed for {url}: {message}")
                continue
            else:
                Enhanced_Menu.print_status(f"Resource validated successfully: {message}", "success")
                break
        if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
            self.get_user_preferences()
        Enhanced_Menu.print_status(f"Starting Playlist download: {url}. This may take a few minutes...", "info")
        output_template = str(self.__output_directory / "%(playlist)s/%(artist)s - %(title)s.%(ext)s")
        for attempt in range(1, MAX_RETRIES + 1):
            Enhanced_Menu.print_status(f"Downloading Playlist", "info")
            if attempt > 1:
                print(f"Waiting {RETRY_DELAY} seconds before retry...")
                time.sleep(RETRY_DELAY)
            try:
                result = self.run_download(url, output_template)
                if result.returncode == 0:
                    self.log_success(f"Successfully downloaded playlist {url}")
                    another = Enhanced_Menu.get_input("Download another playlist? (y/n): ", "yn")
                    if another:
                        continue
                    else:
                        return True
            except subprocess.CalledProcessError as e:
                if attempt < MAX_RETRIES:
                    error_msg = f"Download failed (attempt {attempt}/{MAX_RETRIES}). Error: {e}"
                    self.log_error(error_msg)
                else:
                    self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                    return False
            except Exception as e:
                self.log_error(f"Unexpected error: {e}")
                if attempt < MAX_RETRIES:
                    continue
                else:
                    return False
        return False

    def download_from_file(self):
        """Download various links from a file"""
        Enhanced_Menu.print_header("Batch Download", "Download from a text file containing links")
        filepath = Enhanced_Menu.get_input("Enter the directory of the file): ", "str", default=self.__filepath)
        if not filepath:
            filepath = self.__filepath
        if not os.path.exists(filepath):
            self.log_failure(f"File not found: {filepath}")
            Enhanced_Menu.print_status(f"File not found: {filepath}", "error")
            return False
        self.get_user_preferences()
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                file_lines = [line.rstrip() for line in file if line.strip()]
        except FileNotFoundError:
            self.log_failure(f"File not found: {filepath}")
            return False
        except Exception as e:
            self.log_failure(f"Error reading the file: {e}")
            return False
        if not file_lines:
            self.log_failure("No URLs found in the text file")
            return False
        Enhanced_Menu.print_status(f"Found {len(file_lines)} URLs to process", "info")
        success_count = 0
        failed_count = 0
        for i, url in enumerate(file_lines, 1):
            print("=" * 50)
            self.log_success(f"Processing URL {i}/{len(file_lines)}: {url}")
            clean_url = url.split('#')[0].strip()
            if "# DOWNLOADED" in url:
                self.log_success(f"Skipping already downloaded URL: {clean_url}")
                success_count += 1
                continue
            print("Validating URL...")
            is_valid, message, _ = self.validate_resource(clean_url)
            if not is_valid:
                self.log_failure(f"URL validation failed: {clean_url} - {message}")
                file_lines[i - 1] = f"{clean_url} # VALIDATION_FAILED: {message}"
                failed_count += 1
                continue
            if "playlist" in url.lower():
                output_template = str(self.__output_directory / "%(playlist)s/%(artist)s - %(title)s.%(ext)s")
                additional_args = None
            elif "album" in url.lower():
                output_template = str(self.__output_directory / "%(artist)s/%(album)s/%(artist)s - %(title)s.%(ext)s")
                additional_args = None
            else:
                output_template = str(self.__output_directory / "%(artist)s - %(title)s.%(ext)s")
                additional_args = None
            success = False
            for attempt in range(1, MAX_RETRIES + 1):
                print("=" * 50)
                Enhanced_Menu.print_status(f"Attempt {attempt} for URL {i}", "info")
                if attempt > 1:
                    print(f"Waiting {RETRY_DELAY} seconds before retry...")
                    time.sleep(RETRY_DELAY)
                try:
                    result = self.run_download(clean_url, output_template, additional_args)
                    if result.returncode == 0:
                        success = True
                        break
                except subprocess.CalledProcessError as e:
                    if attempt < MAX_RETRIES:
                        error_msg = f"Download failed (attempt {attempt}/{MAX_RETRIES}). Error: {e}"
                        self.log_error(error_msg)
                    else:
                        self.log_failure(f"Failed after {MAX_RETRIES} attempts: {clean_url}")
                except Exception as e:
                    self.log_failure(f"Exception during download: {e}")
            if success:
                success_count += 1
                self.log_success(f"Successfully downloaded {clean_url}")
                if "#" in url:
                    parts = url.split('#')
                    file_lines[i - 1] = f"{parts[0].strip()} # DOWNLOADED"
                else:
                    file_lines[i - 1] = f"{clean_url} # DOWNLOADED"
            else:
                failed_count += 1
                self.log_failure(f"Failed to download {clean_url}")
                if "#" in url:
                    parts = url.split('#')
                    file_lines[i - 1] = f"{parts[0].strip()} # FAILED"
                else:
                    file_lines[i - 1] = f"{clean_url} # FAILED"
        try:
            with open(filepath, 'w', encoding='utf-8') as file:
                file.write("\n".join(file_lines))
        except Exception as e:
            self.log_failure(f"Error updating the file: {e}")
        print("\n" + "=" * 50)
        Enhanced_Menu.print_header("Download Summary:")
        Enhanced_Menu.print_status(f"Successfully downloaded: {success_count}", "success")
        Enhanced_Menu.print_status(f"Failed: {failed_count}", "failure")
        print("=" * 50)
        return failed_count == 0

    @rate_limit(calls_per_minute=30)
    def search_a_song(self):
        """Search for a song and download it"""
        Enhanced_Menu.print_header("SEARCH & DOWNLOAD")
        song_query = Enhanced_Menu.get_input("What is the name of the song you're looking for: ").strip()
        if not song_query:
            Enhanced_Menu.print_status("No search query provided", "error")
            return False
        if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
            self.get_user_preferences()
        search_time = time.time()
        Enhanced_Menu.print_header("Searching for the song. Browsing through YouTube...")
        output_template = str(self.__output_directory / "%(artist)s - %(title)s.%(ext)s")
        for attempt in range(1, MAX_RETRIES + 1):
            print("=" * 50)
            Enhanced_Menu.print_header("Search and download")
            if attempt > 1:
                print(f"Waiting {RETRY_DELAY} seconds before retry...")
                time.sleep(RETRY_DELAY)
            try:
                result = self.run_download(f"ytsearch1:{song_query}", output_template)
                elapsed_time = time.time() - search_time
                self.log_success(f"Successfully downloaded: '{song_query}' in {elapsed_time:.1f} seconds!")
                print("=" * 50)
                return True
            except Exception as e:
                self.log_error(f"Unexpected error: {e}")
                if attempt < MAX_RETRIES:
                    continue
                else:
                    return False
        return False

    def download_channel(self):
        """Download all videos from a YouTube channel"""
        print("\n" + "=" * 50)
        Enhanced_Menu.print_header("Channel Download")
        print("=" * 50)
        Enhanced_Menu.print_status("Warning: This may download many videos", "error")
        Enhanced_Menu.print_status("It could take a long time and use significant disk space", "error")
        print("=" * 50)
        channel_url = Enhanced_Menu.get_input("Enter YouTube channel URL: ", "str")
        if not channel_url:
            print("No URL provided")
            return False
        if not self.validate_youtube_url(channel_url):
            Enhanced_Menu.print_status("Invalid YouTube URL. Please enter a valid YouTube channel URL", "error")
            return False
        confirm = Enhanced_Menu.get_input("Are you sure you want to download ALL videos from this channel? (y/n)", "yn", default=False)
        if not confirm:
            Enhanced_Menu.print_status("Channel download cancelled", "info")
            return False
        if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
            self.get_user_preferences()
        print(f"Starting Channel download. This may take a VERY long time...")
        start_time = time.time()
        output_template = str(self.__output_directory / "%(channel)s/%(artist)s - %(title)s.%(ext)s")
        additional_args = [
            "--yes-playlist",
            "--download-archive", "downloaded_channels.txt"
        ]
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"{'=' * 50}")
            print(f"Downloading Channel: Attempt {attempt} of {MAX_RETRIES}")
            print(f"{'=' * 50}")
            if attempt > 1:
                print(f"Waiting {RETRY_DELAY} seconds before retry...")
                time.sleep(RETRY_DELAY)
            try:
                result = self.run_download(channel_url, output_template, additional_args)
                if result.returncode == 0:
                    elapsed_time = time.time() - start_time
                    self.log_success(f"Successfully downloaded channel in {elapsed_time:.1f} seconds!")
                    print("=" * 50)
                    return True
            except subprocess.CalledProcessError as e:
                if attempt < MAX_RETRIES:
                    error_msg = f"Download failed (attempt {attempt}/{MAX_RETRIES}). Error: {e}"
                    self.log_error(error_msg)
                else:
                    self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {channel_url}")
                    return False
            except Exception as e:
                self.log_error(f"Unexpected error: {e}")
                if attempt < MAX_RETRIES:
                    continue
                else:
                    return False
        return False

    def manage_cookies(self):
        """Calls the cookie management menu"""
        self.cookie_manager.interactive_menu()
        if self.cookie_manager.current_cookie_file:
            use_cookies = Enhanced_Menu.get_input("Enable cookies for future downloads? (y/n)", "yn", default=False)
            if use_cookies:
                self.use_cookies = True
            else:
                self.use_cookies = False
            self.save_config()

    #  ============================================= Checkers & Yt-DLP Helpers =============================================
    @staticmethod
    def check_ytdlp():
        """Check if yt-dlp is installed"""
        Enhanced_Menu.print_header("Checking for yt-dlp")
        # Check with basic shutil to find the file on PATH
        if shutil.which("yt-dlp"):
            print("yt-dlp is already installed")
            try:
                result = subprocess.run(
                    ["yt-dlp", "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                    timeout=10
                )
                if result.returncode == 0:
                    version = result.stdout.strip()
                    print(f"yt-dlp version: {version}") # Print python
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
                print("Could not determine yt-dlp version")
                return False
        else:
            print("yt-dlp is not installed")
            return False

    @staticmethod
    def check_ffmpeg():
        """Check if ffmpeg is installed"""
        Enhanced_Menu.print_header("Checking for FFMpeg")
        # Check with basic shutil to find the file on PATH
        if shutil.which("ffmpeg"):
            print("ffmpeg is already installed")
            try:
                result = subprocess.run(
                    ["ffmpeg", "-version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                    timeout=10
                )
                if result.returncode == 0:
                    version = result.stdout.strip()
                    Enhanced_Menu.print_status(f"ffmpeg version: {version}", "success")
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
                Enhanced_Menu.print_status("Could not determine ffmpeg version", "error")
                return False
        else:
            Enhanced_Menu.print_status("ffmpeg is not installed", "error")
            return False

    @staticmethod
    def show_ytdlp_help():
        """Display yt-dlp help"""
        try:
            result = subprocess.run(
                ["yt-dlp", "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            print("\n" + "=" * 50)
            Enhanced_Menu.print_header("YT-DLP HELP")
            print("=" * 50)
            print(result.stdout[:1000])
            print("\n... (output truncated, use 'yt-dlp --help' for full help)")
        except subprocess.CalledProcessError as e:
            Enhanced_Menu.print_status(f"Could not get yt-dlp help: {e}", "error")
            return False
        input("\nPress Enter to continue....")
        return True

    @staticmethod
    def check_dependencies():
        """Check for missing dependencies"""
        Enhanced_Menu.print_header("Checking for Missing Dependencies")
        missing_packages = []
        for package in ['browser_cookie3', 'colorama', 'tqdm', 'yt-dlp']:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        if missing_packages:
            print(f"Missing packages: {', '.join(missing_packages)}")
            print("Install with: pip install " + " ".join(missing_packages))
            return False
        input("\nPress Enter to continue....")
        return True

    @staticmethod
    def setup_dependencies():
        """Automatically install required libraries & dependencies"""
        dependencies = {
            'yt-dlp': ['yt-dlp'],
            'ffmpeg': ['ffmpeg-python'],
            'browser_cookie3': ['browser_cookie3'],
            'tqdm': ['tqdm'],
            'colorama': ['colorama']
        }
        for package_name, packages in dependencies.items():
            try:
                __import__(package_name)
            except ImportError:
                Enhanced_Menu.print_color(f"Installing {package_name}....")
                subprocess.check_call([sys.executable, "-m", "pip", "install"] + packages)

    def troubleshooting(self):
        """Troubleshooting"""
        print("\n" + "=" * 50)
        Enhanced_Menu.print_header("TROUBLESHOOTING", "")
        print("=" * 50)
        print("Hello, this troubleshooter is to help if you're experiencing problem in the program")
        print("Running a simple daignostic. This might take a while.....")
        
        # Step 1: Check if yt-dlp is installed
        Enhanced_Menu.print_status("1. Checking yt-dlp installation...", "info")
        if not Youtube_Downloader.check_ytdlp():
            Enhanced_Menu.print_status("yt-dlp not found or not working", "error")
            install = Enhanced_Menu.get_input("Install yt-dlp now? (y/n)", "yn", default=True)
            if install:
                Youtube_Downloader.setup_dependencies()
        
        # Step 2: Check for ffmpeg on path      
        Enhanced_Menu.print_status("\n2. Checking FFmpeg installation...", "info")
        if not Youtube_Downloader.check_ffmpeg():
            Enhanced_Menu.print_status("FFmpeg not found (audio conversion might fail)", "error")
        
        # Check internet connection
        Enhanced_Menu.print_status("\n3. Testing YouTube access...", "info")
        test_url = "https://music.youtube.com/watch?v=215T8NF93kw"
        try:
            test_command = ["yt-dlp", "--skip-download", "--print-json", test_url]
            result = subprocess.run(
                test_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                Enhanced_Menu.print_status("Can access YouTube", "success")
            else:
                Enhanced_Menu.print_status(f"Cannot access YouTube: {result.stderr[:100]}", "error")
        except Exception as e:
            Enhanced_Menu.print_status(f"Test failed: {e}", "error")
        
        # Check directories if the exist
        Enhanced_Menu.print_status("\n4. Checking directories...", "info")
        directories = ["log", "Albums", "links", "cookies"]
        for directory in directories:
            if os.path.exists(directory):
                Enhanced_Menu.print_status(f"{directory}/ exists", "success")
            else:
                Enhanced_Menu.print_status(f"{directory}/ missing", "warning")
        input("\nPress Enter to continue...")
        return True

    @staticmethod
    def program_info():
        """Display program information"""
        print("=" * 80)
        Enhanced_Menu.print_header("Interactive YouTube/YouTube Music Playlist/Album/Track Downloader")
        print("=" * 80)
        print(f"""
            {Fore.CYAN}Description:{Style.RESET_ALL}
            A comprehensive tool for downloading music from YouTube and YouTube Music
            with support for albums, playlists, channels, and individual tracks.

            {Fore.CYAN}Features:{Style.RESET_ALL}
            • Download single tracks from YouTube/YouTube Music
            • Download complete albums from YouTube Music
            • Download playlists with metadata preservation
            • Batch download from text files
            • Search and download songs by name
            • Download entire YouTube channels
            • Cookie management for authentication
            • Customizable audio format and quality
            • Progress tracking with visual feedback

            {Fore.CYAN}Formats Supported:{Style.RESET_ALL}
            MP3, M4A, FLAC, OGG, OPUS, WAV

            {Fore.CYAN}Requirements:{Style.RESET_ALL}
            • Python 3.7+
            • yt-dlp
            • FFmpeg (recommended for audio conversion)
            • Internet connection

            {Fore.CYAN}Usage Tips:{Style.RESET_ALL}
            • Use cookies for age-restricted or region-restricted content
            • Configure settings before large downloads
            • Check dependencies if encountering issues
            • Use batch files for multiple downloads
            • Monitor disk space for large downloads
            """)
        input("\nPress Enter to continue...")
        return True

    def reset_to_defaults(self):
        """Reset all settings to default values"""
        self.__output_directory = Path("Albums")
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.use_cookies = False
        self.save_config()
        Enhanced_Menu.print_status("Settings reset to defaults", "success")

def main():
    """Main function to run the YouTube Downloader with integrated menus."""
    Enhanced_Menu.clear_screen()
    print(f"""{Fore.RED}{Style.BRIGHT}
    ███╗   ███╗██╗   ██╗███████╗██╗ ██████╗     ██████╗ ██████╗ ███╗   ██╗██╗   ██╗███████╗██████╗ ████████╗███████╗██████╗ 
    ████╗ ████║██║   ██║██╔════╝██║██╔════╝    ██╔════╝██╔═══██╗████╗  ██║██║   ██║██╔════╝██╔══██╗╚══██╔══╝██╔════╝██╔══██╗
    ██╔████╔██║██║   ██║███████╗██║██║         ██║     ██║   ██║██╔██╗ ██║██║   ██║█████╗  ██████╔╝   ██║   █████╗  ██████╔╝
    ██║╚██╔╝██║██║   ██║╚════██║██║██║         ██║     ██║   ██║██║╚██╗██║╚██╗ ██╔╝██╔══╝  ██╔══██╗   ██║   ██╔══╝  ██╔══██╗
    ██║ ╚═╝ ██║╚██████╔╝███████║██║╚██████╗    ╚██████╗╚██████╔╝██║ ╚████║ ╚████╔╝ ███████╗██║  ██║   ██║   ███████╗██║  ██║
    ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝ ╚═════╝     ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝                                                                                                 
    {Style.RESET_ALL}""")
    print(f"{Fore.YELLOW}{Style.BRIGHT}YouTube Music Downloader{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{Style.BRIGHT}Initializing...{Style.RESET_ALL}")

    directories = ["log", "Albums", "links", "cookies"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"{Fore.GREEN}✓{Style.RESET_ALL} Directory '{directory}/' ready")

    try:
        downloader = Youtube_Downloader()
        Enhanced_Menu.print_status("Downloader initialized successfully", "success")
        time.sleep(1)
    except Exception as e:
        Enhanced_Menu.print_status(f"Initialization error: {e}", "error")
        input("\nPress Enter to exit...")
        sys.exit(1)

    def handle_exit():
        """Handles exiting the program function"""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("THANK YOU", "Goodbye!")
        print(f"""{Fore.CYAN}
                ╔══════════════════════════════════════════════════════════════╗
                ║                                                              ║
                ║          Thank you for using YouTube Music Downloader!       ║
                ║                                                              ║
                ║                      Happy Listening!                        ║
                ║                                                              ║
                ║                                                              ║
                ╚══════════════════════════════════════════════════════════════╝
                {Style.RESET_ALL}""")
        try:
            downloader.save_config()
            print(f"{Fore.GREEN}Settings saved.{Style.RESET_ALL}")
        except:
            pass
        print(f"\n{Fore.CYAN}Goodbye!{Style.RESET_ALL}\n")
        sys.exit(0)

    def handle_settings():
        """Handle program settings menu"""
        while True:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("PROGRAM SETTINGS", "Configure download preferences")
            
            Enhanced_Menu.print_section("🎵 Audio Settings")
            current_format = downloader._Youtube_Downloader__audio_format
            current_quality = downloader._Youtube_Downloader__audio_quality
            Enhanced_Menu.print_menu_item(1, "Audio Format",
                                          f"Current: {Fore.GREEN}{current_format.upper()}{Style.RESET_ALL}")
            Enhanced_Menu.print_menu_item(2, "Audio Quality",
                                          f"Current: {Fore.GREEN}{current_quality}{Style.RESET_ALL}")
            Enhanced_Menu.print_section("📁 Output Settings")
            current_dir = str(downloader._Youtube_Downloader__output_directory)
            Enhanced_Menu.print_menu_item(3, "Output Directory",
                                          f"Current: {Fore.CYAN}{current_dir}{Style.RESET_ALL}")
            
            Enhanced_Menu.print_section("🌐 NETWORK SETTINGS")
            cookie_status = "ENABLED" if downloader.use_cookies else "DISABLED"
            cookie_color = Fore.GREEN if downloader.use_cookies else Fore.YELLOW
            Enhanced_Menu.print_menu_item(4, "Cookie Authentication",
                                          f"Current: {cookie_color}{cookie_status}{Style.RESET_ALL}")
            
            Enhanced_Menu.print_section("💾 Download Configuration")
            Enhanced_Menu.print_menu_item(5, "Save Settings", "Save current settings to file")
            Enhanced_Menu.print_menu_item(6, "Load Settings", "Load settings from file")
            Enhanced_Menu.print_menu_item(7, "Reset to Defaults", "Restore default settings")
            Enhanced_Menu.print_section("↩️  NAVIGATION")
            Enhanced_Menu.print_menu_item(8, "Back to Main Menu", "Return to main menu")
            print()
            choice = Enhanced_Menu.get_input("Select option", "int", 1, 8)
            if choice == 1:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("AUDIO FORMAT", "Select output format")
                formats = [
                    ("MP3", "mp3", "Most compatible, good quality"),
                    ("FLAC", "flac", "Lossless audio, large files"),
                    ("M4A", "m4a", "Apple format, good quality"),
                    ("OPUS", "opus", "Excellent compression, high quality"),
                    ("OGG", "ogg", "Open format, good compression"),
                    ("WAV", "wav", "Uncompressed, large files"),
                ]
                for i, (name, code, desc) in enumerate(formats, 1):
                    is_current = " ✓" if code == current_format else ""
                    print(f"  {Fore.YELLOW}[{i}]{Style.RESET_ALL} {Fore.CYAN}{name:6}{Style.RESET_ALL} - {desc}{Fore.GREEN}{is_current}{Style.RESET_ALL}")
                print()
                format_choice = Enhanced_Menu.get_input("Select format (1-6)", "int", 1, 6, default=1)
                if format_choice:
                    new_format = formats[format_choice - 1][1]
                    downloader._Youtube_Downloader__audio_format = new_format
                    Enhanced_Menu.print_status(f"Audio format set to {new_format.upper()}", "success")
                    
            elif choice == 2:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("AUDIO QUALITY", "Select bitrate/quality")
                qualities = [
                    ("320k", "High quality (320 kbps)", "Excellent for most music"),
                    ("256k", "Very good (256 kbps)", "Great quality, smaller files"),
                    ("192k", "Good (192 kbps)", "Good balance of quality/size"),
                    ("128k", "Standard (128 kbps)", "Acceptable quality, small files"),
                    ("auto", "Auto-select", "Let yt-dlp choose the best"),
                    ("disable", "Original quality", "Keep original audio as-is"),
                ]
                for i, (code, name, desc) in enumerate(qualities, 1):
                    is_current = " ✓" if code == current_quality else ""
                    print(f"  {Fore.YELLOW}[{i}]{Style.RESET_ALL} {Fore.CYAN}{name:20}{Style.RESET_ALL} - {desc}{Fore.GREEN}{is_current}{Style.RESET_ALL}")
                print()
                quality_choice = Enhanced_Menu.get_input("Select quality (1-6)", "int", 1, 6)
                if quality_choice:
                    new_quality = qualities[quality_choice - 1][0]
                    downloader._Youtube_Downloader__audio_quality = new_quality
                    Enhanced_Menu.print_status(f"Audio quality set to {new_quality}", "success")
                    
            elif choice == 3:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("OUTPUT DIRECTORY", "Set where files are saved")
                print(f"{Fore.YELLOW}Current directory:{Style.RESET_ALL} {Fore.CYAN}{current_dir}{Style.RESET_ALL}")
                print()
                print(f"{Fore.WHITE}Enter new directory path:{Style.RESET_ALL}")
                print(f"{Style.DIM}Examples:{Style.RESET_ALL}")
                print(f"  {Fore.CYAN}./Music{Style.RESET_ALL} - Save to 'Music' folder in current directory")
                print(f"  {Fore.CYAN}~/Downloads{Style.RESET_ALL} - Save to Downloads folder")
                print(f"  {Fore.CYAN}C:\\Users\\You\\Music{Style.RESET_ALL} - Windows absolute path")
                print()
                new_dir = Enhanced_Menu.get_input("New directory path", "str", default=current_dir)
                if new_dir and new_dir != current_dir:
                    try:
                        downloader._Youtube_Downloader__output_directory = Path(new_dir)
                        downloader._Youtube_Downloader__output_directory.mkdir(parents=True, exist_ok=True)
                        Enhanced_Menu.print_status(f"Output directory changed to {new_dir}", "success")
                    except Exception as e:
                        Enhanced_Menu.print_status(f"Error: {str(e)[:50]}", "error")
                        
            elif choice == 4:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("COOKIE SETTINGS", "Manage authentication")
                print(f"{Fore.WHITE}Cookies help with:{Style.RESET_ALL}")
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Age-restricted content")
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Region-restricted videos")
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Private playlists")
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} YouTube Premium content")
                print()
                print(f"{Fore.YELLOW}Current status:{Style.RESET_ALL} ", end="")
                if downloader.use_cookies:
                    print(f"{Fore.GREEN}ENABLED{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}DISABLED{Style.RESET_ALL}")
                print()
                new_setting = Enhanced_Menu.get_input("Enable cookies? (y/n)", "yn", default=downloader.use_cookies)
                if new_setting is not None:
                    downloader.use_cookies = new_setting
                    status = "enabled" if new_setting else "disabled"
                    Enhanced_Menu.print_status(f"Cookies {status}", "success")
                    
            elif choice == 5:
                try:
                    downloader.save_config()
                    Enhanced_Menu.print_status("Settings saved successfully", "success")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Error saving settings: {e}", "error")
                    
            elif choice == 6:
                try:
                    downloader.load_config()
                    Enhanced_Menu.print_status("Settings loaded successfully", "success")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Error loading settings: {e}", "error")
                    
            elif choice == 7:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("RESET SETTINGS", "Restore defaults")
                print(f"{Fore.YELLOW}⚠️  WARNING:{Style.RESET_ALL}")
                print(f"{Fore.WHITE}This will reset ALL settings to their default values.{Style.RESET_ALL}")
                print()
                print(f"{Fore.CYAN}Default settings:{Style.RESET_ALL}")
                print(f"  Format: {Fore.YELLOW}mp3{Style.RESET_ALL}")
                print(f"  Quality: {Fore.YELLOW}320k{Style.RESET_ALL}")
                print(f"  Output: {Fore.YELLOW}Albums/{Style.RESET_ALL}")
                print(f"  Cookies: {Fore.YELLOW}Disabled{Style.RESET_ALL}")
                print()
                confirm = Enhanced_Menu.get_input("Are you sure? (y/n)", "yn", default=False)
                if confirm:
                    downloader.reset_to_defaults()
            elif choice == 8:
                break
            if choice != 8:
                input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")

    actions = {
        1: downloader.download_track,
        2: downloader.download_album,
        3: downloader.download_playlist,
        4: downloader.download_from_file,
        5: downloader.search_a_song,
        6: downloader.download_channel,
        7: downloader.manage_cookies,
        8: downloader.check_dependencies,
        9: handle_settings,
        10: lambda: Youtube_Downloader.program_info(),
        11: downloader.troubleshooting,
        12: lambda: Youtube_Downloader.show_ytdlp_help(),
        13: handle_exit
    }

    while True:
        try:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Main Menu", "Select an option below:")
            Enhanced_Menu.print_section("📥 DOWNLOAD OPTIONS")
            Enhanced_Menu.print_menu_item(1, "Download Track")
            Enhanced_Menu.print_menu_item(2, "Download Album")
            Enhanced_Menu.print_menu_item(3, "Download Playlist")
            Enhanced_Menu.print_menu_item(4, "Download From Text File")
            Enhanced_Menu.print_menu_item(5, "Search & Download a Song")
            Enhanced_Menu.print_menu_item(6, "Download a YouTube Channel")
            
            Enhanced_Menu.print_section("⚙️  TOOLS & SETTINGS")
            Enhanced_Menu.print_menu_item(7, "Manage Cookies (for restricted content)")
            Enhanced_Menu.print_menu_item(8, "Check Dependencies")
            Enhanced_Menu.print_menu_item(9, "Program Settings")
            
            Enhanced_Menu.print_section("❓ HELP & INFORMATION")
            Enhanced_Menu.print_menu_item(10, "Show Program Info")
            Enhanced_Menu.print_menu_item(11, "Troubleshooting")
            Enhanced_Menu.print_menu_item(12, "Show yt-dlp Help")
            
            Enhanced_Menu.print_section("🚪 EXIT")
            Enhanced_Menu.print_menu_item(13, "Exit Program")
            print(f"\n{Style.DIM}{'─' * 60}{Style.RESET_ALL}")
            Enhanced_Menu.print_status("Current Settings:", "info", "⚙️")
            settings = [
                ("Format", downloader._Youtube_Downloader__audio_format),
                ("Quality", downloader._Youtube_Downloader__audio_quality),
                ("Output", str(downloader._Youtube_Downloader__output_directory)),
            ]
            for setting_name, setting_value in settings:
                print(f"  {Fore.CYAN}{setting_name}:{Style.RESET_ALL} {Fore.YELLOW}{setting_value}{Style.RESET_ALL}")
            cookie_status = "Enabled" if downloader.use_cookies else "Disabled"
            cookie_color = Fore.GREEN if downloader.use_cookies else Fore.YELLOW
            print(f"  {Fore.CYAN}Cookies:{Style.RESET_ALL} {cookie_color}{cookie_status}{Style.RESET_ALL}")
            print(f"{Style.DIM}{'─' * 60}{Style.RESET_ALL}")
            choice = Enhanced_Menu.get_input("\nEnter your choice (1-13)", "int", 1, 13)
            action = actions.get(choice)
            if action:
                Enhanced_Menu.clear_screen()
                try:
                    success = action()
                    if success is False and choice not in [8, 10, 11, 12, 13]:
                        print()
                        retry = Enhanced_Menu.get_input("Operation failed. Try again? (y/n)", "yn", default=True)
                        if retry:
                            continue
                except KeyboardInterrupt:
                    Enhanced_Menu.print_status("Operation cancelled", "warning")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Error: {e}", "error")
                    downloader.log_error(f"Menu option {choice} error: {e}", exc_info=True)
            else:
                Enhanced_Menu.print_status("Invalid option", "error")
            if choice != 13:
                print()
                cont = Enhanced_Menu.get_input("Return to main menu? (y/n)", "yn", default=True)
                if not cont:
                    handle_exit()
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Interrupted by user{Style.RESET_ALL}")
            handle_exit()
        except Exception as e:
            Enhanced_Menu.print_status(f"Unexpected error: {e}", "error")
            if Enhanced_Menu.get_input("Continue? (y/n)", "yn", default=True):
                continue
            else:
                handle_exit()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        print("Please check the error log for details.")