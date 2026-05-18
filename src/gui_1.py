import sys
from PySide6.QtWidgets import QApplication
from gui.YoutubeDownloaderGUI import YoutubeMusicGUI

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = YoutubeMusicGUI.MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()