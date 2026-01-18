"""
Interactive Playlist/Album/Track Downloader using SpotDL

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

# Basic Import required
import sys
import os # For directory creation
import subprocess # To run the spotdl in the background
import shutil
import time # Time
from functools import wraps
from pathlib import Path
import logging # Logging
import re # Regex
import urllib.parse

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

os.makedirs("log", exist_ok=True)

"""==== Logger: Initialize the log fies before write ====  """
# Basic Logger info
logger = logging.getLogger("Spotify Downloader")
log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(funcName)s - %(message)s") 
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
        self.__spotdl_version = None

    # Logger Functions -----------------------------------------------------------------
    def log_success(self, message: str):
        """Logs only successful downloads (to success log)"""
        success_downloads.info(message)
        console_logger.info(f"{message}")
        
    def log_failure(self, message: str):
        """ Logs only failed downlaods (to failed log)"""
        failed_downloads.info(message)
        console_logger.info(f"{message}")
        
    def log_error(self, message: str, exc_info=False):
        """ Logs only  error in download process (to error log)"""
        error_downloads.error(message, exc_info=exc_info)
        console_logger.error(f"{message}")
     
    # Preference getters & helper functions ------------------------------------------------        
    def get_user_preferences(self):
        """ Takes in user input for the download settings """
        
        # Handle choice of bitrate inputs
        while True:
            bitrate_input = input("What bitrate would you like (8k-320k, default:- 320k):- ").strip().lower()
            
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
            audio_format_input = input("What format do you wish to download in:(mp3, flac, ogg, opus, m4a, wav, default mp3):- ").strip().lower()
            if not audio_format_input:
                self.__audio_format = "mp3"
                break
            if audio_format_input in ["mp3", "flac", "ogg", "opus", "m4a", "wav"]:
                self.__audio_format = audio_format_input
                break
            print("Invalid format. Please choose from the specified formats.")
            
        # Handle choice of output directory
        output_path = input("Enter output directory (default: Albums):- ").strip()
        if output_path:
            self.__output_dir = Path(output_path)
        else:
            self.__output_dir = Path("Albums")
            
        self.__output_dir.mkdir(parents=True, exist_ok=True)
    
    def validate_spotify_url(self, url: str) -> bool:
        """ Validate if the URL input is a proper URL"""
        
        spotify_patterns = [
            r'^https://open\.spotify\.com/(track|album|playlist|artist)/[A-Za-z0-9]+(\?.*)?$',
            r'^spotify:(track|album|playlist|artist):[A-Za-z0-9]+$',
            r'^https://open\.spotify\.com/user/[^/]+/playlist/[A-Za-z0-9]+$'
        ]
    
        for pattern in spotify_patterns:
            if re.match(pattern, url):
                try:
                    parsed = urllib.parse.urlparse(url)
                    if parsed.scheme in ['http', 'https', 'spotify']:
                        return True
                except:
                    continue
        return False
    
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

    def run_download(self, url: str, output_dir: Path, additional_args=None):
        """ Run spotdl download with modern syntax """
        command = [
            "spotdl",
            "download",
            url,
            "--output", output_dir,
            "--overwrite", "skip",
            "--bitrate", self.__bitrate,
            "--format", self.__audio_format
        ]
        
        if additional_args:
            command.extend(additional_args)
        
        try:
            result = subprocess.run(
                command,
                stdout=sys.stdout,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            self.log_error(f"Command output: {result.stdout[:500]}")
            if result.stderr:
                self.log_error(f"Command errors: {result.stderr[:500]}")
            return result
        
        except subprocess.CalledProcessError as e:
            stderr = e.stderr or ""
             # Error Handling for specific errors during download process ----------------------------
            # ----- NON - RETRYABLE ERRORS -------------------
            if "TypeError: expected string or bytes-like object, got 'NoneType'" in stderr:
                self.log_error(f"{url} - Metadata TypeError (NoneType)")
                # Mark as non-retryable by returning a special object
                return type('obj', (object,), {
                    'returncode': 100,  # Custom return code for non-retryable
                    'stdout': e.stdout,
                    'stderr': stderr
                })()
            
            if "LookupError: No results found for song:" in stderr:
                self.log_error(f"{url} - No results found")
                # Mark as non-retryable
                return type('obj', (object,), {
                    'returncode': 101,  # Custom return code for no results
                    'stdout': e.stdout,
                    'stderr': stderr
                })()

            # ------- RETRYABLE ERRORS -----------
            if "AudioProviderError" in stderr:
                self.log_error(f"{url} - YT-DLP audio provider error")
                # This will be retried normally since we raise the exception
            # -------------------------------------------------------------
            
            # For other errors, log and return the exception
            self.log_failure(f"Command failed for {url}: {e}")
            return e

        except subprocess.TimeoutExpired:
            self.log_error(f"Download timeout for {url}")
            return type('obj', (object,), {
                'returncode': 102, # Timeout
                'stdout': '',
                'stderr': 'Download timeout'        
            })()
            
        except Exception as e:
            self.log_error(f"Unexpected error: {e}")
            return e

    # Extra functions to really on (incase of program failure) ----------------------------
    def rate_limit(calls_per_minute=60):
        """ Added rate limiter to avoid being blocked """
        def decorator(func):
            last_called = [0.0]
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                elapsed_time = time.time() - last_called[0]
                wait_time = (60.0 / calls_per_minute) - elapsed_time
                if wait_time > 0:
                    time.sleep(wait_time)
                last_called[0] = time.time()
                return func(*args, **kwargs)
            return wrapper
        return decorator

    # Main download functions -----------------------------------------------------------
    def download_track(self):
        """ Download a single track """
        print("\n =========== Single Track Download =================")
        url = input("Enter Spotify track url:- ").strip()
        
        if not url:
            print("No URL provided")
            return False

        # Validate URL
        if not self.validate_spotify_url(url):
            print("Invalid Spotify URL. Please enter a valid Spotify track URL")
            return False
        
        # Get user preferences
        self.get_user_preferences()
        print("===========================================================================")
        print(f"Starting Track download: {url}. This may take a few minutes...")
        start_time = time.time()
        output_template = str(self.__output_dir / "{title}.{output-ext}")
            
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"===========  Downloading Track URL: Attempt {attempt} of {MAX_RETRIES} =========== ")
            
            result = self.run_download(url, output_template)
            
            if hasattr(result, 'returncode'):
                if result.returncode == 100: # Metadata TypeError
                    self.log_error(f"Non -retryable error for {url}: Metadata TypeError")
                    return False
                elif result.returncode == 101: # No results found
                    self.log_error(f"Non -retryable error for {url}: No results found")
                    return False
            
            # Check if download was successful as well as record time it took to complete download
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                elapsed_time = time.time() - start_time
                self.log_success(f"Successfully downloaded: {url} in {elapsed_time:.1f} seconds!")
                print("==================================================================")
                return True
            
            # If we get here, there was an error
            elif attempt < MAX_RETRIES:
                self.log_error(f"Download failed. Retrying in {RETRY_DELAY} seconds...")
                print("==================================================================")
                time.sleep(RETRY_DELAY)
                
            # If the download failed
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                return False
              
        return False
    
    def download_album(self):
        """ Download an album"""
        url = input("Enter Spotify Album url:- ").strip()
        
        if not url:
            print("No URL provided")
            return False
        
        # Validate URL
        if not self.validate_spotify_url(url):
            print("Invalid Spotify URL. Please enter a valid Spotify track URL")
            return False

        # Get user preferences
        self.get_user_preferences()
        print("===========================================================================")
        print(f" ============== Starting Album download. This may take a few minutes")
        start_time = time.time()
        output_template = str(self.__output_dir / "{artist}/{album}/{title}.{output-ext}")
        
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"============== Downloading Album URL: attempt {attempt} of {MAX_RETRIES} ==============")
            result = self.run_download(url, output_template)
            
            if hasattr(result, 'returncode'):
                if result.returncode == 100:
                    self.log_error(f"Non - retryable error for {url}: Metadata TypeError")
                    return False
                elif result.returncode == 101:
                    self.log_error(f"Non-retryable error for {url}: No results found")
                    return False
                    
            # Check if download was successful as well as record time it took to complete download
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                elapsed_time = time.time() - start_time
                self.log_success(f"Successfully downloaded album: took {elapsed_time:.1f} seconds!")
                print("==================================================================")                
                return True
            
            # If we get here, there was an error
            if attempt < MAX_RETRIES:
                self.log_error(f"Download failed. Retrying in {RETRY_DELAY} seconds...")
                print("==================================================================")
                time.sleep(RETRY_DELAY)
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                print("==================================================================")                
                return False
            
        return False
            
    def download_playlist(self):
        url = input("Enter Spotify Playlist url:- ").strip()
        
        if not url:
            print("No URL provided")
            return False
        
        # Validate URL
        if not self.validate_spotify_url(url):
            print("Invalid Spotify URL. Please enter a valid Spotify track URL")
            return False
    
        self.get_user_preferences()
        print("===========================================================================")
        print(f"============== Starting Playlist download. This may take a few minutes")
        start_time = time.time()
        output_template = str(self.__output_dir / "{playlist}/{title}.{output-ext}")
        
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"============== Downloading Playlist URL: Attempt {attempt}/{MAX_RETRIES} ==============")
            result = self.run_download(
                url, 
                output_template,
                ["--playlist-numbering", "--playlist-retain-track-cover"])
            
            if hasattr(result, 'returncode'):
                if result.returncode == 100:
                    self.log_error(f"Non -retryable error for {url}: Metadata TypeError")
                    return False
                elif result.returncode == 101: # No results found
                    self.log_error(f"Non -retryable error for {url}: No results found")
                    return False
                
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                elapsed_time = time.time() - start_time
                self.log_success(f"Successfully downloaded: {url} in {elapsed_time:.1f} seconds!")
                print("==================================================================")                                
                return True
            
            elif attempt < MAX_RETRIES:
                self.log_error(f"Download failed. Retrying in {RETRY_DELAY} seconds...")
                print("==================================================================")                
                time.sleep(RETRY_DELAY)
            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {url}")
                print("==================================================================")                
                return False
            
        return False

    def download_from_file(self):
        """ Download various links from a file """
        filepath = input("Enter the directory of the file:- ").strip()
        
        if not filepath or not os.path.exists(filepath):
            self.log_failure(f"File not found: {filepath}")
            return False
        self.get_user_preferences()
        
        try:
            with open(filepath, 'r') as file:
                file_lines = [line.rstrip() for line in file if line.strip()]
        except FileNotFoundError:
            self.log_failure(f" File not found: {filepath}")
            return False
        except Exception as e:
            self.log_failure(f"Error reading the file: {e}")
            return False
        if not file_lines:
            self.log_failure("No URLs found in the text file")
            return False
        
        success_count = 0 # How many urls download successfully
        failed_count = 0 # How many urls failed to download
        
        for i, url in enumerate(file_lines, 1):
            print("===========================================================================")
            self.log_success(f"Processing URL {i}/{len(file_lines)}: {url}")
            
            clean_url = url.split('#')[0].strip()
            
            # Check if URL is already downloaded
            if url.endswith("# DOWNLOADED"):
                self.log_success(f"Skipping already downloaded URL: {url}")
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
                print("===========================================================================")
                print(f"==============Downloading URL {i}: Attempt {attempt} of {MAX_RETRIES} tries ==============")
                
                try:
                    result = self.run_download(url, output_template, additional_args)
                    
                    if hasattr(result, 'returncode'):
                        if result.returncode == 100: # Metadata TypeError
                            self.log_error(f"Non -retryable error for {url}: Metadata TypeError")
                            non_retry_error = True
                            break
                        elif result.returncode == 101: # No results found
                            self.log_error(f"Non -retryable error for {url}: No results found")
                            non_retry_error = True
                            break
                        
                    if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                        success = True
                        break
                    elif attempt < MAX_RETRIES:
                        self.log_error(f"Download failed. Retrying in {RETRY_DELAY} seconds...")
                        time.sleep(RETRY_DELAY)
                except Exception as e:
                    self.log_failure(f"Exception during the download {e}")
                    
            if success:
                success_count += 1
                self.log_success(f"Successfully download {url}")
                
                if "#" in url:
                    # Keep existing comments before # and add DOWNLOADED
                    parts = url.split('#')
                    file_lines[i-1] = f"{parts[0].strip()} # DOWNLOADED"
                else:
                    file_lines[i-1] = f"{clean_url} # DOWNLOADED"
            else:
                failed_count += 1
                self.log_failure(f"Failed download {url}")
            if "#" in url:
                parts = url.split('#')
                file_lines[i-1] = f"{parts[0].strip()} # FAILED"
            else:
                file_lines[i-1] = f"{clean_url} # FAILED"
        
        try: 
            with open(filepath, 'w') as file:
                file.write("\n".join(file_lines))    
        except Exception as e:
            self.log_failure(f"Error updating the file: {e}") 
        self.log_failure(f"Failed to download playlist after {MAX_RETRIES} attempts: {url}")
        return failed_count == 0
    
    def search_a_song(self):
        """ Search for a song and download"""    
        
        song_query = input("What is the name of the song you're looking for: ").strip()

        if not song_query:
            print("No input provided")
            return False
        
        self.get_user_preferences()
        search_time = time.time()
        print("Searching for the song. Browsing through the web.")
        
        output_template = str(self.__output_dir / "{title}.{output-ext}")
        
        for attempt in range(1, MAX_RETRIES + 1):
            print("===========================================================================")
            print(f"Search and download attempt: {attempt} of {MAX_RETRIES}:")
            result = self.run_download(song_query, output_template)
            
            
            if hasattr(result, 'returncode'):
                if result.returncode == 100: 
                    self.log_error(f"Non -retryable error: Metadata TypeError")
                    return False
                elif result.returncode == 101: 
                    self.log_error(f"Non -retryable error: No results found")
                    return False
                
            if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
                self.log_success(f"Successfully downloaded: {song_query}")
                print("==================================================================")                
                return True
            
            elif attempt < MAX_RETRIES:
                self.log_error(f"Download failed. Retrying in {RETRY_DELAY} seconds....")
                print("==================================================================")                                
                time.sleep(RETRY_DELAY)

            else:
                self.log_failure(f"Failed to download after {MAX_RETRIES} attempts: {song_query}")
                print("==================================================================")                                
                return False   

    # Special download functions -------------------------------------------------------
    def download_user_playlist(self):
        """
        Download a user's playlist (requires authentication)
        """
        print("\n=== User Playlist Download ===")
        print("Note: This requires Spotify authentication")
        print("This requires a Spotify Account")
        print("You will be redirected to the Spotify website for authorization")
        
        self.get_user_preferences()
        output_template = str(self.__output_dir / "{playlist}/{title}.{output-ext}")
        
        try:
            print("Downloading user's playlist from Spotify...")
            result = subprocess.run([
                "spotdl",
                "download",
                "all-user-playlists",
                "--user-auth",
                "output", output_template,
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
                self.log_error("Metadata Type Error")
                return False
            
            if "LookupError: No results found for song:" in stderr:
                self.log_error("No results found")
                return False
            
            # ------------ RETRYABLE ERROR ------------
            if "AudioProviderError" in stderr:
                self.log_error(f"YT-DLP audio provider error")
            # -----------------------------------------------------------------------------------

            if result.stdout:
                print(f"spotdl output: {result.stdout.strip()}")
            
            if result.stderr and not ("AudioProviderError" in stderr):
                self.log_error(f"spotdl stderr: {result.stderr.strip()}")
            
            if result.returncode == 0:
                self.log_success("Successfully downloaded user playlists")
                print("==================================================================")                                
                return True
            else:
                self.log_failure(f"Failed to download user playlists. Return code: {result.returncode}")
                print("==================================================================")                                                
                return False
            
        except Exception as e:
            self.log_error(f"Unexpected exception: {e}")
            print("==================================================================")                                
            return False
        
    def download_user_liked_songs(self):
        """Download a user's liked songs"""
        print("\n=== User Liked Song's Download ===")
        print("Note: This requires Spotify authentication")
        print("This requires a Spotify Account")
        print("You will be redirected to the Spotify website for authorization")
        print("==================================================================")                                
        
        self.get_user_preferences()
        output_template = str(self.__output_dir / "{title}/{artist}.{output-ext}")
        
        try:
            print("==================================================================")                                
            print("Downloading the User's Liked Song's from Spotify")
            result = subprocess.run([
                "spotdl",
                "download",
                "saved",
                "--user-auth",
                "--output", output_template,
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
                self.log_error(f"YT-DLP audio provider error")

            if result.stdout:
                self.log_success(f"spotdl output: {result.stdout.strip()}")
            
            if result.stderr and not ("AudioProviderError" in stderr):
                self.log_failure(f"spotdl stderr: {result.stderr.strip()}")
            
            if result.returncode == 0:
                self.log_success("Successfully downloaded user playlist")
                print("==================================================================")                  
                return True
            else:
                self.log_failure(f"Failed to download user playlists. Return code: {result.returncode}")
                print("==================================================================")  
                return False
            
        except Exception as e:
            self.log_error(f"Unexpected exception: {e}") 
            print("==================================================================")              
            return False

    def download_user_saved_albums(self):
        """ Download a user's saved albums """
        print("\n=== User Playlist Download ===")
        print("Note: This requires Spotify authentication")
        print("This requires a Spotify Account")
        print("You will be redirected to the Spotify website for authorization")
        
        self.get_user_preferences()
        output_template = str(self.__output_dir / "{artist}/{album}/{title}.{output-ext}")
        print("==================================================================")
        try:
            print("Downloading the User's Saved Albums")
            result = subprocess.run([
                "spotdl",
                "download",
                "all-user-saved-albums",
                "--user-auth",
                "--output", output_template,
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
                self.log_error("Metadata Type Error")
                return False
            
            if "LookupError: No results found for song:" in stderr:
                self.log_error("No results found")
                return False
            
            # ------------ RETRYABLE ERROR ------------
            if "AudioProviderError" in stderr:
                self.log_error(f"YT-DLP audio provider error")
            # -----------------------------------------------------------------------------------

            if result.stdout:
                print(f"spotdl output: {result.stdout.strip()}")
            
            if result.stderr and not ("AudioProviderError" in stderr):
                self.log_failure(f"spotdl stderr: {result.stderr.strip()}")
            
            if result.returncode == 0:
                self.log_success("Successfully downloaded user saved albums")
                print("==================================================================")
                return True
            else:
                self.log_failure(f"Failed to download user saved albums. Return code: {result.returncode}")
                print("==================================================================")
                return False
            
        except Exception as e:
            self.log_error(f"Unexpected exception: {e}") 
            return False

    # Spotdl helpers ----------------------------------------------------------------------------
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
                    print(f"spotdl version: {version}")
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
                print("Could not determine spotdl version")
                return False
        else:
            print("spotdl not found. Installing...")
            
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "spotdl"])
                print("spotdl installed successfully")
                return True
            except subprocess.CalledProcessError as e:
                print(f"Failed to install spotdl: {e}")
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
            print(f"Could not get spotdl help: {e}")
    
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
    print("==================================================================")
    print("Initializing Spotify Downloader...")
    
    # Check spotdl installation
    if not Downloader.check_spotdl():
        print("==================================================================")
        print("\nFailed to install spotdl. Please install it manually using:")
        print("pip install spotdl")
        print("Then run the program again.")
        print("==================================================================")
        return
    
    downloader = Downloader()
    
    while True:
        display_menu()
        print("==================================================================")
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
            "10": Downloader.show_spotdl_help,
            "11": Downloader.program_info,
        }
        
        if choice == "12":
            print("\nThank you for using Spotify Downloader. Goodbye!")
            print("==================================================================")
            break
        
        action = actions.get(choice)
        if action:
            action()
        else:
            print("==================================================================")
            print("Invalid choice. Please enter a number between 1 and 12.")
            continue
        
        # Ask if user wants to continue (except for help/info actions)
        if choice not in ["10", "11"]:
            cont = input("\nDo you want to perform another operation? (y/n): ").strip().lower()
            if cont not in ['y', 'yes']:
                print("==================================================================")
                print("\nThank you for using Spotify Downloader. Goodbye!")
                break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        print("Please check the error log for details.")
        
