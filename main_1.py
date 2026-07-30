import sys
import time

from pathlib import Path
from colorama import init, Fore, Style

from tools.EnhancedMenu import Enhanced_Menu
from test.TestDownloader2 import YoutubeMusicDownloader

init(autoreset=True)

AUDIO_FORMATS = [
    ("MP3", "mp3", "Most compatible, good quality"),
    ("FLAC", "flac", "Lossless audio, large files"),
    ("M4A", "m4a", "Apple format, good quality"),
    ("OPUS", "opus", "Excellent compression, high quality"),
    ("OGG", "ogg", "Open format, good compression"),
    ("WAV", "wav", "Uncompressed, large files"),
]

AUDIO_QUALITIES = [
    ("320k", "High quality (320 kbps)", "Excellent for most music"),
    ("256k", "Very good (256 kbps)", "Great quality, smaller files"),
    ("192k", "Good (192 kbps)", "Good balance of quality/size"),
    ("128k", "Standard (128 kbps)", "Acceptable quality, small files"),
    ("auto", "Auto-select", "Let yt-dlp choose the best"),
    ("disable", "Original quality", "Keep original audio as-is"),
]


def main():
    """Main function to run the YouTube Downloader with integrated menus."""
    Enhanced_Menu.clear_screen()
    print(f"""{Fore.RED}{Style.BRIGHT}

        ██╗   ██╗ ██████╗ ██╗   ██╗████████╗██╗   ██╗██████╗ ███████╗    ███╗   ███╗██╗   ██╗███████╗██╗ ██████╗    ██████╗  ██████╗ ██╗    ██╗███╗   ██╗██╗      ██████╗  █████╗ ██████╗ ███████╗██████╗ 
        ╚██╗ ██╔╝██╔═══██╗██║   ██║╚══██╔══╝██║   ██║██╔══██╗██╔════╝    ████╗ ████║██║   ██║██╔════╝██║██╔════╝    ██╔══██╗██╔═══██╗██║    ██║████╗  ██║██║     ██╔═══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗
        ╚████╔╝ ██║   ██║██║   ██║   ██║   ██║   ██║██████╔╝█████╗      ██╔████╔██║██║   ██║███████╗██║██║         ██║  ██║██║   ██║██║ █╗ ██║██╔██╗ ██║██║     ██║   ██║███████║██║  ██║█████╗  ██████╔╝
        ╚██╔╝  ██║   ██║██║   ██║   ██║   ██║   ██║██╔══██╗██╔══╝      ██║╚██╔╝██║██║   ██║╚════██║██║██║         ██║  ██║██║   ██║██║███╗██║██║╚██╗██║██║     ██║   ██║██╔══██║██║  ██║██╔══╝  ██╔══██╗
        ██║   ╚██████╔╝╚██████╔╝   ██║   ╚██████╔╝██████╔╝███████╗    ██║ ╚═╝ ██║╚██████╔╝███████║██║╚██████╗    ██████╔╝╚██████╔╝╚███╔███╔╝██║ ╚████║███████╗╚██████╔╝██║  ██║██████╔╝███████╗██║  ██║
        ╚═╝    ╚═════╝  ╚═════╝    ╚═╝    ╚═════╝ ╚═════╝ ╚══════╝    ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝ ╚═════╝    ╚═════╝  ╚═════╝  ╚══╝╚══╝ ╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝
    {Style.RESET_ALL}""")
    print(f"{Fore.YELLOW}{Style.BRIGHT}YouTube Music Downloader{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{Style.BRIGHT}Initializing...{Style.RESET_ALL}")

    # Define directories using pathlib
    music_dir = Path.home() / "Music" / "Collection" / "YouTube"
    cookies_dir = Path("cookies")

    # Ensure they exist
    music_dir.mkdir(parents=True, exist_ok=True)
    cookies_dir.mkdir(parents=True, exist_ok=True)

    print(f"{Fore.GREEN}✓{Style.RESET_ALL} Music directory: {music_dir}")
    print(f"{Fore.GREEN}✓{Style.RESET_ALL} Cookies directory: {cookies_dir}")

    try:
        downloader = YoutubeMusicDownloader()
        Enhanced_Menu.print_status("Downloader initialized successfully", "success")
        time.sleep(1)
    except Exception as e:
        Enhanced_Menu.print_status(f"Initialization error: {e}", "error")
        input("\nPress Enter to exit...")
        sys.exit(1)

    def handle_exit():
        """Handles exiting the program function"""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("THANK YOU", "Goodbye!")
        print(f"""{Fore.CYAN}
                ╔══════════════════════════════════════════════════════════════╗
                ║                                                              ║
                ║          Thank you for using YouTube Music Downloader!       ║
                ║                                                              ║
                ║                      Happy Listening!                        ║
                ║                                                              ║
                ║                                                              ║
                ╚══════════════════════════════════════════════════════════════╝
                {Style.RESET_ALL}""")
        try:
            downloader.save_config()
            print(f"{Fore.GREEN}Settings saved.{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.YELLOW}Could not save settings: {e}{Style.RESET_ALL}")
        print(f"\n{Fore.CYAN}Goodbye!{Style.RESET_ALL}\n")
        sys.exit(0)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    # Everything here goes through the downloader's public properties
    # (audio_format / audio_quality / output_directory). Their setters validate
    # the value and create the directory, so an invalid pick is rejected by the
    # downloader itself instead of being written straight into a private
    # attribute and only failing later, mid-download.
    def handle_settings():
        """Handle program settings menu"""
        while True:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("PROGRAM SETTINGS", "Configure download preferences")

            current_format = downloader.audio_format
            current_quality = downloader.audio_quality
            current_dir = str(downloader.output_directory)

            Enhanced_Menu.print_section("🎵 Download Settings")
            Enhanced_Menu.print_menu_item(1, "Audio Format", f"Current: {Fore.GREEN}{current_format.upper()}{Style.RESET_ALL}")
            Enhanced_Menu.print_menu_item(2, "Audio Quality", f"Current: {Fore.GREEN}{current_quality}{Style.RESET_ALL}")
            Enhanced_Menu.print_menu_item(3, "Output Directory", f"Current: {Fore.CYAN}{current_dir}{Style.RESET_ALL}")

            Enhanced_Menu.print_section("🌐 COOKIE SETTINGS")
            cookie_status = "ENABLED" if downloader.use_cookies else "DISABLED"
            cookie_color = Fore.GREEN if downloader.use_cookies else Fore.YELLOW
            Enhanced_Menu.print_menu_item(4, "Cookie Authentication", f"Current: {cookie_color}{cookie_status}{Style.RESET_ALL}")

            Enhanced_Menu.print_section("💾 Download Configuration")
            Enhanced_Menu.print_menu_item(5, "Save Configuration")
            Enhanced_Menu.print_menu_item(6, "Load Configuration")
            Enhanced_Menu.print_menu_item(7, "Reset to Defaults")
            Enhanced_Menu.print_section("↩️  NAVIGATION")
            Enhanced_Menu.print_menu_item(8, "Back to Main Menu")
            print()

            choice = Enhanced_Menu.get_input("Select option", "int", 1, 8)

            if choice == 1:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("AUDIO FORMAT", "Select output format")
                for i, (name, code, desc) in enumerate(AUDIO_FORMATS, 1):
                    is_current = " ✓" if code == current_format else ""
                    print(f"  {Fore.YELLOW}[{i}]{Style.RESET_ALL} {Fore.CYAN}{name:6}{Style.RESET_ALL} - {desc}{Fore.GREEN}{is_current}{Style.RESET_ALL}")
                print()
                format_choice = Enhanced_Menu.get_input("Select format (1-6)", "int", 1, 6, default=1)
                if format_choice:
                    try:
                        downloader.audio_format = AUDIO_FORMATS[format_choice - 1][1]
                        downloader.save_config()
                        Enhanced_Menu.print_status(
                            f"Audio format set to {downloader.audio_format.upper()}", "success")
                    except ValueError as e:
                        Enhanced_Menu.print_status(str(e), "error")

            elif choice == 2:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("AUDIO QUALITY", "Select bitrate/quality")
                for i, (code, name, desc) in enumerate(AUDIO_QUALITIES, 1):
                    is_current = " ✓" if code == current_quality else ""
                    print(f"  {Fore.YELLOW}[{i}]{Style.RESET_ALL} {Fore.CYAN}{name:20}{Style.RESET_ALL} - {desc}{Fore.GREEN}{is_current}{Style.RESET_ALL}")
                print()
                quality_choice = Enhanced_Menu.get_input("Select quality (1-6)", "int", 1, 6)
                if quality_choice:
                    try:
                        downloader.audio_quality = AUDIO_QUALITIES[quality_choice - 1][0]
                        downloader.save_config()
                        Enhanced_Menu.print_status(
                            f"Audio quality set to {downloader.audio_quality}", "success")
                    except ValueError as e:
                        Enhanced_Menu.print_status(str(e), "error")

            # Set output
            elif choice == 3:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("OUTPUT DIRECTORY", "Set where files are saved")
                print(f"{Fore.YELLOW}Current directory:{Style.RESET_ALL} {Fore.CYAN}{current_dir}{Style.RESET_ALL}")
                print()
                print(f"{Fore.WHITE}Enter new directory path:{Style.RESET_ALL}")
                print(f"{Style.DIM}Examples:{Style.RESET_ALL}")
                print(f"  {Fore.CYAN}./Music{Style.RESET_ALL} - Save to 'Music' folder in current directory")
                print(f"  {Fore.CYAN}~/Downloads{Style.RESET_ALL} - Save to Downloads folder")
                print(f"  {Fore.CYAN}C:\\Users\\You\\Music{Style.RESET_ALL} - Windows absolute path")
                print()
                new_dir = Enhanced_Menu.get_input("New directory path", "str", default=current_dir)
                new_dir = (new_dir or "").strip().strip('"').strip("'")
                if new_dir and new_dir != current_dir:
                    try:
                        # The setter expands nothing, so do ~ here; it does mkdir.
                        downloader.output_directory = Path(new_dir).expanduser()
                        downloader.save_config()
                        Enhanced_Menu.print_status(
                            f"Output directory changed to {downloader.output_directory}", "success")
                    except OSError as e:
                        Enhanced_Menu.print_status(f"Could not use that path: {str(e)[:60]}", "error")

            elif choice == 4:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("COOKIE SETTINGS", "Manage authentication")
                print(f"{Fore.WHITE}Cookies help with:{Style.RESET_ALL}")
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Age-restricted content")
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Region-restricted videos")
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Private playlists")
                print(f"  {Fore.GREEN}✓{Style.RESET_ALL} YouTube Premium content")
                print()
                print(f"{Fore.YELLOW}Current status:{Style.RESET_ALL} ", end="")
                if downloader.use_cookies:
                    print(f"{Fore.GREEN}ENABLED{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}DISABLED{Style.RESET_ALL}")
                print()
                new_setting = Enhanced_Menu.get_input("Enable cookies? (y/n)", "yn",
                                                      default=downloader.use_cookies)
                if new_setting is not None:
                    downloader.use_cookies = bool(new_setting)
                    downloader.save_config()
                    Enhanced_Menu.print_status(
                        f"Cookies {'enabled' if downloader.use_cookies else 'disabled'}", "success")

            elif choice == 5:
                try:
                    downloader.save_config()
                    Enhanced_Menu.print_status("Settings saved successfully", "success")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Error saving settings: {e}", "error")

            elif choice == 6:
                try:
                    downloader.load_config()
                    Enhanced_Menu.print_status("Settings loaded successfully", "success")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Error loading settings: {e}", "error")

            elif choice == 7:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("RESET SETTINGS", "Restore defaults")
                print(f"{Fore.YELLOW}⚠️  WARNING:{Style.RESET_ALL}")
                print(f"{Fore.WHITE}This will reset ALL settings to their default values.{Style.RESET_ALL}")
                print()
                print(f"{Fore.CYAN}Default settings:{Style.RESET_ALL}")
                print(f"  Format: {Fore.YELLOW}mp3{Style.RESET_ALL}")
                print(f"  Quality: {Fore.YELLOW}320k{Style.RESET_ALL}")
                print(f"  Output: {Fore.YELLOW}~/Music/Collection/YouTube{Style.RESET_ALL}")
                print(f"  Cookies: {Fore.YELLOW}Disabled{Style.RESET_ALL}")
                print()
                confirm = Enhanced_Menu.get_input("Are you sure? (y/n)", "yn", default=False)
                if confirm:
                    downloader.reset_to_defaults()

            elif choice == 8:
                break

            if choice != 8:
                input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")

    # ------------------------------------------------------------------
    # Menu definition
    # ------------------------------------------------------------------
    # Rebuilt each pass so hints (the retry queue size) stay current, and
    # numbered automatically rather than by hand - that keeps the printed
    # numbers and the dispatch table in step, and stops "exit" from drifting
    # away from the number the loop compares against.
    #
    # Entries are (label, hint, action, retryable); retryable marks the ones
    # that return False on failure and are worth re-offering.
    def build_menu():
        queued = downloader.retry_queue_count
        retry_hint = (f"{Fore.YELLOW}{queued} link(s) waiting{Style.RESET_ALL}" if queued
                      else f"{Style.DIM}queue empty{Style.RESET_ALL}")

        return [
            ("📥 DOWNLOAD OPTIONS", [
                ("Download Track", "", downloader.download_track, True),
                ("Download Album", "", downloader.download_album, True),
                ("Download Playlist", "", downloader.download_playlist, True),
                ("Search & Download a Song", "", downloader.search_and_download, True),
            ]),
            ("📄 BATCH DOWNLOAD", [
                ("Download Links from a File", ".txt or .csv, one at a time",
                 downloader.download_from_file, True),
                ("Retry Failed Links", retry_hint,
                 downloader.download_from_retry_queue, True),
            ]),
            ("⚙️  TOOLS & SETTINGS", [
                ("Manage Cookies (for restricted content)", "", downloader.manage_cookies, False),
                ("Check Dependencies", "", downloader.check_dependencies, False),
                ("Program Settings", "", handle_settings, False),
            ]),
            ("❓ HELP & INFORMATION", [
                ("Show Program Info", "", downloader.program_info, False),
                ("Troubleshooting", "", downloader.troubleshooting, False),
                ("Show yt-dlp Help", "", downloader.show_ytdlp_help, False),
            ]),
            ("📊 LOG MANAGEMENT", [
                ("Log Manager", "", downloader.log_manager.interactive_menu, False),
                ("Input History", "", downloader.history.interactive_menu, False),
            ]),
            ("🚪 EXIT", [
                ("Exit Program", "", handle_exit, False),
            ]),
        ]

    def render_menu(sections):
        """Print the menu, return {number: (label, action, retryable)}."""
        entries = {}
        number = 1
        for heading, items in sections:
            Enhanced_Menu.print_section(heading)
            for label, hint, action, retryable in items:
                Enhanced_Menu.print_menu_item(number, label, hint)
                entries[number] = (label, action, retryable)
                number += 1
        return entries

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    while True:
        try:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Main Menu", "Select an option below:")

            entries = render_menu(build_menu())
            exit_choice = max(entries)

            print(f"\n{Style.DIM}{'─' * 60}{Style.RESET_ALL}")
            Enhanced_Menu.print_status("Current Settings:", "info", "⚙️")

            settings = [
                ("Format", downloader.audio_format),
                ("Quality", downloader.audio_quality),
                ("Output", str(downloader.output_directory)),
            ]
            for setting_name, setting_value in settings:
                print(f"  {Fore.CYAN}{setting_name}:{Style.RESET_ALL} {Fore.YELLOW}{setting_value}{Style.RESET_ALL}")

            cookie_status = "Enabled" if downloader.use_cookies else "Disabled"
            cookie_color = Fore.GREEN if downloader.use_cookies else Fore.YELLOW
            print(f"  {Fore.CYAN}Cookies:{Style.RESET_ALL} {cookie_color}{cookie_status}{Style.RESET_ALL}")
            print(f"{Style.DIM}{'─' * 60}{Style.RESET_ALL}")

            choice = Enhanced_Menu.get_input(
                f"\nEnter your choice (1-{exit_choice})", "int", 1, exit_choice)
            entry = entries.get(choice)

            if not entry:
                Enhanced_Menu.print_status("Invalid option", "error")
                continue

            label, action, retryable = entry
            Enhanced_Menu.clear_screen()
            try:
                # The download methods run their own retry loop and return
                # True/False; only the ones marked retryable are worth offering
                # another go at from here.
                result = action()
                if result is False and retryable:
                    print()
                    if Enhanced_Menu.get_input(f"{label} failed. Try again? (y/n)",
                                               "yn", default=True):
                        continue
            except KeyboardInterrupt:
                Enhanced_Menu.print_status("Operation cancelled", "warning")
            except RuntimeError as e:
                # yt-dlp itself is missing - no point retrying, and the
                # traceback below would bury the one line that matters.
                Enhanced_Menu.print_status(str(e), "error")
            except Exception as e:
                Enhanced_Menu.print_status(f"Error: {e}", "error")
                import traceback
                traceback.print_exc()

            if choice != exit_choice:
                print()
                cont = Enhanced_Menu.get_input("Return to main menu? (y/n)", "yn", default=True)
                if not cont:
                    handle_exit()

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Interrupted by user{Style.RESET_ALL}")
            handle_exit()
        except Exception as e:
            Enhanced_Menu.print_status(f"Unexpected error: {e}", "error")
            import traceback
            traceback.print_exc()
            if Enhanced_Menu.get_input("Continue? (y/n)", "yn", default=True):
                continue
            else:
                handle_exit()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        print("Please check the error log for details.")