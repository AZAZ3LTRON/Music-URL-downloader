import sys
import subprocess
import shutil
import io
from PIL import Image
import requests
from urllib.request import urlopen
from colorama import init, Fore, Style

init(autoreset=True)

from .EnhancedMenu import Enhanced_Menu

class DownloaderUtils:    
    @staticmethod
    def check_ffmpeg() -> bool:
        """Check if ffmpeg is installed"""
        print(f"\n{Fore.CYAN}Checking for FFmpeg...{Style.RESET_ALL}")
        
        # Check with basic shutil to find the file on PATH
        if shutil.which("ffmpeg"):
            print(f"{Fore.GREEN}✓{Style.RESET_ALL} FFmpeg is installed")
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
                    # Extract first line of version info
                    version = result.stdout.strip().split('\n')[0]
                    print(f"  {Fore.YELLOW}{version[:60]}...{Style.RESET_ALL}")
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
                print(f"{Fore.YELLOW}⚠{Style.RESET_ALL} FFmpeg found but version check failed")
                return True
        else:
            print(f"{Fore.RED}✗{Style.RESET_ALL} FFmpeg is not installed")
            print(f"  {Fore.YELLOW}Note:{Style.RESET_ALL} FFmpeg is recommended for audio conversion")
            return False

    @staticmethod
    def check_ytdlp() -> bool:
        """Check if yt-dlp is installed"""
        print(f"\n{Fore.CYAN}Checking for yt-dlp...{Style.RESET_ALL}")
        
        if shutil.which("yt-dlp"):
            print(f"{Fore.GREEN}✓{Style.RESET_ALL} yt-dlp is installed")
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
                    print(f"  Version: {Fore.YELLOW}{version}{Style.RESET_ALL}")
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
                print(f"{Fore.YELLOW}⚠{Style.RESET_ALL} Could not determine yt-dlp version")
                return True
        else:
            print(f"{Fore.RED}✗{Style.RESET_ALL} yt-dlp is not installed")
            return False

    @staticmethod
    def check_spotdl() -> bool:
        """ Checks if spotdl is installed on user's device"""
        print(f"\n {Fore.CYAN} Checking for spotdl...")
        
        if shutil.which("spotdl"):
            print(f"{Fore.GREEN}✓{Style.RESET_ALL} spotdl is installed")
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
                    print(f"  Version: {Fore.YELLOW}{version}{Style.RESET_ALL}")
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
                print(f"{Fore.YELLOW}⚠{Style.RESET_ALL} Could not determine spotdl version")
                return True
        else:
            print(f"{Fore.RED}✗{Style.RESET_ALL} spotdl is not installed")
            return False

    @staticmethod
    def show_ytdlp_help():
        """Display yt-dlp help"""
        try:
            # First check if yt-dlp is installed
            if not DownloaderUtils.check_ytdlp():
                print(f"{Fore.RED}yt-dlp is not installed. Please install it first.{Style.RESET_ALL}")
                input("\nPress Enter to continue...")
                return False
                
            result = subprocess.run(
                ["yt-dlp", "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=30
            )
            print("\n" + "=" * 50)
            # Check if Enhanced_Menu is available
            try:
                Enhanced_Menu.print_header("YT-DLP HELP")
            except:
                print(f"{Fore.CYAN}YT-DLP HELP{Style.RESET_ALL}")
            print("=" * 50)
            print(result.stdout[:1000])
            print("\n... (output truncated, use 'yt-dlp --help' for full help)")
        except subprocess.CalledProcessError as e:
            try:
                Enhanced_Menu.print_status(f"Could not get yt-dlp help: {e}", "error")
            except:
                print(f"{Fore.RED}Could not get yt-dlp help: {e}{Style.RESET_ALL}")
            return False
        except FileNotFoundError:
            print(f"{Fore.RED}yt-dlp not found. Please install it first.{Style.RESET_ALL}")
            return False
        except Exception as e:
            print(f"{Fore.RED}Unexpected error: {e}{Style.RESET_ALL}")
            return False
            
        input("\nPress Enter to continue...")
        return True
    
    @staticmethod
    def show_spotdl_help():
        """Display spotdl help menu"""
        try:
            # First check if yt-dlp is installed
            if not DownloaderUtils.check_spotdl():
                print(f"{Fore.RED}spotdl is not installed. Please install it first.{Style.RESET_ALL}")
                input("\nPress Enter to continue...")
                return False
                
            result = subprocess.run(
                ["spotdl", "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=30
            )
            print("\n" + "=" * 50)
            # Check if Enhanced_Menu is available
            try:
                Enhanced_Menu.print_header("SPOTDL HELP")
            except:
                print(f"{Fore.CYAN}SPOTDL HELP{Style.RESET_ALL}")
            print("=" * 50)
            print(result.stdout[:1000])
            print("\n... (output truncated, use 'spotdl --help' for full help)")
        except subprocess.CalledProcessError as e:
            try:
                Enhanced_Menu.print_status(f"Could not get spotdl help: {e}", "error")
            except:
                print(f"{Fore.RED}Could not get spotdl help: {e}{Style.RESET_ALL}")
            return False
        except FileNotFoundError:
            print(f"{Fore.RED}spotdl not found. Please install it first.{Style.RESET_ALL}")
            return False
        except Exception as e:
            print(f"{Fore.RED}Unexpected error: {e}{Style.RESET_ALL}")
            return False
            
        input("\nPress Enter to continue...")
        return True       
    
    
    @staticmethod
    def check_dependencies():
        """Check for missing dependencies"""
        try:
            Enhanced_Menu.print_header("Checking for Missing Dependencies")
        except:
            print(f"\n{Fore.CYAN}Checking for Missing Dependencies{Style.RESET_ALL}\n")
            
        missing_packages = []
        installed_packages = []
        
        # List of packages to check
        packages_to_check = [
            ('browser_cookie3', 'browser-cookie3'),
            ('colorama', 'colorama'),
            ('tqdm', 'tqdm'),
            ('yt_dlp', 'yt-dlp'),
            ('spotdl', 'spotdl')
        ]
        
        for import_name, package_name in packages_to_check:
            try:
                __import__(import_name.replace('-', '_'))
                installed_packages.append(package_name)
                print(f"{Fore.GREEN}✓{Style.RESET_ALL} {package_name}")
            except ImportError:
                missing_packages.append(package_name)
                print(f"{Fore.RED}✗{Style.RESET_ALL} {package_name}")
        
        if missing_packages:
            print(f"\n{Fore.YELLOW}Missing packages:{Style.RESET_ALL} {', '.join(missing_packages)}")
            print(f"{Fore.CYAN}Install with:{Style.RESET_ALL} pip install " + " ".join(missing_packages))
            input("\nPress Enter to continue...")
            return False
        else:
            print(f"\n{Fore.GREEN}All dependencies satisfied!{Style.RESET_ALL}")
            input("\nPress Enter to continue...")
            return True

    @staticmethod
    def setup_dependencies():
        """Automatically install required libraries & dependencies"""
        print(f"\n{Fore.CYAN}Setting up dependencies...{Style.RESET_ALL}")
        
        dependencies = {
            'yt-dlp': 'yt-dlp',
            'browser_cookie3': 'browser-cookie3',
            'tqdm': 'tqdm',
            'colorama': 'colorama',
        }
        
        success_count = 0
        fail_count = 0
        
        for package_name, pip_name in dependencies.items():
            # Check if already installed
            try:
                if package_name == 'yt-dlp':
                    __import__('yt_dlp')
                elif package_name == 'browser_cookie3':
                    __import__('browser_cookie3')
                else:
                    __import__(package_name)
                print(f"{Fore.GREEN}✓{Style.RESET_ALL} {pip_name} already installed")
                success_count += 1
                continue
            except ImportError:
                pass
                
            # Install if not installed
            print(f"{Fore.YELLOW}Installing {pip_name}...{Style.RESET_ALL}")
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", pip_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    print(f"{Fore.GREEN}✓{Style.RESET_ALL} {pip_name} installed successfully")
                    success_count += 1
                else:
                    print(f"{Fore.RED}✗{Style.RESET_ALL} Failed to install {pip_name}")
                    print(f"  Error: {result.stderr[:100]}")
                    fail_count += 1
            except subprocess.TimeoutExpired:
                print(f"{Fore.RED}✗{Style.RESET_ALL} Installation timeout for {pip_name}")
                fail_count += 1
            except Exception as e:
                print(f"{Fore.RED}✗{Style.RESET_ALL} Error installing {pip_name}: {e}")
                fail_count += 1
        
        print("-" * 40)
        print(f"Installed: {Fore.GREEN}{success_count}{Style.RESET_ALL}, Failed: {Fore.RED}{fail_count}{Style.RESET_ALL}")
        
        if fail_count > 0:
            print(f"\n{Fore.YELLOW}Some packages failed to install. You may need to install them manually.{Style.RESET_ALL}")
        
        return fail_count == 0

    @staticmethod
    def setup_spotdl():
        print(f"{Fore.YELLOW} Installing Spotdl (Special)... {Style.RESET_ALL}")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "git+https://github.com/TzurSoffer/spotify-downloader"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                print(f"{Fore.GREEN}✓{Style.RESET_ALL} spotdl installed successfully")
            else:
                print(f"{Fore.RED}✗{Style.RESET_ALL} Failed to install spotdl")
                print(f"  Error: {result.stderr[:100]}")
        except subprocess.TimeoutExpired:
                print(f"{Fore.RED}✗{Style.RESET_ALL} Installation timeout for spotdl")
        except Exception as e:
                print(f"{Fore.RED}✗{Style.RESET_ALL} Error installing spotdl: {e}")

    @staticmethod
    def program_info():
        """Display program information"""
        print("=" * 80)
        try:
            Enhanced_Menu.print_header("Interactive Music Downloader")
        except:
            print(f"{Fore.CYAN}Interactive Music Downloader{Style.RESET_ALL}")
        print("=" * 80)
        print(f"""
            {Fore.CYAN}Description:{Style.RESET_ALL}
            A comprehensive tool for downloading music with support for albums, playlists, channels, and individual tracks.

            {Fore.CYAN}Features:{Style.RESET_ALL}
            • Download single tracks 
            • Download complete albums
            • Download playlists with metadata preservation
            • Batch download from text files
            • Search and download songs by name
            • Download entire channels, saved playlist & liked songs
            • Cookie management for authentication
            • Customizable audio format and quality
            • Progress tracking with visual feedback

            {Fore.CYAN}Formats Supported:{Style.RESET_ALL}
            MP3, M4A, FLAC, OGG, OPUS, WAV

            {Fore.CYAN}Requirements:{Style.RESET_ALL}
            • Python 3.7+
            • yt-dlp (For Youtube Music Downloader)
            • spotdl (For Spotify Music Downloader)
            • FFmpeg (recommended for audio conversion)
            • Internet connection
            • Particular python libraries & dependencies

            {Fore.CYAN}Usage Tips:{Style.RESET_ALL}
            • Use cookies for age-restricted or region-restricted content
            • Configure settings before large downloads
            • Check dependencies if encountering issues
            • Use batch files for multiple downloads
            • Monitor disk space for large downloads
            
            {Fore.CYAN}To note:{Style.RESET_ALL}
            • This code was written on a Windows machine
            • I have pointed out areas that can be changed to suit Linux and Apple Machines
            • Other than that, enjoy the program & feel free to make any changes of your own
                """)
        input("\nPress Enter to continue...")
        return True

