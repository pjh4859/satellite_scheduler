import os
import sys

def resource_path(relative_path):
    """ PyInstaller 개발 환경 및 빌드 후 EXE 환경 모두에서 파일 절대 경로를 찾아주는 함수 """
    try:
        # PyInstaller에 의해 실행될 때 생성되는 임시 폴더 경로
        base_path = sys._MEIPASS
    except Exception:
        # 일반 파이썬 실행 환경 (개발 환경)
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)