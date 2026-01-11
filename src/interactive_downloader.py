"""
Interactive Spotify Playlist/Album/Track Downloader

This is a simple to use downloader that can help in downloading albums/playlist/single tracks etc from Spotfiy
With the rise of Artificial Intelligence and the music industry rallying to replace artist as well as Spotify 

Its features a:
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
"""
import sys
import os # For directory creation
import subprocess # To run the spotdl in the background
import shutil
import time # Time 
from pathlib import Path
from datetime import datetime
import logging # Logging
from packaging import version

""" =========================================== Pre Config ===========================================
This part of the pre-configuration of the downloader, it can be change. Each part is explained below:
* SUCCESS_LOG - Logs the successful downloads (subject to change)
* FAILED_LOG - Logs failed downloads (subject to change)
* ERROR_LOG - Logs error in the download process (subject to change)
* MAX_RETRIES - No of times the downloader can retry on a link (subject to change)
* RETRY_DELAY - The delay between each retry (subject to change)
======================================================================================================= """
USER_CONSOLE = r"log\console.log"
SUCCESS_LOG = r"log\successes.log" 
FAILED_LOG = r"log\failure.log"
ERROR_LOG = r"log\error.log"
MAX_RETRIES = 5
RETRY_DELAY = 20

os.makedirs("log", exist_ok=True)
"""=========================================== Logger ===========================================
Initialize the log fies before write
"""

successful_downloads = logging.getLogger("successful_downloads")
failed_downloads = logging.getLogger("failed_downloads")
error_downloads = logging.getLogger("error_downloads")
console_logger = logging.getLogger("console")

# Set Levels
successful_downloads.setLevel(logging.INFO)
failed_downloads.setLevel(logging.INFO)
error_downloads.setLevel(logging.ERROR)
console_logger.setLevel(logging.INFO)

# Disable propagation to avoid duplicate logging
successful_downloads.propagate = False
failed_downloads.propagate = False
error_downloads.propagate = False
console_logger.propagate = False

# Formats
log_format = logging.Formatter("%(asctime)s - %(message)s")
error_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# Success logger - only to success.log file
success_handler = logging.FileHandler(SUCCESS_LOG, encoding='utf-8')
success_handler.setLevel(logging.INFO)
success_handler.setFormatter(log_format)
successful_downloads.addHandler(success_handler)

# Failed logger - only to failed.log file
failed_handler = logging.FileHandler(FAILED_LOG, encoding='utf-8')
failed_handler.setLevel(logging.INFO)
failed_handler.setFormatter(log_format)
failed_downloads.addHandler(failed_handler)

# Error logger - only to error.log file
error_handler = logging.FileHandler(ERROR_LOG, encoding='utf-8')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(error_format)
error_downloads.addHandler(error_handler)

# Console logger for user feedback
console_file_handler = logging.FileHandler(USER_CONSOLE, encoding='utf-8')
console_file_handler.setLevel(logging.INFO)
console_file_handler.setFormatter(log_format)
console_file_handler = logging.StreamHandler()
console_logger.addHandler(console_file_handler)

# Stream handler
console_stream_handler = logging.StreamHandler()
console_stream_handler.setLevel(logging.INFO)
console_stream_handler.setFormatter(log_format)
console_logger.addHandler(console_stream_handler)

