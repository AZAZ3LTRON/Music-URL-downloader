# Managers Module Documentation

The `managers/` folder contains utility modules for managing files, resuming downloads, and scheduling tasks.

## Folder Overview

This module provides management utilities that support the core download functionality:
- **File Management**: Duplicate detection and file organization
- **Resume Management**: Saving and resuming interrupted batch downloads
- **Schedule Management**: Scheduling automatic downloads at specific times

---

## Files

### `file_manager.py`
**Purpose**: Provides file management utilities including duplicate detection and file organization by artist.

**How it works**:

1. **`hash_file(filepath, blocksize=65536)`**:
   - Calculates MD5 hash of a file for duplicate detection
   - Reads file in chunks (64KB blocks) to handle large files efficiently
   - Returns hexadecimal hash string
   - Uses `hashlib.md5()` for hashing

2. **`detect_duplicates(directory)`**:
   - Recursively walks through directory tree
   - Calculates MD5 hash for each file
   - Maintains dictionary of seen hashes
   - Identifies duplicates by comparing hashes
   - Logs duplicate pairs (duplicate file path and original file path)
   - Returns list of duplicate tuples: `[(duplicate_path, original_path), ...]`

3. **`organize_files(output_dir)`**:
   - Scans output directory for MP3 files
   - Parses filename format: `"Artist - Title.mp3"`
   - Extracts artist name from filename
   - Creates artist-named subdirectory if it doesn't exist
   - Moves file into artist's folder
   - Skips files that are already in correct location
   - Uses `shutil.move()` for file operations

**Key Features**:
- Efficient duplicate detection using MD5 hashing
- Automatic file organization by artist
- Safe file operations (checks before moving)
- Recursive directory scanning

**Dependencies**:
- `os` - File system operations
- `hashlib` - MD5 hashing
- `shutil` - File moving operations
- `utils.logger` - Logging functions

**Usage**: 
- Called from `menus.management_menu` for duplicate detection and file organization
- Can be used programmatically for batch file management

---

### `resume_manager.py`
**Purpose**: Manages saving and resuming interrupted batch downloads.

**How it works**:

1. **`save_progress(pending_tracks)`**:
   - Saves list of pending tracks to `data/download_progress.json`
   - Creates JSON file with track list
   - Used to save state before starting batch download
   - Logs success or failure

2. **`resume_batch(config)`**:
   - Loads saved progress from `data/download_progress.json`
   - Handles missing file gracefully (returns early)
   - Handles corrupted JSON gracefully
   - Checks if there are tracks to resume
   - Calls `batch_download` with saved track list
   - Clears progress file after successful completion
   - Logs progress and completion

**Key Features**:
- Progress persistence across application restarts
- Graceful error handling
- Automatic cleanup after completion
- Works with async batch downloader

**Dependencies**:
- `json` - JSON file operations
- `asyncio` - Async operations
- `utils.logger` - Logging
- `constants.PROGRESS_FILE` - Progress file path
- `downloader.base_downloader.batch_download` - Core download function

**Usage**: 
- Called from `menus.automation_menu` to resume interrupted downloads
- `save_progress` should be called before starting batch downloads (if implemented)

---

### `schedule_manager.py`
**Purpose**: Provides functionality to schedule automatic downloads at specific times.

**How it works**:

1. **`schedule_download(config)`**:
   - Prompts user for time in HH:MM format (24-hour clock)
   - Creates a job function that:
     - Loads tracks from `tracks_file`
     - Checks which tracks are already downloaded
     - Downloads only pending tracks using batch download
     - Logs progress
   - Schedules job to run daily at specified time using `schedule` library
   - Runs infinite loop checking for pending jobs
   - Executes job when scheduled time arrives
   - Continues running until interrupted (Ctrl+C)

2. **Helper Functions** (`load_tracks`, `load_playlists`):
   - Duplicate implementations of loader functions
   - Used within scheduled job context
   - Load JSON data from files

**Key Features**:
- Daily scheduled downloads
- Automatic duplicate detection before downloading
- Runs continuously until interrupted
- Uses `schedule` library for time-based job execution

**Dependencies**:
- `schedule` - Job scheduling library
- `time` - Time operations
- `asyncio` - Async batch downloads
- `json` - JSON file operations
- `utils.logger` - Logging
- `utils.track_checker` - Check downloaded files
- `downloader.base_downloader.batch_download` - Core download function

**Usage**: 
- Called from `menus.automation_menu` to set up scheduled downloads
- Runs as a blocking operation (keeps terminal open)

**Note**: The scheduled job runs in the same process, so the application must remain running for scheduled downloads to execute.

---

### `__init__.py`
**Purpose**: Makes the managers folder a Python package.

**How it works**: Empty or contains package-level imports/exports.

**Usage**: Allows importing modules from the managers package.

