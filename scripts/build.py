"""Build a standalone Windows folder, smoke-test it, and create a ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
APP_DIR = DIST / "FocusFlow"


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def verify_bundle() -> None:
    executable = APP_DIR / "FocusFlow.exe"
    required = [
        executable,
        APP_DIR / "_internal" / "assets" / "notification.mp3",
        APP_DIR / "_internal" / "PySide6" / "plugins" / "platforms" / "qwindows.dll",
    ]
    for path in required:
        if not path.is_file():
            raise RuntimeError(f"Required bundle file is missing: {path}")
    if not list(APP_DIR.rglob("Qt6Multimedia.dll")):
        raise RuntimeError("Qt6Multimedia.dll is missing")
    if not list(APP_DIR.rglob("ffmpegmediaplugin.dll")):
        raise RuntimeError("The Qt FFmpeg media plugin is missing")
    asset = ROOT / "assets" / "notification.mp3"
    if asset.read_bytes() != required[1].read_bytes():
        raise RuntimeError("Bundled notification.mp3 differs from the source")

    # Launch outside the source tree with Python/Conda paths removed.
    env = os.environ.copy()
    for key in list(env):
        if key.upper().startswith(("PYTHON", "CONDA", "QT_", "PYSIDE")):
            env.pop(key)
    env["PATH"] = str(Path(env.get("SystemRoot", r"C:\Windows")) / "System32")
    env["QT_MEDIA_BACKEND"] = "ffmpeg"
    with tempfile.TemporaryDirectory(prefix="focus-flow-build-") as temp_dir:
        report = Path(temp_dir) / "smoke-report.json"
        completed = subprocess.run(
            [str(executable), "--smoke-test", str(report)],
            cwd=temp_dir,
            env=env,
            check=False,
            timeout=40,
        )
        if not report.is_file():
            raise RuntimeError(f"Frozen application produced no smoke report (exit {completed.returncode})")
        result = json.loads(report.read_text(encoding="utf-8"))
        result["media_backend"] = "ffmpeg"
        (DIST / "smoke-report.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if completed.returncode or not result.get("ok") or not result.get("frozen"):
            raise RuntimeError(f"Frozen application smoke test failed: {result}")
        print(f"Standalone EXE and MP3 playback verified: {result}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-install", action="store_true", help="Use already installed build dependencies")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("Build Windows executables on Windows")
    if sysconfig.get_platform() != "win-amd64":
        parser.error("Use 64-bit x86 Python to build the Windows x64 distribution")
    if Path(sys.prefix).name.lower() != "adhd-timer":
        parser.error("Run this script in the dedicated adhd-timer Conda environment")
    # Invalidate only outputs owned by this pipeline, so failures cannot leave
    # an earlier ZIP or a success report looking like the current release.
    for name in ("FocusFlow-windows-x64.zip", "FocusFlow-windows-x64.zip.sha256", "smoke-report.json", "build-info.json"):
        (DIST / name).unlink(missing_ok=True)
    if not args.skip_install:
        run([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements-build.txt")])
    run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--distpath", str(DIST), "--workpath", str(ROOT / "build"),
        str(ROOT / "bundle" / "FocusFlow.spec"),
    ])
    verify_bundle()
    build_info = {
        "python": platform.python_version(),
        "python_platform": sysconfig.get_platform(),
        "windows": platform.platform(),
        "packages": {
            name: version(name)
            for name in (
                "PySide6-Essentials", "PySide6-Addons", "shiboken6", "PyInstaller",
                "pyinstaller-hooks-contrib", "altgraph", "pefile", "pywin32-ctypes", "packaging", "setuptools",
            )
        },
    }
    metadata = json.dumps(build_info, ensure_ascii=False, indent=2)
    (DIST / "build-info.json").write_text(metadata, encoding="utf-8")
    (APP_DIR / "build-info.json").write_text(metadata, encoding="utf-8")
    shutil.copy2(ROOT / "LICENSE", APP_DIR / "LICENSE")
    (APP_DIR / "READ_ME.txt").write_text(
        "Focus Flow for Windows\n\n"
        "Extract the entire ZIP, then run FocusFlow.exe.\n"
        "No Python or Conda installation is needed.\n"
        "Keep the _internal folder beside FocusFlow.exe.\n"
        "Closing the window hides it to the system tray; use the tray menu to exit.\n"
        "Planner data is stored in the Windows user application-data directory.\n",
        encoding="utf-8",
    )
    archive_base = DIST / "FocusFlow-windows-x64"
    archive = Path(shutil.make_archive(str(archive_base), "zip", root_dir=DIST, base_dir="FocusFlow"))
    checksum = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    archive.with_suffix(".zip.sha256").write_text(
        f"{checksum.hexdigest()}  {archive.name}\n", encoding="ascii"
    )
    print(f"Executable: {APP_DIR / 'FocusFlow.exe'}", flush=True)
    print(f"Distributable: {archive}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
