def _download_item(self, item_type: str, url_prompt: str, output_template: str = None,
                   additional_args: list = None, confirm_large: bool = False,
                   use_archive: bool = False, concurrent: bool = False,
                   max_workers: int = 3) -> bool:
    """Unified download for tracks, albums, and playlists.

    When concurrent=True (playlist mode) the resource is expanded into its
    individual items which are downloaded in parallel. Otherwise a single
    yt-dlp call handles the whole URL (track / album mode).
    """
    while True:
        print("\n" + "=" * 55)
        Enhanced_Menu.clear_screen()
        Enhanced_Menu.print_header(f"Download {item_type.title()}")

        url = Enhanced_Menu.get_input(f"Enter YouTube Music {url_prompt} (or 'back' to return)", "str")
        if url.lower() == 'back':
            return False
        self.history.add_input(url, item_type)
        if not url:
            Enhanced_Menu.print_status("No URL provided", "error")
            continue

        # Validate URL format
        if not Helpers.validate_youtube_url(url):
            Enhanced_Menu.print_status("Invalid YouTube URL. Enter a valid YouTube/YouTube Music URL", "error")
            continue

        # Validate resource availability
        is_valid, message, metadata = Helpers.validate_resource_youtube(url)
        if not is_valid or not metadata:
            Enhanced_Menu.print_status(f"Validation failed: {message}", "error")
            continue

        # Display resource information
        Enhanced_Menu.print_status("Resource information:", "success")
        if item_type == "track":
            title = metadata.get('title', 'Unknown')
            artist = metadata.get('artist') or metadata.get('uploader', 'Unknown Artist')
            album = metadata.get('album', 'Unknown Album')
            print(f"  {Fore.CYAN}Track:{Style.RESET_ALL} {title}")
            print(f"  {Fore.CYAN}Artist:{Style.RESET_ALL} {artist}")
            if album != 'Unknown Album':
                print(f"  {Fore.CYAN}Album:{Style.RESET_ALL} {album}")
        elif item_type == "album":
            album_title = metadata.get('title', 'Unknown Album')
            album_artist = metadata.get('artist') or metadata.get('uploader', 'Unknown Artist')
            track_count = metadata.get('playlist_count', '?')
            print(f"  {Fore.CYAN}Album:{Style.RESET_ALL} {album_title}")
            print(f"  {Fore.CYAN}Artist:{Style.RESET_ALL} {album_artist}")
            print(f"  {Fore.CYAN}Tracks:{Style.RESET_ALL} {track_count}")
        elif item_type == "playlist":
            playlist_title = metadata.get('title', 'Unknown Playlist')
            playlist_count = metadata.get('playlist_count', 0)
            print(f"  {Fore.CYAN}Playlist:{Style.RESET_ALL} {playlist_title}")
            print(f"  {Fore.CYAN}Videos:{Style.RESET_ALL} {playlist_count}")
        print()  # blank line for readability

        # Confirm large collections
        if confirm_large and metadata.get('playlist_count', 0) > 50:
            count = metadata['playlist_count']
            Enhanced_Menu.print_status(f"This {item_type} contains {count} items. This may take a while.", "warning")
            if not Enhanced_Menu.get_input("Continue with download? (y/n)", "yn", default=False):
                Enhanced_Menu.print_status("Download cancelled", "info")
                continue

        # Ask for configuration if desired
        if Enhanced_Menu.get_input("Configure download settings? (y/n)", "yn", default=False):
            self.get_user_preferences()

        # ---------------- Concurrent (playlist) path ----------------
        if concurrent:
            items = Helpers.get_youtube_playlist_items(url, self.log_manager)
            if not items:
                Enhanced_Menu.print_status("Failed to retrieve playlist items.", "error")
                success = False
            else:
                # Reverse order option
                order = Enhanced_Menu.get_input(
                    "Download order: (t)op-to-bottom or (b)ottom-to-top", "str", default="t")
                if order.lower() == 'b':
                    items.reverse()

                # Setup archive
                playlist_id = Helpers.extract_youtube_playlist_id(url)
                if playlist_id:
                    archive_path = self.archives_dir / f"{playlist_id}.txt"
                else:
                    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                    archive_path = self.archives_dir / f"playlist_{url_hash}.txt"

                # Prepare output folder
                safe_title = Helpers.sanitize_filename(playlist_title)
                playlist_folder = self.__output_directory / safe_title
                playlist_folder.mkdir(parents=True, exist_ok=True)
                collection_template = str(playlist_folder / "%(artist)s - %(title)s.%(ext)s")

                # Build tasks
                tasks = []
                for item in items:
                    video_id = item.get('id')
                    if not video_id:
                        continue
                    video_url = f"https://music.youtube.com/watch?v={video_id}"
                    item_args = ["--download-archive", str(archive_path)]
                    tasks.append((video_url, collection_template, item_args, archive_path, video_id))

                if not tasks:
                    Enhanced_Menu.print_status("No videos to download.", "warning")
                    success = False
                else:
                    Enhanced_Menu.print_status(
                        f"Starting concurrent download of {len(tasks)} videos (max {max_workers} at a time)...", "info")
                    results = self._download_items_concurrently(tasks, max_workers=max_workers, desc="Playlist Download")

                    success_count = sum(1 for v in results.values() if v)
                    failed_count = len(results) - success_count

                    print("\n" + "=" * 55)
                    Enhanced_Menu.print_header("Playlist Download Complete")
                    print(f"  {Fore.GREEN}Successfully downloaded: {success_count}{Style.RESET_ALL}")
                    if failed_count > 0:
                        print(f"  {Fore.RED}Failed: {failed_count}{Style.RESET_ALL}")
                    print("=" * 55)

                    success = failed_count == 0

        # ---------------- Single-call (track / album) path ----------------
        else:
            # copy per-loop so archive flags don't accumulate across iterations
            item_args = list(additional_args) if additional_args else []
            if use_archive:
                playlist_id = Helpers.extract_youtube_playlist_id(url)
                if playlist_id:
                    archive_path = self.archives_dir / f"{playlist_id}.txt"
                    item_args.extend(["--download-archive", str(archive_path)])
                    self.log_manager.log_success(f"Using archive: {archive_path}")
                else:
                    self.log_manager.log_warning(f"Could not extract playlist ID from {url}, archive not used")

            Enhanced_Menu.print_status(f"Starting {item_type} download...", "info")
            success = self._download_with_retry(url, output_template, item_args, item_type)

        # ---------------- Post-download prompt (shared) ----------------
        if success:
            time.sleep(0.5)
            if Enhanced_Menu.get_input(f"\nDownload another {item_type}? (y/n): ", "yn", default=True):
                continue
            return True
        else:
            if Enhanced_Menu.get_input(f"\nDownload failed. Try another {item_type}? (y/n): ", "yn", default=True):
                continue
            return False


def download_playlist(self):
    """Download a playlist with concurrent downloads"""
    return self._download_item(
        item_type="playlist",
        url_prompt="playlist URL",
        output_template=None,        # computed per-playlist inside
        confirm_large=True,
        concurrent=True,
        max_workers=3,
    )