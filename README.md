# Interactive Music Downloader

So I created this simple to use Music Downloader project to help people who wish to convert from Spotify and Youtube Music for people who just like hoarding music like I do. It possesses the capability to download playlist, albums & tracks, liked songs, saved albims, personal playlisr etc under the condition you possess an account with either one of them. Quite simple to run, configure & understand, each class has been divided the only requirements is that you have spotdl installed but no worries the downloader can install it for you.

However, there are certain requirements to use the downloader.
1. You must have experience with Python and must have installed all required libraries in the requirements.txt
2. If your are using the SpotifyDownloader, you must have a spotify account and a developer based web api (requires Spotify Premium) and Spotdl installed
3. If your are using the YoutubeMusicDownloader, all you need is to have a Youtube account and yt-dlp installed

As for the file structure, it goes like this:
Music-URL-Downloader
    │
    ├── assets                     # Image files for the GUI (in development)
    ├── config                     # Configuration used by the Downloaders (Subject to change)
    ├── gui                        # Contains test files for the GUI
    ├── logs                       # Logs for the downloaders to keep track of success & failed downloads as well as errors
    ├── src/
    |   ├──core
    │   ├──gui          
    │   ├──interface          
    │   ├── test             
    │   ├── utils              
    |   
    |
    ├── .gitignore                   # Git ignore file
    ├── README.md                    # Project documentation
    └── requirements.txt           # Docker setup (optional)
