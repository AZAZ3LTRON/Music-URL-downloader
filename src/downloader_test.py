#!/usr/bin/env python3
"""
Deezer Music Downloader using deemix library
Features: Track, Album, Playlist, Artist downloads with ARL authentication
"""

import os
import sys
import json
import logging
import asyncio
import aiohttp
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
import re

# Import deemix
try:
    from deemix import Deezer
    from deemix.utils import getBitrateNumberFromText
    from deemix.settings import load as loadSettings
    from deemix.settings import save as saveSettings
    from deemix.downloader import Downloader
    from deemix.utils import getBitrateNumberFromText
    HAVE_DEEMIX = True
except ImportError:
    HAVE_DEEMIX = False
    print("Warning: deemix not installed. Install with: pip install deemix-py")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deemix_downloader.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DeemixDownloader:
    """Main class for Deezer downloading using deemix library"""
    
    def __init__(self, config_path: str = "deemix_config.json"):
        self.config_path = Path(config_path)
        self.config = self.load_config()
        self.deezer = None
        self.downloader = None
        self.session = None
        
        self.setup_directories()
        self.setup_deemix_config()
        
        self.stats = {
            "total_downloads": 0,
            "successful": 0,
            "failed": 0,
            "start_time": None,
            "end_time": None
        }
        
        # URL patterns
        self.deezer_patterns = [
            r'deezer\.com/(?:[a-z]{2}/)?(track|album|playlist|artist)/(\d+)',
            r'deezer\.page\.link/([a-zA-Z0-9]+)',
            r'track/(\d+)',
            r'^(\d+)$'  # Direct ID
        ]
    
    def load_config(self) -> Dict[str, Any]:
        """Load or create configuration file"""
        default_config = {
            "download_dir": "./Deezer Downloads",
            "quality": "FLAC",  # MP3_128, MP3_256, MP3_320, FLAC
            "fallback_quality": "MP3_320",
            "arl_token": "",  # Required for downloads
            "save_covers": True,
            "embedded_artwork": True,
            "embedded_artwork_size": 1000,
            "save_lyrics": False,
            "embedded_lyrics": False,
            "synced_lyrics": False,
            "save_metadata": True,
            "create_m3u": False,
            "create_single_folder": False,
            "create_album_folder": True,
            "create_playlist_folder": True,
            "max_bitrate": None,
            "queue_concurrency": 3,
            "max_retries": 3,
            "retry_delay": 5,
            "template": {
                "track": "{artist} - {title}",
                "album": "{artist}/{album}/{tracknumber}. {title}",
                "playlist": "Playlists/{playlist}/{position} - {artist} - {title}",
                "compilation": "Various Artists/{album}/{tracknumber}. {title}"
            }
        }
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Merge with defaults
                    for key, value in default_config.items():
                        if key not in loaded:
                            loaded[key] = value
                    return loaded
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        
        # Create default config
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2)
        
        return default_config
    
    def save_config(self) -> None:
        """Save current configuration"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)
    
    def setup_directories(self) -> None:
        """Create necessary directories"""
        directories = [
            self.config["download_dir"],
            f"{self.config['download_dir']}/Tracks",
            f"{self.config['download_dir']}/Albums",
            f"{self.config['download_dir']}/Playlists",
            f"{self.config['download_dir']}/Artists",
            f"{self.config['download_dir']}/Covers",
            "./logs",
            "./temp",
            str(Path.home() / ".config/deemix")
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def setup_deemix_config(self) -> None:
        """Setup deemix configuration files"""
        deemix_config_dir = Path.home() / ".config/deemix"
        deemix_config_dir.mkdir(parents=True, exist_ok=True)
        
        # Settings file
        settings_file = deemix_config_dir / "config.json"
        
        if not settings_file.exists():
            settings = {
                "downloadLocation": str(Path(self.config["download_dir"]).absolute()),
                "tracknameTemplate": self.config["template"]["track"],
                "albumTracknameTemplate": self.config["template"]["album"],
                "playlistTracknameTemplate": self.config["template"]["playlist"],
                "createPlaylistFolder": self.config["create_playlist_folder"],
                "createCDFolder": False,
                "createSingleFolder": self.config["create_single_folder"],
                "createAlbumFolder": self.config["create_album_folder"],
                "saveArtwork": self.config["save_covers"],
                "embeddedArtwork": self.config["embedded_artwork"],
                "embeddedArtworkSize": self.config["embedded_artwork_size"],
                "saveArtworkArtist": False,
                "jpegImageQuality": 90,
                "paddingLength": "0",
                "createM3U": self.config["create_m3u"],
                "playlistFilenameTemplate": "playlist",
                "syncedLyrics": self.config["synced_lyrics"],
                "embeddedLyrics": self.config["embedded_lyrics"],
                "tags": {
                    "title": True,
                    "artist": True,
                    "album": True,
                    "cover": True,
                    "trackNumber": True,
                    "trackTotal": False,
                    "discNumber": True,
                    "discTotal": False,
                    "albumArtist": True,
                    "genre": True,
                    "year": True,
                    "date": True,
                    "explicit": False,
                    "isrc": True,
                    "length": False,
                    "barcode": False,
                    "bpm": False,
                    "replayGain": False,
                    "label": True,
                    "lyrics": self.config["save_lyrics"],
                    "syncedLyrics": self.config["synced_lyrics"],
                    "copyright": False,
                    "rating": False,
                    "savePlaylistAsCompilation": False,
                    "useNullSeparator": False,
                    "featuredToTitle": {
                        "format": "%title% (feat. %artist%)",
                        "separator": "; "
                    }
                },
                "queueConcurrency": self.config["queue_concurrency"],
                "maxBitrate": self.config["max_bitrate"],
                "fallbackBitrate": getBitrateNumberFromText(self.config["fallback_quality"]),
                "logErrors": True
            }
            
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
            
            logger.info("Deemix configuration created")
    
    async def initialize(self) -> bool:
        """Initialize deemix with ARL token"""
        if not HAVE_DEEMIX:
            logger.error("deemix library not installed. Install with: pip install deemix-py")
            return False
        
        try:
            # Load settings
            settings = loadSettings()
            
            # Create Deezer instance
            self.deezer = Deezer()
            
            # Login with ARL token
            if self.config["arl_token"]:
                logger.info("Logging in to Deezer with ARL token...")
                self.deezer.login_via_arl(self.config["arl_token"])
                
                if self.deezer.logged_in:
                    logger.info("Successfully logged in to Deezer")
                    
                    # Create downloader
                    self.downloader = Downloader(self.deezer, settings)
                    
                    # Create aiohttp session
                    self.session = aiohttp.ClientSession()
                    
                    return True
                else:
                    logger.error("Failed to login to Deezer. Check ARL token.")
                    return False
            else:
                logger.error("No ARL token provided. Please add your ARL token to config.")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize deemix: {e}")
            return False
    
    async def close(self) -> None:
        """Close connections"""
        if self.session:
            await self.session.close()
    
    def extract_deezer_id(self, url: str) -> Optional[Dict[str, str]]:
        """Extract Deezer ID and type from URL"""
        for pattern in self.deezer_patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:
                    return {"type": match.group(1), "id": match.group(2)}
                elif len(match.groups()) == 1:
                    # Try to determine type from URL
                    if "track" in url.lower():
                        return {"type": "track", "id": match.group(1)}
                    elif "album" in url.lower():
                        return {"type": "album", "id": match.group(1)}
                    elif "playlist" in url.lower():
                        return {"type": "playlist", "id": match.group(1)}
                    elif "artist" in url.lower():
                        return {"type": "artist", "id": match.group(1)}
                    else:
                        # Default to track
                        return {"type": "track", "id": match.group(1)}
        return None
    
    async def download_track(self, track_id: str) -> bool:
        """Download a single track"""
        try:
            logger.info(f"Downloading track ID: {track_id}")
            
            # Get track object
            track = self.deezer.get_track(track_id)
            
            if not track:
                logger.error(f"Track not found: {track_id}")
                return False
            
            # Download track
            result = await self.downloader.download(track, self.config["quality"])
            
            if result:
                logger.info(f"Successfully downloaded track: {track['title']}")
                self.stats["successful"] += 1
                return True
            else:
                logger.error(f"Failed to download track: {track_id}")
                self.stats["failed"] += 1
                return False
                
        except Exception as e:
            logger.error(f"Error downloading track {track_id}: {e}")
            self.stats["failed"] += 1
            return False
    
    async def download_album(self, album_id: str) -> bool:
        """Download an entire album"""
        try:
            logger.info(f"Downloading album ID: {album_id}")
            
            # Get album object
            album = self.deezer.get_album(album_id)
            
            if not album:
                logger.error(f"Album not found: {album_id}")
                return False
            
            # Get album tracks
            tracks = self.deezer.get_album_tracks(album_id)
            
            if not tracks:
                logger.error(f"No tracks found for album: {album_id}")
                return False
            
            logger.info(f"Found {len(tracks)} tracks in album: {album['title']}")
            
            success_count = 0
            for i, track in enumerate(tracks, 1):
                logger.info(f"Downloading track {i}/{len(tracks)}: {track['title']}")
                
                result = await self.downloader.download(track, self.config["quality"])
                
                if result:
                    success_count += 1
                else:
                    logger.warning(f"Failed to download track: {track['title']}")
            
            if success_count == len(tracks):
                logger.info(f"Successfully downloaded entire album: {album['title']}")
                self.stats["successful"] += 1
                return True
            elif success_count > 0:
                logger.info(f"Partially downloaded album: {success_count}/{len(tracks)} tracks")
                self.stats["successful"] += 1
                return True
            else:
                logger.error(f"Failed to download album: {album_id}")
                self.stats["failed"] += 1
                return False
                
        except Exception as e:
            logger.error(f"Error downloading album {album_id}: {e}")
            self.stats["failed"] += 1
            return False
    
    async def download_playlist(self, playlist_id: str) -> bool:
        """Download a playlist"""
        try:
            logger.info(f"Downloading playlist ID: {playlist_id}")
            
            # Get playlist object
            playlist = self.deezer.get_playlist(playlist_id)
            
            if not playlist:
                logger.error(f"Playlist not found: {playlist_id}")
                return False
            
            # Get playlist tracks
            tracks = self.deezer.get_playlist_tracks(playlist_id)
            
            if not tracks:
                logger.error(f"No tracks found for playlist: {playlist_id}")
                return False
            
            logger.info(f"Found {len(tracks)} tracks in playlist: {playlist['title']}")
            
            success_count = 0
            for i, track in enumerate(tracks, 1):
                logger.info(f"Downloading track {i}/{len(tracks)}: {track['title']}")
                
                result = await self.downloader.download(track, self.config["quality"])
                
                if result:
                    success_count += 1
                else:
                    logger.warning(f"Failed to download track: {track['title']}")
            
            if success_count == len(tracks):
                logger.info(f"Successfully downloaded entire playlist: {playlist['title']}")
                self.stats["successful"] += 1
                return True
            elif success_count > 0:
                logger.info(f"Partially downloaded playlist: {success_count}/{len(tracks)} tracks")
                self.stats["successful"] += 1
                return True
            else:
                logger.error(f"Failed to download playlist: {playlist_id}")
                self.stats["failed"] += 1
                return False
                
        except Exception as e:
            logger.error(f"Error downloading playlist {playlist_id}: {e}")
            self.stats["failed"] += 1
            return False
    
    async def download_artist(self, artist_id: str) -> Dict[str, int]:
        """Download artist's top tracks and albums"""
        try:
            logger.info(f"Downloading artist ID: {artist_id}")
            
            # Get artist object
            artist = self.deezer.get_artist(artist_id)
            
            if not artist:
                logger.error(f"Artist not found: {artist_id}")
                return {"tracks": 0, "albums": 0, "success": False}
            
            logger.info(f"Downloading content for artist: {artist['name']}")
            
            results = {"tracks": 0, "albums": 0, "success": True}
            
            # Download top tracks
            top_tracks = self.deezer.get_artist_top_tracks(artist_id, limit=25)
            if top_tracks:
                logger.info(f"Downloading {len(top_tracks)} top tracks...")
                for track in top_tracks:
                    if await self.download_track(str(track['id'])):
                        results["tracks"] += 1
            
            # Download albums
            albums = self.deezer.get_artist_albums(artist_id)
            if albums:
                logger.info(f"Downloading {len(albums)} albums...")
                for album in albums:
                    if await self.download_album(str(album['id'])):
                        results["albums"] += 1
            
            logger.info(f"Finished downloading artist: {artist['name']}")
            logger.info(f"Downloaded {results['tracks']} tracks and {results['albums']} albums")
            
            self.stats["successful"] += 1
            return results
                
        except Exception as e:
            logger.error(f"Error downloading artist {artist_id}: {e}")
            self.stats["failed"] += 1
            return {"tracks": 0, "albums": 0, "success": False}
    
    async def download_from_url(self, url: str) -> bool:
        """Download from any Deezer URL"""
        url_info = self.extract_deezer_id(url)
        
        if not url_info:
            logger.error(f"Invalid Deezer URL: {url}")
            return False
        
        logger.info(f"Detected {url_info['type']} with ID: {url_info['id']}")
        
        if url_info["type"] == "track":
            return await self.download_track(url_info["id"])
        elif url_info["type"] == "album":
            return await self.download_album(url_info["id"])
        elif url_info["type"] == "playlist":
            return await self.download_playlist(url_info["id"])
        elif url_info["type"] == "artist":
            result = await self.download_artist(url_info["id"])
            return result["success"]
        else:
            logger.error(f"Unknown type: {url_info['type']}")
            return False
    
    async def download_from_file(self, file_path: str) -> Dict[str, int]:
        """Download multiple URLs from a text file"""
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return {"success": 0, "failed": 0}
        
        with open(file_path, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        logger.info(f"Found {len(urls)} URLs to download")
        
        results = {"success": 0, "failed": 0}
        
        for i, url in enumerate(urls, 1):
            logger.info(f"Processing URL {i}/{len(urls)}: {url}")
            
            success = await self.download_from_url(url)
            
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1
        
        return results
    
    async def search_and_download(self, query: str, limit: int = 10) -> Dict[str, int]:
        """Search for tracks and download"""
        try:
            logger.info(f"Searching for: {query}")
            
            # Search for tracks
            search_results = self.deezer.search_track(query, limit=limit)
            
            if not search_results or 'data' not in search_results or not search_results['data']:
                logger.warning(f"No results found for: {query}")
                return {"success": 0, "failed": 0}
            
            logger.info(f"Found {len(search_results['data'])} results")
            
            results = {"success": 0, "failed": 0}
            
            for i, track in enumerate(search_results['data'], 1):
                logger.info(f"Downloading result {i}/{len(search_results['data'])}: {track['title']}")
                
                success = await self.download_track(str(track['id']))
                
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching for {query}: {e}")
            return {"success": 0, "failed": 0}
    
    def interactive_mode(self) -> None:
        """Interactive command-line mode"""
        print("\n" + "="*60)
        print("DEEZER DOWNLOADER - Interactive Mode")
        print("="*60)
        
        async def run_interactive():
            # Initialize deemix
            if not await self.initialize():
                print("Failed to initialize deemix. Please check your ARL token.")
                return
            
            try:
                while True:
                    print("\nOptions:")
                    print("1. Download Track/Album/Playlist/Artist")
                    print("2. Download from File")
                    print("3. Search and Download")
                    print("4. View Statistics")
                    print("5. Update Configuration")
                    print("6. Exit")
                    
                    choice = input("\nEnter choice (1-6): ").strip()
                    
                    if choice == "1":
                        url = input("Enter Deezer URL: ").strip()
                        if url:
                            await self.download_from_url(url)
                    
                    elif choice == "2":
                        file_path = input("Enter path to text file: ").strip()
                        if file_path and os.path.exists(file_path):
                            results = await self.download_from_file(file_path)
                            print(f"Results: {results['success']} successful, {results['failed']} failed")
                    
                    elif choice == "3":
                        query = input("Enter search query: ").strip()
                        limit = input("Number of results to download (default 10): ").strip()
                        limit = int(limit) if limit.isdigit() else 10
                        
                        if query:
                            results = await self.search_and_download(query, limit)
                            print(f"Results: {results['success']} successful, {results['failed']} failed")
                    
                    elif choice == "4":
                        self.show_statistics()
                    
                    elif choice == "5":
                        self.update_config_interactive()
                        # Reinitialize with new config
                        await self.initialize()
                    
                    elif choice == "6":
                        print("Exiting...")
                        self.show_statistics()
                        break
                    
                    else:
                        print("Invalid choice. Please try again.")
            
            finally:
                await self.close()
        
        # Run async interactive mode
        asyncio.run(run_interactive())
    
    def update_config_interactive(self) -> None:
        """Update configuration interactively"""
        print("\nCurrent Configuration:")
        for key, value in self.config.items():
            if isinstance(value, dict):
                print(f"\n{key}:")
                for sub_key, sub_value in value.items():
                    print(f"  {sub_key}: {sub_value}")
            else:
                print(f"{key}: {value}")
        
        print("\nAvailable qualities: MP3_128, MP3_256, MP3_320, FLAC")
        new_quality = input("Enter new quality (press Enter to keep current): ").strip()
        if new_quality in ["MP3_128", "MP3_256", "MP3_320", "FLAC"]:
            self.config["quality"] = new_quality
        
        if not self.config["arl_token"]:
            print("\nARL Token is required for downloading from Deezer.")
            print("Get your ARL token by:")
            print("1. Log into Deezer in your browser")
            print("2. Open Developer Tools (F12)")
            print("3. Go to Application/Storage > Cookies > https://www.deezer.com")
            print("4. Copy the value of the 'arl' cookie")
        
        new_arl = input("Enter ARL token (press Enter to keep current): ").strip()
        if new_arl:
            self.config["arl_token"] = new_arl
        
        new_dir = input(f"Enter download directory (current: {self.config['download_dir']}): ").strip()
        if new_dir:
            self.config["download_dir"] = new_dir
            self.setup_directories()
        
        save_covers = input("Save cover art? (y/n): ").strip().lower()
        if save_covers in ['y', 'n']:
            self.config["save_covers"] = save_covers == 'y'
        
        self.save_config()
        print("Configuration updated!")
    
    def show_statistics(self) -> None:
        """Display download statistics"""
        print("\n" + "="*60)
        print("DOWNLOAD STATISTICS")
        print("="*60)
        print(f"Successful downloads: {self.stats['successful']}")
        print(f"Failed downloads: {self.stats['failed']}")
        print(f"Total downloads: {self.stats['successful'] + self.stats['failed']}")
        
        if self.stats['successful'] + self.stats['failed'] > 0:
            success_rate = (self.stats['successful'] / (self.stats['successful'] + self.stats['failed'])) * 100
            print(f"Success rate: {success_rate:.1f}%")
        
        print("="*60)
    
    def cleanup(self) -> None:
        """Clean up temporary files"""
        temp_dir = Path("./temp")
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir)
            logger.info("Cleaned up temporary files")


