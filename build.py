import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 💡 assets/ 폴더 내 app_icon.ico 탐색
ICON_PATH = os.path.join(BASE_DIR, "assets", "app_icon.ico")

print("🚀 Starting PyInstaller Build Process...\n")

add_data_args = [
    f"--add-data={os.path.join(BASE_DIR, 'assets')};assets",
    f"--add-data={os.path.join(BASE_DIR, 'tle')};tle",
    f"--add-data={os.path.join(BASE_DIR, 'stations')};stations",
]

extra_icon_args = []
if os.path.exists(ICON_PATH):
    print(f"🎨 Found icon file: {ICON_PATH}")
    extra_icon_args = [f"--icon={ICON_PATH}"]
else:
    print(f"⚠️ Warning: 'app_icon.ico' not found in 'assets/' folder. Building with default icon.")

pyinstaller_cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--onedir",
    "--windowed",
    "--name=LEOP_Pass_Scheduler",
    *extra_icon_args,
    *add_data_args,
    "--hidden-import=cartopy",
    "--hidden-import=skyfield",
    "--hidden-import=matplotlib.backends.backend_qtagg",
    os.path.join(BASE_DIR, "main.py")
]

print("\nExecuting Command:")
print(" ".join(pyinstaller_cmd))
print("\n" + "="*60 + "\n")

try:
    subprocess.run(pyinstaller_cmd, check=True)
    print("\n" + "="*60)
    print("✅ Build Completed Successfully!")
    print(f"📁 Output Directory: {os.path.join(BASE_DIR, 'dist', 'LEOP_Pass_Scheduler')}")
    print("="*60)
except subprocess.CalledProcessError as e:
    print(f"\n❌ Build Failed with error: {e}")