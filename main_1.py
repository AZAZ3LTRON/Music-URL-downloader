import sys
import time

from pathlib import Path
from colorama import init, Fore, Style

from utils.enhancedmenu import Enhanced_Menu
from downloader.YoutubeMusicDownloader import YoutubeMusicDownloader

init(autoreset=True)

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
        except Exception:
            pass
        print(f"\n{Fore.CYAN}Goodbye!{Style.RESET_ALL}\n")
        sys.exit(0)

    def handle_settings():
        """Handle program settings menu"""
        while True:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("PROGRAM SETTINGS", "Configure download preferences")

            Enhanced_Menu.print_section("🎵 Download Settings")
            current_format = downloader._YoutubeMusicDownloader__audio_format
            current_quality = downloader._YoutubeMusicDownloader__audio_quality
            Enhanced_Menu.print_menu_item(1, "Audio Format", f"Current: {Fore.GREEN}{current_format.upper()}{Style.RESET_ALL}")
            Enhanced_Menu.print_menu_item(2, "Audio Quality", f"Current: {Fore.GREEN}{current_quality}{Style.RESET_ALL}")
            current_dir = str(downloader._YoutubeMusicDownloader__output_directory)
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
                formats = [
                    ("MP3", "mp3", "Most compatible, good quality"),
                    ("FLAC", "flac", "Lossless audio, large files"),
                    ("M4A", "m4a", "Apple format, good quality"),
                    ("OPUS", "opus", "Excellent compression, high quality"),
                    ("OGG", "ogg", "Open format, good compression"),
                    ("WAV", "wav", "Uncompressed, large files"),
                ]
                for i, (name, code, desc) in enumerate(formats, 1):
                    is_current = " ✓" if code == current_format else ""
                    print(f"  {Fore.YELLOW}[{i}]{Style.RESET_ALL} {Fore.CYAN}{name:6}{Style.RESET_ALL} - {desc}{Fore.GREEN}{is_current}{Style.RESET_ALL}")
                print()
                format_choice = Enhanced_Menu.get_input("Select format (1-6)", "int", 1, 6, default=1)
                if format_choice:
                    new_format = formats[format_choice - 1][1]
                    downloader._YoutubeMusicDownloader__audio_format = new_format
                    Enhanced_Menu.print_status(f"Audio format set to {new_format.upper()}", "success")

            elif choice == 2:
                Enhanced_Menu.clear_screen()
                Enhanced_Menu.print_header("AUDIO QUALITY", "Select bitrate/quality")
                qualities = [
                    ("320k", "High quality (320 kbps)", "Excellent for most music"),
                    ("256k", "Very good (256 kbps)", "Great quality, smaller files"),
                    ("192k", "Good (192 kbps)", "Good balance of quality/size"),
                    ("128k", "Standard (128 kbps)", "Acceptable quality, small files"),
                    ("auto", "Auto-select", "Let yt-dlp choose the best"),
                    ("disable", "Original quality", "Keep original audio as-is"),
                ]
                for i, (code, name, desc) in enumerate(qualities, 1):
                    is_current = " ✓" if code == current_quality else ""
                    print(f"  {Fore.YELLOW}[{i}]{Style.RESET_ALL} {Fore.CYAN}{name:20}{Style.RESET_ALL} - {desc}{Fore.GREEN}{is_current}{Style.RESET_ALL}")
                print()
                quality_choice = Enhanced_Menu.get_input("Select quality (1-6)", "int", 1, 6)
                if quality_choice:
                    new_quality = qualities[quality_choice - 1][0]
                    downloader._YoutubeMusicDownloader__audio_quality = new_quality
                    Enhanced_Menu.print_status(f"Audio quality set to {new_quality}", "success")

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
                if new_dir and new_dir != current_dir:
                    try:
                        downloader._YoutubeMusicDownloader__output_directory = Path(new_dir)
                        downloader._YoutubeMusicDownloader__output_directory.mkdir(parents=True, exist_ok=True)
                        Enhanced_Menu.print_status(f"Output directory changed to {new_dir}", "success")
                    except Exception as e:
                        Enhanced_Menu.print_status(f"Error: {str(e)[:50]}", "error")

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
                new_setting = Enhanced_Menu.get_input("Enable cookies? (y/n)", "yn", default=downloader.use_cookies)
                if new_setting is not None:
                    downloader.use_cookies = new_setting
                    status = "enabled" if new_setting else "disabled"
                    Enhanced_Menu.print_status(f"Cookies {status}", "success")

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
                print(f"  Output: {Fore.YELLOW}~/Music/YouTube{Style.RESET_ALL}")
                print(f"  Cookies: {Fore.YELLOW}Disabled{Style.RESET_ALL}")
                print()
                confirm = Enhanced_Menu.get_input("Are you sure? (y/n)", "yn", default=False)
                if confirm:
                    downloader.reset_to_defaults()
            elif choice == 8:
                break
            if choice != 8:
                input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")

    # Define actions as lambdas to ensure they're called only when selected
    actions = {
        1: lambda: downloader.download_track(),
        2: lambda: downloader.download_album(),
        3: lambda: downloader.download_playlist(),
        4: lambda: downloader.search_and_download(),
        5: lambda: downloader.download_artist(),   # FIX: was download_channel() (no such method)
        6: lambda: downloader.manage_cookies(),
        7: lambda: downloader.check_dependencies(),
        8: lambda: handle_settings(),
        9: lambda: downloader.program_info(),
        10: lambda: downloader.troubleshooting(),
        11: lambda: downloader.show_ytdlp_help(),
        12: lambda: downloader.log_manager.interactive_menu(),
        13: lambda: downloader.history.interactive_menu(),
        14: lambda: handle_exit()
    }

    while True:
        try:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Main Menu", "Select an option below:")
            Enhanced_Menu.print_section("📥 DOWNLOAD OPTIONS")
            Enhanced_Menu.print_menu_item(1, "Download Track")
            Enhanced_Menu.print_menu_item(2, "Download Album")
            Enhanced_Menu.print_menu_item(3, "Download Playlist")
            Enhanced_Menu.print_menu_item(4, "Search & Download a Song")
            Enhanced_Menu.print_menu_item(5, "Download Artist")

            Enhanced_Menu.print_section("⚙️  TOOLS & SETTINGS")
            Enhanced_Menu.print_menu_item(6, "Manage Cookies (for restricted content)")
            Enhanced_Menu.print_menu_item(7, "Check Dependencies")
            Enhanced_Menu.print_menu_item(8, "Program Settings")

            Enhanced_Menu.print_section("❓ HELP & INFORMATION")
            Enhanced_Menu.print_menu_item(9, "Show Program Info")
            Enhanced_Menu.print_menu_item(10, "Troubleshooting")
            Enhanced_Menu.print_menu_item(11, "Show yt-dlp Help")

            Enhanced_Menu.print_section("📊 LOG MANAGEMENT")
            Enhanced_Menu.print_menu_item(12, "Log Manager")
            Enhanced_Menu.print_menu_item(13, "Input History")
            Enhanced_Menu.print_section("🚪 EXIT")
            Enhanced_Menu.print_menu_item(14, "Exit Program")
            print(f"\n{Style.DIM}{'─' * 60}{Style.RESET_ALL}")
            Enhanced_Menu.print_status("Current Settings:", "info", "⚙️")

            settings = [
                ("Format", downloader._YoutubeMusicDownloader__audio_format),
                ("Quality", downloader._YoutubeMusicDownloader__audio_quality),
                ("Output", str(downloader._YoutubeMusicDownloader__output_directory)),
            ]

            for setting_name, setting_value in settings:
                print(f"  {Fore.CYAN}{setting_name}:{Style.RESET_ALL} {Fore.YELLOW}{setting_value}{Style.RESET_ALL}")
            cookie_status = "Enabled" if downloader.use_cookies else "Disabled"
            cookie_color = Fore.GREEN if downloader.use_cookies else Fore.YELLOW
            print(f"  {Fore.CYAN}Cookies:{Style.RESET_ALL} {cookie_color}{cookie_status}{Style.RESET_ALL}")
            print(f"{Style.DIM}{'─' * 60}{Style.RESET_ALL}")

            choice = Enhanced_Menu.get_input("\nEnter your choice (1-14)", "int", 1, 14)
            action = actions.get(choice)

            if action:
                Enhanced_Menu.clear_screen()
                try:
                    # Call the selected action. Download/utility methods handle
                    # their own retry loops and return True/False; we don't
                    # re-prompt here (the old `result is False and choice not in
                    # [...]` guard was always False, i.e. dead code).
                    action()
                except KeyboardInterrupt:
                    Enhanced_Menu.print_status("Operation cancelled", "warning")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Error: {e}", "error")
                    import traceback
                    traceback.print_exc()
            else:
                Enhanced_Menu.print_status("Invalid option", "error")

            if choice != 13:
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