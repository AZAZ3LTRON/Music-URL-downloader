# Managers module exports
from managers.file_manager import hash_file, detect_duplicates, organize_files
from managers.resume_manager import resume_batch
from managers.schedule_manager import schedule_download
from managers.cleanup_manager import cleanup_after_download, get_cleanup_preview
from managers.backup_manager import backup_json_file, backup_all, list_backups, restore_backup
from managers.sync_manager import sync_exportify_folder, run_sync_once, get_sync_status

__all__ = [
    # File manager
    "hash_file",
    "detect_duplicates", 
    "organize_files",
    # Resume manager
    "resume_batch",
    # Schedule manager
    "schedule_download",
    # Cleanup manager
    "cleanup_after_download",
    "get_cleanup_preview",
    # Backup manager
    "backup_json_file",
    "backup_all",
    "list_backups",
    "restore_backup",
    # Sync manager
    "sync_exportify_folder",
    "run_sync_once",
    "get_sync_status"
]

