# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['F:\\MINE\\Code\\python\\LEOP_pass_schedule_gemini\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('F:\\MINE\\Code\\python\\LEOP_pass_schedule_gemini\\assets', 'assets'), ('F:\\MINE\\Code\\python\\LEOP_pass_schedule_gemini\\tle', 'tle'), ('F:\\MINE\\Code\\python\\LEOP_pass_schedule_gemini\\stations', 'stations'), ('F:\\MINE\\Code\\python\\LEOP_pass_schedule_gemini\\plans', 'plans'), ('F:\\MINE\\Code\\python\\LEOP_pass_schedule_gemini\\pass_output', 'pass_output')],
    hiddenimports=['PyQt6', 'cartopy', 'matplotlib', 'matplotlib.backends.backend_qtagg', 'skyfield', 'numpy', 'openpyxl', 'xlwings', 'yaml'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LEOP_Pass_Scheduler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['F:\\MINE\\Code\\python\\LEOP_pass_schedule_gemini\\assets\\app_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LEOP_Pass_Scheduler',
)
