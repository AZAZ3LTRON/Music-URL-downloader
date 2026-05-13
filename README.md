# Interactive Music Downloader

So I created this simple to use Music Downloader project to help people who just like hoarding music like I do. 

It possesses the basic capability of download music from either Spotify or Youtube Music, without requiring an account for either of them (still ok if you got one). Other functionalities include auto sort, mass download, GUI function, download history etc. The downloader has support for both GUI & CLI

To use the downloader, you must:
1. Install all required libraries in the requirements.txt
2. If you're using the SpotifyDownloader, you must have a Spotify account & install SpotDL from this specific repo https://github.com/TzurSoffer/spotify-downloader. Differs from the other SpotDL as it makes use of a non api library to download music from Spotify
3. If you're using the YoutubeMusicDownloader, don't really need a Youtube Account but I recommend so you don't get flag as a bot

Concerning the folder structure, it goes like this:
Music-URL-Downloader
    ├── assets                     # Image files for the GUI
    ├── config                     # Configuration used by both downloaders
    ├── logs                       # Logs for downloaders, helps keep track of successful & failed downloads as well as errors in download process to help with debugging
    │
    ├── src/    
    |   ├──core/                    # Holds the main download processes for both Youtube Music & Spotify 
    │   ├──interface/               # Connects GUI to the core downloader process
    │   ├── gui/                    # GUI elements for the GUI 
    │   ├── test/                   # For test 
    │   ├── utils/                  # Class for better downloader functionality
    |   ├── yt_gui.py               # GUI for youtube music downloader
    |   ├── spot_gui.py             # GUI Spotify Music Downloader 
    |   ├── main_1.py               # CLI for YoutubeMusicDownloader
    │   └── main_2.py               # CLI for SpotifyMusicDownloader
    │
    ├── .gitignore                   # Git ignore file
    ├── README.md                    # Project documentation
    └── requirements.txt           # Docker setup (optional)
