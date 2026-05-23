import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import SatelliteSchedulerApp

def main():
    app = QApplication(sys.argv)
    window = SatelliteSchedulerApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()