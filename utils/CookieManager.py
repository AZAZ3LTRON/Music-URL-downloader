import shutil
import time
from pathlib import Path
import os
import platform
import ctypes
import subprocess
from typing import List, Optional, Dict, Any
import browser_cookie3
from colorama import init, Fore, Style
import requests  # moved import to top
import json

init(autoreset=True)

from .enhancedmenu import Enhanced_Menu  # assumed existing

COOKIE_DIRECTORY = r"cookies"
os.makedirs(COOKIE_DIRECTORY, exist_ok=True)

class CookieManager:
    """Manages cookies for authentication"""
    def __init__(self, config_path: Optional[Path] = None):
        self.cookie_directory = Path(COOKIE_DIRECTORY)
        self.cookie_directory.mkdir(exist_ok=True)
        self.current_cookie_file: Optional[Path] = None
        self.config_path = Path("config/spotify_downloader.json")
        self.use_auth = False
        
        # Load credentials from the config file
        self._client_id = None
        self._client_secret = None
        self._auth_token = None
        
        self.cookie_sources: Dict[str, Any] = {
            'chrome': browser_cookie3.chrome,
            'firefox': browser_cookie3.firefox,
            'edge': browser_cookie3.edge,
            'opera': browser_cookie3.opera,
            'opera_gx': browser_cookie3.opera_gx,
            'brave': browser_cookie3.brave,
            'safari': browser_cookie3.safari,
            'chromium': browser_cookie3.chromium
        }

        # For Linux fallback (not used yet, but kept for future expansion)
        self.linux_cookie_paths = {
            'chrome': '~/.config/google-chrome/Default/Cookies',
            'chromium': '~/.config/chromium/Default/Cookies',
            'firefox': '~/.mozilla/firefox/*.default-release/cookies.sqlite'
        }

        self.is_admin = self._check_admin()
        self._load_credentials()
        
    def _load_credentials(self):
        """Load Spotify credentials from the main config file."""
        if not self.config_path.exists():
            return
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self._client_id = config.get("client_id")
            self._client_secret = config.get("client_secret")
            self._auth_token = config.get("auth_token")
        except Exception as e:
            Enhanced_Menu.print_status(f"Failed to load credentials from config: {e}", "error")
            
    def set_credentials(self, client_id=None, client_secret=None, auth_token=None):
        """Set Spotify credentials (used to sync from downloader)."""
        self._client_id = client_id
        self._client_secret = client_secret
        self._auth_token = auth_token
    
    def save_credentials(self):
        """Write current credentials back to the main config file."""
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Load existing config to preserve other keys
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {}
            # Update only the Spotify keys
            config["client_id"] = self._client_id
            config["client_secret"] = self._client_secret
            config["auth_token"] = self._auth_token
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            Enhanced_Menu.print_status("Spotify credentials saved to config.", "success")
        except Exception as e:
            Enhanced_Menu.print_status(f"Failed to save credentials: {e}", "error")
            
    def clear_spotify_credentials(self):
        """Remove Spotify credentials from config and instance."""
        self._client_id = None
        self._client_secret = None
        self._auth_token = None
        # Remove keys from config file
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                config.pop("client_id", None)
                config.pop("client_secret", None)
                config.pop("auth_token", None)
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2)
                Enhanced_Menu.print_status("Spotify credentials cleared from config.", "success")
        except Exception as e:
            Enhanced_Menu.print_status(f"Failed to clear credentials: {e}", "error")
                     
    def _check_admin(self) -> bool:
        """Check if script is running with admin privileges on Windows"""
        if platform.system() == "Windows":
            try:
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            except Exception:
                return False
        return True
                
    def get_status(self):
        """Check available browser cookies and report status."""
        Enhanced_Menu.print_header("Checking available browser cookies....")

        if platform.system() == "Windows" and not self.is_admin:
            Enhanced_Menu.print_status("⚠️ Running without admin privileges on Windows", "warning")
            Enhanced_Menu.print_status("Some browsers may not be accessible", "info")

        available_browsers = []

        for browser, cookie_func in self.cookie_sources.items():
            try:
                # Convert generator to list to avoid exhaustion
                cookies = list(cookie_func(domain_name="music.youtube.com"))
                cookie_count = len(cookies)
                if cookie_count > 0:
                    available_browsers.append(browser)
                    Enhanced_Menu.print_status(f"✓ {browser}: Found {cookie_count} cookies", "success")
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
        """Extract cookies from specified browser and save to a file."""
        Enhanced_Menu.print_header(f"Extracting cookies from {browser_name}....")

        if browser_name not in self.cookie_sources:
            Enhanced_Menu.print_status("Browser not supported", "error")
            Enhanced_Menu.print_status(f"Available browsers: {', '.join(self.cookie_sources.keys())}", "info")
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
            cookie_ids = set()  # Track unique cookies by name+value prefix

            for domain in domains:
                try:
                    # Get cookies as a list to avoid generator exhaustion
                    cookies = list(self.cookie_sources[browser_name](domain_name=domain))
                    for cookie in cookies:
                        cookie_key = f"{cookie.name}:{cookie.value[:30]}"
                        if cookie_key not in cookie_ids:
                            cookie_ids.add(cookie_key)
                            all_cookies.append(cookie)
                    Enhanced_Menu.print_status(
                        f"Found {len(cookies)} cookies for {domain}",
                        "success" if cookies else "info"
                    )
                except PermissionError as e:
                    Enhanced_Menu.print_status(f"Permission denied for {domain}: Need admin rights", "error")
                    return self._handle_permission_error(browser_name)
                except Exception as e:
                    Enhanced_Menu.print_status(f"Couldn't get cookies for {domain}: {str(e)[:50]}", "error")

            if not all_cookies:
                Enhanced_Menu.print_status(f"No cookies found for YouTube Music in {browser_name}", "info")
                return None

            # Save cookies to file in Netscape format
            cookie_file = self.cookie_directory / f"{browser_name}_cookies.txt"
            with open(cookie_file, "w", encoding='utf-8') as f:
                f.write("# Netscape HTTP cookie file\n")
                f.write("# This file was generated by Music Downloader\n")
                for cookie in all_cookies:
                    # Use the domain exactly as provided by browser_cookie3
                    # (may already have a leading dot for domain-wide cookies)
                    domain = cookie.domain
                    domain_dot = "TRUE" if domain.startswith('.') else "FALSE"
                    path = cookie.path or '/'
                    secure = "TRUE" if cookie.secure else "FALSE"
                    expires = str(int(cookie.expires)) if cookie.expires else "0"
                    f.write(f"{domain}\t{domain_dot}\t{path}\t{secure}\t{expires}\t{cookie.name}\t{cookie.value}\n")

            Enhanced_Menu.print_status(f"Successfully extracted {len(all_cookies)} cookies to {cookie_file}", "success")
            Enhanced_Menu.print_status(f"Cookies saved to: {cookie_file}", "info")
            self.current_cookie_file = cookie_file
            return cookie_file

        except Exception as e:
            Enhanced_Menu.print_status(f"Failed to extract cookies: {str(e)}", "error")
            return self._handle_permission_error(browser_name)

    def _handle_permission_error(self, browser_name: str) -> Optional[Path]:
        """Handle permission errors by offering alternatives."""
        Enhanced_Menu.print_section("\n🔧 Cookie Extraction Failed")
        Enhanced_Menu.print_status("This usually happens because:", "info")
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
        """Guide user through manual cookie export and load the file."""
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
        """Load cookies from an existing file."""
        cookie_path = Path(cookie_file)

        # Try different paths
        if not cookie_path.exists():
            cookie_path = self.cookie_directory / cookie_file
        if not cookie_path.exists():
            cookie_path = Path(cookie_file)  # absolute path
        if not cookie_path.exists():
            Enhanced_Menu.print_status(f"Cookie file not found: {cookie_file}", "failure")
            return None

        try:
            # Validate file format (simple check)
            with open(cookie_path, 'r', encoding='utf-8') as f:
                content = f.read(200)
                if "Netscape" not in content and ".youtube.com" not in content:
                    Enhanced_Menu.print_status("Warning: Cookie file may not be in Netscape format", "error")
                    proceed = Enhanced_Menu.get_input("Continue anyway? (y/n): ", "yn", default=False)
                    if not proceed:
                        return None

            self.current_cookie_file = cookie_path
            Enhanced_Menu.print_status(f"Cookies loaded from: {cookie_path}", "info")
            return cookie_path
        except Exception as e:
            Enhanced_Menu.print_status(f"Failed to load cookies: {e}", "failure")
            return None

    def save_cookies(self, name: str = "cookies") -> Optional[Path]:
        """Save current cookie file to persistent storage with a warning."""
        if not self.current_cookie_file or not self.current_cookie_file.exists():
            Enhanced_Menu.print_status("No active cookie file to save", "error")
            return None

        # Security warning
        Enhanced_Menu.print_status(
            "⚠️  WARNING: Cookies will be stored in plain text. Protect this file.",
            "warning"
        )
        proceed = Enhanced_Menu.get_input("Proceed with saving? (y/n): ", "yn", default=True)
        if not proceed:
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
        """List all saved cookie files."""
        cookie_files = list(self.cookie_directory.glob("*.txt"))
        if not cookie_files:
            Enhanced_Menu.print_status("No saved cookie files found.", "error")
            return []

        Enhanced_Menu.print_status("Saved cookie files:", "info")
        for i, cookie_file in enumerate(cookie_files, 1):
            file_size = cookie_file.stat().st_size
            mod_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(cookie_file.stat().st_mtime))
            print(f"{Fore.YELLOW}[{i}]{Style.RESET_ALL} {Fore.CYAN}{cookie_file.name:30}{Style.RESET_ALL}")
            print(f"     Size: {file_size} bytes | Modified: {mod_time}")
        return cookie_files

    def clear_cookies(self):
        """Delete all cookie files from the main cookie directory."""
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

    def test_cookies(self, url="https://music.youtube.com/watch?v=215T8NF93kw"):
        """Test if cookies work by trying to access a URL."""
        if not self.current_cookie_file:
            Enhanced_Menu.print_status("No active cookie file to test", "error")
            return False

        try:
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
        
    def get_auth_key(self) -> Optional[str]:
        """
        Execute the curl command to obtain a Spotify access token using client credentials.
        Returns the access token string or None on failure.
        """
        if not self._client_id or not self._client_secret:
            Enhanced_Menu.print_status(
                "Client ID and Secret are required. Please run spotify_auth first.",
                "error"
            )
            return None

        # Check if curl is available
        if not shutil.which("curl"):
            Enhanced_Menu.print_status("curl not found in PATH. Please install curl.", "error")
            return None

        # Build the command (Windows line continuation characters removed)
        command = [
            "curl", "-X", "POST",
            "https://accounts.spotify.com/api/token",
            "-H", "Content-Type: application/x-www-form-urlencoded",
            "-d", f"grant_type=client_credentials&client_id={self._client_id}&client_secret={self._client_secret}"
        ]

        Enhanced_Menu.print_status("Requesting access token from Spotify...", "info")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=30
            )

            if result.returncode != 0:
                Enhanced_Menu.print_status(f"curl failed with error:\n{result.stderr}", "error")
                return None

            # Parse JSON response
            try:
                response = json.loads(result.stdout)
            except json.JSONDecodeError:
                Enhanced_Menu.print_status("Failed to parse JSON response from Spotify.", "error")
                Enhanced_Menu.print_status(f"Raw output: {result.stdout[:200]}", "debug")
                return None

            # Extract access token
            access_token = response.get("access_token")
            if access_token:
                self._auth_token = access_token
                Enhanced_Menu.print_status("Access token obtained successfully.", "success")
                return access_token
            else:
                error_msg = response.get("error", "Unknown error")
                error_desc = response.get("error_description", "")
                Enhanced_Menu.print_status(f"Spotify error: {error_msg} {error_desc}", "error")
                return None

        except subprocess.TimeoutExpired:
            Enhanced_Menu.print_status("curl command timed out after 30 seconds.", "error")
            return None
        except Exception as e:
            Enhanced_Menu.print_status(f"Unexpected error while obtaining auth key: {e}", "error")
            return None        
           
    def spotify_auth(self):
        """Use spotdl's built‑in authentication with automatic token fetching."""
        Enhanced_Menu.print_header("\n🎵 Starting Spotify authentication...")

        # Get Client ID (with instructions)
        while True:
            client_id = Enhanced_Menu.get_input(
                "Enter the Client ID of your Spotify Web API (or 'get' for instructions): ",
                "str"
            )
            if not client_id:
                self._client_id = None
                Enhanced_Menu.print_status("No Client ID provided, program may fail", "warning")
                break
            if client_id.lower() == 'get':
                print(" 1. Go to Spotify for Developers")
                print(" 2. Go to the app you created (make sure it's a Web API app)")
                print(" 3. Copy the Client ID from the app dashboard")
                continue
            self._client_id = client_id
            break

        # Get Client Secret
        while True:
            client_secret = Enhanced_Menu.get_input(
                "Enter the Client Secret of your Spotify Web API (or 'get' for instructions): ",
                "str"
            )
            if not client_secret:
                self._client_secret = None
                Enhanced_Menu.print_status("No Client Secret provided, program may fail", "warning")
                break
            if client_secret.lower() == 'get':
                print(" 1. Go to Spotify for Developers")
                print(" 2. Go to the app you created")
                print(" 3. Click 'Show Client Secret' and copy the text")
                continue
            self._client_secret = client_secret
            break

        # Auto‑fetch token if both credentials are present
        if self._client_id and self._client_secret:
            Enhanced_Menu.print_status("Attempting to fetch access token using client credentials...", "info")
            token = self.get_auth_key()          # sets self._auth_token and returns it
            if token:
                Enhanced_Menu.print_status("Access token obtained successfully.", "success")
            else:
                Enhanced_Menu.print_status("Failed to obtain access token automatically.", "error")
                # Offer manual token entry
                manual = Enhanced_Menu.get_input(
                    "Would you like to enter an access token manually? (y/n): ",
                    "yn",
                    default=False
                )
                if manual:
                    while True:
                        auth_token = Enhanced_Menu.get_input(
                            "Enter the Auth Token (or 'get' for instructions): ",
                            "str"
                        )
                        if not auth_token:
                            self._auth_token = None
                            Enhanced_Menu.print_status("No Auth Token provided, continuing without token.", "warning")
                            break
                        if auth_token.lower() == 'get':
                            print(" 1. Go to this link: https://developer.spotify.com/documentation/web-api/tutorials/getting-started")
                            print(" 2. Scroll down to the area where it says 'Request an access token'")
                            print(" 3. Follow the instructions given to acquire your access token.")
                            print(" Note: The auth token/access token only lasts for an hour, so best to renew consistently")
                            continue
                        self._auth_token = auth_token
                        break
        else:
            # Credentials missing; optionally ask for manual token
            Enhanced_Menu.print_status("Client ID and/or Secret not provided. Automatic token fetch skipped.", "info")
            manual = Enhanced_Menu.get_input(
                "Would you like to enter an access token manually? (y/n): ",
                "yn",
                default=False
            )
            if manual:
                while True:
                    auth_token = Enhanced_Menu.get_input(
                        "Enter the Auth Token (or 'get' for instructions): ",
                        "str"
                    )
                    if not auth_token:
                        self._auth_token = None
                        Enhanced_Menu.print_status("No Auth Token provided, continuing without token.", "warning")
                        break
                    if auth_token.lower() == 'get':
                        print(" 1. Go to this link: https://developer.spotify.com/documentation/web-api/tutorials/getting-started")
                        print(" 2. Scroll down to the area where it says 'Request an access token'")
                        print(" 3. Follow the instructions given to acquire your access token.")
                        print(" Note: The auth token/access token only lasts for an hour, so best to renew consistently")
                        continue
                    self._auth_token = auth_token
                    break

        # Check if spotdl is installed
        if not shutil.which("spotdl"):
            Enhanced_Menu.print_status("spotdl not found in PATH. Please install it first.", "error")
            return False

        # Build base command
        command = ["spotdl", "download", "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT", ]
        if self._client_id:
            command += ["--client-id", self._client_id]
        if self._client_secret:
            command += ["--client-secret", self._client_secret]
        if self._auth_token:
            command += ["--auth-token", self._auth_token]

        # Test authentication with a dry run
        try:
            process = subprocess.run(
                command,
                capture_output=True,
                text=True
            )
            if process.returncode == 0:
                Enhanced_Menu.print_status("Authentication successful!", "success")
                self.save_credentials()
                return True
            else:
                Enhanced_Menu.print_status("Authentication failed", "error")
                self.save_credentials()
                if process.stderr:
                    print(process.stderr)
                return False
        except Exception as e:
            Enhanced_Menu.print_status(f"Error during authentication: {e}", "error")
            return False

    def ytdlp_auth(self):
        """Use yt‑dlp's built‑in authentication."""
        Enhanced_Menu.print_header("\n🎵 Starting YouTube Music authentication...")

        if not self.current_cookie_file or not self.current_cookie_file.exists():
            Enhanced_Menu.print_status("No active cookie file. Please load cookies first.", "error")
            return False

        username = Enhanced_Menu.get_input("Enter your account username: ")
        password = Enhanced_Menu.get_input("Enter your account password: ")

        if not shutil.which("yt-dlp"):
            Enhanced_Menu.print_status("yt-dlp not found in PATH. Please install it first.", "error")
            return False

        try:
            # Using --cookies and --username/--password together; password is visible in process list.
            # For better security, consider using --netrc or environment variables.
            process = subprocess.run(
                [
                    "yt-dlp",
                    "--netrc",
                    "--cookies", str(self.current_cookie_file),
                    "--username", username,
                    "--password", password,
                    "--simulate",  # don't download anything
                    "https://music.youtube.com/"
                ],
                capture_output=True,
                text=True
            )
            if process.returncode == 0:
                Enhanced_Menu.print_status("Authentication successful!", "success")
                return True
            else:
                Enhanced_Menu.print_status("Authentication failed", "error")
                if process.stderr:
                    print(process.stderr)
                return False
        except Exception as e:
            Enhanced_Menu.print_status(f"Error during authentication: {e}", "error")
            return False

    def get_arguments_ytdlp(self) -> List[str]:
        """Get yt‑dlp cookie arguments if cookies are available."""
        if self.current_cookie_file and self.current_cookie_file.exists():
            return ["--cookies", str(self.current_cookie_file)]
        return []

    def get_arguments_spotdl(self) -> List[str]:
        """Get spotdl cookie arguments if cookies are available."""
        if self.current_cookie_file and self.current_cookie_file.exists():
            return ["--cookie-file", str(self.current_cookie_file)]
        return []

    def __del__(self):
        """Clear reference to current cookie file (does not delete the file)."""
        self.current_cookie_file = None

    def interactive_menu(self):
        """Interactive cookie setup menu."""
        while True:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("🍪 Cookie Manager Menu", "A simple program to help manage cookies")

            Enhanced_Menu.print_section("Options:")
            Enhanced_Menu.print_menu_item(1, "Check available browser cookies")
            Enhanced_Menu.print_menu_item(2, "Extract cookies from browser")
            Enhanced_Menu.print_menu_item(3, "List saved cookie files")
            Enhanced_Menu.print_menu_item(4, "Load cookies from file")
            Enhanced_Menu.print_menu_item(5, "Save current cookies")
            Enhanced_Menu.print_menu_item(6, "Clear all cookie files")
            Enhanced_Menu.print_menu_item(7, "Show current cookie status")
            Enhanced_Menu.print_menu_item(8, "Use SpotDL Authentication")
            Enhanced_Menu.print_menu_item(9, "Use YT-DLP Authentication")
            Enhanced_Menu.print_menu_item(10, "Test current cookies")
            Enhanced_Menu.print_menu_item(11, "Return to main menu")

            Enhanced_Menu.print_section("STATUS")
            if self.current_cookie_file:
                Enhanced_Menu.print_status(f"Active cookie file: {self.current_cookie_file}", "success")
            else:
                Enhanced_Menu.print_status("No active cookie file", "error")

            choice = input("Select option (1-11): ").strip()

            if choice == "1":
                self.get_status()
                input("\nPress Enter to continue... ")
            elif choice == "2":
                print(f"\n====={Fore.CYAN}Available Browsers:{Style.RESET_ALL}======")
                browsers = list(self.cookie_sources.keys())
                for i, browser in enumerate(browsers, 1):
                    Enhanced_Menu.print_color(f"{i}. {browser}")
                browser_choice = Enhanced_Menu.get_input("\nSelect browser (name or number): ", "str").strip()
                if browser_choice.isdigit():
                    num = int(browser_choice)
                    if 1 <= num <= len(browsers):
                        browser_name = browsers[num - 1]
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
                input("\nPress Enter to continue...")
            elif choice == "3":
                cookie_files = self.list_cookies()
                if cookie_files:
                    load_choice = Enhanced_Menu.get_input("\nEnter number to load cookie file (or press Enter to skip): ", "str")
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
                    Enhanced_Menu.print_status("No active cookies to save", "info")
                input("\nPress Enter to continue...")
            elif choice == "6":
                self.clear_cookies()
                input("\nPress Enter to continue...")
            elif choice == "7":
                status = self.get_status()
                if self.current_cookie_file:
                    Enhanced_Menu.print_status(f"Active cookie file: {self.current_cookie_file.name}", "success")
                else:
                    Enhanced_Menu.print_status("No active cookie file", "info")
                input("\nPress Enter to continue...")
            elif choice == "8":
                self.spotify_auth()
                input("\nPress Enter to continue...")
            elif choice == "9":
                self.ytdlp_auth()
                input("\nPress Enter to continue...")
            elif choice == "10":
                self.test_cookies()
                input("\nPress Enter to continue...")
            elif choice == "11":
                break
            else:
                Enhanced_Menu.print_status("Invalid choice", "info")
                input("\nPress Enter to continue...")