# Run through scripts/build.bat to build, validate, and archive the app.
from pathlib import Path

project_root = Path(SPECPATH).parent

a = Analysis(
    [str(project_root / "bundle" / "launcher.py")],
    pathex=[str(project_root), str(project_root / "bundle")],
    binaries=[],
    datas=[(str(project_root / "assets" / "notification.mp3"), "assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tkinter", "PyQt5", "PyQt6", "PySide2"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FocusFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="FocusFlow",
)
