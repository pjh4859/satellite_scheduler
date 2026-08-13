import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui.main_window import SatelliteSchedulerApp

def main():
    app = QApplication(sys.argv)
    
    # 💡 윈도우 작업 표시줄(Taskbar)에서 다른 앱과 겹치지 않고 독립 아이콘으로 표출되도록 설정
    try:
        from ctypes import windll
        myappid = 'space.satellitescheduler.leop.1.0.4'
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    # 💡 main.py와 같은 위치에 있는 app_icon.ico 로드 및 적용
    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, "app_icon.ico")
    
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = SatelliteSchedulerApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()