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
COOKIE_DIRECTORY= r"cookies"

os.makedirs("log", exist_ok=True)
os.makedirs(COOKIE_DIRECTORY, exist_ok=True)

"""==== Logger: Initialize the log fies before write ====  """

logger = logging.getLogger("Spotify Downloader")
log_format = logging.Formatter("SpotDL_Music_Converter - %(asctime)s - %(levelname)s - %(funcName)s - %(message)s") 
error_format = logging.Formatter("SpotDL_Music_Converter - %(asctime)s - %(levelname)s - %(message)s") 

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
    """ An enhanced menu system for better program interaction"""
    
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
        """Clear the terminal screen """
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_color(text, color_type='info', bold=False, end='\n'):
        """ Print colored text"""
        color_code = Enhanced_Menu.COLORS.get(color_type)
        if bold and 'BRIGHT' not in color_code:
            text = f"{Style.BRIGHT}{text}"
            
        print(f"{color_code}{text}{Style.RESET_ALL}", end=end)

    def print_boxed_title(title, width=60):
        """Print a title in a decorative box"""
        border = "═" * (width - 2)
        print(f"{Enhanced_Menu.COLORS['title']}╔{border}╗")
        padding = width - len(title) - 4
        left_pad = padding // 2
        right_pad = padding - left_pad
        print(f"{Enhanced_Menu.COLORS['title']}║{' ' * left_pad}{title}{' ' * right_pad}║")
        print(f"{Enhanced_Menu.COLORS['title']}╚{border}╝")
    
    def print_header(title, subtitle=""):
        """Print a formatted header"""
        print()
        Enhanced_Menu.print_boxed_title(title)
        if subtitle:
            print(f"\n{Enhanced_Menu.COLORS['info']}{subtitle}")
        print()
    
    def print_section(title, symbol="─"):
        """Print a section header"""
        print(f"\n{Enhanced_Menu.COLORS['section']}{symbol * 60}")
        print(f"  {title}")
        print(f"{symbol * 60}{Style.RESET_ALL}")
    
    def print_menu_item(number, title, description="", indent=2):
        """Print a menu item with number and description"""
        indent_str = " " * indent
        print(f"{indent_str}{Enhanced_Menu.COLORS['menu_item']}[{number:2}]{Style.RESET_ALL} "
              f"{Enhanced_Menu.COLORS['menu_item']}{Style.BRIGHT}{title}{Style.RESET_ALL}")
        
        if description:
            desc_indent = " " * (indent + 5)
            wrapped_desc = Enhanced_Menu.wrap_text(description, width=50)
            for line in wrapped_desc:
                print(f"{desc_indent}{Enhanced_Menu.COLORS['menu_desc']}{line}")
    
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
        
        print(f"{Enhanced_Menu.COLORS[config['color']]}{icon_to_use} {message}")
    
    def get_input(prompt, input_type="int", min_val=None, max_val=None, default=None):
        """Get validated user input with colored prompt"""
        prompt_color = Enhanced_Menu.COLORS['input']
        reset = Style.RESET_ALL
        
        while True:
            try:
                # Build prompt with default value
                full_prompt = f"{prompt_color}{prompt}{reset}"
                if default is not None:
                    full_prompt += f" [{Fore.YELLOW}{default}{reset}]"
                full_prompt += f"{prompt_color}:{reset} "
                
                user_input = input(full_prompt).strip()
                
                # Use default if no input
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
        Enhanced_Menu.print_header(f"\n Checking available browser cookies.... ")
        
        available_browsers = []
        failed_browsers = []
        
        for browser, cookie_func in self.cookie_sources.items():
            try:
                # Get cookies from this browser
                cookies = cookie_func(domain_name="https://open.spotify.com/")
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
            Enhanced_Menu.print_status("No browser cookies found for Spotify", "error")
            return 

    def extract_cookies(self, browser_name: str = 'brave') -> Optional[Path]:
        """Extract cookies from your browser of choice & saves to files"""
        if browser_name not in self.cookie_sources:
            Enhanced_Menu.print_status("Browser not supported", "error")
            Enhanced_Menu.print_status(f"Available browsers are: {', '.join(self.cookie_sources.keys())}", "info")
            return None
        
        Enhanced_Menu.print_header(f" Extracting cookies from {browser_name}....")
            
        try:
            # Retrieve cookies from Spotify domains
            domains = ['https://open.spotify.com/']
            all_cookies = []
            
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
                    f.write(f"{int(time.time()) + 3600*24*365}\t")  # Expiry (1 year from now)
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
                cookie_path = Path(cookie_file)
                if not cookie_path.exists():
                    Enhanced_Menu.print_status(f"Cookie file not found: {cookie_file}", "failure")
                    return None
        
        try:
            with open(cookie_path, 'r', encoding='utf-8') as f:
                content = f.read(200)
                if "# Netscape HTTP Cookie File" not in content:
                    Enhanced_Menu.print_status(f" Warning: Cookie file may not be in Netscape format", "errror")
            
            self.current_cookie_file = cookie_path
            Enhanced_Menu.print_status(f"Cookies loaded from:- {cookie_path}", "info")
            return cookie_path
        
        except Exception as e:
            Enhanced_Menu.print_status(f"Failed to load cookies:- {e}", "failure")
            return None
        
    def save_cookies(self, name: str = "cookies") -> List[Path]:
        """Save current cookie file to persistent storage"""
        if not self.current_cookie_file or not self.current_cookie_file.exists():
            Enhanced_Menu.print_status(f"No active cookie file to save", "error")
            return None
        
        try:
            # Create a text file for the cookies
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_path = self.cookie_directory / f"{name}_{timestamp}.txt"
            
            # Copy the cookie file
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
            Enhanced_Menu.print_status(f"No saved cookies files found.", "error")
            return []
        
        Enhanced_Menu.print_status(f"Saved cookie files:", "info")
        for i, cookie_file in enumerate(cookie_files, 1):
            file_size = cookie_file.stat().st_size
            mod_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(cookie_file.stat().st_mtime))
            print(f"{Fore.YELLOW}[{i}]{Style.RESET_ALL} {Fore.CYAN}{cookie_file.name:30}{Style.RESET_ALL}")
            print(f"     Size: {file_size} bytes | Modified: {mod_time}")
            
        return cookie_files

    def clear_cookies(self):
        """Clear all cookie files from the main cookie directory"""
        try:
            deleted_count = 0
            cookie_files = list(self.cookie_directory.glob("*.txt"))
            
            if not cookie_files:
                Enhanced_Menu.print_color(f"No cookie files found in {self.cookie_directory}")
                return
            
            Enhanced_Menu.print_color(f"Found {len(cookie_files)} cookie file(s) to delete:-")
            
            # List files to be deleted
            for cookie_file in cookie_files:
                Enhanced_Menu.print_color(f"  - {cookie_file.name}")
            
            # Ask for confirmation
            confirm = input(f"\nAre you sure you want to delete ALL {len(cookie_files)} cookie files? (y/n):- ").strip().lower()
            if confirm not in ['y', 'yes']:
                Enhanced_Menu.print_status("Cookie deletion cancelled.", "failure")
                return
            
            # Delete the files
            for cookie_file in cookie_files:
                try:
                    cookie_file.unlink()
                    deleted_count += 1
                    Enhanced_Menu.print_status(f"Deleted: {cookie_file.name}", "success")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Failed to delete {cookie_file.name}: {e}", "failure")
            
            # Clear current cookie file reference if it was deleted
            if self.current_cookie_file and not self.current_cookie_file.exists():
                self.current_cookie_file = None
            
            Enhanced_Menu.print_status(f"\nSuccessfully deleted {deleted_count} cookie file(s) from {self.cookie_directory}", "success")
            
        except Exception as e:
            Enhanced_Menu.print_status(f"Error clearing cookies: {e}", "error")

    def get_arguments(self) -> List[str]:
        """Get yt-dlp cookie arguments if cookies are available"""
        if self.current_cookie_file and self.current_cookie_file.exists():
            return ["--cookies", str(self.current_cookie_file)]
        return []
                
    def interactive_menu(self):
        """Interactive cookie setup menu"""
        while True:
            Enhanced_Menu.clear_screen()
            
            Enhanced_Menu.print_color('='*50)
            Enhanced_Menu.print_header("Cookie Manager Menu")
            Enhanced_Menu.print_color('='*50)
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
                Enhanced_Menu.print_status(f"You're active cookie files are: {self.current_cookie_file}", "success")
            else:
                Enhanced_Menu.print_status("You have no cookie files", "error")
                       
            choice = input("Select option (1-8): ").strip()
            
            if choice == "1":
                self.get_status()
                input("\nPress Enter to continue... ")
                
            elif choice == "2":
                print(f"\n====={Fore.CYAN}Available Browsers:{Style.RESET_ALL}======")

                for i, browser in enumerate(self.cookie_sources.keys(), 1):
                    Enhanced_Menu.print_color(f"{i}. {browser}")
                
                browser_choice = Enhanced_Menu.get_input("\nSelect browser (name or number): ", "str").strip()
                
                # Try to interpret as number
                if browser_choice.isdigit():
                    browser_num = int(browser_choice)
                    if 1 <= browser_num <= len(self.cookie_sources):
                        browser_name = list(self.cookie_sources.keys())[browser_num - 1]
                        self.extract_cookies(browser_name)
                else:
                    self.extract_cookies(browser_choice)
                    
                # Ask to save
                if self.current_cookie_file:
                    save = Enhanced_Menu.get_input("Save these cookies for future use? (y/n):- ", "yn", default=True)
                    if save in ['y', 'yes']:
                        name = Enhanced_Menu.get_input("Enter name for cookie file (optional):- ", "str").strip()
                        if not name:
                            name = "cookies"
                        self.save_cookies(name)
                
            elif choice == "3":
                cookie_files = self.list_cookies()
                if cookie_files:
                    load_choice = Enhanced_Menu.get_input("\nEnter number to load cookie file (or press Enter to skip):- ", "str")
                    if load_choice.isdigit():
                        idx = int(load_choice) - 1
                        if 0 <= idx < len(cookie_files):
                            self.load_cookies(str(cookie_files[idx]))
                input("\nPress Enter to continue...")
                
            elif choice == "4":
                cookie_file = Enhanced_Menu.get_input("Enter cookie filename or path: ", "str").strip()
                if cookie_file:
                    self.load_cookies(cookie_file)
                input("\nPress Enter to continue... ")
                
            elif choice == "5":
                if self.current_cookie_file:
                    name = Enhanced_Menu.get_input("Enter name for cookie file (optional): ", "str", default="cookies")
                    if not name:
                        name = "cookies"
                    self.save_cookies(name)
                else:
                    Enhanced_Menu.print_status(f"No active cookies to save", "info")
                input("\nPress Enter to continue...")
                
            elif choice == "6":
                self.clear_cookies()
                input("\nPress Enter to continue")
                
            elif choice == "7":
                status = self.get_status()
                if self.current_cookie_file:
                    Enhanced_Menu.print_status(f"Active cookie file: {self.current_cookie_file.name}", "success")
                else:
                    Enhanced_Menu.print_status("No active cookie file", "info")
                
            elif choice == "8":
                break
                
            else:
                Enhanced_Menu.print_status("Invalid choice", "info")
            
            input("\nPress Enter to continue...")                

