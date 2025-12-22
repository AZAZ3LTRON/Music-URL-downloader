"""
Spotify Spotify Playlist/Album/Track Downloader

This is a simple to use downloader that can help in downloading albums/playlist/single tracks etc from Spotfiy
With Spotfiy allying itself with a 

Its features a:
- 320kbps download quality
- Metadata Support
- Organizes albums by artist
- Marks links as DOWNLOADED or FAILED
- Logs successful, failed & errors in between downloads
- Retry failed 
"""

import sys
import os # For directory creation
import subprocess # To run the spotdl in the background
import shutil
import time
from pathlib import Path
from datetime import datetime
import logging
from zipfile import ZipFile

""" =================================================================== CONFIGURATION (Subject to change) =================================================================== """
TEXT_FILE = r"links\spotify_links.txt" # text file location  
TEMPORARY_DOWNLOAD_DIR = r"temporary_downloads" # Temporary download location 
FINAL_MUSIC_DIR = r"Albums" # Final Organization Folder 

MAX_RETRIES = 4 # Retry a download in case of failure 
RETRY_DELAY_TIME = 10 # Seconds between each retry

SUCCESS_LOG_FILE = r"log\success.log" # Logging directory for successful downloads 
ERROR_LOG_FILE = r"log\errors.log" # Logging directory for errors during downloads 

""" =================================================================== LOGGER =================================================================== """
os.makedirs("log", exist_ok=True)
logger = logging.getLogger("Spotify_DOWNLOADER")
logger.setLevel(logging.INFO)

log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

success_download_handler = logging.FileHandler(SUCCESS_LOG_FILE, encoding="utf-8")
success_download_handler.setLevel(logging.INFO)
success_download_handler.setFormatter(log_format)
success_download_handler.addFilter(lambda r: r.levelno == logging.INFO)

# Logger for errors during download
error_download_handler = logging.FileHandler(ERROR_LOG_FILE, encoding= "utf-8")
error_download_handler.setLevel(logging.ERROR)
error_download_handler.setFormatter(log_format)

logger.addHandler(success_download_handler)
logger.addHandler(error_download_handler)

logger.info("=" * 40)
logger.info(f"New download session started at {datetime.now().isoformat()}")
logger.info("=" * 40)

""" =================================================================== DIRECTORY SETUP ==================================================================="""
os.makedirs(TEMPORARY_DOWNLOAD_DIR, exist_ok=True)
os.makedirs(FINAL_MUSIC_DIR, exist_ok=True)

""" =================================================================== FILE READER =================================================================== """
try:
    with open(TEXT_FILE, 'r') as file:
        file_lines = [line.rstrip() for line in file]
except FileNotFoundError:
    logger.error(f"Links file not found: {TEXT_FILE}")
    raise
except Exception as e:
    logger.exception(f"Failed to read links file: {e}")
    raise
    
urls = []
for i, line in enumerate(file_lines):
    if not line:
        continue
    if line.endswith("# DOWNLOADED"): # Skips links marked with # DOWNLOADED
        continue
    urls.append((i, line))

if not urls:
    print("No URLs found in urls.txt")
    exit(0)

