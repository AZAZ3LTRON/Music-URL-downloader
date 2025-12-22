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
import importlib.util
import time # Time 
from pathlib import Path
from datetime import datetime
import logging # Logging
from zipfile import ZipFile, ZIP_DEFLATED
from packaging import version

""" =========================================== Pre Config ===========================================
This part of the pre-configuration of the downloader, it can be change. Each part is explained below:
* TEMP_DOWNLOAD_DIRECTORY - Destination the tracks/albums/playlist stay before being moved to the final directory (subject to change)
* FINAL_MUSIC_DIR - Final destination for downloaded files (subject to change)
* SUCCESS_LOG - Logs the successful downloads (subject to change)
* FAILED_LOG - Logs failed downloads (subject to change)
* ERROR_LOG - Logs error in the download process (subject to change)
* MAX_RETRIES - No of times the downloader can retry on a link (subject to change)
* RETRY_DELAY - The delay between each retry (subject to change)
======================================================================================================= """

TEMP_DOWNLOAD_DIRECTORY = r"Temporary"
SUCCESS_LOG = r"log\success.log" 
FAILED_LOG = r"log\failed.log"
ERROR_LOG = r"log\error.log"
MAX_RETRIES = 5
RETRY_DELAY = 20


os.makedirs("log", exist_ok=True)
os.makedirs(TEMP_DOWNLOAD_DIRECTORY, exist_ok=True)

"""=========================================== Logger ===========================================
Initialize the log fies before write
"""

logger = logging.getLogger("Spotify Downloader")
logger.setLevel(logging.INFO)
log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(funcName)s - %(message)s")  

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_format)
logger.addHandler(console_handler)

# Logs only successful downloads
success_downloads = logging.FileHandler(SUCCESS_LOG, encoding='utf-8')
success_downloads.setLevel(logging.INFO)
success_downloads.setFormatter(log_format)

# Logs only failed downloads
failed_downloads = logging.FileHandler(FAILED_LOG, encoding='utf-8')
failed_downloads.setLevel(logging.INFO)
failed_downloads.setFormatter(log_format)

# Logs only error in download process
errors_log = logging.FileHandler(ERROR_LOG, encoding='utf-8')
errors_log.setLevel(logging.ERROR)
errors_log.setFormatter(log_format)

