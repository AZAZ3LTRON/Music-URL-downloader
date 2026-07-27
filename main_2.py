import sys
import time
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path
from colorama import init, Fore, Style

from tools.EnhancedMenu import Enhanced_Menu

from downloader.SpotifyDownloader import SpotifyMusicDownloader
init(autoreset=True)

def main():
    """Main function to run the Spotify Music Downloader"""
    Enhanced_Menu.clear_screen()
    print(f"""{Fore.GREEN}{Style.BRIGHT}
         ███████╗██████╗  ██████╗ ████████╗██╗███████╗██╗   ██╗    ███╗   ███╗██╗   ██╗███████╗██╗ ██████╗    ██████╗  ██████╗ ██╗    ██╗███╗   ██╗██╗      ██████╗  █████╗ ██████╗ ███████╗██████╗ 
         ██╔════╝██╔══██╗██╔═══██╗╚══██╔══╝██║██╔════╝╚██╗ ██╔╝    ████╗ ████║██║   ██║██╔════╝██║██╔════╝    ██╔══██╗██╔═══██╗██║    ██║████╗  ██║██║     ██╔═══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗
         ███████╗██████╔╝██║   ██║   ██║   ██║█████╗   ╚████╔╝     ██╔████╔██║██║   ██║███████╗██║██║         ██║  ██║██║   ██║██║ █╗ ██║██╔██╗ ██║██║     ██║   ██║███████║██║  ██║█████╗  ██████╔╝
         ╚════██║██╔═══╝ ██║   ██║   ██║   ██║██╔══╝    ╚██╔╝      ██║╚██╔╝██║██║   ██║╚════██║██║██║         ██║  ██║██║   ██║██║███╗██║██║╚██╗██║██║     ██║   ██║██╔══██║██║  ██║██╔══╝  ██╔══██╗
         ███████║██║     ╚██████╔╝   ██║   ██║██║        ██║       ██║ ╚═╝ ██║╚██████╔╝███████║██║╚██████╗    ██████╔╝╚██████╔╝╚███╔███╔╝██║ ╚████║███████╗╚██████╔╝██║  ██║██████╔╝███████╗██║  ██║
         ╚══════╝╚═╝      ╚═════╝    ╚═╝   ╚═╝╚═╝        ╚═╝       ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝ ╚═════╝    ╚═════╝  ╚═════╝  ╚══╝╚══╝ ╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝                                                                                                                                                                      
    {Style.RESET_ALL}""")
    print(f"{Fore.YELLOW}{Style.BRIGHT}Spotify Music Downloader{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{Style.BRIGHT}Initializing...{Style.RESET_ALL}")

    music_dir = Path.home() / "Music" / "Collection" / "Spotify"
    cookies_dir = Path("cookies") 

    # Ensure they exist
    music_dir.mkdir(parents=True, exist_ok=True)
    cookies_dir.mkdir(parents=True, exist_ok=True)

    print(f"{Fore.GREEN}✓{Style.RESET_ALL} Music directory: {music_dir}")
    print(f"{Fore.GREEN}✓{Style.RESET_ALL} Cookies directory: {cookies_dir}")

    try:
        downloader = SpotifyMusicDownloader()
        downloader.output_directory = music_dir
        Enhanced_Menu.print_status("Downloader initialized successfully", "success")
        time.sleep(1)
    except Exception as e:
        Enhanced_Menu.print_status(f"Initialization error: {e}", "error")
        input("\nPress Enter to exit...")
        sys.exit(1)

    def handle_exit():
        """Exits the program, saving settings if possible."""
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header("THANK YOU", "Goodbye!")
        print(f"""{Fore.CYAN}
                ╔══════════════════════════════════════════════════════════════╗
                ║                                                              ║
                ║          Thank you for using Spotify Music Downloader!       ║
                ║                                                              ║
                ║                      Happy Listening!                        ║
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

    def get_current_settings():
        """Return current settings from the downloader’s private attributes."""
        return {
            'format': downloader._SpotifyMusicDownloader__audio_format,
            'quality': downloader._SpotifyMusicDownloader__audio_quality,
            'directory': str(downloader._SpotifyMusicDownloader__output_directory)
        }

    def set_current_settings(fmt=None, quality=None, directory=None):
        """Modify private attributes (temporary workaround)."""
        if fmt is not None:
            downloader._SpotifyMusicDownloader__audio_format = fmt
        if quality is not None:
            downloader._SpotifyMusicDownloader__audio_quality = quality
        if directory is not None:
            downloader._SpotifyMusicDownloader__output_directory = Path(directory)

    def handle_settings():
        """Settings menu – works directly with the downloader’s attributes."""
        while True:
            Enhanced_Menu.clear_screen()
            Enhanced_Menu.print_header("Program Settings", "Configure download preferences")

            settings = get_current_settings()

            Enhanced_Menu.print_section("🎵 Download Settings")
            Enhanced_Menu.print_menu_item(1, "Audio Format", f"Current: {Fore.GREEN}{settings['format'].upper()}{Style.RESET_ALL}")
            Enhanced_Menu.print_menu_item(2, "Audio Quality", f"Current: {Fore.GREEN}{settings['quality']}{Style.RESET_ALL}")
            Enhanced_Menu.print_menu_item(3, "Output Directory", f"Current: {Fore.CYAN}{settings['directory']}{Style.RESET_ALL}")

            Enhanced_Menu.print_section("💾 Configuration")
            Enhanced_Menu.print_menu_item(4, "Save Configuration")
            Enhanced_Menu.print_menu_item(5, "Load Configuration")
            Enhanced_Menu.print_menu_item(6, "Reset to Defaults")

            Enhanced_Menu.print_section("↩️  NAVIGATION")
            Enhanced_Menu.print_menu_item(7, "Back to Main Menu")
            print()

            choice = Enhanced_Menu.get_input("Select option", "int", 1, 7)
            if choice == 1:
                # Change format
                formats = {
                    "1": ("mp3", "MP3 - Most compatible"),
                    "2": ("flac", "FLAC - Lossless"),
                    "3": ("m4a", "M4A - Apple format"),
                    "4": ("opus", "OPUS - Good compression"),
                    "5": ("ogg", "OGG - Open format"),
                    "6": ("wav", "WAV - Uncompressed")
                }
                print("\nSelect format:")
                for key, (code, desc) in formats.items():
                    print(f"  {key}. {desc}")
                fmt_choice = Enhanced_Menu.get_input("Choice", "int", 1, 6)
                if fmt_choice:
                    new_format = formats[str(fmt_choice)][0]
                    # Update the private attribute directly and save
                    set_current_settings(fmt=new_format)
                    downloader.save_config()
                    Enhanced_Menu.print_status(f"Format set to {new_format.upper()}", "success")
            elif choice == 2:
                # Change bitrate
                bitrates = ["320k", "256k", "192k", "128k", "auto"]
                print("\nSelect bitrate:")
                for i, br in enumerate(bitrates, 1):
                    print(f"  {i}. {br}")
                br_choice = Enhanced_Menu.get_input("Choice", "int", 1, len(bitrates))
                if br_choice:
                    new_quality = bitrates[br_choice - 1]
                    set_current_settings(quality=new_quality)
                    downloader.save_config()
                    Enhanced_Menu.print_status(f"Bitrate set to {new_quality}", "success")
            elif choice == 3:
                current_dir = settings['directory']
                new_dir = Enhanced_Menu.get_input("New output directory", "str", default=current_dir)
                if new_dir and new_dir != current_dir:
                    try:
                        set_current_settings(directory=new_dir)
                        downloader.save_config()
                        Enhanced_Menu.print_status(f"Output directory changed to {new_dir}", "success")
                    except Exception as e:
                        Enhanced_Menu.print_status(f"Error: {e}", "error")
            elif choice == 4:
                downloader.save_config()
                Enhanced_Menu.print_status("Settings saved", "success")
            elif choice == 5:
                # Load configuration and refresh our display
                downloader.load_config()
                Enhanced_Menu.print_status("Settings loaded", "success")
            elif choice == 6:
                if Enhanced_Menu.get_input("Reset all settings to defaults? (y/n)", "yn", default=False):
                    downloader.reset_to_defaults()
                    Enhanced_Menu.print_status("Reset to defaults", "success")
            elif choice == 7:
                break
            if choice != 7:
                input("\nPress Enter to continue...")

    # Action mapping
    actions = {
        1: lambda: downloader.download_track(),
        2: lambda: downloader.download_album(),
        3: lambda: downloader.download_playlist(),
        4: lambda: downloader.download_artist(),
        5: lambda: downloader.search_and_download(),
        
        # Dont make use of 7,8,9 as functions are problematic        
        6: lambda: Enhanced_Menu.print_status("User authentication not available yet", "warning"),
        7: lambda: Enhanced_Menu.print_status("User authentication not available yet", "warning"),
        8: lambda: Enhanced_Menu.print_status("User authentication not available yet", "warning"),        9: lambda: downloader.manage_cookies(),
        10: lambda: downloader.check_dependencies(),
        11: lambda: downloader.check_spotdl(),          # class method, not .utils
        12: lambda: handle_settings(),
        13: lambda: downloader.program_info(),
        14: lambda: downloader.troubleshooting(),
        15: lambda: downloader.show_spotdl_help(),
        16: lambda: downloader.log_manager.interactive_menu(),
        17: lambda: handle_exit()
    }

    while True:
        try:
            Enhanced_Menu.print_header("Main Menu", "Select an option below:")
            current = get_current_settings()

            Enhanced_Menu.print_section("📥 DOWNLOAD OPTIONS")
            Enhanced_Menu.print_menu_item(1, "Download Track")
            Enhanced_Menu.print_menu_item(2, "Download Album")
            Enhanced_Menu.print_menu_item(3, "Download Playlist")
            Enhanced_Menu.print_menu_item(4, "Download Artist")
            Enhanced_Menu.print_menu_item(5, "Search & Download a Song")

            Enhanced_Menu.print_section("🔐 USER-SPECIFIC (requires authentication) not working")
            Enhanced_Menu.print_menu_item(6, "Download User Playlist")
            Enhanced_Menu.print_menu_item(7, "Download User Liked Songs")
            Enhanced_Menu.print_menu_item(8, "Download User Saved Albums")

            Enhanced_Menu.print_section("⚙️  TOOLS & SETTINGS")
            Enhanced_Menu.print_menu_item(9, "Manage Cookies")
            Enhanced_Menu.print_menu_item(10, "Check Dependencies (spotdl & ffmpeg)")
            Enhanced_Menu.print_menu_item(11, "Check spotdl Version")
            Enhanced_Menu.print_menu_item(12, "Program Settings")

            Enhanced_Menu.print_section("❓ HELP & INFORMATION")
            Enhanced_Menu.print_menu_item(13, "Show Program Info")
            Enhanced_Menu.print_menu_item(14, "Troubleshooting")
            Enhanced_Menu.print_menu_item(15, "Show spotdl Help")

            Enhanced_Menu.print_section("📊 LOG MANAGEMENT")
            Enhanced_Menu.print_menu_item(16, "Log Manager")

            Enhanced_Menu.print_section("🚪 EXIT")
            Enhanced_Menu.print_menu_item(17, "Exit Program")

            print(f"\n{Style.DIM}{'─' * 60}{Style.RESET_ALL}")
            Enhanced_Menu.print_status("Current Settings:", "info", "⚙️")
            print(f"  {Fore.CYAN}Format:{Style.RESET_ALL} {Fore.YELLOW}{current['format']}{Style.RESET_ALL}")
            print(f"  {Fore.CYAN}Quality:{Style.RESET_ALL} {Fore.YELLOW}{current['quality']}{Style.RESET_ALL}")
            print(f"  {Fore.CYAN}Output:{Style.RESET_ALL} {Fore.YELLOW}{current['directory']}{Style.RESET_ALL}")
            print(f"{Style.DIM}{'─' * 60}{Style.RESET_ALL}")

            choice = Enhanced_Menu.get_input("\nEnter your choice (1-17)", "int", 1, 17)
            action = actions.get(choice)
            if action:
                Enhanced_Menu.clear_screen()
                try:
                    result = action()
                    # If a download method returns False (failure), offer retry
                    if result is False and choice in (1,2,3,4,5,6,7,8):
                        print()
                        if Enhanced_Menu.get_input("Operation failed. Try again? (y/n)", "yn", default=True):
                            continue
                except KeyboardInterrupt:
                    Enhanced_Menu.print_status("Operation cancelled", "warning")
                except Exception as e:
                    Enhanced_Menu.print_status(f"Error: {e}", "error")
                    import traceback
                    traceback.print_exc()
            else:
                Enhanced_Menu.print_status("Invalid option", "error")

            if choice != 17:
                print()
                if not Enhanced_Menu.get_input("Return to main menu? (y/n)", "yn", default=True):
                    handle_exit()
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Interrupted by user{Style.RESET_ALL}")
            handle_exit()
        except Exception as e:
            Enhanced_Menu.print_status(f"Unexpected error: {e}", "error")
            if not Enhanced_Menu.get_input("Continue? (y/n)", "yn", default=True):
                handle_exit()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        print("Please check the error log for details.")
