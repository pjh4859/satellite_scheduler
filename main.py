import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui.main_window import SatelliteSchedulerApp

def get_resource_path(relative_path):
    """PyInstaller (EXE) 환경 및 일반 실행 환경 모두에서 파일 경로를 안전하게 찾아주는 함수"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

def main():
    app = QApplication(sys.argv)
    
    # 윈도우 작업 표시줄(Taskbar) 독립 아이콘 지정
    try:
        from ctypes import windll
        myappid = 'space.satellitescheduler.leop.1.0.4'
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    # 💡 assets/app_icon.ico 경로 지정
    icon_path = get_resource_path(os.path.join("assets", "app_icon.ico"))
    
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = SatelliteSchedulerApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()