import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from colorama import Fore, Style

class DownloadHistory:
    """Records only user‑supplied URLs / search queries (no status)."""

    def __init__(self, history_file: Path = Path("logs/download_history.log")):
        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.history_file.exists():
            self.history_file.touch()
        self._lock = threading.Lock()

    def add_input(self, url: str, item_type: str):
        """Log the exact URL or search term the user gave."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "type": item_type,
        }
        with self._lock:
            with open(self.history_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def _read_entries(self) -> List[Dict]:
        entries = []
        if not self.history_file.exists():
            return entries
        with self._lock:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        return entries

    def get_history(self, limit: int = None) -> List[Dict]:
        """Most recent entries first."""
        entries = self._read_entries()
        if limit:
            entries = entries[-limit:]
        return list(reversed(entries))

    def clear_history(self):
        with self._lock:
            self.history_file.unlink(missing_ok=True)
            self.history_file.touch()

    def get_stats(self) -> Dict:
        entries = self._read_entries()
        by_type = {}
        for e in entries:
            t = e.get('type', '?')
            by_type[t] = by_type.get(t, 0) + 1
        return {"total": len(entries), "by_type": by_type}

    def interactive_menu(self):
        from utils.EnhancedMenu import Enhanced_Menu
        while True:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("INPUT HISTORY", "All URLs / queries entered")

            stats = self.get_stats()
            print(f"{Fore.CYAN}Total inputs: {stats['total']}{Style.RESET_ALL}")
            print(f"By type: {stats['by_type']}")
            print()

            Enhanced_Menu.print_menu_item(1, "Show last 10 inputs")
            Enhanced_Menu.print_menu_item(2, "Show last 50 inputs")
            Enhanced_Menu.print_menu_item(3, "Show all inputs")
            Enhanced_Menu.print_menu_item(4, "Clear history")
            Enhanced_Menu.print_menu_item(5, "Back")

            choice = Enhanced_Menu.get_input("Select option", "int", 1, 5)
            if choice in (1, 2, 3):
                limit = {1: 10, 2: 50, 3: None}[choice]
                self._display_entries(limit)
            elif choice == 4:
                if Enhanced_Menu.get_input("Clear all history? (y/n)", "yn", default=False):
                    self.clear_history()
                    Enhanced_Menu.print_status("History cleared", "success")
            else:
                break
            input("\nPress Enter to continue...")

    def _display_entries(self, limit: int = None):
        entries = self.get_history(limit)
        if not entries:
            print(f"{Fore.YELLOW}No inputs recorded yet.{Style.RESET_ALL}")
            return
        for i, entry in enumerate(entries, 1):
            ts = entry['timestamp'][:19]
            url = entry['url']
            url_disp = url[:80] + '...' if len(url) > 80 else url
            t = entry.get('type', '?')
            icon = {'track':'🎵','album':'💿','playlist':'📋','artist':'🎤','search':'🔍'}.get(t, '❓')
            print(f"{i:2}. {icon} {Fore.CYAN}{t.upper():8}{Style.RESET_ALL} {ts}  {url_disp}")