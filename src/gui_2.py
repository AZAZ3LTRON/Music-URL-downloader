# launch.py
import sys
from PySide6.QtWidgets import QApplication
from gui.YoutubeDownloaderGUI import MainWindow

app = QApplication(sys.argv)
win = MainWindow()
win.show()
sys.exit(app.exec())