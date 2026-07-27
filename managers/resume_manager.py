import json
from utils.logger import log_info, log_error
from utils.constants import PROGRESS_FILE

def save_progress(pending_tracks):
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(pending_tracks, f, indent=2)
        log_info("Saved download progress.")
    except Exception as e:
        log_error(f"Failed to save progress: {e}")

def resume_batch(config):
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            pending_tracks = json.load(f)
    except FileNotFoundError:
        log_info("No saved progress found.")
        return
    except Exception as e:
        log_error(f"Error reading progress: {e}")
        return

    if not pending_tracks:
        log_info("No tracks to resume.")
        return

    from downloader.base_downloader import batch_download
    import asyncio

    log_info(f"Resuming batch download of {len(pending_tracks)} tracks...")
    asyncio.run(batch_download(pending_tracks, config["output_dir"], config["audio_format"]))

    # After successful download clear progress file
    try:
        with open(PROGRESS_FILE, "w") as f:
            json.dump([], f)
        log_info("Cleared progress file.")
    except Exception as e:
        log_error(f"Failed to clear progress file: {e}")