# Add handlers to logger
logger.addHandler(success_downloads)
logger.addHandler(failed_downloads)
logger.addHandler(errors_log)


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
                logger.error(f"{url} - Metadata TypeError (NoneType)")
                # Mark as non-retryable by returning a special object
                return type('obj', (object,), {
                    'returncode': 100,  # Custom return code for non-retryable
                    'stdout': e.stdout,
                    'stderr': stderr
                })()
            
            if "LookupError: No results found for song:" in stderr:
                logger.error(f"{url} - No results found")
                # Mark as non-retryable
                return type('obj', (object,), {
                    'returncode': 101,  # Custom return code for no results
                    'stdout': e.stdout,
                    'stderr': stderr
                })()

            # ------- RETRYABLE ERRORS -----------
            if "AudioProviderError" in stderr:
                logger.warning(f"{url} - YT-DLP audio provider error")
                # This will be retried normally since we raise the exception
            # -------------------------------------------------------------
            
            # For other errors, log and return the exception
            logger.error(f"Command failed for {url}: {e}")
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
            
        # Handle choice of output directory
        output_path = input("Enter output directory (default: Albums): ").strip()
        if output_path:
            self.__output_dir = Path(output_path)
        else:
            self.__output_dir = Path("Albums")
            
        self.__output_dir.mkdir(parents=True, exist_ok=True)
        
    def download_track_album(self):
        """
        Download a single track or album
        """
        url = input("Enter Spotify track or album URL: ").strip()
        
        # Get user preferences
        self.get_user_preferences()
        
        # Set the template:
        if "album" in url.lower():
            output_template = str(self.__output_dir / "{artist}/{album}/{title}.{output-ext}")
        else:
            output_template = str(self.__output_dir / "{artist} - {title}.{output-ext}")
            
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"Downloading ({attempt}/{MAX_RETRIES} tries): {url}")
            
            result = self.run_download(url, output_template)
            
            
            if hasattr(result, 'returncode'):
                if result.returncode == 100: # Metadat TypeError
                    logger.error(f"Non -retryable error for {url}: Metadata TypeError")
                    return False
                elif result.returncode == 101: # No results found
                    logger.error(f"Non -retryable error for {url}: No results found")
                    return False
                
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                logger.info(f"Successfully downloaded: {url}")
                return True
            elif attempt < MAX_RETRIES:
                logger.warning(f"Download failed. Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                return False
            
    def download_playlist(self):
        url = input("What track or album will you like to download")
        
        self.get_user_preferences()
        
        output_template = str(self.__output_dir / "{playlist}/{title}.{output-ext}")
        
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"Downloading ({attempt}/{MAX_RETRIES} tries): {url}")
            
            result = self.run_download(
                url, 
                output_template,
                ["--playlist-numbering", "--playlist-retain-track-cover"])
            
            if hasattr(result, 'returncode'):
                if result.returncode == 100: # Metadat TypeError
                    logger.error(f"Non -retryable error for {url}: Metadata TypeError")
                    return False
                elif result.returncode == 101: # No results found
                    logger.error(f"Non -retryable error for {url}: No results found")
                    return False
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                logger.info(f"Successfully downloaded: {url}")
                return True
            elif attempt < MAX_RETRIES:
                logger.warning(f"Download failed. Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                return False

    def download_from_file(self):
        """ 
        Download various links from a file
        """
        
        filepath = input("Enter the directory of the file").strip()
        
        if not filepath or not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return False
        self.get_user_preferences()
        
        try:
            with open(filepath, 'r') as file:
                file_lines = [line.rstrip() for line in file if line.strip()]
        except FileNotFoundError:
            logger.error(f" File not found: {filepath}")
            return False
        except Exception as e:
            logger.error(f"Error reading the file: {e}")
            return False
        if not file_lines:
            logger.error("No URLs found in the text file")
            return False
        
        success_count = 0 # How many urls download successfully
        failed_count = 0 # How many urls failed to download
        
        for i, url in enumerate(file_lines, 1):
            logger.info(f"Processing URL {i}/{len(file_lines)}: {url}")
            
            clean_url = url.split('#')[0].strip()
            
            # Check if URL is already downloaded
            if url.endswith("# DOWNLOADED"):
                logger.info(f"Skipping already downloaded URL: {url}")
                success_count += 1
                continue
                
            if "playlist" in url.lower():
                output_template = str(self.__output_dir / "{playlist}/{title}.{output-ext}")
                additional_args = ["--playlist-numbering", "--playlist-retain-track-cover"]
            elif "album" in url.lower():
                output_template = str(self.__output_dir / "{artist}/{album}/{title}.{output-ext}")
                additional_args = None
            else:
                output_template = str(self.__output_dir / "{artist} - {title}.{output-ext}")
                additional_args = None
                
            success = False
            non_retry_error = False
            for attempt in range(1, MAX_RETRIES + 1):
                print(f"Downloading ({attempt}/{MAX_RETRIES} tries): {url}")
                
                try:
                    result = self.run_download(url, output_template, additional_args)
                    
                    if hasattr(result, 'returncode'):
                        if result.returncode == 100: # Metadata TypeError
                            logger.error(f"Non -retryable error for {url}: Metadata TypeError")
                            non_retry_error = True
                            break
                        elif result.returncode == 101: # No results found
                            logger.error(f"Non -retryable error for {url}: No results found")
                            non_retry_error = True
                            break
                        
                    if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                        success = True
                        break
                    elif attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY)
                except Exception as e:
                    logger.error(f"Exception during the download {e}")
                    
            if success:
                success_count += 1
                logger.info(f"Successfully download {url}")
                
                if "#" in url:
                    # Keep existing comments before # and add DOWNLOADED
                    parts = url.split('#')
                    file_lines[i-1] = f"{parts[0].strip()} # DOWNLOADED"
                else:
                    file_lines[i-1] = f"{clean_url} # DOWNLOADED"
            else:
                failed_count += 1
                logger.error(f"Failed download {url}")
            if "#" in url:
                parts = url.split('#')
                file_lines[i-1] = f"{parts[0].strip()} # FAILED"
            else:
                file_lines[i-1] = f"{clean_url} # FAILED"
        
        try: 
            with open(filepath, 'w') as file:
                file.write("\n".join(file_lines))    
        except Exception as e:
            logger.error(f"Error updating the file: {e}") 
        logger.error(f"Failed to download playlist after {MAX_RETRIES} attempts: {url}")
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
                    logger.error(f"Non -retryable error for {song_query}: Metadata TypeError")
                    return False
                elif result.returncode == 101: # No results found
                    logger.error(f"Non -retryable error for {song_query}: No results found")
                    return False
                
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                logger.info(f"Successfully downloaded: {song_query}")
                return True
            elif attempt < MAX_RETRIES:
                logger.warning(f"Download failed. Retrying in {RETRY_DELAY} seconds....")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"Failed to download after {MAX_RETRIES} attempts: {song_query}")
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
                logger.error("Metadata Type Error")
                return False
            
            if "LookupError: No results found for song:" in stderr:
                logger.error("No results found")
                return False
            
            # ------------ RETRYABLE ERROR ------------
            if "AudioProviderError" in stderr:
                logger.warning(f"YT-DLP audio provider error")
            # -----------------------------------------------------------------------------------

            if result.stdout:
                logger.info(f"spotdl output: {result.stdout.strip()}")
            
            if result.stderr and not ("AudioProviderError" in stderr):
                logger.error(f"spotdl stderr: {result.stderr.strip()}")
            
            if result.returncode == 0:
                logger.info("Successfully downloaded user playlists")
                return True
            else:
                logger.error(f"Failed to download user playlists. Return code: {result.returncode}")
                return False
            
        except Exception as e:
            logger.exception(f"Unexpected exception: {e}") 
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
                logger.error("Metadata Type Error")
                return False
            
            if "LookupError: No results found for song:" in stderr:
                logger.error("No results found")
                return False
            
            # ------------ RETRYABLE ERROR ------------
            if "AudioProviderError" in stderr:
                logger.warning(f"YT-DLP audio provider error")
            # -----------------------------------------------------------------------------------

            if result.stdout:
                logger.info(f"spotdl output: {result.stdout.strip()}")
            
            if result.stderr and not ("AudioProviderError" in stderr):
                logger.error(f"spotdl stderr: {result.stderr.strip()}")
            
            if result.returncode == 0:
                logger.info("Successfully downloaded user playlists")
                return True
            else:
                logger.error(f"Failed to download user playlists. Return code: {result.returncode}")
                return False
            
        except Exception as e:
            logger.exception(f"Unexpected exception: {e}") 
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
                logger.error("Metadata Type Error")
                return False
            
            if "LookupError: No results found for song:" in stderr:
                logger.error("No results found")
                return False
            
            # ------------ RETRYABLE ERROR ------------
            if "AudioProviderError" in stderr:
                logger.warning(f"YT-DLP audio provider error")
            # -----------------------------------------------------------------------------------

            if result.stdout:
                logger.info(f"spotdl output: {result.stdout.strip()}")
            
            if result.stderr and not ("AudioProviderError" in stderr):
                logger.error(f"spotdl stderr: {result.stderr.strip()}")
            
            if result.returncode == 0:
                logger.info("Successfully downloaded user playlists")
                return True
            else:
                logger.error(f"Failed to download user playlists. Return code: {result.returncode}")
                return False
            
        except Exception as e:
            logger.exception(f"Unexpected exception: {e}") 
            return False

    @staticmethod
    def check_spotdl():
        """
        Check if spotdl is installed and install it if not
        """
        if shutil.which("spotdl"):
            logger.info("spotdl is already installed")
            
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
                logger.info(f"spotdl version: {version_str}")
                return True
            except subprocess.CalledProcessError:
                logger.warning("Could not determine spotdl version")
                return True
        else:
            logger.info("spotdl not found. Installing...")
            
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "spotdl"])
                logger.info("spotdl installed successfully")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install spotdl: {e}")
                return False
    
    @staticmethod     
    def show_spotdl_help():
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
            logger.error(f"Could not get spotdl help: {e}")
    
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
def main():
    """
    Main function to run the Spotify Downloader
    """
    downloader = Downloader()
    
    while True:
        print("\n" + "="*80)
        print("INTERACTIVE SPOTIFY DOWNLOADER")
        print("="*80)
        print("Select an option:")
        print("1. Download Track or Album")
        print("2. Download Playlist")
        print("3. Download from Text File")
        print("4. Search and Download Song")
        print("5. Download User Playlists (Requires Spotify Account)")
        print("6. Download Liked Songs (Requires Spotify Account)")
        print("7. Download Saved Albums (Requires Spotify Account)")
        print("8. Check/Install spotdl")
        print("9. Show spotdl Help")
        print("10. Show Program Info")
        print("11. Exit")
        print("="*80)
        
        choice = input("\nEnter your choice (1-11): ").strip()
        
        if choice == "1":
            downloader.download_track_album()
        elif choice == "2":
            downloader.download_playlist()
        elif choice == "3":
            downloader.download_from_file()
        elif choice == "4":
            downloader.search_a_song()
        elif choice == "5":
            downloader.download_user_playlist()
        elif choice == "6":
            downloader.download_user_liked_songs()
        elif choice == "7":
            downloader.download_user_saved_albums()
        elif choice == "8":
            downloader.check_spotdl()
        elif choice == "9":
            downloader.show_spotdl_help()
        elif choice == "10":
            downloader.program_info()
        elif choice == "11":
            print("\nThank you for using Spotify Downloader. Goodbye!")
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 11.")
        
        # Ask if user wants to continue
        if choice != "11":
            cont = input("\nDo you want to perform another operation? (y/n): ").strip().lower()
            if cont not in ['y', 'yes']:
                print("\nThank you for using Spotify Downloader. Goodbye!")
                break


if __name__ == "__main__":
    # First check if spotdl is available
    print("Checking spotdl installation...")
    if Downloader.check_spotdl():
        main()
    else:
        print("Failed to install spotdl. Please install it manually using:")
        print("pip install spotdl")
        print("Then run the program again.")