# Downloader Module Documentation

The `downloader/` folder contains all core downloading functionality for both Spotify and Youtube Music. It handles downloading music from YouTube Music and Spotify using yt-dlp, spotdl, ytmusicapi etc. It is capable of downloading tracks, albums, playlist and file exports with additional features such as embedding metadata, and retrying failed downloads.

## Folder Overview

This module is the heart of the application's download functionality. It provides:
- Single and batch track downloads
- Playlist downloading with folder organization
- Direct YouTube Music & Spotify link/playlist downloads
- Metadata embedding for downloaded files
- Retry mechanisms for failed downloads
- Verify python libraries
---

## Files

### `SpotifyDownloader.py`
**Purpose**: Core download functions to download music from Spotify.

**How it works**:
1. **`get_user_preference(self)`**:
   
2. **`run_download(self, url: str, output_template: str = None, extra_args: List[str] =None, total_items: int = None, item_desc: str = "item", desc: str = None) -> bool`**:

3. **`_download_item(self)`**:

4. **`download_track(self)`**:

5. **`_download_album(self)`**:

6. **`_download_playlist(self)`**:

7. **`_download_from_file(self, file_path)`**

8. **`search_and_download(self)`**:
   

**Key Features**:
- Download function for Spotify
- Concurrent batch downloads for efficiency
- Progress tracking with tqdm
- Error handling and logging

**Dependencies**:
- `re`, `os`,`random`, `hashlib`, `threading`, `subprocess`, `time`, `asyncio`, `concurrent.futures`, `typing`, `colorama`, `functools`, `pathlib`
- `tqdm` - Progress bars
- `utils.logger` - Logging functions
- `utils.validators`
- `utils.historylogger`
- `utils.helpers`
- `tools.BatchFile`
- `tools.ConfigManager`
- `tools.RetryQueue`
- `tools.RateLimiter`
- `tools.EnhancedMenu`
- `tools.CookieManager`
  
**Usage**: Called from `main_1.py` 
---

### `YoutubeMusicDownloader.py`
**Purpose**: Downloads playlist, albums & tracks from 

**How it works**:
1. **`get_user_preference(self)`**:
   
2. **`run_download(self, url: str, output_template: str = None, extra_args: List[str] =None, total_items: int = None, item_desc: str = "item", desc: str = None) -> bool`**:

3. **`_download_item(self)`**:

4. **`download_track(self)`**:

5. **`_download_album(self)`**:

6. **`_download_playlist(self)`**:

7. **`_download_from_file(self, file_path)`**

8. **`search_and_download(self)`**:

**Dependencies**:
- `re`, `os`,`random`, `hashlib`, `threading`, `subprocess`, `time`, `asyncio`, `concurrent.futures`, `typing`, `colorama`, `functools`, `pathlib`
- `tqdm` - Progress bars
- `utils.logger` - Logging functions
- `utils.validators`
- `utils.historylogger`
- `utils.helpers`
- `tools.BatchFile`
- `tools.ConfigManager`
- `tools.RetryQueue`
- `tools.RateLimiter`
- `tools.EnhancedMenu`
- `tools.CookieManager`

**Usage**: Called from `main_2.py`.


### `Other Functions`

1. **`manage_cookies(self)`**

2. **`check_ffmpeg(self)`**
   
3. **`check_ytdlp(self)`**

4. **`check_spotdl(self)`**

4. **`show_ytdlp_help(self)`**

5. **`check_dependencies(self)`**

6. **`setup_dependencies(self)`**

7. **`program_info(self)`**

8. **`troubleshooting(self)`**

---
