# Interactive Music Downloader

So I created this simple to use Music Downloader project to help people who wish to convert from Spotify and Youtube Music for people who just like hoarding music like I do. It possesses the capability to download playlist, albums & tracks, liked songs, saved albims, personal playlisr etc under the condition you possess an account with either one of them. Quite simple to run, configure & understand, each class has been divided the only requirements is that you have spotdl installed but no worries the downloader can install it for you.

However, there are certain requirements to use the downloader.
1. You must have experience with Python and must have installed all required libraries in the requirements.txt
2. If your are using the SpotifyDownloader, you must have a spotify account and a developer based web api (requires Spotify Premium) and Spotdl installed
3. If your are using the YoutubeMusicDownloader, all you need is to have a Youtube account and yt-dlp installed

As for the file structure, it goes like this:
Music-URL-Downloader
<<<<<<< HEAD
    │
    ├── assets                     # Image files for the GUI (in development)
    ├── config                     # Configuration used by the Downloaders (Subject to change)
    ├── gui                        # Contains test files for the GUI
    ├── logs                       # Logs for the downloaders to keep track of success & failed downloads as well as errors
    ├── src/
    |   ├── __pycache__
    │   ├── CookieManager.py             # Manages Cookie collection from browser
    │   ├── Downloader_Utils.py          # Handles all downloader utilities like checking for missing libraries and user authentication and downloader configuration
    │   ├── EnhancedMenu.py              # Creates beautiful menu interfaces
    │   ├── Logs_Handler.py              # Is responsible for logging successful, failed & errors in downloads
    |   ├── SpotifyDownloader.py         # Music Downloader that makes use of Spotdl
    |   ├── TestDownloader.py            # Always make sure to test before implementing changes permanently
    |   └── YoutubeMusicDownloader.py     # Music Downloader that makes use of Ytdlp
    |
    ├── .gitignore                   # Git ignore file
    ├── README.md                    # Project documentation
    └── requirements.txt           # Docker setup (optional)

Unfortuntely, this program was developed on a Windows machine, however, I have pointed out areas subject to change for Linux & Mac Machines. Other than that, have a good one with the Program
=======
│
├── assets                     # Image files for the GUI (in development)
├── config                     # Configuration used by the Downloaders (Subject to change)
├── gui                        # Contains test files for the GUI
├── logs                       # Logs for the downloaders to keep track of success & failed downloads as well as errors
├── src/
|   ├── __pycache__
│   ├── CookieManager.py             # Manages Cookie collection from browser
│   ├── Downloader_Utils.py          # Handles all downloader utilities like checking for missing libraries
│   ├── EnhancedMenu.py              # Creates beautiful menu interfaces
│   ├── Logs_Handler.py              # Is responsible for logging successful, failed & errors in downloads
|   ├── SpotifyDownloader.py         # Music Downloader that makes use of Spotdl
|   ├── TestDownloader.py            # Always make sure to test before implementing changes permanently
|   └──YoutubeMusicDownloader.py     # Music Downloader that makes use of Ytdlp
|
├── .gitignore                   # Git ignore file
├── README.md                    # Project documentation
└── requirements.txt           # Docker setup (optional)

 Unfortuntely, this program was developed on a Windows machine, however, I have pointed out areas subject to change for Linux & Mac Machines

 Have a good one with the Program
>>>>>>> 9c6f8d9992bcfe94147c809242bc5beff5e85d73

# PLEASE READ:

As of 18th of Febraury, A Web API from Spotify Downloader will be required to download from Spotify as they have begun to crack down on Piracy due to a massive database scrap of about 300TB occuring last year. Their new policy requires that you pay for the Web API to do this.
<<<<<<< HEAD

spotdl download https://open.spotify.com/track/0bM9c5A7CterSOEssmWqAa --output {artist} - {title}.{output-ext} --ovewrite skip --bitrate 320k --format mp3 --client-id 2562110a6d974603b50bf0fd76927293 --client-secret 371cf8fe99aa423188eebdf4784be347 --auth-token BQDOux5LAAnVOLhHVOL5XP4JD7CvxuD_3Iz3g2Ye6GkQ64r7UFZlC9q2oGxgXvVFKDEI7CZEYqK4XaoqGr7KCF2qMSKJT2LPe1DblEKRrvet-PXqIKU4spmknCUEU1mnXVtR185ykAM

spotdl download https://open.spotify.com/track/0bM9c5A7CterSOEssmWqAa --bitrate 320k --format mp3 --auth-token BQBh2PIqhwVnCpfwewRg4Byqs6acRBrwx6vvwqqsacpGEbHhN6T-PmtTYOTABSsTegsuqBLYB6wmq2xRbcBUCQZEZGAkAtbCCD2a08mSAXLYAVdUNCIah1S8ahax-R4uZxabsL5RpfE
=======
>>>>>>> 9c6f8d9992bcfe94147c809242bc5beff5e85d73
