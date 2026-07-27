import os
import glob
import shutil
from utils.logger import log_info, log_warning, log_error
from utils.constants import VALID_AUDIO_EXTENSIONS


def cleanup_after_download(config: dict) -> dict:
    """
    Perform post-download cleanup operations.
    
    Config options used:
    - auto_cleanup: Whether to perform cleanup (must be True)
    - output_dir: Directory to clean
    
    Returns dict with cleanup statistics.
    """
    if not config.get("auto_cleanup", True):
        return {"skipped": True, "reason": "auto_cleanup disabled"}
    
    output_dir = config.get("output_dir", "music")
    
    stats = {
        "temp_files_removed": 0,
        "empty_dirs_removed": 0,
        "partial_files_removed": 0,
        "cache_cleared": False
    }
    
    # Clean temporary files
    stats["temp_files_removed"] = remove_temp_files(output_dir)
    
    # Remove empty directories
    stats["empty_dirs_removed"] = remove_empty_directories(output_dir)
    
    # Clean partial/incomplete downloads
    stats["partial_files_removed"] = remove_partial_downloads(output_dir)
    
    # Clear yt-dlp cache (optional)
    stats["cache_cleared"] = clear_ytdlp_cache()
    
    total_removed = stats["temp_files_removed"] + stats["empty_dirs_removed"] + stats["partial_files_removed"]
    if total_removed > 0:
        log_info(f"Cleanup complete: removed {total_removed} items")
    
    return stats


def remove_temp_files(directory: str) -> int:
    """
    Remove temporary files created during downloads.
    Common patterns: .part, .ytdl, .temp, .tmp
    """
    temp_patterns = ["*.part", "*.ytdl", "*.temp", "*.tmp", "*.partial"]
    removed_count = 0
    
    if not os.path.exists(directory):
        return 0
    
    for pattern in temp_patterns:
        for filepath in glob.glob(os.path.join(directory, "**", pattern), recursive=True):
            try:
                os.remove(filepath)
                log_info(f"Removed temp file: {os.path.basename(filepath)}")
                removed_count += 1
            except OSError as e:
                log_warning(f"Could not remove {filepath}: {e}")
    
    return removed_count


def remove_empty_directories(directory: str) -> int:
    """
    Remove empty subdirectories within the output directory.
    Does not remove the root output directory.
    """
    removed_count = 0
    
    if not os.path.exists(directory):
        return 0
    
    # Walk bottom-up to remove nested empty dirs first
    for root, dirs, files in os.walk(directory, topdown=False):
        # Skip the root directory
        if root == directory:
            continue
        
        # Check if directory is empty (no files and no subdirs)
        if not os.listdir(root):
            try:
                os.rmdir(root)
                log_info(f"Removed empty directory: {os.path.basename(root)}")
                removed_count += 1
            except OSError as e:
                log_warning(f"Could not remove directory {root}: {e}")
    
    return removed_count


def remove_partial_downloads(directory: str) -> int:
    """
    Remove incomplete downloads (files under 100KB that aren't valid).
    This helps clean up corrupted or incomplete files.
    """
    min_valid_size = 100 * 1024  # 100KB minimum for valid audio
    removed_count = 0
    
    if not os.path.exists(directory):
        return 0
    
    for root, _, files in os.walk(directory):
        for file in files:
            filepath = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()
            
            # Only check audio files
            if ext not in VALID_AUDIO_EXTENSIONS:
                continue
            
            try:
                size = os.path.getsize(filepath)
                if size < min_valid_size:
                    os.remove(filepath)
                    log_warning(f"Removed potentially corrupted file ({size} bytes): {file}")
                    removed_count += 1
            except OSError as e:
                log_warning(f"Could not check/remove {filepath}: {e}")
    
    return removed_count


def clear_ytdlp_cache() -> bool:
    """
    Clear yt-dlp cache directory.
    Cache is typically at ~/.cache/yt-dlp or similar.
    """
    cache_locations = [
        os.path.expanduser("~/.cache/yt-dlp"),
        os.path.expanduser("~/AppData/Local/yt-dlp"),  # Windows
        os.path.expanduser("~/.yt-dlp")
    ]
    
    cleared = False
    
    for cache_dir in cache_locations:
        if os.path.exists(cache_dir) and os.path.isdir(cache_dir):
            try:
                # Only remove cache files, not the directory itself
                for item in os.listdir(cache_dir):
                    item_path = os.path.join(cache_dir, item)
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                log_info(f"Cleared yt-dlp cache at: {cache_dir}")
                cleared = True
            except OSError as e:
                log_warning(f"Could not clear cache at {cache_dir}: {e}")
    
    return cleared


def cleanup_specific_patterns(directory: str, patterns: list) -> int:
    """
    Remove files matching specific glob patterns.
    
    Args:
        directory: Directory to search
        patterns: List of glob patterns (e.g., ["*.log", "*.bak"])
    
    Returns:
        Number of files removed
    """
    removed_count = 0
    
    if not os.path.exists(directory):
        return 0
    
    for pattern in patterns:
        for filepath in glob.glob(os.path.join(directory, "**", pattern), recursive=True):
            try:
                if os.path.isfile(filepath):
                    os.remove(filepath)
                    removed_count += 1
            except OSError:
                pass
    
    return removed_count


def get_cleanup_preview(config: dict) -> dict:
    """
    Preview what would be cleaned without actually removing files.
    Useful for user confirmation.
    """
    output_dir = config.get("output_dir", "music")
    
    preview = {
        "temp_files": [],
        "empty_dirs": [],
        "partial_files": []
    }
    
    if not os.path.exists(output_dir):
        return preview
    
    # Find temp files
    temp_patterns = ["*.part", "*.ytdl", "*.temp", "*.tmp", "*.partial"]
    for pattern in temp_patterns:
        for filepath in glob.glob(os.path.join(output_dir, "**", pattern), recursive=True):
            preview["temp_files"].append(filepath)
    
    # Find empty directories
    for root, dirs, files in os.walk(output_dir, topdown=False):
        if root != output_dir and not os.listdir(root):
            preview["empty_dirs"].append(root)
    
    # Find partial files
    min_valid_size = 100 * 1024
    for root, _, files in os.walk(output_dir):
        for file in files:
            filepath = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()
            
            if ext in VALID_AUDIO_EXTENSIONS:
                try:
                    if os.path.getsize(filepath) < min_valid_size:
                        preview["partial_files"].append(filepath)
                except OSError:
                    pass
    
    return preview

