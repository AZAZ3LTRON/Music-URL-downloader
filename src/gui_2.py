import sys
from PySide6.QtWidgets import QApplication
from gui.SpotifyDownloaderGUI import SpotifyMusicGUI

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = SpotifyMusicGUI.MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()