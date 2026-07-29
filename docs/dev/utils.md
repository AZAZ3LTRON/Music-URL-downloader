# Utils Module Documentation

The `utils/` folder contains utility functions used throughout the application, including logging, data loading, system checks, link verification.

## Folder Overview

This module provides foundational utilities that support all other modules:
- **Logging**: Terminal output and file logging
- **System**: System resource monitoring
- **Archiving**: Archiving
- **System Utilities**: Dependency checking and log viewing
---

## Files

### `constants.py`

### `helpers.py`
**Purpose**: .

**How it works**:

1. **`safe_name(name, fallback: str = "Playlist") -> str`**:

2. **`load_archive(self, archive_path: Path) -> Set[str]:`**:

3. **`append_archive(self, archive_path: Path, video_id: str, lock: threading.Lock)`**

**Dependencies**:
- `re` - System and process utilities
- `threading`
- `pathlib`
- `typing`

**Usage**: 
- Called from `menus.tools_menu` for system diagnostics
- Can be used before large batch downloads to verify system readiness

### `history_logger.py`

### `logger.py`
**Purpose**: Provides logging functionality with colored terminal output and persistent file logging.

**How it works**:

1. **`setup_logs()`**:
   - Configures Python's `logging` module
   - Sets log file to `app.log` (from constants)
   - Sets log level to INFO, for errors the level is set to ERROR
   - Configures format: `"%(asctime)s - %(levelname)s - %(funcName)s - %(lineno)d - %(message)s"` for errors, the format is `"%(asctime)s - %(levelname)s - %(message)s"`

2. **`log_success(self, message: str, console: bool = True)`**:
   - Prints message in GREEN color to terminal
   - Logs message at INFO level to file

3. **`log_failure(self, message: str, console: bool = True)`**:
   

4. **`log_error(self, message: str, exc_info=False, console: bool = True)`**:
   - Prints message in RED color to terminal
   - Logs message at ERROR level to file

5. **`log_warning(msg)`**:
   - Prints message in YELLOW color to terminal
   - Logs message at WARNING level to file

**Key Features**:
- Color-coded terminal output for better readability
- Persistent logging to `app.log` file
- Consistent logging format across application
- Cross-platform color support via colorama

**Dependencies**:
- `logging` - Python logging module
- `re` - 
- `colorama` - Colored terminal output
- `threading` - 
- `pathlib` - 
- `constants.LOG_FILE` - Log file path

**Usage**: Imported by virtually every module in the application for consistent logging.

---




### `utilities.py`
**Purpose**: Provides functions to that check if require system dependencies exist

**How it works**:


**Dependencies**:
- `os` - File system operations
- `csv` - CSV file parsing
- `json` - JSON file parsing
- `utils.logger` - Logging functions

**Usage**: 
- Called from menu handlers to load data
- Used throughout application when track/playlist data is needed

**Data Formats**:
- **Tracks JSON**: `{"tracks": [{"artist": "...", "album": "...", "track": "...", "uri": "..."}]}`
- **Playlists JSON**: `{"playlists": [{"name": "...", "items": [...]}]}`
- **Exportify CSV**: Columns include "Artist Name(s)" and "Track Name"

---


---

### `validators.py`
**Purpose**: Validates links enter to both spotify & youtube music downloadee



**Dependencies**:
- `os` - File system operations
- `constants.VALID_AUDIO_EXTENSIONS` - Valid audio extensions
- `utils.logger` - Logging functions

**Usage**: 
- Called from `menus.downloads_menu` to avoid duplicates and show accurate counts
- Used by the per-playlist song selection UI to auto-uncheck existing songs

---

### `__init__.py`
**Purpose**: Makes the utils folder a Python package.

**How it works**: May contain package-level imports/exports for convenience.

**Usage**: Allows importing modules from the utils package.

