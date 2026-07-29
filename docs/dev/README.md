# Developer Documentation

Technical documentation for HARMONI's codebase.

## Architecture

| Module | Description |
|--------|-------------|
| [Root Files](root-files.md) | Entry points (`main.py`, `gui_main.py`) and configuration |
| [Downloader](downloader.md) | Core download functionality and yt-dlp integration |
| [Menus](menus.md) | Interactive CLI menu system |
| [Managers](managers.md) | File management, sync, backup, and scheduling |
| [Utils](utils.md) | Logging, loading, and system utilities |
| [Tools](tools.md) | Library management tools |

## Data

| Doc | Description |
|-----|-------------|
| [Data & Export](data-export.md) | Data storage and export formats |
| [History](history.md) | Historical prototypes and deprecated code |

## Project Structure

```
harmoni/
├── main.py              # CLI entry point
├── gui_main.py          # GUI entry point
├── config.py            # Configuration management
├── constants.py         # App constants
├── downloader/          # Download logic
├── menus/               # CLI menus
├── managers/            # File/sync/backup managers
├── tools/               # Utility tools
├── utils/               # Shared utilities
├── gui/                 # PySide6 GUI
│   ├── views/           # UI screens
│   ├── dialogs/         # Popup dialogs
│   └── workers/         # Background threads
├── spotify_api/         # Spotify integration
└── data/                # Runtime data storage
```

## Contributing

1. Read the module documentation before modifying code
2. Follow existing code patterns and style
3. Test changes with both GUI and CLI
4. Update relevant documentation