"""=================================================================== FUNCTION DEFINITION =================================================================== """
def download_url(url, temp_dir):
    """ Download URL and confirm s
    Logs errors during download process
    Snapshots output
    
    To edit the file you can edit these variables
    """
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"Downloading ({attempt}/{MAX_RETRIES} tries): {url}")
        
        # ----------------------------------------------------------------------------------------
        try:
            before_files = set(Path(temp_dir).rglob("*"))
            result = subprocess.run([
                "spotdl", "download", url,
                "--output", os.path.join(temp_dir, "{artist}/{album}/{title}.{output-ext}"),
                "--overwrite", "skip", # Skip existing files
                "--bitrate", "320k"
            ],
                stdout=sys.stdout,
                stderr=subprocess.PIPE,
                text=True
            )
            stderr = result.stderr or ""
            
            if stderr.strip():
                logger.error(f"{url} - spotdl stderr: {stderr.strip()}")
            
            # Error Handling for specific errors during download process ----------------------------
            # ----- NON - RETRYABLE ERRORS -------------------
            if "TypeError: expected string or bytes-like object, got 'NoneType'" in stderr:
                logger.error(f"{url} - Metadata TypeError (NoneType)")
                return False
            
            if "LookupError: No results found for song:" in stderr:
                logger.error(f"{url} - No results found")
                return False

            # ------- RETRYABLE ERRORS -----------
            if "AudioProviderError" in stderr:
                logger.warning(f"{url} - YT-DLP audio provider error")
            # -------------------------------------------------------------
            
            after_files = set(Path(temp_dir).rglob("*"))
            new_files = after_files - before_files
            
            if result.returncode == 0 and new_files:
                return True
        
        except Exception:
            logger.exception(f"{url} - Unexpected exception")
            
        if attempt <= MAX_RETRIES:
            print(f"Download failed. Retrying in {RETRY_DELAY_TIME} seconds")
            time.sleep(RETRY_DELAY_TIME)
            
    logger.error(f"{url} - Download failed after max retries")
    return False

def zip_album(album_folder_path, zip_dest_path):
    """Zip the album folder into a single zipfile"""
    with ZipFile(zip_dest_path, 'w') as zipf:
        for root, dirs, files in os.walk(album_folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, album_folder_path)
                zipf.write(file_path, arcname)
    print(f"Album zipped to: {zip_dest_path}")

def strip_status_tags(line: str) -> str:
    """Remove/Replace status tags in the text file"""
    return (
        line.replace(" # FAILED", "")
            .replace(" # DOWNLOADED", "")
            .strip()
    )
"""=================================================================== MAIN DOWNLOAD LOOP =================================================================== """
total_urls = len(urls)
print(f"Found {total_urls} links to download")
 
for index, (line_index, url_line) in enumerate(urls, start=1):
    print(f"\n =================================================================== Downloading {index} \ {total_urls} ===================================================================")
    
    retry_link = url_line.endswith("# FAILED")
    url = strip_status_tags(url_line)
    # Call the download function
    download = download_url(url, TEMPORARY_DOWNLOAD_DIR)
    
    # Update the file correspondingly ------------------------------------------------------
    try:
        if download == True:
            print(f"Successfully downloaded: {url}")
            file_lines[line_index] = f"{url_line} # DOWNLOADED"
            logger.info(f"{url} - Successfully downloaded") # Log success
        else:
            print(f"Failed to download after retries: {url}")
            file_lines[line_index] = f"{url_line} # FAILED"
            logger.warning(f"{url} - Failed download")

        with open(TEXT_FILE, 'w') as file:
            file.write("\n".join(file_lines))
    except Exception as e:
        logger.exception(f"Failed to update links file for {url}: {e}")
    # --------------------------------------------------------------------------------------
    
    # Move files once done downloading -----------------------------------------------------
    for root, dirs, files in os.walk(TEMPORARY_DOWNLOAD_DIR):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, TEMPORARY_DOWNLOAD_DIR)
            dest_path = os.path.join(FINAL_MUSIC_DIR, rel_path)
            
            try:
                if os.path.exists(dest_path):
                    print(f"Skipping existing file: {dest_path}")
                    continue

                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.move(file_path, dest_path)
                
            except Exception as e:
                logger.exception(f"Failed to move {file_path} -> {dest_path}: {e}")
    # --------------------------------------------------------------------------------------
    
# Clean up temporary directory
try:
    shutil.rmtree(TEMPORARY_DOWNLOAD_DIR)
except Exception as e:
    logger.exception(f"Failed to clean temporary directory: {e}")
print(f"Downloaded {total_urls} and marking complete!")