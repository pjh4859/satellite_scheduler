import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(BASE_DIR, "assets", "app_icon.ico")

print("🚀 Starting PyInstaller Build Process for LEOP Pass Scheduler...\n")

# 1. 필수 기본 런타임 폴더 사전 확인 및 생성
required_folders = ["assets", "tle", "stations", "plans", "pass_output"]
for folder in required_folders:
    folder_path = os.path.join(BASE_DIR, folder)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"📁 Created directory: {folder}")

# 2. 리소스 번들링 데이터 구성
add_data_args = [
    f"--add-data={os.path.join(BASE_DIR, 'assets')};assets",
    f"--add-data={os.path.join(BASE_DIR, 'tle')};tle",
    f"--add-data={os.path.join(BASE_DIR, 'stations')};stations",
    f"--add-data={os.path.join(BASE_DIR, 'plans')};plans",
    f"--add-data={os.path.join(BASE_DIR, 'pass_output')};pass_output",
]

# 3. 앱 아이콘 설정 확인
extra_icon_args = []
if os.path.exists(ICON_PATH):
    print(f"🎨 Found icon file: {ICON_PATH}")
    extra_icon_args = [f"--icon={ICON_PATH}"]
else:
    print(f"⚠️ Warning: 'app_icon.ico' not found in 'assets/'. Building with default icon.")

# 4. PyInstaller 빌드 명령어 조합
pyinstaller_cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--onedir",
    "--windowed",
    "--name=LEOP_Pass_Scheduler",
    *extra_icon_args,
    *add_data_args,
    # GUI & 시각화 라이브러리
    "--hidden-import=PyQt6",
    "--hidden-import=cartopy",
    "--hidden-import=matplotlib",
    "--hidden-import=matplotlib.backends.backend_qtagg",
    # 궤도 전파 및 수학 라이브러리
    "--hidden-import=skyfield",
    "--hidden-import=numpy",
    # 파일 입출력 및 DRM 우회 엔진
    "--hidden-import=openpyxl",
    "--hidden-import=xlwings",
    "--hidden-import=yaml",
    os.path.join(BASE_DIR, "main.py")
]

print("\nExecuting Command:")
print(" ".join(pyinstaller_cmd))
print("\n" + "=" * 60 + "\n")

try:
    subprocess.run(pyinstaller_cmd, check=True)
    
    # 5. 빌드 결과 디렉터리에 런타임 폴더 존재 보장
    dist_dir = os.path.join(BASE_DIR, "dist", "LEOP_Pass_Scheduler")
    if os.path.exists(dist_dir):
        for folder in ["tle", "stations", "plans", "pass_output"]:
            target_path = os.path.join(dist_dir, folder)
            if not os.path.exists(target_path):
                os.makedirs(target_path)

    print("\n" + "=" * 60)
    print("✅ Build Completed Successfully!")
    print(f"📁 Output Directory: {dist_dir}")
    print("=" * 60)
except subprocess.CalledProcessError as e:
    print(f"\n❌ Build Failed with error: {e}")