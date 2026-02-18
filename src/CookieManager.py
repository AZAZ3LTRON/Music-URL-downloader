import shutil
import time
import os
from pathlib import Path
from urllib.parse import urlparse
import platform
import ctypes
import subprocess
from typing import List, Optional
import browser_cookie3
from colorama import init, Fore, Back, Style
init(autoreset=True)

from EnhancedMenu import Enhanced_Menu
COOKIE_DIRECTORY = r"cookies" # Subject to change for linux
os.makedirs(COOKIE_DIRECTORY, exist_ok=True)

class CookieManager:
    """Manages cookies for authentication"""
    def __init__(self):
        self.cookie_directory = Path(COOKIE_DIRECTORY)
        self.cookie_directory.mkdir(exist_ok=True)
        self.current_cookie_file = None
        self.use_auth = False
        self.cookie_sources = {
            'chrome': browser_cookie3.chrome,
            'firefox': browser_cookie3.firefox,
            'edge': browser_cookie3.edge,
            'opera': browser_cookie3.opera,
            'opera_gx': browser_cookie3.opera_gx,
            'brave': browser_cookie3.brave,
            'safari': browser_cookie3.safari,
            'chromium': browser_cookie3.chromium
        }

        # For Linux
        if platform.system() == "Linux":
            self.linux_cookie_paths = {
            'chrome': '~/.config/google-chrome/Default/Cookies',
            'chromium': '~/.config/chromium/Default/Cookies',
            'firefox': '~/.mozilla/firefox/*.default-release/cookies.sqlite' 
            } # Add more in case
            
        # Detect of admin is running (Windows Only)
        self.is_admin = self._check_admin()
        
    def _check_admin(self) -> bool:
        """Check if script is running with admin privileges on Windows"""
        if platform.system() == "Windows":
            try:
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            except:
                return False
        return True
        
    def get_status(self):
        """Get cookie status"""
        Enhanced_Menu.print_header("Checking available browser cookies....")
        
        if platform.system() == "Windows" and not self.is_admin:
            Enhanced_Menu.print_status("⚠️ Running without admin privileges on Windows", "warning")
            Enhanced_Menu.print_status("Some browsers may not be accessible", "info")
        
        available_browsers = []
        
        for browser, cookie_func in self.cookie_sources.items():
            try:
                cookies = cookie_func(domain_name="music.youtube.com")
                if cookies:
                    cookie_count = len(list(cookies))
                    if cookie_count > 0:
                        available_browsers.append(browser)
                        Enhanced_Menu.print_status(f"✓ {browser}: Found {cookie_count} cookies", "success")
                    else:
                        Enhanced_Menu.print_status(f"• {browser}: No cookies found", "info")
                else:
                    Enhanced_Menu.print_status(f"• {browser}: No cookies found", "info")
                    
            except PermissionError as e:
                if "admin" in str(e).lower():
                    Enhanced_Menu.print_status(f"⚠️ {browser}: Need admin rights", "warning")
                else:
                    Enhanced_Menu.print_status(f"⚠️ {browser}: Permission denied", "warning")
                    
            except Exception as e:
                Enhanced_Menu.print_status(f"⚠️ {browser}: {str(e)[:50]}", "error")
        
        if available_browsers:
            Enhanced_Menu.print_status(f"✅ Available cookies from: {', '.join(available_browsers)}", "success")
            return True
        else:
            Enhanced_Menu.print_status("❌ No browser cookies found for YouTube Music", "error")
            Enhanced_Menu.print_status("Try:\n1. Run as Administrator\n2. Manual export\n3. Use yt-dlp auth", "info")
            return False
          
    def extract_cookies(self, browser_name: str = 'brave') -> Optional[Path]:
        """Extract cookies from your browser of choice & saves to files"""
        Enhanced_Menu.print_header(f"Extracting cookies from {browser_name}....")

        if browser_name not in self.cookie_sources:
            Enhanced_Menu.print_status("Browser not supported", "error")
            Enhanced_Menu.print_status(f"Available browsers are: {', '.join(self.cookie_sources.keys())}", "info")
            return None
        
        if platform.system() == "Windows" and not self.is_admin:
            Enhanced_Menu.print_status("⚠️  Warning: Running without admin privileges", "warning")
            Enhanced_Menu.print_status("Cookie extraction may fail. Consider:", "info")
            Enhanced_Menu.print_status("1. Run as Administrator", "info")
            Enhanced_Menu.print_status("2. Use manual export (option in menu)", "info")
            
            proceed = Enhanced_Menu.get_input("Continue anyway? (y/n): ", "yn", default=False)
            if not proceed:
                return None            
        
        try:
            domains = ['music.youtube.com', 'youtube.com', 'open.spotify.com']
            all_cookies = []
            cookie_names = set() # Track unique cookeis
            
            for domain in domains:
                try:
                    cookies = self.cookie_sources[browser_name](domain_name=domain)
                    for cookie in cookies:
                        cookie_key = f"{cookie.name}:{cookie.value[:30]}"
                        if cookie_key not in cookie_names:
                            cookie_names.add(cookie_key)
                            all_cookies.append(cookie)
                    
                    cookie_count = len(list(cookies))
                    Enhanced_Menu.print_status(f"Found {len(list(cookies))} cookies for {domain}", "success" if cookie_count > 0 else "info")
                
                except PermissionError as e:
                    Enhanced_Menu.print_status(f"Permission denied for {domain}: Need admin rights", "error")
                    # Offer alternative
                    return self._handle_permission_error(browser_name)
                    
                except Exception as e:
                    Enhanced_Menu.print_status(f"Couldn't get cookies for {domain}: {str(e)[:50]}", "error")

            if not all_cookies:
                Enhanced_Menu.print_status(f"No cookies found for Youtube Music in {browser_name}", "info")
                return None
            
            # Save cookies to file
            cookie_file = self.cookie_directory / f"{browser_name}_cookies.txt"
            with open(cookie_file, "w", encoding='utf-8') as f:
                f.write("# Netscape HTTP cookie file\n")
                f.write("# This file was generated by Music Downloader\n")
                for cookie in all_cookies:
                    # Handle domain properly
                    domain = cookie.domain
                    if domain.startswith('.'):
                        domain_dot = "TRUE"
                    else:
                        domain_dot = "FALSE"
                        if not domain.startswith('.'):
                            domain = '.' + domain
                            
                    path = cookie.path or '/'
                    secure = "TRUE" if cookie.secure else "FALSE"
                    expires = str(int(cookie.expires)) if cookie.expires else "0"
                    
                    f.write(f"{domain}\t")
                    f.write(f"{domain_dot}\t")
                    f.write(f"{path}\t")
                    f.write(f"{secure}\t")
                    f.write(f"{expires}\t")
                    f.write(f"{cookie.name}\t")
                    f.write(f"{cookie.value}\n")                   
            
            Enhanced_Menu.print_status(f"Successfully extracted {len(all_cookies)} cookies to {cookie_file}", "success")
            Enhanced_Menu.print_status(f"Cookies saved to: {cookie_file}", "info")
            self.current_cookie_file = cookie_file
            return cookie_file
        
        except Exception as e:
            Enhanced_Menu.print_status(f"Failed to extract cookies: {str(e)}", "error")
            return self._handle_permission_error(browser_name)
    
    # Handles permission errors
    def _handle_permission_error(self, browser_name: str) -> Optional[Path]:
        """Handle permission errors by offering alternatives"""
        Enhanced_Menu.print_section("\n🔧 Cookie Extraction Failed")
        Enhanced_Menu.print_status(
            "This usually happens because:", 
            "info"
        )
        Enhanced_Menu.print_status("• Browser is running in protected mode", "info")
        Enhanced_Menu.print_status("• Need administrator privileges", "info")
        Enhanced_Menu.print_status("• Browser cookies are encrypted", "info")
        
        print(f"\n{Fore.CYAN}Alternative solutions:{Style.RESET_ALL}")
        print("1. Run this program as Administrator")
        print("2. Use manual cookie export:")
        print("   • Install 'Get cookies.txt' extension for Chrome/Edge")
        print("   • Export cookies from music.youtube.com")
        print("   • Load the exported file using option 4")
        print("3. Use yt-dlp authentication (option 9)")
        print("4. Try a different browser")
        
        choice = Enhanced_Menu.get_input(
            "\nTry manual export now? (y/n): ", 
            "yn", 
            default=True
        )
        
        if choice:
            return self.manual_cookie_instructions()
        return None

    def manual_cookie_instructions(self) -> Optional[Path]:
        """Guide user through manual cookie export"""
        Enhanced_Menu.print_section("\n📋 Manual Cookie Export Instructions")
        
        print(f"\n{Fore.YELLOW}For Chrome/Edge/Brave:{Style.RESET_ALL}")
        print("1. Install 'Get cookies.txt' extension:")
        print("   • Chrome: https://chrome.google.com/webstore/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid")
        print("   • Edge: Get from Chrome Web Store")
        print("2. Go to https://music.youtube.com")
        print("3. Make sure you're logged in")
        print("4. Click the extension icon → 'Export'")
        print("5. Save the file to the 'cookies' folder")
        
        print(f"\n{Fore.YELLOW}For Firefox:{Style.RESET_ALL}")
        print("1. Install 'cookies.txt' extension")
        print("2. Go to https://music.youtube.com")
        print("3. Click extension → 'Export Cookies'")
        
        cookie_path = Enhanced_Menu.get_input(
            "\nEnter path to exported cookie file (or press Enter to skip): ",
            "str"
        )
        
        if cookie_path:
            return self.load_cookies(cookie_path)
        return None

    def load_cookies(self, cookie_file: str) -> Optional[Path]:
        """Load cookies from an existing file"""
        cookie_path = Path(cookie_file)
        
        # Ttry different paths
        if not cookie_path.exists():
            cookie_path = self.cookie_directory / cookie_file
            if not cookie_path.exists():
                cookie_path = Path(cookie_file)
                if not cookie_path.exists():
                    Enhanced_Menu.print_status(f"Cookie file not found: {cookie_file}", "failure")
                    return None
        
        try:
            # Validate file format
            with open(cookie_path, 'r', encoding='utf-8') as f:
                content = f.read(200)
                if "Netscape" not in content and ".youtube.com" not in content:
                    Enhanced_Menu.print_status(f"Warning: Cookie file may not be in Netscape format", "error")
                    proceed = Enhanced_Menu.get_input("Continue anyway? (y/n):- ", "yn", default=False)
                    if not proceed:
                        return None
                    
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
    
    def test_cookies(self, url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"):
        """Test if cookies work by trying to access a URL"""
        if not self.current_cookie_file:
            Enhanced_Menu.print_status("No active cookie file to test", "error")
            return False
        
        try:
            import requests
            
            # Convert Netscape cookies to requests format
            session = requests.Session()
            
            with open(self.current_cookie_file, 'r') as f:
                for line in f:
                    if line.startswith('#') or not line.strip():
                        continue
                    parts = line.strip().split('\t')
                    if len(parts) >= 7:
                        session.cookies.set(
                            name=parts[5],
                            value=parts[6],
                            domain=parts[0],
                            path=parts[2]
                        )
            
            # Test the cookies
            response = session.get(url, timeout=10)
            if response.status_code == 200:
                Enhanced_Menu.print_status("✅ Cookies work! Successfully accessed URL", "success")
                return True
            else:
                Enhanced_Menu.print_status(f"❌ Cookies may not work. Status code: {response.status_code}", "error")
                return False
                
        except Exception as e:
            Enhanced_Menu.print_status(f"Error testing cookies: {e}", "error")
            return False

    def spotify_auth(self):
        """ Use spotdl's built in authentication"""
        Enhanced_Menu.print_header("\n🎵 Starting Spotify authentication...")
        print("Expect a browser window to pop up. Log into Spotify there")
        try:
            process = subprocess.run(
                ["spotdl", "--user-auth"],
                capture_output=True,
                text = True
            )

            if process.returncode == 0:
                print("Authentication successful!")
                
                # SpotDl saves auth token internally, no need for cookie file
                self.current_cookie_file = None
                self.use_auth = True
                return True
            else:
                print("Authentication Failed")
                return False
        
        except Exception as e:
            print(f"Error during authentication {e}")
            return False
        
    def ytdlp_auth(self):
        """Use yt-dlp's built in authentication"""
        Enhanced_Menu.print_header("\n🎵 Starting Youtube Music authentication...")
        username = Enhanced_Menu.get_input("Enter your account username:- ") # Get User Name
        password = Enhanced_Menu.get_input("Enter your account password:- ") # Get User password

        try:
            process = subprocess.run(["yt-dlp",
                                    "-v",
                                    "--cookies", self.current_cookie_file,
                                    "--username", username,
                                    "--password", password],
                                    capture_output=True,
                                    text=True)
            
            if process.returncode == 0:
                print("Authentication successful")
            else:
                print("Error occured")
                return False
        except Exception as e:
            print(f"Error occured: {e}")
            return False
    
    # Gets cookie arguments for yt-dlp
    def get_arguments_ytdlp(self) -> List[str]:
        """Get yt-dlp cookie arguments if cookies are available"""
        if self.current_cookie_file and self.current_cookie_file.exists():
            return ["--cookies", str(self.current_cookie_file)]
        return []
    
    def get_arguments_spotdl(self) -> List[str]:
        """Get spotdl cookie arguments if cookies are available"""
        if self.current_cookie_file and self.current_cookie_file.exists():
            return ["--cookie-file", str(self.current_cookie_file)]
        return []

    def __del__(self):
        """Doesnt actually delete files, just clear references"""
        self.current_cookie_file = None
        
    def interactive_menu(self):
        """Interactive cookie setup menu"""
        while True:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("🍪 Cookie Manager Menu", "A simple program to help manages cookies ")
            
            Enhanced_Menu.print_section("Options:- ")
            Enhanced_Menu.print_menu_item(1, "Check available browser for cookies")
            Enhanced_Menu.print_menu_item(2, "Extract cookies from browser")
            Enhanced_Menu.print_menu_item(3, "List saved cookie files")
            Enhanced_Menu.print_menu_item(4, "Load cookies from file")
            Enhanced_Menu.print_menu_item(5, "Save current cookies")
            Enhanced_Menu.print_menu_item(6, "Clear all cookie files")
            Enhanced_Menu.print_menu_item(7, "Show current cookie status")
            Enhanced_Menu.print_menu_item(8, "Use SpotDL Authentication")
            Enhanced_Menu.print_menu_item(9, "Use YT-DLP Authentication")
            Enhanced_Menu.print_menu_item(10, "Return to main menu")
            Enhanced_Menu.print_section("STATUS")
            if self.current_cookie_file:
                Enhanced_Menu.print_status(f"Your active cookie files are: {self.current_cookie_file}", "success")
            else:
                Enhanced_Menu.print_status("You have no cookie files", "error")
            choice = input("Select option (1-10): ").strip()
            
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
                self.spotify_auth()
            
            elif choice == "9":
                self.ytdlp_auth()
                
            elif choice == "10":
                break
            
            else:
                Enhanced_Menu.print_status("Invalid choice", "info")
                input("\nPress Enter to continue...")
