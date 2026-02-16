import sys
import os
import subprocess
import shutil
import time
from functools import wraps
from pathlib import Path
import logging
import re
import urllib.parse
from urllib.parse import urlparse
from typing import List, Dict, Optional, Tuple
import threading
import json
from tqdm import tqdm
from colorama import init, Fore, Back, Style

from CookieManager import CookieManager
from EnhancedMenu import Enhanced_Menu

init(autoreset=True)

class Log_Manager:
    """ Log Manager and history viewer for the Downlaoder"""
    def __init__(self):
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # Define log file paths
        self.success_log = self.log_dir/"success.log"
        self.failed_log = self.log_dir/"failed.log"
        self.error_log = self.log_dir/"error.log"
        
        # Initialize the log path
        self.setup_logs()
        
        self.color_map = {
            'success': Fore.GREEN,
            'failed': Fore.RED,
            'error': Fore.YELLOW,
            'warning': Fore.MAGENTA           
        }
        
    def setup_logs(self):
        """Setup all log with format and configuration"""
        
        # log format
        log_format = logging.Formatter("YT-DLP - %(asctime)s - %(levelname)s - %(funcName)s - %(lineno)d - %(message)s")
        error_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        
        # Successful downloads log
        self.success_log = logging.getLogger("successful_downloads")
        self.success_log.setLevel(logging.INFO)
        self.success_log.propagate = False
        success_handler = logging.FileHandler(str(self.success_log), encoding='utf-8')
        success_handler.setLevel(logging.INFO)
        success_handler.setFormatter(log_format)
        self.success_log.addHandler(success_handler)
        
        # Failed download log
        self.failed_log = logging.getLogger("failed_downloads")
        self.failed_log.setLevel(logging.INFO)
        self.failed_log.propagate = False
        failed_handler = logging.FileHandler(str(self.failed_log), encoding='utf-8')
        failed_handler.setLevel(logging.INFO)
        failed_handler.setFormatter(log_format)
        self.success_log.addHandler(failed_handler)
        
        # Error log
        self.error_log = logging.getLogger("Errors")
        self.error_log.setLevel(logging.INFO)
        self.error_log.propagate = False
        error_handler = logging.FileHandler(str(self.error_log), encoding='utf-8')
        error_handler.setLevel(logging.INFO)
        error_handler.setFormatter(error_format)
        self.error_log.addHandler(error_handler)
        
        
        # Console logs
        self.console_logger = logging.getLogger("console")
        self.console_logger.setLevel(logging.INFO)
        self.console_logger.propagate = False
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(log_format)
        self.console_logger.addHandler(console_handler)        
    
    # ========== Logging Methods ==============
    def log_success(self, message: str, console: bool = True):
        """ Log successful music downloads"""
        self.success_log.info(message)
        if console:
            self.console_logger.info(f"{self.color_map['success']}{message}{Style.RESET_ALL}")
        
    def log_failure(self, message: str, console: bool = True):
        """ Log failed music downloads"""
        self.failed_log.info(message)
        if console:
            self.console_logger.info(f"{self.color_map['failed']}{message}{Style.RESET_ALL}")
            
    def log_error(self, message: str, exc_info=False, console: bool = True):
        """ Log error during music download process"""
        self.error_log.error(message, exc_info=exc_info)
        if console:
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
            'last_download': 0,
            'success_rate': 0
        }
        
        # Count entries in each log
        for log_file, key in [(self.success_log, 'success_count'), 
                              (self.failed_log, 'failed_count'), 
                              (self.error_log, 'error_count')]:
            
            # Check if file exist
            if log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        # Coi
                        lines = [l for l in f.readlines() if l.strip()]
                        stats[key] = len(lines)
                        stats['total_count'] += len(lines)
                
                except Exception as e:
                    self.log_error(f"Error reading log file {log_file}: {e}", console=False)

            # Calculate Download success rate
            if stats['total_count'] >0:
                stats['success_rate'] = (int(stats['success_count'])) / int(stats['total_count']) * 100
                
            return stats
        
    def get_common_errors(self, limit: int = 7):
        """ Get the most common error message that occur in the program"""
        error_patterns = {}
        
        # Check if error logs exist
        if not self.error_log.exists():
            return []
        
        # Open error logs and extract error messages
        try:
            with open(self.error_log, 'r', econding='utf-8') as f:
                for line in f:
                    error_match = re.search(r'ERROR - (.+?)(?:\d0+|$)', line) # Check 
                    if error_match:
                        error_message = error_match.group(1).strip()
                        
                        # Normalize error message (remove variable parts from line)
                        error_message = re.sub(r'\d+', '#', error_message)
                        error_patterns[error_message] = error_patterns.get(error_message, 0)
        
        except Exception as e:
            self.log_error(f"Error analyzing error log: {e}", console=False)
            
        # Sort by occurence frequency and return top errors
        sorted_errors = sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)
        return sorted_errors[:limit]
    
    def get_recent_activity(self, limit: int = 10):
        """Get most recent download activity"""
        activities = []
        
        for log_file, status, color in [(self.success_log, "✅ Success", 'success'),
                                        (self.failed_log, "❌ Failed", 'failed')]:
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
    
    def view_logs(self, log_type: str, title: str = None, color: str = None):
        """ Display records from log file with formatting"""
        
        # Dictionary stores tuples of
        log_files = {
            'success': (self.success_log, 'Successful downloads', self.color_map['success']),
            'failed': (self.failed_log, 'Failed downloads', self.color_map['failed']),
            'error': (self.error_log, 'Error Logs', self.color_map['error']),
            'all': (None, ' All Logs', Fore.WHITE)
        }
        
        log_type = Enhanced_Menu.get_input("What logs would do wish to view:- ")
        
        # The user input must be in the dictionary
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
        Enhanced_Menu.print_header(f"{display_title:^80}")
        print("="*80)
        
        if not log_file or not log_file.exists():
            Enhanced_Menu.print_status("Log file does not exist", "error")
            return
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = [l.rstrip for l in f.readlines() if l.strip()]
                
            if not lines:
                Enhanced_Menu.print_status("Log file is empty.", "error")
                return
            
            self._display_paginated(lines, display_color)
        
        except Exception as e:
            Enhanced_Menu.print_status(f"Error reading log file: {e}", "error")
    
    def _display_all_logs(self):
        """ Display all logs in a combined view"""
        stats = self.log_statistics()
        
        Enhanced_Menu.clear_screen()
        print(f"\n{Fore.CYAN}{'=' * 80}{Style.RESET_ALL}")
        Enhanced_Menu.print_header(f"{'COMBINED LOG VIEW':^80}")
        print(f"{Fore.CYAN}{'=' * 80}{Style.RESET_ALL}")
        
        for log_file, label, color in [(self.success_log, 'SUCCESS', Fore.GREEN),
                                       (self.failed_log, 'FAILED', Fore.RED),
                                       (self.error_log, 'ERROR', Fore.YELLOW)]:
            if log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        lines = [l.rstrip() for l in f.readlines() if l.strip()]
                    
                    if lines:
                        print(f"\n{color}{label} LOG ({len(lines)} entries):{Style.RESET_ALL}")
                        print(f"{color}{'-' * 40}{Style.RESET_ALL}")
                        for line in lines[-5:]:  # Show last 5 from each
                            print(f"{color}  {line[:100]}{Style.RESET_ALL}")
                except:
                    pass
    
    def _display_paginated(self, lines: list, color: str, page_size: int):
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
            Enhanced_Menu.print_header("Navigation")
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
                except:
                    pass
            elif nav == 's':
                self.search_logs_interactive(lines)
            elif nav == 'e':
                self.export_log(log_file=self.success_log)  # You'd need to track current log
            elif nav == 'q':
                break
            
    def view_common_errors(self):
        """Display most common errors"""
        Enhanced_Menu.clear_screen()
        print("\n" + "=" *80)
        Enhanced_Menu.print_header("Most Common Errors")
        
        common_errors = self.get_common_errors(10)
        
        if common_errors:
            for i, (error, count) in enumerate(common_errors, 1):
                print(f"\n{Fore.YELLOW}{i}.{Style.RESET_ALL} {error}")
                print(f"   {Fore.CYAN}Occurrences: {count}{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.GREEN}No errors found in logs{Style.RESET_ALL}")

    def view_recent_activity():
        pass
           
    # ============= Log Management Functions =================
    def export_logs(self, export_dir: Path = None, format: str = 'txt'):
        """Export all logs to specified format"""
        
        # Create export file
        if export_dir is None:
            export_dir = self.log_dir / "exports"
        export_dir.mkdir(exist_ok=True)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        exported_files = []
        
        for log_file, prefix in [(self.success_log, 'success'),
                                 (self.failed_log, 'failed'),
                                 (self.error_log, 'error')]:
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
        summary_file = export_dir / f"summary.txt"
        
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
        """ Format file su[pport] function"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:1f} TB"
    
    def clear_logs(self):
        """ Clear all logs"""
        # Ask if user wishes to back up
        backup_choice = Enhanced_Menu.get_input("Do you wish to backup the logs:- ")
        if backup_choice in ['y', 'yes']:
            backup_dir = self.log_dir / "backups"
            backup_dir.mkdir(exist_ok=True)
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            
            for log_file in [self.success_log, self.failed_log, self.error_log]:
                if log_file.exists():
                    backup_file = backup_dir / f"{log_file.stem}_{timestamp}{log_file.suffix}"
                    shutil.copy2(log_file, backup_file)
        
        elif backup_choice in ['n', 'no']:
            for log_file in [self.success_log, self.failed_log, self.error_log]:
                try:
                    with open(log_file, 'w', encoding='utf-8') as f:
                        f.write(f"# Logs cleared: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                        if backup_choice:
                            f.write(f"# Backup created: {backup_dir}")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Error clearning {log_file}: {e}", "error")
                    return False
        else:
            Enhanced_Menu.print_status("Enter yes or no")
        
    # ================= Interactive Menu and Function Helpers ===================
    
    def interactive_export(self):
        pass
    
    def interactive_clear(self):
        pass
             
    def interactive_menu(self):
        """Interactive log menu for log manager"""
        while True:
            print("\n" + "=" *55)
            Enhanced_Menu.print_header("📊 Log Manager", "View and manage download logs")
            
            # Get current stats
            log_stats = self.log_statistics()
            
            Enhanced_Menu.print_header("Log Statistics")            
            print(f"  {Fore.GREEN}✓ Successful: {log_stats['success_count']}{Style.RESET_ALL}")
            print(f"  {Fore.RED}✗ Failed: {log_stats['failed_count']}{Style.RESET_ALL}")
            print(f"  {Fore.YELLOW}⚠ Errors: {log_stats['error_count']}{Style.RESET_ALL}")
            print(f"  {Fore.MAGENTA}📊 Success Rate: {log_stats['success_rate']:.1f}%{Style.RESET_ALL}")
            
            Enhanced_Menu.print_menu_item(1, "View successful downloads")
            Enhanced_Menu.print_menu_item(2, "View failed downloads")
            Enhanced_Menu.print_menu_item(3, "View error logs")
            Enhanced_Menu.print_menu_item(4, "View all logs")
            Enhanced_Menu.print_menu_item(5, "View recent activity")
            Enhanced_Menu.print_menu_item(6, "View common error")
            Enhanced_Menu.print_menu_item(7, "Export logs")
            Enhanced_Menu.print_menu_item(8, "Clear logs")
            Enhanced_Menu.print_menu_item(9, "Return to main menu")
            
            choice = Enhanced_Menu.get_input("\nSelect option", "int", 1, 10)
            
            actions = {
                1:Log_Manager.view_logs('success'),
                2:Log_Manager.view_logs('failed'),
                3:Log_Manager.view_logs('error'),
                4:Log_Manager.view_logs('all'),
                5:Log_Manager.view_recent_activity(),
                6:Log_Manager.view_common_errors(),
                7: Log_Manager.export_logs(),    
                
            }
            
            if choice == 1:
                self.display_log('success')
            elif choice == 2:
                self.display_log('failed')
            elif choice == 3:
                self.display_log('error')
            elif choice == 4:
                self.search_logs_interactive()
            elif choice == 5:
                self.display_recent_activity()
            elif choice == 6:
                self.display_common_errors()
            elif choice == 7:
                self.interactive_export()
            elif choice == 8:
                self.interactive_clear()
            elif choice == 9:
                self.open_log_folder()
            elif choice == 10:
                break