""" =========================================== The Downloader Class =========================================== """
class Downloader:
    def __init__(self):
        """
        Initialize the downloader with default values
        
        Args:
        output_dir - The output directory we wish to send our playlist once downloaded
        bitrate - The quality of the audio
        audio_format - The format we wish to download the Spotify url
        
        The values here are set to default and can be changed later to fit your preference 
        """
        self.__output_dir = Path("Albums")
        self.__bitrate = "320k"
        self.__audio_format = "mp3"
        self.__filepath = r"links/spotify_links.txt"
        self.__lyrics_provider = None
   
    """ Logger functions"""
    def log_success(self, message: str):
        """ Log successful downloads only to success.log"""
        successful_downloads.info(message)
        console_logger.info(f"{message}")
        
    def log_failure(self, message: str):
        """ Log failed downloads only to failed.log"""
        failed_downloads.info(message)
        console_logger.info(f"{message}")        
    
    def log_errors(self, message: str, exc_info=False):
        """Log errors only to error.log"""
        error_downloads.error(message, exc_info=exc_info)
        console_logger.error(f"{message}")
    
    """ Required"""
    def run_download(self, url: str, output_dir: Path, additional_args=None):
        """
        Method to run Spotdl's download command
        """
        command = [
            "spotdl",
            "download",
            url,
            "--output", output_dir,
            "--overwrite", "skip",
            "--bitrate", self.__bitrate,
            "--format", self.__audio_format,
        ]
        if self.__lyrics_provider:
            command.extend(["--lyrics", self.__lyrics_provider])
        
        if additional_args:
            command.extend(additional_args)
            
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            return result
        
        except subprocess.CalledProcessError as e:
            stderr = e.stderr or ""
             # Error Handling for specific errors during download process ----------------------------
            # ----- NON - RETRYABLE ERRORS -------------------
            if "TypeError: expected string or bytes-like object, got 'NoneType'" in stderr:
                self.log_failure(f"{url} - Metadata TypeError (NoneType)")
                # Mark as non-retryable by returning a special object
                return type('obj', (object,), {
                    'returncode': 100,  # Custom return code for non-retryable
                    'stdout': e.stdout,
                    'stderr': stderr
                })()
            
            if "LookupError: No results found for song:" in stderr:
                self.log_failure(f"{url} - No results found")
                # Mark as non-retryable
                return type('obj', (object,), {
                    'returncode': 101,  # Custom return code for no results
                    'stdout': e.stdout,
                    'stderr': stderr
                })()

            # ------- RETRYABLE ERRORS -----------
            if "AudioProviderError" in stderr:
                self.log_failure(f"{url} - YT-DLP audio provider error")
                # This will be retried normally since we raise the exception
            # -------------------------------------------------------------
            
            # For other errors, log and return the exception
            self.log_errors(f"Command failed for {url}: {e}")
            return e
            
    def get_user_preferences(self):
        """
        Takes in user input for the download settings
        """
        # Handle choice of bitrate inputs
        while True:
            bitrate_input = input("What bitrate would you like (8k-320k, default:- 320k): ").strip().lower()
            
            if not bitrate_input:
                self.__bitrate = "320K"
                break
            if bitrate_input in ["auto", "disable", "8k", "16k", "24k", "32k", "40k", "48k", "64k",
                                "80k", "96k", "112k", "128k", "160k", "192k", "224k", "256k", "320k"]:
                self.__bitrate = bitrate_input
                break
            print("Invalid bitrate. Please choose from the specified values.")
            
        # Handles choice of audio format
        while True:
            audio_format_input = input("What format do you wish to download in:(mp3, flac, ogg, opus, m4a, wav, default mp3): ").strip().lower()
            if not audio_format_input:
                self.__audio_format = "mp3"
                break
            if audio_format_input in ["mp3", "flac", "ogg", "opus", "m4a", "wav"]:
                self.__audio_format = audio_format_input
                break
            print("Invalid format. Please choose from the specified formats.")
            
        # Handle downloaded of lyrics
        while True:  
            lyrics_input = input("Would you like lyrics with the song (Y/N, default:N)").strip().lower()
            if not lyrics_input:
                self.__lyrics_provider = None
                break
            elif lyrics_input == "Y":
                lyrics_provider_input = input("Which provider will you like to take from").strip().lower()
                
                if not lyrics_provider_input:
                    self.__lyrics_provider = "genius"
                elif lyrics_provider_input in ["genius", "musixmatch", "azlyrics", "synced"]:
                    self.__lyrics_provider = lyrics_provider_input
                else:
                    console_logger.error("Invalid provider given. Setting default to genius lyrics") 
                    self.__lyrics_provider = "genius"
                break
            else:    
                print("Please enter 'y' or 'n'. ")
                        
        # Handle choice of output directory
        output_path = input("Enter output directory (default: Albums): ").strip()
        if output_path:
            self.__output_dir = Path(output_path)
        else:
            self.__output_dir = Path("Albums")
            
        self.__output_dir.mkdir(parents=True, exist_ok=True)
                    
    """ Download functions"""
    def download_track(self):
        """
        Download a single track
        """
        console_logger.info("\n === Single Track Download === ")
        url = input("Enter Spotify track url:- ").strip()
        
        if not url:
            console_logger.error("No URL provided")
            return False
        
        # Get user preferences
        self.get_user_preferences()
        
        # Set the template:
        output_template = str(self.__output_dir / "{title}.{output-ext}")
            
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"Downloading ({attempt}/{MAX_RETRIES} tries): {url}")
            
            result = self.run_download(url, output_template)
            
            if hasattr(result, 'returncode'):
                if result.returncode == 100: # Metadat TypeError
                    self.log_failure(f"Non -retryable error for {url}: Metadata TypeError")
                    return False
                elif result.returncode == 101: # No results found
                    self.log_failure(f"Non -retryable error for {url}: No results found")
                    return False
                
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                self.log_success(f"Successfully downloaded: {url}")
                return True
            elif attempt < MAX_RETRIES:
                console_logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                return False
    
    def download_album(self):
        """ Download an album"""
        
        console_logger.info("\n === Download Album ===")
        url = input("Enter Spotify album url:- ").strip()
        
        if not url:
            console_logger.error("No URL provided")
            return False
        
        self.get_user_preferences()
        output_template = str(self.__output_dir / "{artist}/{album}/{title}.{output-ext}")
        
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"Downloading ({attempt}/{MAX_RETRIES} tries): {url}")
            result = self.run_download(url, output_template)
            
            if hasattr(result, 'returncode'):
                if result.returncode == 100:
                    self.log_failure(f"Non - retryable error for {url}: Metadata TypeError")
                    return False
                elif result.returncode == 101:
                    self.log_failure(f"Non-retryable error for {url}: No results found")
                    return False
                
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                self.log_success(f"Successful downloaded: {url}")
                return True
            elif attempt < MAX_RETRIES:
                console_logger.info(f"Retrying in {RETRY_DELAY} seconds... ")
                time.sleep(RETRY_DELAY)
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                return False
            
    def download_playlist(self):
        console_logger.info("\n ==== Download Playlist ====")
        url = input("What playlist will you like to download:- ")
        
        if not url:
            console_logger.error("No URL provided.")
            return False
        
        self.get_user_preferences()
        output_template = str(self.__output_dir / "{playlist}/{title}.{output-ext}")
        
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"Downloading ({attempt}/{MAX_RETRIES} tries): {url}")
            
            result = self.run_download(
                url, 
                output_template,
                ["--playlist-numbering", "--playlist-retain-track-cover"])
            
            if hasattr(result, 'returncode'):
                if result.returncode == 100: # Metadata TypeError
                    self.log_failure(f"Non -retryable error for {url}: Metadata TypeError")
                    return False
                elif result.returncode == 101: # No results found
                    self.log_failure(f"Non -retryable error for {url}: No results found")
                    return False
                
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                self.log_success(f"Successfully downloaded: {url}")
                return True
            elif attempt < MAX_RETRIES:
                console_logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                return False

    def download_from_file(self):
        """ 
        Download various links from a file
        """
        console_logger.info("\n ==== Download from text file ==== ")
        filepath = input("Enter the directory of the file:- ").strip()
        
        if not filepath or not os.path.exists(filepath):
            self.log_errors(f"File not found: {filepath}")
            return False
        
        self.get_user_preferences()
        
        try:
            with open(filepath, 'r') as file:
                file_lines = [line.rstrip() for line in file if line.strip()]
        except FileNotFoundError:
            self.log_errors(f" File not found: {filepath}")
            return False
        except Exception as e:
            self.log_errors(f"Error reading the file: {e}")
            return False
        
        if not file_lines:
            self.log_errors("No URLs found in the text file")
            return False
        
        success_count = 0 # How many urls download successfully
        failed_count = 0 # How many urls failed to download
        total_lines = len(file_lines)
        
        console_logger.info(f"Found {total_lines} URLs found in the file")
        
        for i, line in enumerate(file_lines, 1):
            # Clean the URL (remove comments)
            clean_url = line.split('#')[0].strip()
        
            if not line:
                console_logger.info(f"Line {i}: Empty line, skipping")
                continue
            
            # Check if URL is already downloaded
            if line.endswith("# DOWNLOADED"):
                console_logger.info(f"Skipping url- Already downloaded")
                success_count += 1
                continue
            
            # Check if URL is marked failed
            if line.endswith("# FAILED"):
                console_logger.info(f"Previously marked as failed, will retry")
                failed_count += 1

                
            if "playlist" in clean_url.lower():
                output_template = str(self.__output_dir / "{playlist}/{title}.{output-ext}")
                additional_args = ["--playlist-numbering", "--playlist-retain-track-cover"]
            elif "album" in clean_url.lower():
                output_template = str(self.__output_dir / "{artist}/{album}/{title}.{output-ext}")
                additional_args = None
            else:
                output_template = str(self.__output_dir / "{artist} - {title}.{output-ext}")
                additional_args = None
                
            success = False
            non_retry_error = False
            
            for attempt in range(1, MAX_RETRIES + 1):
                console_logger.info(f"Downloading ({attempt}/{MAX_RETRIES} tries): {clean_url}")
                
                try:
                    result = self.run_download(clean_url, output_template, additional_args)
                    
                    if hasattr(result, 'returncode'):
                        if result.returncode == 100: # Metadata TypeError
                            self.log_failure(f"Non -retryable error for {clean_url}: Metadata TypeError")
                            non_retry_error = True
                            break
                        elif result.returncode == 101: # No results found
                            self.log_failure(f"Non -retryable error for {clean_url}: No results found")
                            non_retry_error = True
                            break
                        
                    if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                        success = True
                        break
                    elif attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY)
                except Exception as e:
                    self.log_errors(f"Exception during the download {e}")
                    
            if success:
                success_count += 1
                self.log_success(f"Successfully downloaded {clean_url}")
                # Update line in file
                file_lines[i-1] = f"{clean_url} # DOWNLOADED"
            else:
                failed_count += 1
                self.log_failure(f"Failed download {clean_url}")
                 # Update line to mark as failed (but keep previous status if exists)
                if "# DOWNLOADED" not in file_lines[i-1].upper():
                    file_lines[i-1] = f"{clean_url} # FAILED"
        
        try: 
            with open(filepath, 'w', encoding='utf-8') as file:
                file.write("\n".join(file_lines))    
        except Exception as e:
            self.log_errors(f"Error updating the file: {e}") 
        self.log_failure(f"Failed to download playlist after {MAX_RETRIES} attempts: {clean_url}")
        return failed_count == 0
    
    def search_a_song(self):
        """ Search for a song and download"""    
        song_query = input("What is the name of the song you're looking for: ").strip()

        self.get_user_preferences()
        output_template = str(self.__output_dir / "{artist}/{album}/{title}.{output-ext)")
        
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"Search and download attempt {attempt}/{MAX_RETRIES}: {song_query}")
            result = self.run_download(song_query, output_template)
            
            
            if hasattr(result, 'returncode'):
                if result.returncode == 100: # Metadat TypeError
                    self.log_failure(f"Non -retryable error for {song_query}: Metadata TypeError")
                    return False
                elif result.returncode == 101: # No results found
                    self.log_failure(f"Non -retryable error for {song_query}: No results found")
                    return False
                
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                self.log_success(f"Successfully downloaded: {song_query}")
                return True
            elif attempt < MAX_RETRIES:
                console_logger.info(f"Retrying in {RETRY_DELAY} seconds....")
                time.sleep(RETRY_DELAY)
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {song_query}")
                return False   

    def download_user_playlist(self):
        """
        Download a user's playlist (requires authentication)
        """
        print("\n=== User Playlist Download ===")
        print("Note: This requires Spotify authentication")
        print("This requires a Spotify Account")
        print("You will be redirected to the Spotify website for authorization")
        
        self.get_user_preferences()
        
        try:
            print("Downloading user's playlist...")
            result = subprocess.run([
                "spotdl",
                "download",
                "all-user-playlists",
                "--user-auth",
                "output", str(self.__output_dir),
                "overwrite", "skip",
                "--bitrate", self.__bitrate,
                "--format", self.__audio_format,
            ],
                stdout=sys.stdout,
                stderr=subprocess.PIPE,
                text=True
            )
            stderr = result.stderr or ""
            
            # Error handling for specific errors during download process
            # ------------ NON -RETRYABLE ERRORS ------------
            if "TypeError: expected string or bytes-line object, got 'NoneType'" in stderr:
                self.log_failure("Metadata Type Error")
                return False
            
            if "LookupError: No results found for song:" in stderr:
                self.log_failure("No results found")
                return False
            
            # ------------ RETRYABLE ERROR ------------
            if "AudioProviderError" in stderr:
                self.log_errors(f"YT-DLP audio provider error")
            # -----------------------------------------------------------------------------------

            if result.stdout:
                self.log_success(f"spotdl output: {result.stdout.strip()}")
            
            if result.stderr and not ("AudioProviderError" in stderr):
                self.log_errors(f"spotdl stderr: {result.stderr.strip()}")
            
            if result.returncode == 0:
                self.log_success("Successfully downloaded user playlists")
                return True
            else:
                self.log_failure(f"Failed to download user playlists. Return code: {result.returncode}")
                return False
            
        except Exception as e:
            console_logger.info(f"Unexpected exception: {e}") 
            return False
        
    def download_user_liked_songs(self):
        """
        Download a user's playlist
        """
        print("\n=== User Playlist Download ===")
        print("Note: This requires Spotify authentication")
        print("This requires a Spotify Account")
        print("You will be redirected to the Spotify website for authorization")
        
        self.get_user_preferences()
        
        try:
            print("Downloading the User's playlist")
            print("You will be redirected to the Spotify site")
            result = subprocess.run([
                "spotdl",
                "download",
                "saved",
                "--user-auth",
                "--output", str(self.__output_dir),
                "--overwrite", "skip",
                "--bitrate", self.__bitrate,
                "--format", self.__audio_format,
            ],
                stdout=sys.stdout,
                stderr=subprocess.PIPE,
                text=True
            )
            stderr = result.stderr or ""
            
            # Error handling for specific errors during download process
            # ------------ NON -RETRYABLE ERRORS ------------
            if "TypeError: expected string or bytes-line object, got 'NoneType'" in stderr:
                self.log_failure("Metadata Type Error")
                return False
            
            if "LookupError: No results found for song:" in stderr:
                self.log_failure("No results found")
                return False
            
            # ------------ RETRYABLE ERROR ------------
            if "AudioProviderError" in stderr:
                self.log_errors(f"YT-DLP audio provider error")
            # -----------------------------------------------------------------------------------

            if result.stdout:
                self.log_success(f"spotdl output: {result.stdout.strip()}")
            
            if result.stderr and not ("AudioProviderError" in stderr):
                self.log_errors(f"spotdl stderr: {result.stderr.strip()}")
            
            if result.returncode == 0:
                self.log_success("Successfully downloaded user playlists")
                return True
            else:
                self.log_errors(f"Failed to download user playlists. Return code: {result.returncode}")
                return False
            
        except Exception as e:
            console_logger.info(f"Unexpected exception: {e}") 
            return False

    def download_user_saved_albums(self):
        """
        Download a user's saved albums
        """
        print("\n=== User Playlist Download ===")
        print("Note: This requires Spotify authentication")
        print("This requires a Spotify Account")
        print("You will be redirected to the Spotify website for authorization")
        
        self.get_user_preferences()
           
        try:
            print("Downloading the User's playlist")
            print("You will be redirected to the Spotify site")
            result = subprocess.run([
                "spotdl",
                "download",
                "all-user-saved-albums",
                "--user-auth",
                "--output", str(self.__output_dir),
                "--overwrite", "skip",
                "--bitrate", self.__bitrate,
                "--format", self.__audio_format,
            ],
                stdout=sys.stdout,
                stderr=subprocess.PIPE,
                text=True
            )
            stderr = result.stderr or ""
            
            # Error handling for specific errors during download process
            # ------------ NON -RETRYABLE ERRORS ------------
            if "TypeError: expected string or bytes-line object, got 'NoneType'" in stderr:
                self.log_failure("Metadata Type Error")
                return False
            
            if "LookupError: No results found for song:" in stderr:
                self.log_failure("No results found")
                return False
            
            # ------------ RETRYABLE ERROR ------------
            if "AudioProviderError" in stderr:
                self.log_errors(f"YT-DLP audio provider error")
            # -----------------------------------------------------------------------------------

            if result.stdout:
                self.log_success(f"spotdl output: {result.stdout.strip()}")
            
            if result.stderr and not ("AudioProviderError" in stderr):
                self.log_errors(f"spotdl stderr: {result.stderr.strip()}")
            
            if result.returncode == 0:
                self.log_success("Successfully downloaded user playlists")
                return True
            else:
                self.log_errors(f"Failed to download user playlists. Return code: {result.returncode}")
                return False
            
        except Exception as e:
            console_logger.info(f"Unexpected exception: {e}") 
            return False

    @staticmethod
    def check_spotdl():
        """
        Check if spotdl is installed and install it if not
        """
        if shutil.which("spotdl"):
            console_logger.info("spotdl is already installed")
            
            # Check version
            try:
                result = subprocess.run(
                    ["spotdl", "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True
                )
                version_str = result.stdout.strip()
                console_logger.info(f"spotdl version: {version_str}")
                return True
            except subprocess.CalledProcessError:
                console_logger.warning("Could not determine spotdl version")
                return True
        else:
            console_logger.warning("spotdl not found. Installing...")
            
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "spotdl"])
                console_logger.info("spotdl installed successfully")
                return True
            except subprocess.CalledProcessError as e:
                console_logger.info(f"Failed to install spotdl: {e}")
                return False
    
    @staticmethod     
    def show_spotdl_help(self):
        """
        Display spotdl help
        """
        try:
            result = subprocess.run(
                ["spotdl", "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            print("\n" + "="*50)
            print("SPOTDL HELP")
            print("="*50)
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            console_logger.info(f"Could not get spotdl help: {e}")
    
    @staticmethod     
    def program_info():
        """
        Display program information
        """
        print("="*80)
        print("Interactive Spotify Playlist/Album/Track Downloader")
        print("="*80)
        print("This is a simple to use downloader that can help in downloading")
        print("albums/playlist/single tracks etc from Spotify")
        print("\n" + "-"*80)
        print("Each function explained:")
        print("\n=== Basic Functions: Can work without having a Spotify account ===")
        print("* download_track_album - Downloads a single track or a single album")
        print("* download_playlist - Downloads a playlist and compile it into a single folder")
        print("* download_from_file - Downloads from a text file")
        print("* search_a_song - Search for a song & download it")
        print("\n=== Special Functions: For those with a Spotify account (requires authentication) ===")
        print("* download_user_playlist - Downloads a user's playlist from their Spotify Account")
        print("* download_user_liked_songs - Downloads a user's liked songs from their Spotify Account")
        print("* download_user_saved_albums - Downloads a user's saved albums from their Spotify Account")
        print("\n=== Help functions: Provides help with the program ===")
        print("* program_info - Provides context on the program")
        print("* check_spotdl - Checks for spotdl & installs it if doesn't exist")
        print("* show_spotdl_help - Provides context on spotdl commands")
        print("="*80)

""" The downloader """
def display_menu() -> None:
    """Display the main menu."""
    menu = """
    ========================================================================
    INTERACTIVE SPOTIFY DOWNLOADER
    ========================================================================
    Select an option:
    1.  Download Track
    2.  Download Album
    3.  Download Playlist
    4.  Download from Text File
    5.  Search and Download Song
    6.  Download User Playlists (Requires Spotify Account)
    7.  Download Liked Songs (Requires Spotify Account)
    8.  Download Saved Albums (Requires Spotify Account)
    9.  Check/Install spotdl
    10. Show spotdl Help
    11. Show Program Info
    12. Exit
    ========================================================================
    """
    print(menu)


def main():
    """Main function to run the Spotify Downloader."""
    print("Initializing Spotify Downloader...")
    
    # Check spotdl installation
    if not Downloader.check_spotdl():
        print("\nFailed to install spotdl. Please install it manually using:")
        print("pip install spotdl")
        print("Then run the program again.")
        return
    
    downloader = Downloader()
    
    while True:
        display_menu()
        choice = input("\nEnter your choice (1-12): ").strip()
        
        actions = {
            "1": downloader.download_track,
            "2": downloader.download_album,
            "3": downloader.download_playlist,
            "4": downloader.download_from_file,
            "5": downloader.search_a_song,
            "6": downloader.download_user_playlist,
            "7": downloader.download_user_liked_songs,
            "8": downloader.download_user_saved_albums,
            "9": downloader.check_spotdl,
            "10": downloader.show_spotdl_help,
            "11": downloader.program_info,
        }
        
        if choice == "12":
            print("\nThank you for using Spotify Downloader. Goodbye!")
            break
        
        action = actions.get(choice)
        if action:
            action()
        else:
            print("Invalid choice. Please enter a number between 1 and 12.")
            continue
        
        # Ask if user wants to continue (except for help/info actions)
        if choice not in ["10", "11"]:
            cont = input("\nDo you want to perform another operation? (y/n): ").strip().lower()
            if cont not in ['y', 'yes']:
                print("\nThank you for using Spotify Downloader. Goodbye!")
                break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user. Goodbye!")
    except Exception as e:
        console_logger.info(f"Unexpected error in main: {e}")
        print(f"\nAn unexpected error occurred: {e}")
        print("Please check the error log for details.")