async def main_async():
    """Async main function"""
    parser = argparse.ArgumentParser(description="Deezer Music Downloader using deemix")
    
    parser.add_argument(
        "-u", "--url",
        help="Download from Deezer URL (track, album, playlist, artist)"
    )
    
    parser.add_argument(
        "-i", "--input-file",
        help="Download from text file containing URLs"
    )
    
    parser.add_argument(
        "-s", "--search",
        help="Search and download tracks"
    )
    
    parser.add_argument(
        "-q", "--quality",
        choices=["MP3_128", "MP3_256", "MP3_320", "FLAC"],
        help="Audio quality"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Output directory"
    )
    
    parser.add_argument(
        "-a", "--arl",
        help="Deezer ARL token"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Limit for search results"
    )
    
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Start in interactive mode"
    )
    
    parser.add_argument(
        "--config",
        default="deemix_config.json",
        help="Configuration file path"
    )
    
    args = parser.parse_args()
    
    if not HAVE_DEEMIX:
        print("Error: deemix library not found.")
        print("Install it with: pip install deemix-py")
        sys.exit(1)
    
    # Initialize downloader
    downloader = DeemixDownloader(args.config)
    
    # Update config from command line arguments
    if args.quality:
        downloader.config["quality"] = args.quality
    
    if args.output:
        downloader.config["download_dir"] = args.output
        downloader.setup_directories()
    
    if args.arl:
        downloader.config["arl_token"] = args.arl
    
    # Initialize deemix
    if not await downloader.initialize():
        print("Failed to initialize deemix. Check your ARL token.")
        sys.exit(1)
    
    try:
        if args.interactive:
            downloader.interactive_mode()
        elif args.url:
            await downloader.download_from_url(args.url)
        elif args.input_file:
            results = await downloader.download_from_file(args.input_file)
            print(f"Results: {results['success']} successful, {results['failed']} failed")
        elif args.search:
            results = await downloader.search_and_download(args.search, args.limit)
            print(f"Results: {results['success']} successful, {results['failed']} failed")
        else:
            # No arguments, show help and start interactive
            parser.print_help()
            print("\nStarting interactive mode...\n")
            downloader.interactive_mode()
    
    except KeyboardInterrupt:
        print("\n\nDownload interrupted by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"Error: {e}")
    finally:
        await downloader.close()
        downloader.show_statistics()
        downloader.cleanup()


def main():
    """Main entry point"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user.")


if __name__ == "__main__":
    main()