class Spotify_Downloader:
    def __init__(self):
        """Initialize the """
        if 'MAX_RETRIES' not in globals():
            global MAX_RETRIES, RETRY_DELAY, DOWNLOAD_TIMEOUT
            MAX_RETRIES = 3
            RETRY_DELAY = 5
            DOWNLOAD_TIMEOUT = 300
            
        self.__output_directory = Path("Albums")
        self.__audio_quality = "320k"
        self.__audio_format = "mp3"
        self.__filepath = r"links/spotify_links.txt"
        self.__configuration_file = r"config/spotify_downloader_config.json"
        self.cookie_manager = CookieManager()
        self.use_cookies = False
        
        self.__output_directory.mkdir(parents=True, exist_ok=True)
        Path("links").mkdir(parents=True, exist_ok=True)
        Path("log").mkdir(parents=True, exist_ok=True)
        
        try:
            self.load_config()
        except Exception as e:
            self.log_error(f"Error loading config: {e}")        
        
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

            # Apply configuration safely
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
            # Use defaults
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
            audio_quality_input = Enhanced_Menu.get_input("What bitrate would you like (enter 'choice' to see options):- ", "str", default=self.__audio_quality)
            
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
            
        # Handle choice of audio format
        while True:
            audio_format_input = Enhanced_Menu.get_input("What format would you like(enter 'choice' to see options):- ", "str", default=self.__audio_format)
            
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
            
        # Handle choice of output directory
        output_path = Enhanced_Menu.get_input("Enter output directory (default: Albums):- ", "str", ).strip()
        if output_path:
            self.__output_directory = Path(output_path)
        else:
            self.__output_directory = Path("Albums")
            
        self.__output_directory.mkdir(parents=True, exist_ok=True)  

        # Handles choice for cookies
        Enhanced_Menu.print_status("Cookie Settings", "info")
        print(f"\n{Fore.CYAN}Cookies can help with:{Style.RESET_ALL}")
        print(" Age-restricted content")
        print(" Region-restricted videos")
        print(" Private playlists")
        
        cookie_choice = Enhanced_Menu.get_input("Use cookies for authentication? (y/n):- ", "yn", default=True)
        
        if cookie_choice in ['y', 'yes']:
            self.use_cookies = True
            Enhanced_Menu.print_status("Note: Make sure you have extracted the cookies beforehand, if make use of Cookie Mnager to help you", "info")
        else:
            self.use_cookies = False
    
    def validate_spotify_url(self, url: str) -> Tuple[bool, str]:
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
        
        for pattern in spotify_patterns:
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

    def validate_resource(self, url: str) -> Tuple[bool, str]:
        """ Validate if a resource is available before downloading to the device """
        print(f"Validating resource: {url}")
        
        try:
            # Use spotdl's metadata fetching capability
            command = ["spotdl", 
                       url,
                       "--skip-download",
                       "--print-json",
                       "--no-warnings"]
            
            result = subprocess.run(
                command, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
                timeout=30, check=False
            )
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    metadata = json.loads(result.stdout.strip())
                    
                    # Check for critical metadata
                    if not metadata.get('name') and not metadata.get('title'):
                        return False, "Invalid metadata - no title found", metadata
                    
                    # Check duration for tracks
                    if 'duration' in metadata:
                        duration = metadata.get('duration', 0)
                        if duration <= 0:
                            return False, "Invalid duration", metadata
                    
                    # Check if it's a playlist/album and get track count
                    if metadata.get('type') in ['playlist', 'album']:
                        tracks = metadata.get('tracks', [])
                        if not tracks:
                            return False, f"No tracks found in {metadata.get('type')}", metadata
                        
                        available_tracks = 0
                        unavailable_tracks = []
                        
                        for track in tracks:
                            if track.get('available', True):
                                available_tracks += 1
                            else:
                                unavailable_tracks.append(track.get('name', 'Unknown'))
                        
                        total_tracks = len(tracks)
                        if available_tracks == 0:
                            return False, f"No available tracks in {metadata.get('type')}", metadata
                        
                        if unavailable_tracks:
                            self.log_error(f"{len(unavailable_tracks)} tracks unavailable in {metadata.get('type')}")
                        
                        message = f"{metadata.get('type').title()} available with {available_tracks}/{total_tracks} tracks"
                        return True, message, metadata
                    
                    # For single tracks
                    return True, "Track available", metadata
                    
                except json.JSONDecodeError as e:
                    # Try to parse error message from stderr
                    error_msg = result.stderr.lower() if result.stderr else str(e)
                    
                    if "not found" in error_msg:
                        return False, "Resource not found on Spotify", None
                    elif "private" in error_msg:
                        return False, "Private resource - requires authentication", None
                    elif "unavailable" in error_msg:
                        return False, "Resource unavailable in your region", None
                    else:
                        return False, f"Invalid response: {error_msg[:100]}", None
            
            else:
                # Parse error from stderr
                error_msg = result.stderr.lower() if result.stderr else "Unknown error"
                
                if "not found" in error_msg:
                    return False, "Resource not found", None
                elif "private" in error_msg or "access" in error_msg:
                    return False, "Private or restricted access", None
                elif "unavailable" in error_msg:
                    return False, "Resource unavailable", None
                elif "quota" in error_msg or "rate limit" in error_msg:
                    return False, "Rate limit exceeded - try again later", None
                else:
                    return False, f"Validation failed: {error_msg[:100]}", None

        except subprocess.TimeoutExpired:
            return False, "Validation timeout - resource may be too large", None
        except FileNotFoundError:
            return False, "spotdl not found - please install it first", None
        except Exception as e:
            return False, f"Validation error: {str(e)[:100]}", None
           
    def parse_size(self, size_str: str) -> Optional[int]:
        """Parse size string to bytes"""
        if not size_str:
            return None
        
        size_str = size_str.strip().upper()
        units = {
        'B': 1,'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4, # Bits
        'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4,
        'KIB': 1024, 'MIB': 1024**2, 'GIB': 1024**3, 'TIB': 1024**4           
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
    
    def _parse_size_to_bytes(self, size_str: str) -> Optional[int]:
        """Parse size string to bytes"""
        return self.parse_size(size_str)
    
    # ==================================== The Download Function ===================================
    def run_download(self, url: str, output_template: str, additional_args=None):
        """ Run spotdl download with modern syntax """
        command = [
            "spotdl",
            "download", 
            url,
            "--output", output_template,
            "--overwrite", "skip",
            "--bitrate", self.__audio_quality,
            "--format", self.__audio_format
        ]
        
        if self.use_cookies and self.cookie_manager.current_cookie_file:
            cookie_args = self.cookie_manager.get_arguments()
            if cookie_args:
                command.extend(cookie_args)
                self.log_success("Using cookies from authentication")
            else:
                self.log_error("Error using cookies")
                    
        if additional_args:
            command.extend(additional_args)
        
        try:
            # Initialize progress bar
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
                    try:
                        # Parse percentage
                        percent_match = re.search(r'(\d+\.?\d*)%', line)
                        if percent_match:
                            percent = float(percent_match.group(1))
                            progress_bar.set_description(f"{Fore.CYAN}Downloading: {percent:.1f}%{Style.RESET_ALL}")
                        
                        # Parse total size
                        size_match = re.search(r'of\s+([\d\.]+\s*[KMGT]?i?B)', line)
                        if size_match and progress_bar.total is None:
                            total_str = size_match.group(1)
                            total_bytes = self._parse_size_to_bytes(total_str)
                            if total_bytes:
                                progress_bar.total = total_bytes
                        
                        # Parse downloaded size
                        downloaded_match = re.search(r'([\d\.]+\s*[KMGT]?i?B)\s+at', line) or \
                                        re.search(r'([\d\.]+\s*[KMGT]?i?B)\s+ETA', line) or \
                                        re.search(r'([\d\.]+\s*[KMGT]?i?B)\s*\/', line)
                        if downloaded_match:
                            downloaded_str = downloaded_match.group(1)
                            downloaded_bytes = self._parse_size_to_bytes(downloaded_str)
                            if downloaded_bytes:
                                progress_bar.n = downloaded_bytes
                        
                        # Parse download speed
                        speed_match = re.search(r'at\s+([\d\.]+\s*[KMGT]?i?B/s)', line)
                        if speed_match:
                            speed = speed_match.group(1)
                            progress_bar.set_postfix_str(f"Speed: {speed}")
                        
                        # Parse ETA
                        eta_match = re.search(r'ETA\s+([\d:]+)', line)
                        if eta_match:
                            eta = eta_match.group(1)
                            progress_bar.set_postfix_str(f"ETA: {eta}")
                        
                        progress_bar.refresh()
                        
                    except Exception:
                        continue
                
                if "100%" in line or "already been downloaded" in line or "[Merger]" in line:
                    if progress_bar.total and progress_bar.n < progress_bar.total:
                        progress_bar.n = progress_bar.total
                    progress_bar.set_description(f"{Fore.GREEN}Downloaded{Style.RESET_ALL}")
                    progress_bar.set_postfix_str("")
                    progress_bar.refresh()
                    break
            
            # Wait for process to complete
            result.wait()
            stdout, stderr = result.communicate()
            
            if progress_bar:
                progress_bar.close()
                    
            if result.returncode == 0:
                self.log_success(f"Successfully downloaded: {url}")
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=stdout,
                    stderr=""
                )

            else:
                self.log_failure(f"Download failed for {url} with code {result.returncode}")
                if result.stderr:
                    self.log_error(f"Error: {result.stderr[:200]}")
                return subprocess.CalledProcessError(
                    result.returncode, 
                    command, 
                    result.stdout, 
                    result.stderr
                )
                
        except subprocess.TimeoutExpired:
            self.log_error(f"Download timeout for {url}")
            return None
        except Exception as e:
            self.log_error(f"Unexpected error in run_download: {e}")
            return None

    def rate_limit(self, calls_per_minute=60):
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
                        last_called[0] = time.time() - (60.0/ calls_per_minute)
            return wrapper
        return decorator

    # ==================================== Main Download Functions ===================================
    @rate_limit(calls_per_minute=30)
    def download_track(self):
        """Download a single track"""
        while True:  # Add outer loop for URL input retry
            print("\n" + "="*55)
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Download Track")

            url = Enhanced_Menu.get_input("Enter Spotify URL (or 'back' to return)", "str")
            
            if url.lower() == 'back':
                return False
            
            if not url:
                Enhanced_Menu.print_status(f"No URL provided", "error")
                continue  # Go back to asking for URL
            
            # Validate URL
            is_valid, resource_type =  self.validate_spotify_url(url)
            if not is_valid:
                Enhanced_Menu.print_status("Invalid Spotify URL. Enter a valid Spotify/Spotify Music URL", "error")
                continue
            
            if resource_type != "track":
                Enhanced_Menu.print_status(f"Warning: URL appears to be a {resource_type}, not a track", "warning")
                proceed = Enhanced_Menu.get_input("Continue anyway? (y/n): ", "yn", default=False)
                if not proceed:
                    continue
            
            # Validate resource before downloading
            Enhanced_Menu.print_status("Validating resource availability...", "info")
            is_available, message, metadata = self.validate_resource(url)
            
            if not is_available:
                Enhanced_Menu.print_status(f"Resource validation failed, Please try a different URL.", "failed")
                self.log_failure(f"Resource validation failed for {url}: {message}")
                continue
            
            Enhanced_Menu.print_status(f"{message}", "success")
            if metadata:
                print(f"\n{Fore.CYAN}Track Details:{Style.RESET_ALL}")
                print(f"  Title: {Fore.YELLOW}{metadata.get('name', 'Unknown')}{Style.RESET_ALL}")
                artists = metadata.get('artists', [{}])
                if artists:
                    print(f"  Artist: {Fore.YELLOW}{artists[0].get('name', 'Unknown')}{Style.RESET_ALL}")
                duration = metadata.get('duration', 0)
                if duration:
                    print(f"  Duration: {Fore.YELLOW}{duration//60}:{duration%60:02d}{Style.RESET_ALL}")
            
            else:
                Enhanced_Menu.print_status(f"Resource validated successfully: {message}", "success")
                break
            
        # Get user preferences
        if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
            self.get_user_preferences()
            
        Enhanced_Menu.print_status(f"Starting Track download: {url}. This may take a few minutes...", "info")
        output_template = str(self.__output_directory / "{artists} - {title}.{output.ext}")
            
        for attempt in range(1, MAX_RETRIES + 1):
            Enhanced_Menu.print_section(f"Downloading Track")
            
            # Add delay between retries
            if attempt > 1:
                print(f"Waiting {RETRY_DELAY} seconds before retry...")
                time.sleep(RETRY_DELAY)
            
            result = self.run_download(url, output_template)
            
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                self.log_success(f"Successfully downloaded track: {url}")
                
                # Ask if user wants to download another track
                another = Enhanced_Menu.get_input("Download another track? (y/n): ", "yn")
                if another in ['y', 'yes']:
                    continue  # Go back to URL input
                else:
                    return True
            
            # If we get here, there was an error
            elif attempt < MAX_RETRIES:
                Enhanced_Menu.print_status(f"Download failed, retrying...", "error")
            
            # If the download failed after all retries
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts")
                return False
            
        print("="*55)
        return False
    
    @rate_limit(calls_per_minute=30)
    def download_album(self):
        """Download an album"""
        while True:
            print("\n" + "="*50)
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Album Download")
            
            url = Enhanced_Menu.get_input("Enter Spotify album URL (or 'back' to return): ", "str")
            
            if url.lower() == 'back':
                return False
            
            if not url:
                Enhanced_Menu.print_status("No URL provided", "error")
                continue
            
            # Validate URL
            is_valid, resource_type = self.validate_spotify_url(url)
            if not is_valid:
                Enhanced_Menu.print_status("Invalid Spotify URL. Please enter a valid Spotify album URL", "error")
                continue
            
            if resource_type != "album":
                Enhanced_Menu.print_status(f"Warning: URL appears to be a {resource_type}, not an album", "warning")
                proceed = Enhanced_Menu.get_input("Continue anyway? (y/n): ", "yn", default=False)
                if not proceed:
                    continue
            
            # Validate resource availability
            Enhanced_Menu.print_status("Validating album availability...", "info")
            is_available, message, metadata = self.validate_resource(url)
            
            if not is_available:
                Enhanced_Menu.print_status(f"Album unavailable: {message}", "error")
                retry = Enhanced_Menu.get_input("Try to download anyway? (y/n): ", "yn", default=False)
                if not retry:
                    continue
            
            Enhanced_Menu.print_status(f"{message}", "success")
            if metadata:
                print(f"\n{Fore.CYAN}Album Details:{Style.RESET_ALL}")
                print(f"  Album: {Fore.YELLOW}{metadata.get('name', 'Unknown')}{Style.RESET_ALL}")
                artists = metadata.get('artists', [{}])
                if artists:
                    print(f"  Artist: {Fore.YELLOW}{artists[0].get('name', 'Unknown')}{Style.RESET_ALL}")
                tracks = metadata.get('tracks', [])
                if tracks:
                    available_tracks = sum(1 for t in tracks if t.get('available', True))
                    print(f"  Tracks: {Fore.YELLOW}{available_tracks}/{len(tracks)} available{Style.RESET_ALL}")
            
            # Get user preferences
            if Enhanced_Menu.get_input("Configure download settings? (y/n): ", "yn", default=False):
                self.get_user_preferences()
            
            Enhanced_Menu.print_status(f"Starting Album download: {url}. This may take a few minutes...", "info")
            output_template = str(self.__output_directory / "{artists}/{album}/{artist} - {title}.{output-ext}")
            
            for attempt in range(1, MAX_RETRIES + 1):
                Enhanced_Menu.print_status(f"Downloading Album", "info")
                
                # Add delay between retries
                if attempt > 1:
                    print(f"Waiting {RETRY_DELAY} seconds before retry...")
                    time.sleep(RETRY_DELAY)
                
                result = self.run_download(url, output_template)
                
                if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                    self.log_success(f"Successfully downloaded album {url}")
                    
                # Ask if user wishes to download another album
                    another = input("Download another album? (y/n):- ").strip().lower()
                    if another in ['y', 'yes']:
                        continue # Go back to URL input
                    else:
                        return True # Return success but exit to menu
                                   
                elif attempt < MAX_RETRIES:
                    Enhanced_Menu.print_status(f"Download failed, retrying...", "error")
                    error_msg = f"Download failed (attempt {attempt}/{MAX_RETRIES})."
                    if result.stderr:
                        error_msg += f" Error: {result.stderr[:200]}"
                    self.log_error(error_msg)
                    print("="*50)
                
                else:
                    self.log_failure(f"Failed to download after {MAX_RETRIES} attempts")
                    return False
            
            print("="*50)
            return False
    
    @rate_limit(calls_per_minute=30)
    def download_playlist(self):
        """Download a playlist"""
        while True:
            print("\n" + "="*55)
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Playlist Download", "Download playlists from Spotify")
            
            url = Enhanced_Menu.get_input("Enter Spotify playlist URL (or 'back' to return): ", "str")
            
            if url.lower() == 'back':
                return False
            
            if not url:
                Enhanced_Menu.print_status("No URL provided", "error")
                continue
            
            # Validate URL
            is_valid, resource_type = self.validate_spotify_url(url)
            if not is_valid:
                Enhanced_Menu.print_status("Invalid Spotify URL. Please enter a valid Spotify playlist URL", "error")
                continue
            
            if resource_type != "playlist":
                Enhanced_Menu.print_status(f"Warning: URL appears to be a {resource_type}, not a playlist", "warning")
                proceed = Enhanced_Menu.get_input("Continue anyway? (y/n): ", "yn", default=False)
                if not proceed:
                    continue
            
            # Validate resource availability
            Enhanced_Menu.print_status("Validating playlist availability...", "info")
            is_available, message, metadata = self.validate_resource(url)
            
            if not is_available:
                Enhanced_Menu.print_status(f"Playlist unavailable: {message}", "error")
                retry = Enhanced_Menu.get_input("Try to download anyway? (y/n): ", "yn", default=False)
                if not retry:
                    continue
            
            Enhanced_Menu.print_status(f"{message}", "success")
            if metadata:
                print(f"\n{Fore.CYAN}Playlist Details:{Style.RESET_ALL}")
                print(f"  Playlist: {Fore.YELLOW}{metadata.get('name', 'Unknown')}{Style.RESET_ALL}")
                tracks = metadata.get('tracks', [])
                if tracks:
                    available_tracks = sum(1 for t in tracks if t.get('available', True))
                    print(f"  Tracks: {Fore.YELLOW}{available_tracks}/{len(tracks)} available{Style.RESET_ALL}")
            
            # Get user preferences
            if Enhanced_Menu.get_input("Configure download settings? (y/n): ", "yn", default=False):
                self.get_user_preferences()
            
            Enhanced_Menu.print_status(f"Starting Playlist download: {url}. This may take a few minutes...", "info")
            output_template = str(self.__output_directory / "{playlist}/{artists} - {title}.{output-ext}")
            
            for attempt in range(1, MAX_RETRIES + 1):
                Enhanced_Menu.print_status(f"Downloading Playlist", "info")
                
                # Add delay between retries
                if attempt > 1:
                    print(f"Waiting {RETRY_DELAY} seconds before retry...")
                    time.sleep(RETRY_DELAY)
                
                result = self.run_download(
                    url, 
                    output_template,
                    ["--playlist-numbering", "--playlist-retain-track-cover"]
                )
                
                if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                    self.log_success(f"Successfully downloaded playlist {url}")
                    
                    # Ask if user wants to download another track
                    another = Enhanced_Menu.get_input("Download another playlist? (y/n): ", "yn")
                    if another in ['y', 'yes']:
                        continue  # Go back to URL input
                    else:
                        return True  # Return success but exit to menu
                
                elif attempt < MAX_RETRIES:
                    Enhanced_Menu.print_status(f"Download failed, retrying...", "error")
                
                else:
                    self.log_failure(f"Failed to download after {MAX_RETRIES} attempts")
                    return False
                    
            return False
    
    @rate_limit(calls_per_minute=30)
    def download_from_file(self):
        """Download various links from a file"""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Batch Download", "Download from a text file containing links")
        
        filepath = Enhanced_Menu.get_input("Enter the path to the text file: ",  "str", default=self.__filepath)
        
        if not filepath or not os.path.exists(filepath):
            self.log_failure(f"File not found: {filepath}")
            Enhanced_Menu.print_status(f"File not found: {filepath}", "error")
            return False
        
        # Ask about validation
        Enhanced_Menu.print_section("VALIDATION OPTIONS")
        Enhanced_Menu.print_menu_item(1, "Validate all resources before downloading", "Recommended")
        Enhanced_Menu.print_menu_item(2, "Skip validation and download directly", "Faster but may fail")
        Enhanced_Menu.print_menu_item(3, "Validate but ignore cache", "Fresh validation")
        
        validation_choice = Enhanced_Menu.get_input("Choose option (1-3): ", "int", 1, 3, default=1)
        
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
        
        # Filter out already downloaded URLs
        urls_to_process = []
        for line in file_lines:
            if "# DOWNLOADED" not in line:
                # Extract URL (remove comments)
                url = line.split('#')[0].strip()
                if url:
                    urls_to_process.append(url)
        
        if not urls_to_process:
            Enhanced_Menu.print_status("All URLs in file are already marked as downloaded.", "info")
            return True
        
        # Validate resources if chosen
        if validation_choice in [1, 3]:
            skip_cache = (validation_choice == 3)
            
            # Validate each URL individually
            validation_results = {}
            print(f"\n{Fore.CYAN}Validating {len(urls_to_process)} resources...{Style.RESET_ALL}")
            
            for i, url in enumerate(urls_to_process, 1):
                print(f"  Validating {i}/{len(urls_to_process)}: {url[:80]}...")
                is_available, message, metadata = self.validate_resource(url, skip_cache)
                validation_results[url] = (is_available, message, metadata)
            
            # Show validation summary
            available_count = sum(1 for result in validation_results.values() if result[0])
            total_count = len(validation_results)
            
            Enhanced_Menu.print_section("VALIDATION SUMMARY")
            Enhanced_Menu.print_status(f"Available: {available_count}/{total_count}", "success")
            Enhanced_Menu.print_status(f"Unavailable: {total_count - available_count}/{total_count}", "failure" if total_count - available_count > 0 else "info")
            
            # Ask user how to proceed
            Enhanced_Menu.print_section("DOWNLOAD OPTIONS")
            Enhanced_Menu.print_menu_item(1, "Download only available resources", "Recommended")
            Enhanced_Menu.print_menu_item(2, "Download all resources", "May fail for unavailable ones")
            Enhanced_Menu.print_menu_item(3, "Show detailed validation results")
            Enhanced_Menu.print_menu_item(4, "Cancel download")
            
            download_choice = Enhanced_Menu.get_input("Choose option (1-4): ", "int", 1, 4, default=1)
            
            if download_choice == 3:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("DETAILED VALIDATION RESULTS")
                
                for url, (is_available, message, _) in validation_results.items():
                    status = "✓" if is_available else "✗"
                    color = Fore.GREEN if is_available else Fore.RED
                    print(f"  {color}{status}{Style.RESET_ALL} {url[:60]}...")
                    print(f"     {message}\n")
                
                print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
                Enhanced_Menu.print_menu_item(1, "Download only available resources")
                Enhanced_Menu.print_menu_item(2, "Download all resources")
                Enhanced_Menu.print_menu_item(3, "Cancel download")
                download_choice = Enhanced_Menu.get_input("Choose option (1-3): ", "int", 1, 3, default=1)
            
            if download_choice == 4 or (download_choice == 3 and download_choice == 3):
                Enhanced_Menu.print_status("Download cancelled.", "info")
                return False
            
            # Filter URLs based on choice
            if download_choice == 1:
                urls_to_download = [url for url in urls_to_process if validation_results[url][0]]
                Enhanced_Menu.print_status(f"Downloading {len(urls_to_download)} available resources...", "info")
            else:
                urls_to_download = urls_to_process
                Enhanced_Menu.print_status(f"Downloading all {len(urls_to_download)} resources...", "info")
        else:
            urls_to_download = urls_to_process
            Enhanced_Menu.print_status(f"Downloading {len(urls_to_download)} resources without validation...", "warning")
        
        success_count = 0
        failed_count = 0
        
        for i, url in enumerate(urls_to_download, 1):
            Enhanced_Menu.print_section(f"PROCESSING URL {i}/{len(urls_to_download)}")
            print(f"URL: {url[:80]}...")
            
            clean_url = url.split('#')[0].strip()
            
            # Determine output template based on URL type
            is_valid, resource_type = self.validate_spotify_url(url)
            if is_valid and resource_type == "playlist":
                output_template = str(self.__output_directory / "{playlist}/{title}.{output-ext}")
                additional_args = ["--playlist-numbering", "--playlist-retain-track-cover"]
            elif is_valid and resource_type == "album":
                output_template = str(self.__output_directory / "{artists}/{album}/{title}.{output-ext}")
                additional_args = None
            else:
                output_template = str(self.__output_directory / "{artists} - {title}.{output-ext}")
                additional_args = None
                
            success = False
            for attempt in range(1, MAX_RETRIES + 1):
                print(f"\n{Fore.CYAN}Attempt {attempt} of {MAX_RETRIES}{Style.RESET_ALL}")
                
                try:
                    result = self.run_download(url, output_template, additional_args)
                    
                    if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                        success = True
                        break
                    elif attempt < MAX_RETRIES:
                        Enhanced_Menu.print_status(f"Download failed. Retrying in {RETRY_DELAY} seconds...", "error")
                        time.sleep(RETRY_DELAY)
                except Exception as e:
                    self.log_failure(f"Exception during the download: {e}")
            
            if success:
                success_count += 1
                self.log_success(f"Successfully downloaded {url}")
                
                # Update the original file lines
                for idx, line in enumerate(file_lines):
                    if line.startswith(clean_url):
                        if "#" in line:
                            parts = line.split('#')
                            file_lines[idx] = f"{parts[0].strip()} # DOWNLOADED"
                        else:
                            file_lines[idx] = f"{clean_url} # DOWNLOADED"
                        break
            else:
                failed_count += 1
                self.log_failure(f"Failed to download {url}")
                # Update the original file lines
                for idx, line in enumerate(file_lines):
                    if line.startswith(clean_url):
                        if "#" in line:
                            parts = line.split('#')
                            file_lines[idx] = f"{parts[0].strip()} # FAILED"
                        else:
                            file_lines[idx] = f"{clean_url} # FAILED"
                        break
        
        # Update the file
        try: 
            with open(filepath, 'w', encoding='utf-8') as file:
                file.write("\n".join(file_lines))    
        except Exception as e:
            self.log_failure(f"Error updating the file: {e}")
        
        # Summary
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("DOWNLOAD SUMMARY")
        
        Enhanced_Menu.print_section("RESULTS")
        Enhanced_Menu.print_status(f"Successful Downloads: {success_count}", "success")
        Enhanced_Menu.print_status(f"Failed Downloads: {failed_count}", "failure" if failed_count > 0 else "info")
        Enhanced_Menu.print_status(f"Total Processed: {len(urls_to_download)}", "info")
        
        return failed_count == 0
    
    @rate_limit(calls_per_minute=30)
    def search_a_song(self):
        """Search for a song and download"""    
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Search & Download", "Search for songs by name")
        
        song_query = Enhanced_Menu.get_input("Enter song name or search query: ", "str").strip()

        if not song_query:
            Enhanced_Menu.print_status("No input provided", "error")
            return False
        
        if Enhanced_Menu.get_input("Configure download settings? (y/n): ", "yn", default=False):
            self.get_user_preferences()
        
        Enhanced_Menu.print_status(f"Searching for: '{song_query}'", "info")
        search_time = time.time()
        
        output_template = str(self.__output_directory / "{artists} - {title}.{output-ext}")
        
        for attempt in range(1, MAX_RETRIES + 1):
            Enhanced_Menu.print_section(f"SEARCHing")
            
            # Add delay between retries
            if attempt > 1:
                print(f"{Fore.YELLOW}Waiting {RETRY_DELAY} seconds before retry...{Style.RESET_ALL}")
                time.sleep(RETRY_DELAY)
            
            try:
                # Use our run_download method
                result = self.run_download(song_query, output_template)
                
                if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                    elapsed_time = time.time() - search_time
                    self.log_success(f"Successfully downloaded in {elapsed_time:.1f} seconds!")
                    return True
                elif attempt < MAX_RETRIES:
                    Enhanced_Menu.print_status(f"Download failed. Retrying...", "error")
                else:
                    self.log_failure(f"Failed to download after {MAX_RETRIES} attempts")
                    return False
                    
            except Exception as e:
                self.log_error(f"Unexpected error: {e}")
                if attempt < MAX_RETRIES:
                    continue
                else:
                    return False

        return False

    # ==================================== 
    # Special Download Functions
    # ===================================
    
    @rate_limit(calls_per_minute=30)
    def download_user_playlist(self):
        """Download a user's playlist (requires authentication)"""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("USER PLAYLIST DOWNLOAD", "Download your personal playlists")
        
        Enhanced_Menu.print_status("Note: This requires Spotify authentication", "warning")
        Enhanced_Menu.print_status("You will be redirected to the Spotify website for authorization", "info")
        
        proceed = Enhanced_Menu.get_input("Continue? (y/n): ", "yn", default=True)
        if not proceed:
            return False
        
        if Enhanced_Menu.get_input("Configure download settings? (y/n): ", "yn", default=False):
            self.get_user_preferences()
        
        output_template = str(self.__output_directory / "{playlist}/{artists} - {title}.{output-ext}")
        
        Enhanced_Menu.print_status("Starting download...", "info")
        
        try:
            result = subprocess.run([
                "spotdl",
                "download",
                "all-user-playlists",
                "--user-auth",
                "--output", output_template,
                "--overwrite", "skip",
                "--bitrate", self.__audio_quality,
                "--format", self.__audio_format,
            ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
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
        
        output_template = str(self.__output_directory / "Liked Songs/{artists} - {title}.{output-ext}")
        
        Enhanced_Menu.print_status("Starting download...", "info")
        
        try:
            result = subprocess.run([
                "spotdl",
                "download",
                "saved",
                "--user-auth",
                "--output", output_template,
                "--overwrite", "skip",
                "--bitrate", self.__audio_quality,
                "--format", self.__audio_format,
            ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
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
        
        output_template = str(self.__output_directory / "{artists}/{album}/{artists} - {title}.{output-ext}")
        
        Enhanced_Menu.print_status("Starting download...", "info")
        
        try:
            result = subprocess.run([
                "spotdl",
                "download",
                "all-user-saved-albums",
                "--user-auth",
                "--output", output_template,
                "--overwrite", "skip",
                "--bitrate", self.__audio_quality,
                "--format", self.__audio_format,
            ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
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
    def check_spotdl():
        """
        Check if spotdl is installed (cache spotdl)
        """
        if shutil.which("spotdl"):
            print("spotdl is already installed")
            
            # Check version
            try:
                result = subprocess.run(
                    ["spotdl", "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                    timeout=10
                )
                if result.returncode == 0:
                    version = result.stdout.strip()
                    Enhanced_Menu.print_status(f"spotdl version: {version}", "success")
                    return True
                
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
                Enhanced_Menu.print_status("Could not determine spotdl version")
                return False
    
    @staticmethod     
    def show_spotdl_help():
        """ Display spotdl help """
        try:
            result = subprocess.run(
                ["spotdl", "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            print("="*50)
            Enhanced_Menu.print_header("SPOTDL HELP")
            print("="*50)
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            Enhanced_Menu.print_status(f"Could not get spotdl help: {e}")

    @staticmethod
    def check_ffmpeg():
        """ Check if ffmpeg is installed"""
        Enhanced_Menu.print_header("Checking for FFMpeg")
        if shutil.which("ffmpeg"):
            print("ffmpeg is already installed")
            
            # Check version
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
                    Enhanced_Menu.print_status(f"ffmpeg version: {version}")
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
                Enhanced_Menu.print_status("Could not determine ffmpeg version", "")
                return False
    
    @staticmethod
    def check_dependencies():
        "Check for missing dependencies"
        Enhanced_Menu.print_header("Checking for Missing Dependencies")
        missing_packages = []
        for package in ['browser_cookie3' ,'colorama', 'tqdm', 'spotdl']:
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
            'spotdl': ['spotdl'],
            'browser_cookie3': ['browser_cookie3'],
            'ffmpeg': ['ffmpeg'],
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
        print("\n" + "="*50)
        Enhanced_Menu.print_header("Troubleshooting", "")
        print("="*50)
        
        print("Hello, this troubleshooter is to help if you're experiencing problem in the program")
        print("Running a simple daignostic. This might take a while.....")
        
        # 1. Check if yt-dlp is installed
        Enhanced_Menu.print_status("1. Checking spotdl installation...", "info")
        if not Spotify_Downloader.check_spotdl():
            Enhanced_Menu.print_status("spotdl not found or not working", "error")
            install = Enhanced_Menu.get_input("Install yt-dlp now? (y/n)", "yn", default=True)
            if install:
                self.setup_dependencies()
        

        Enhanced_Menu.print_status("\n2. Checking FFmpeg installation...", "info")
        if not Spotify_Downloader.check_ffmpeg():
            Enhanced_Menu.print_status("FFmpeg not found (audio conversion might fail)", "warning")


        Enhanced_Menu.print_status("\n3. Testing Spotify access...", "info")
        test_url = "https://music.youtube.com/watch?v=215T8NF93kw"
        try:
            test_command = ["spotdl", "--skip-download", "--print-json", test_url]
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
                320k, 256k, 128k, 44k,
                
                {Fore.CYAN}Supported Audio Formats:{Style.RESET_ALL}
                MP3, M4A, FLAC, OGG, OPUS, WAV

                {Fore.CYAN}Usage Tips:{Style.RESET_ALL}
                • Use authentication for personal content
                • Configure settings before large downloads
                • Use batch files for multiple downloads
                • Monitor disk space for large downloads
        """)

def main():
    """Main function to run the Spotify Downloader with integrated menus."""
    # Initialize
    Enhanced_Menu.clear_screen()
    
    print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}")
    print(r"""
     _____             __  _  ______          _      _____                  
    / ___/____  ____  / /_(_)/ ____/___  ____| |    / /   |  ______________ 
    \__ \/ __ \/ __ \/ __/ / /   / __ \/ __ \ |   / / /| | / ___/ ___/ __ \
   ___/ / /_/ / /_/ / /_/ / /___/ /_/ / /_/ / |  / / ___ |(__  ) /__/ /_/ /
  /____/ .___/\____/\__/_/\____/\____/\____/| | /_/_/  |_/____/\___/\____/ 
      /_/                                   |_/                           
    """)
    print(f"{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{Style.BRIGHT}Initializing Spotify Music Downloader...{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
    
    # Create necessary directories
    directories = ["log", "Albums", "links"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"{Fore.GREEN}✓{Style.RESET_ALL} Directory '{directory}/' ready")
    
    # Check dependencies
    if not Spotify_Downloader.check_dependencies():
        input(f"\n{Fore.RED}Press Enter to exit...{Style.RESET_ALL}")
        sys.exit(1)
    
    # Create downloader instance
    try:
        downloader = Spotify_Downloader()
        Enhanced_Menu.print_status("Downloader initialized successfully", "success")
        time.sleep(1)
    except Exception as e:
        Enhanced_Menu.print_status(f"Initialization error: {e}", "error")
        input(f"\n{Fore.RED}Press Enter to exit...{Style.RESET_ALL}")
        sys.exit(1)
    
    # Define action handlers
    def handle_exit():
        """Graceful exit function"""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("THANK YOU", "Goodbye!")
        
        print(f"""
{Fore.CYAN}
╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║          Thank you for using Spotify Music Downloader!                  ║
║                                                                          ║
║                      Happy Listening!                                    ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
{Style.RESET_ALL}""")
        
        # Save settings on exit
        try:
            downloader.save_config()
            print(f"{Fore.GREEN}Settings saved.{Style.RESET_ALL}")
        except:
            pass
        
        # Clean up
        downloader.cleanup_directory()
        
        print(f"\n{Fore.CYAN}Goodbye!{Style.RESET_ALL}\n")
        sys.exit(0)
    
    def handle_settings():
        """Handle program settings menu"""
        while True:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("PROGRAM SETTINGS", "Configure download preferences")
            
            # Audio Settings Section
            Enhanced_Menu.print_section("🎵 AUDIO SETTINGS")
            
            current_format = downloader._Spotify_Downloader__audio_format
            current_quality = downloader._Spotify_Downloader__audio_quality
            
            Enhanced_Menu.print_menu_item(1, "Audio Format", 
                                       f"Current: {Fore.GREEN}{current_format.upper()}{Style.RESET_ALL}")
            Enhanced_Menu.print_menu_item(2, "Audio Quality", 
                                       f"Current: {Fore.GREEN}{current_quality}{Style.RESET_ALL}")
            
            # Output Settings Section
            Enhanced_Menu.print_section("📁 OUTPUT SETTINGS")
            
            current_dir = str(downloader._Spotify_Downloader__output_directory)
            Enhanced_Menu.print_menu_item(3, "Output Directory", 
                                       f"Current: {Fore.CYAN}{current_dir}{Style.RESET_ALL}")
            
            # Configuration Management Section
            Enhanced_Menu.print_section("⚙️ CONFIGURATION")
            Enhanced_Menu.print_menu_item(4, "Save Settings", "Save current settings to file")
            Enhanced_Menu.print_menu_item(5, "Load Settings", "Load settings from file")
            Enhanced_Menu.print_menu_item(6, "Reset to Defaults", "Restore default settings")
            
            # Navigation
            Enhanced_Menu.print_section("↩️ NAVIGATION")
            Enhanced_Menu.print_menu_item(7, "Back to Main Menu", "Return to main menu")
            
            print()
            
            choice = Enhanced_Menu.get_input("Select option", "int", 1, 7)
            
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
                    downloader._Spotify_Downloader__audio_format = new_format
                    Enhanced_Menu.print_status(f"Audio format set to {new_format.upper()}", "success")
                    
            elif choice == 2:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("AUDIO QUALITY", "Select bitrate/quality")
                
                qualities = [
                    ("320k", "High quality (320 kbps)", "Excellent for most music"),
                    ("256k", "Very good (256 kbps)", "Great quality, smaller files"),
                    ("192k", "Good (192 kbps)", "Good balance of quality/size"),
                    ("128k", "Standard (128 kbps)", "Acceptable quality, small files"),
                    ("auto", "Auto-select", "Let spotdl choose the best"),
                    ("disable", "Original quality", "Keep original audio as-is"),
                ]
                
                for i, (code, name, desc) in enumerate(qualities, 1):
                    is_current = " ✓" if code == current_quality else ""
                    print(f"  {Fore.YELLOW}[{i}]{Style.RESET_ALL} {Fore.CYAN}{name:20}{Style.RESET_ALL} - {desc}{Fore.GREEN}{is_current}{Style.RESET_ALL}")
                
                print()
                quality_choice = Enhanced_Menu.get_input("Select quality (1-6)", "int", 1, 6)
                if quality_choice:
                    new_quality = qualities[quality_choice - 1][0]
                    downloader._Spotify_Downloader__audio_quality = new_quality
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
                        downloader._Spotify_Downloader__output_directory = Path(new_dir)
                        downloader._Spotify_Downloader__output_directory.mkdir(parents=True, exist_ok=True)
                        Enhanced_Menu.print_status(f"Output directory changed to {new_dir}", "success")
                    except Exception as e:
                        Enhanced_Menu.print_status(f"Error: {str(e)[:50]}", "error")
                        
            elif choice == 4:
                try:
                    downloader.save_config()
                    Enhanced_Menu.print_status("Settings saved successfully", "success")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Error saving settings: {e}", "error")
                    
            elif choice == 5:
                try:
                    downloader.load_config()
                    Enhanced_Menu.print_status("Settings loaded successfully", "success")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Error loading settings: {e}", "error")
                    
            elif choice == 6:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("RESET SETTINGS", "Restore defaults")
                
                print(f"{Fore.YELLOW}⚠️ WARNING:{Style.RESET_ALL}")
                print(f"{Fore.WHITE}This will reset ALL settings to their default values.{Style.RESET_ALL}")
                print()
                print(f"{Fore.CYAN}Default settings:{Style.RESET_ALL}")
                print(f"  Format: {Fore.YELLOW}mp3{Style.RESET_ALL}")
                print(f"  Quality: {Fore.YELLOW}320k{Style.RESET_ALL}")
                print(f"  Output: {Fore.YELLOW}Albums/{Style.RESET_ALL}")
                print()
                
                confirm = Enhanced_Menu.get_input("Are you sure? (y/n)", "yn", default=False)
                if confirm:
                    downloader.__init__()
                    Enhanced_Menu.print_status("Settings reset to defaults", "success")
                    
            elif choice == 7:
                break
                
            if choice != 7:
                input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    # Define actions dictionary
    actions = {
        1: downloader.download_track,
        2: downloader.download_album,
        3: downloader.download_playlist,
        4: downloader.download_from_file,
        5: downloader.search_a_song,
        6: downloader.download_user_playlist,
        7: downloader.download_user_liked_songs,
        8: downloader.download_user_saved_albums,
        9: Spotify_Downloader.check_spotdl,
        10: lambda: Spotify_Downloader.show_spotdl_help(),
        11: handle_settings,
        12: lambda: Spotify_Downloader.program_info(),
        13: handle_exit
    }
    
    # Main program loop
    while True:
        try:
            Enhanced_Menu.clear_screen()
            
            # Display main menu
            print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}{Style.BRIGHT}")
            print(r"""
     _____             __  _  ______          _      _____                  
    / ___/____  ____  / /_(_)/ ____/___  ____| |    / /   |  ______________ 
    \__ \/ __ \/ __ \/ __/ / /   / __ \/ __ \ |   / / /| | / ___/ ___/ __ \
   ___/ / /_/ / /_/ / /_/ / /___/ /_/ / /_/ / |  / / ___ |(__  ) /__/ /_/ /
  /____/ .___/\____/\__/_/\____/\____/\____/| | /_/_/  |_/____/\___/\____/ 
      /_/                                   |_/                           
    """)
            print(f"{Style.RESET_ALL}")
            print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
            Enhanced_Menu.print_header("Main Menu", "Select an option below:")
            
            Enhanced_Menu.print_section("📥 DOWNLOAD OPTIONS")
            Enhanced_Menu.print_menu_item(1, "Download Track", "Download individual tracks")
            Enhanced_Menu.print_menu_item(2, "Download Album", "Download complete albums")
            Enhanced_Menu.print_menu_item(3, "Download Playlist", "Download playlists")
            Enhanced_Menu.print_menu_item(4, "Download From Text File", "Batch download from file")
            Enhanced_Menu.print_menu_item(5, "Search & Download Song", "Search by song name")
            
            Enhanced_Menu.print_section("👤 PERSONAL CONTENT (Requires Login)")
            Enhanced_Menu.print_menu_item(6, "Download User Playlists", "Your personal playlists")
            Enhanced_Menu.print_menu_item(7, "Download Liked Songs", "Your liked songs")
            Enhanced_Menu.print_menu_item(8, "Download Saved Albums", "Your saved albums")
            
            # Tools Section
            Enhanced_Menu.print_section("🛠️ TOOLS & SETTINGS")
            Enhanced_Menu.print_menu_item(9, "Check/Install spotdl", "Verify installation")
            Enhanced_Menu.print_menu_item(10, "Show spotdl Help", "Command reference")
            Enhanced_Menu.print_menu_item(11, "Program Settings", "Configure preferences")
            
            # Help Section
            Enhanced_Menu.print_section("ℹ️ HELP & INFORMATION")
            Enhanced_Menu.print_menu_item(12, "Show Program Info", "About this program")
            
            # Exit Section
            Enhanced_Menu.print_section("🚪 EXIT")
            Enhanced_Menu.print_menu_item(13, "Exit Program", "Close the application")
            
            print(f"\n{Style.DIM}{'─' * 60}{Style.RESET_ALL}")
            
            # Display current settings
            Enhanced_Menu.print_status("Current Settings:", "info", "⚙️")
            
            settings = [
                ("Format", downloader._Spotify_Downloader__audio_format),
                ("Quality", downloader._Spotify_Downloader__audio_quality),
                ("Output", str(downloader._Spotify_Downloader__output_directory)),
            ]
            
            for setting_name, setting_value in settings:
                print(f"  {Fore.CYAN}{setting_name}:{Style.RESET_ALL} {Fore.YELLOW}{setting_value}{Style.RESET_ALL}")
            
            print(f"{Style.DIM}{'─' * 60}{Style.RESET_ALL}")
            
            # Get user choice
            choice = Enhanced_Menu.get_input("\nEnter your choice (1-13): ", "int", 1, 13)
            
            # Execute action
            action = actions.get(choice)
            if action:
                Enhanced_Menu.clear_screen()
                try:
                    # Execute the action
                    success = action()
                    
                    # If action returns False (failure), ask to retry
                    if success is False and choice not in [9, 10, 12, 13]:
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
            
            # Ask to continue (unless exiting)
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