import shutil
import time
from pathlib import Path
import logging
import re
from typing import List, Dict, Optional, Tuple
import json
import sys
import os
from colorama import init, Fore, Style
import threading

from .EnhancedMenu import Enhanced_Menu

init(autoreset=True)

class Logs_Manager:
    """ Log Manager and history viewer for the Downloader"""
    def __init__(self):
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # Define log file paths
        self.success_log_path = self.log_dir / "success.log" # Directory for successful downloads
        self.failed_log_path = self.log_dir / "failed.log"  # Directory for failed downloads
        self.error_log_path = self.log_dir / "error.log" # Directory for errors during downloads
        self._lock = threading.Lock() # Locks the thread
        
        # Initialize loggers
        self.success_logger = None
        self.failed_logger = None
        self.error_logger = None
        self.console_logger = None
        
        # Setup the logs
        self.setup_logs()
        
        # Color map for respective logs
        self.color_map = {
            'success': Fore.GREEN,
            'failed': Fore.RED,
            'error': Fore.YELLOW,
            'warning': Fore.MAGENTA           
        }
        
    def setup_logs(self):
        """Setup all log with format and configuration"""
        
        # Full format for file logs (includes date/time)
        file_format = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(funcName)s - %(lineno)d - %(message)s"
        )
        error_format = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )

        # Console format – only the message, no timestamp
        console_format = logging.Formatter("%(message)s")

        # --- Success log (file only) ---
        self.success_logger = logging.getLogger("successful_downloads")
        self.success_logger.setLevel(logging.INFO)
        self.success_logger.propagate = False
        success_handler = logging.FileHandler(str(self.success_log_path), encoding='utf-8')
        success_handler.setLevel(logging.INFO)
        success_handler.setFormatter(file_format)          # full timestamp in file
        self.success_logger.addHandler(success_handler)

        # --- Failed log (file only) ---
        self.failed_logger = logging.getLogger("failed_downloads")
        self.failed_logger.setLevel(logging.INFO)
        self.failed_logger.propagate = False
        failed_handler = logging.FileHandler(str(self.failed_log_path), encoding='utf-8')
        failed_handler.setLevel(logging.INFO)
        failed_handler.setFormatter(file_format)
        self.failed_logger.addHandler(failed_handler)

        # --- Error log (file only) ---
        self.error_logger = logging.getLogger("Errors")
        self.error_logger.setLevel(logging.ERROR)
        self.error_logger.propagate = False
        error_handler = logging.FileHandler(str(self.error_log_path), encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(error_format)
        self.error_logger.addHandler(error_handler)

        # --- Console logger (terminal) – timestamp‑free ---
        self.console_logger = logging.getLogger("console")
        self.console_logger.setLevel(logging.INFO)        # show INFO and above
        self.console_logger.propagate = False
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_format)      # 👈 only the message
        self.console_logger.addHandler(console_handler)     
        
    # ========== Logging Methods ==============
    def log_success(self, message: str, console: bool = True):
        """ Log successful music downloads"""
        with self._lock:
            if self.success_logger:
                self.success_logger.info(message)
            if console and self.console_logger:
                self.console_logger.info(f"{self.color_map['success']}{message}{Style.RESET_ALL}")
        
    def log_failure(self, message: str, console: bool = True):
        """ Log failed music downloads"""
        with self._lock:
            if self.failed_logger:
                self.failed_logger.info(message)
            if console and self.console_logger:
                self.console_logger.info(f"{self.color_map['failed']}{message}{Style.RESET_ALL}")
            
    def log_error(self, message: str, exc_info=False, console: bool = True):
        """ Log error during music download process"""
        with self._lock:
            if self.error_logger:
                self.error_logger.error(message, exc_info=exc_info)
            if console and self.console_logger:
                self.console_logger.info(f"{self.color_map['error']}{message}{Style.RESET_ALL}")
    
    # =============== Log Statistics & Other function ============
    def log_statistics(self):
        """ Get the statistics for all log files."""
        
        # Stats dictionary to hold all possible records
        stats = {
            'success_count': 0,
            'failed_count': 0,
            'error_count': 0,
            'total_count': 0,
            'last_download': None,
            'success_rate': 0,
            'file_sizes': {},
            'oldest_entry': None,
            'newest_entry': None
        }
        
        # Count entries in each log
        for log_file, key in [(self.success_log_path, 'success_count'), 
                              (self.failed_log_path, 'failed_count'), 
                              (self.error_log_path, 'error_count')]:
            
            # Check if file exist
            if log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        lines = [l for l in f.readlines() if l.strip()]
                        stats[key] = len(lines)
                        stats['total_count'] += len(lines)
                        stats['file_sizes'][log_file.name] = log_file.stat().st_size
                        
                        # Get timestamps from first and last lines
                        if lines:
                            timestamps = []
                            for line in lines[:5] + lines[-5:]:
                                ts_match = self._extract_timestamp(line)
                                if ts_match:
                                    timestamps.append(ts_match)
                                    
                            # 
                            if timestamps:
                                stats['oldest_entry'] = min(timestamps) if timestamps else None
                                stats['newest_entry'] = max(timestamps) if timestamps else None
                
                # Raise error
                except Exception as e:
                    self.log_error(f"Error reading log file {log_file}: {e}", console=False)

        # Calculate Download success rate
        if stats['total_count'] > 0:
            stats['success_rate'] = (stats['success_count'] / stats['total_count']) * 100
            
        return stats
    
    def _extract_timestamp(self, line: str) -> Optional[str]:
        """Extract timestamp from log line"""
        match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', line)
        return match.group() if match else None
    
    def get_common_errors(self, limit: int = 7):
        """ Get the most common error message that occur in the program"""
        error_patterns = {} # Dictionary to store download patterns
        
        # Check if error logs exist
        if not self.error_log_path.exists():
            return []
        
        # Open error logs and extract error messages
        try:
            with open(self.error_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    error_match = re.search(r'ERROR - (.+?)(?:\d+|$)', line)
                    if error_match:
                        error_message = error_match.group(1).strip()
                        
                        # Normalize error message (remove variable parts from line)
                        error_message = re.sub(r'\d+', '#', error_message)
                        error_patterns[error_message] = error_patterns.get(error_message, 0) + 1
        
        except Exception as e:
            self.log_error(f"Error analyzing error log: {e}", console=False)
            
        # Sort by occurence frequency and return top errors
        sorted_errors = sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)
        return sorted_errors[:limit]
    
    def get_recent_activity(self, limit: int = 10):
        """Get most recent download activity"""
        activities = []
        
        for log_file, status, color in [(self.success_log_path, "✅ Success", 'success'),
                                        (self.failed_log_path, "❌ Failed", 'failed')]:
            if log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        for line in lines[-limit:]:
                            if line.strip():
                                activities.append({
                                    'status': status,
                                    'message': line.strip(),
                                    'color': color,
                                    'timestamp': self._extract_timestamp(line)
                                })
                except Exception as e:
                    self.log_error(f"Error reading {log_file}: {e}", console=False)
        
        # Sort by timestamp (most recent first) if available
        activities.sort(key=lambda x: x['timestamp'] if x['timestamp'] else '', reverse=True)
        
        return activities[:limit]
    
    # =============== Display Methods ======================
    def view_logs(self, log_type: str = None, title: str = None, color: str = None):
        """ Display records from log file with formatting"""
        
        # If log_type not provided, ask user
        if log_type is None:
            print(f"\n{Fore.CYAN}Log View Options:{Style.RESET_ALL}")
            print(f"  {Fore.YELLOW}success{Style.RESET_ALL} - View successful downloads") # 
            print(f"  {Fore.YELLOW}failed{Style.RESET_ALL}  - View failed downloads")
            print(f"  {Fore.YELLOW}error{Style.RESET_ALL}   - View error logs")
            print(f"  {Fore.YELLOW}all{Style.RESET_ALL}      - View all logs combined")
            print()
            log_type = Enhanced_Menu.get_input("What logs would you like to view", "str").strip().lower()
        
        # Dictionary stores tuples of all log paths and their color codes
        log_files = {
            'success': (self.success_log_path, 'Successful downloads', self.color_map['success']),
            'failed': (self.failed_log_path, 'Failed downloads', self.color_map['failed']),
            'error': (self.error_log_path, 'Error Logs', self.color_map['error']),
            'all': (None, 'All Logs', Fore.WHITE)
        }
        
        # The user input must be in the dictionary, else error
        if log_type not in log_files:
            Enhanced_Menu.print_status("Invalid log type. Enter a valid log type", "error")
            return
        
        # Parse log 
        log_file, default_title, default_color = log_files[log_type]
        display_title = title or default_title
        display_color = color or default_color
        
        # If user enters all, call support functions
        if log_type == 'all':
            self._display_all_logs()
            return
        
        Enhanced_Menu.clear_screen()
        print(f"\n{Fore.CYAN}{'=' * 80}{Style.RESET_ALL}")
        print(f"{display_color}{display_title:^80}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'=' * 80}{Style.RESET_ALL}")
        
        if not log_file or not log_file.exists():
            Enhanced_Menu.print_status("Log file does not exist", "error")
            return
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = [line.rstrip() for line in f.readlines() if line.strip()]
                
            if not lines:
                Enhanced_Menu.print_status("Log file is empty.", "info")
                return
            
            self._display_paginated(lines, display_color, page_size=20)
        
        except Exception as e:
            Enhanced_Menu.print_status(f"Error reading log file: {e}", "error")
    
    def _display_all_logs(self):
        """ Display all logs in a combined view"""
        stats = self.log_statistics() # Grab stats from log statistics function
        
        Enhanced_Menu.clear_screen()
        print(f"\n{Fore.CYAN}{'=' * 80}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}{'COMBINED LOG VIEW':^80}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'=' * 80}{Style.RESET_ALL}")
        
        # Loop through all paths to display
        for log_file, label, color in [(self.success_log_path, 'SUCCESS', Fore.GREEN),
                                       (self.failed_log_path, 'FAILED', Fore.RED),
                                       (self.error_log_path, 'ERROR', Fore.YELLOW)]:
            if log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        lines = [line.rstrip() for line in f.readlines() if line.strip()]
                    
                    if lines:
                        print(f"\n{color}{label} LOG ({len(lines)} entries):{Style.RESET_ALL}")
                        print(f"{color}{'-' * 40}{Style.RESET_ALL}")
                        for line in lines[-5:]:  # Show last 5 from each
                            display_line = line[:100] + "..." if len(line) > 100 else line
                            print(f"{color}  {display_line}{Style.RESET_ALL}")
                except:
                    pass
        
        input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}") # Self explanatory
    
    def _display_paginated(self, lines: list, color: str, page_size: int = 20):
        """Display log lines with pagination capabilities"""
        total_lines = len(lines)
        total_pages = (total_lines + page_size - 1) // page_size
        current_page = 0
        
        while True:
            start_idx = current_page * page_size
            end_idx = min(start_idx + page_size, total_lines)
            
            print(f"\n{Fore.CYAN}Showing entries {start_idx + 1}-{end_idx} of {total_lines}{Style.RESET_ALL}")
            print("-" * 80)
            
            for i in range(start_idx, end_idx):
                line = lines[i]
                # Truncate long lines
                if len(line) > 100:
                    line = line[:97] + "..."
                print(f"{color}{i+1:4d}: {line}{Style.RESET_ALL}")
            
            print("-" * 80)
            
            # Navigation
            print(f"\n{Fore.CYAN}Navigation:{Style.RESET_ALL}")
            print(f"  {Fore.YELLOW}[N]{Style.RESET_ALL} Next page  {Fore.YELLOW}[P]{Style.RESET_ALL} Previous page")
            print(f"  {Fore.YELLOW}[G]{Style.RESET_ALL} Go to page  {Fore.YELLOW}[S]{Style.RESET_ALL} Search")
            print(f"  {Fore.YELLOW}[E]{Style.RESET_ALL} Export      {Fore.YELLOW}[Q]{Style.RESET_ALL} Quit")
            
            nav = input(f"\n{Fore.CYAN}Enter choice: {Style.RESET_ALL}").strip().lower()
            
            if nav == 'n' and current_page < total_pages - 1:
                current_page += 1
            elif nav == 'p' and current_page > 0:
                current_page -= 1
            elif nav == 'g':
                try:
                    page = int(input(f"Enter page number (1-{total_pages}): "))
                    if 1 <= page <= total_pages:
                        current_page = page - 1
                except ValueError:
                    pass
            elif nav == 's':
                self._search_in_current_view(lines)
            elif nav == 'e':
                self.interactive_export()
            elif nav == 'q':
                break
    
    def _search_in_current_view(self, lines: list):
        """Search within the current log view"""
        search_term = Enhanced_Menu.get_input("Enter search term", "str")
        if not search_term:
            return
        
        matches = []
        for i, line in enumerate(lines, 1):
            if search_term.lower() in line.lower():
                matches.append((i, line))
        
        if matches:
            print(f"\n{Fore.GREEN}Found {len(matches)} matches:{Style.RESET_ALL}")
            for i, (line_num, line) in enumerate(matches[:10], 1):
                display_line = line[:80] + "..." if len(line) > 80 else line
                print(f"  {Fore.YELLOW}{line_num}:{Style.RESET_ALL} {display_line}")
            
            if len(matches) > 10:
                print(f"\n{Fore.CYAN}... and {len(matches) - 10} more matches{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.YELLOW}No matches found{Style.RESET_ALL}")
        
        input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def view_common_errors(self):
        """Display most common errors"""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Most Common Errors")
        print("=" * 80)
        
        common_errors = self.get_common_errors(10)
        
        if common_errors:
            for i, (error, count) in enumerate(common_errors, 1):
                print(f"\n{Fore.YELLOW}{i}.{Style.RESET_ALL} {error}")
                print(f"   {Fore.CYAN}Occurrences: {count}{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.GREEN}No errors found in logs{Style.RESET_ALL}")
        
        input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")

    def view_recent_activity(self):
        """View recent download activity"""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("Recent Download Activity")
        print("=" * 80)
        
        recent = self.get_recent_activity(20)
        
        if recent:
            for activity in recent:
                color = self.color_map.get(activity['color'], Fore.WHITE)
                message = activity['message']
                if len(message) > 100:
                    message = message[:97] + "..."
                print(f"{color}{activity['status']} {message}{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.YELLOW}No recent activity found{Style.RESET_ALL}")
        
        input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
           
    # ============= Log Management Functions =================
    def export_logs(self, export_dir: Path = None, format: str = 'txt'):
        """Export all logs to specified format"""
        
        # Create export file
        if export_dir is None:
            export_dir = self.log_dir / "exports"
        export_dir.mkdir(exist_ok=True)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        exported_files = []
        
        for log_file, prefix in [(self.success_log_path, 'success'),
                                 (self.failed_log_path, 'failed'),
                                 (self.error_log_path, 'error')]:
            if log_file.exists():
                export_file = export_dir / f"{prefix}_log_{timestamp}.{format}"
                
                try:
                    with open(log_file, 'r', encoding='utf-8') as src:
                        content = src.read()
                    
                    if format == 'txt':
                        with open(export_file, 'w', encoding='utf-8') as dest:
                            dest.write("=" * 60 + "\n")
                            dest.write(f"YOUTUBE MUSIC DOWNLOADER - {prefix.upper()} LOG\n")
                            dest.write(f"Exported: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                            dest.write("=" * 60 + "\n\n")
                            dest.write(content)
                    elif format == 'json':
                        export_data = self._prepare_export_data(content)
                        with open(export_file, 'w', encoding='utf-8') as dest:
                            json.dump(export_data, dest, indent=2, ensure_ascii=False)
                    
                    exported_files.append(export_file)
                    print(f"{Fore.GREEN}✓{Style.RESET_ALL} Exported: {export_file}")
                except Exception as e:
                    print(f"{Fore.RED}✗{Style.RESET_ALL} Failed to export {prefix}: {e}")
        
        # Create summary
        summary_file = self.create_summary_report(export_dir, timestamp)
        if summary_file:
            exported_files.append(summary_file)
        
        return exported_files
    
    def _prepare_export_data(self, content: str) -> Dict:
        """Prepare log content for JSON export. Supporter Function"""
        lines = content.strip().split('\n')
        entries = []
        
        for line in lines:
            if line.strip():
                entry = {
                    'raw': line,
                    'timestamp': self._extract_timestamp(line),
                    'length': len(line)
                }
                entries.append(entry)
        
        return {
            'exported': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_entries': len(entries),
            'entries': entries
        }
    
    def create_summary_report(self, export_dir: Path, timestamp: str) -> Optional[Path]:
        """Create a summary report of all logs."""
        stats = self.log_statistics()
        summary_file = export_dir / f"summary_{timestamp}.txt"
        
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("YOUTUBE MUSIC DOWNLOADER - SUMMARY REPORT\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                f.write("DOWNLOAD STATISTICS:\n")
                f.write("-" * 40 + "\n")
                f.write(f"Successful downloads: {stats['success_count']}\n")
                f.write(f"Failed downloads: {stats['failed_count']}\n")
                f.write(f"Errors logged: {stats['error_count']}\n")
                f.write(f"Total entries: {stats['total_count']}\n\n")
                
                if stats['total_count'] > 0:
                    f.write(f"Success rate: {stats['success_rate']:.1f}%\n\n")
                    
                f.write("FILE SIZES:\n")
                f.write("-" * 40 + "\n")
                for filename, size in stats['file_sizes'].items():
                    f.write(f"{filename}: {self._format_size(size)}\n")
                
                if stats['oldest_entry']:
                    f.write(f"\nOldest entry: {stats['oldest_entry']}\n")
                if stats['newest_entry']:
                    f.write(f"Newest entry: {stats['newest_entry']}\n")
                
                # Add recent activity
                f.write(f"\n\nRECENT ACTIVITY (last 5 entries):\n")
                f.write("-" * 40 + "\n")
                recent = self.get_recent_activity(5)
                for activity in recent:
                    f.write(f"{activity['status']} {activity['message'][:100]}\n")
            
            Enhanced_Menu.print_status(f"Summary created", "success")
            return summary_file

        except Exception as e:
            Enhanced_Menu.print_status(f"Failed to create summary: {e}")
            return None
        
    def _format_size(self, size: int) -> str:
        """ Format file support function"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def clear_logs(self, backup: bool = True) -> bool:
        """ Clear all logs"""
        # Ask if user wishes to back up
        if backup:
            backup_dir = self.log_dir / "backups"
            backup_dir.mkdir(exist_ok=True)
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            
            for log_file in [self.success_log_path, self.failed_log_path, self.error_log_path]:
                if log_file.exists():
                    backup_file = backup_dir / f"{log_file.stem}_{timestamp}{log_file.suffix}"
                    shutil.copy2(log_file, backup_file)
        
        # Clear logs
        for log_file in [self.success_log_path, self.failed_log_path, self.error_log_path]:
            try:
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.write(f"# Log cleared: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    if backup:
                        f.write(f"# Backup created: {backup_dir}\n")
            except Exception as e:
                print(f"{Fore.RED}Error clearing {log_file}: {e}{Style.RESET_ALL}")
                return False
        
        return True
    
    def open_folder(self, folder_path: Path):
        """Open a folder in file explorer"""
        try:
            if sys.platform == 'win32':
                os.startfile(folder_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', folder_path])
            else:
                subprocess.run(['xdg-open', folder_path])
        except Exception as e:
            Enhanced_Menu.print_status(f"Could not open folder: {e}", "error")
    
    # ================= Interactive Menu and Function Helpers ===================
    def interactive_export(self):
        """Interactive log export"""
        Enhanced_Menu.clear_screen()
        
        print("\n" + "=" * 55)
        Enhanced_Menu.print_header("Export Logs")
        
        print(f"\n{Fore.CYAN}Export Options:{Style.RESET_ALL}")
        Enhanced_Menu.print_menu_item(1, "Export as TXT", "Export as a text file")
        Enhanced_Menu.print_menu_item(2, "Export as JSON", "Export as JSON format")
        Enhanced_Menu.print_menu_item(3, "Export as both", "Export as both TXT and JSON")

        format_choice = Enhanced_Menu.get_input("Select format", "int", 1, 3)
        
        export_dir = None
        custom_dir = Enhanced_Menu.get_input("Use custom export directory?", "yn", default=False)

        if custom_dir:
            dir_input = Enhanced_Menu.get_input("Enter export directory path", "str")
            
            if dir_input:
                export_dir = Path(dir_input)
                
        if format_choice == 1:
            files = self.export_logs(export_dir, 'txt')
        elif format_choice == 2:
            files = self.export_logs(export_dir, 'json')
        else:
            files = self.export_logs(export_dir, 'txt')
            files.extend(self.export_logs(export_dir, 'json'))
        
        if files:
            open_folder = Enhanced_Menu.get_input("\nOpen export folder?", "yn", default=False)
            if open_folder:
                self.open_folder(files[0].parent)
        
        input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
                
    def interactive_clear(self):
        """Interactive log clearing with confirmation"""
        Enhanced_Menu.clear_screen()
        
        print("\n" + "="*55)
        Enhanced_Menu.print_header("Clear Logs", "Warning: This will remove all log entries")
        
        stats = self.log_statistics()
        print(f"\n{Fore.YELLOW}Current logs to be cleared:{Style.RESET_ALL}")
        print(f"  • Successful: {stats['success_count']} entries")
        print(f"  • Failed: {stats['failed_count']} entries")
        print(f"  • Errors: {stats['error_count']} entries")
        
        confirm = Enhanced_Menu.get_input("\nCreate backup before clearing?", "yn", default=True)
        
        if confirm:
            if self.clear_logs(backup=True):
                Enhanced_Menu.print_status("✅ Logs cleared and backed up", "success")
        else:
            double_confirm = Enhanced_Menu.get_input("Are you sure? No backup will be created! (yes/no): ", "str")
            if double_confirm.lower() == 'yes':
                if self.clear_logs(backup=False):
                    Enhanced_Menu.print_status("✅ Logs cleared permanently", "success")
            else:
                Enhanced_Menu.print_status("Operation cancelled", "info")
        
        input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
             
    def interactive_menu(self):
        """Interactive log menu for log manager"""
        while True:
            Enhanced_Menu.clear_screen()
            print("\n" + "=" * 55)
            Enhanced_Menu.print_header("📊 Log Manager", "View and manage download logs")
            
            # Get current stats
            log_stats = self.log_statistics()
            
            print(f"\n{Fore.CYAN}📈 Current Statistics:{Style.RESET_ALL}")
            print(f"  {Fore.GREEN}✓ Successful: {log_stats['success_count']}{Style.RESET_ALL}")
            print(f"  {Fore.RED}✗ Failed: {log_stats['failed_count']}{Style.RESET_ALL}")
            print(f"  {Fore.YELLOW}⚠ Errors: {log_stats['error_count']}{Style.RESET_ALL}")
            print(f"  {Fore.MAGENTA}📊 Success Rate: {log_stats['success_rate']:.1f}%{Style.RESET_ALL}")
            if log_stats['newest_entry']:
                print(f"  {Fore.CYAN}🕒 Last Activity: {log_stats['newest_entry']}{Style.RESET_ALL}")
            
            print(f"\n{Fore.CYAN}Options:{Style.RESET_ALL}")
            Enhanced_Menu.print_menu_item(1, "View successful downloads")
            Enhanced_Menu.print_menu_item(2, "View failed downloads")
            Enhanced_Menu.print_menu_item(3, "View error logs")
            Enhanced_Menu.print_menu_item(4, "View all logs")
            Enhanced_Menu.print_menu_item(5, "View recent activity")
            Enhanced_Menu.print_menu_item(6, "View common errors")
            Enhanced_Menu.print_menu_item(7, "Export logs")
            Enhanced_Menu.print_menu_item(8, "Clear logs")
            Enhanced_Menu.print_menu_item(9, "Return to main menu")
            
            choice = Enhanced_Menu.get_input("\nSelect option", "int", 1, 9)
            
            if choice == 1:
                self.view_logs('success')
            elif choice == 2:
                self.view_logs('failed')
            elif choice == 3:
                self.view_logs('error')
            elif choice == 4:
                self.view_logs('all')
            elif choice == 5:
                self.view_recent_activity()
            elif choice == 6:
                self.view_common_errors()
            elif choice == 7:
                self.interactive_export()
            elif choice == 8:
                self.interactive_clear()
            elif choice == 9:
                break