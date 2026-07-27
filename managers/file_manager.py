import os
import hashlib
from utils.logger import log_info, log_warning

def hash_file(filepath, blocksize=65536):
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        buf = f.read(blocksize)
        while buf:
            hasher.update(buf)
            buf = f.read(blocksize)
    return hasher.hexdigest()

def detect_duplicates(directory):
    seen_hashes = {}
    duplicates = []

    for root, _, files in os.walk(directory):
        for file in files:
            filepath = os.path.join(root, file)
            try:
                file_hash = hash_file(filepath)
                if file_hash in seen_hashes:
                    duplicates.append((filepath, seen_hashes[file_hash]))
                else:
                    seen_hashes[file_hash] = filepath
            except Exception as e:
                log_warning(f"Skipping {filepath}: {e}")

    if duplicates:
        log_warning("Duplicates found:")
        for dup, orig in duplicates:
            log_warning(f"Duplicate: {dup} (original: {orig})")
    else:
        log_info("No duplicates found.")

def organize_files(output_dir):
    import shutil
    try:
        # Collect all mp3s first so moves don't interfere with walking
        mp3s = []
        for root, _, files in os.walk(output_dir):
            for file in files:
                if file.endswith(".mp3"):
                    mp3s.append(os.path.join(root, file))

        for src in mp3s:
            file = os.path.basename(src)
            artist = file.split(" - ")[0].strip()
            artist_dir = os.path.join(output_dir, artist)
            dst = os.path.join(artist_dir, file)
            if src == dst:
                continue
            os.makedirs(artist_dir, exist_ok=True)
            if not os.path.exists(dst):
                shutil.move(src, dst)
                log_info(f"Moved {file} to {artist_dir}")
    except Exception as e:
        log_info(f"Error organizing files: {e}")
