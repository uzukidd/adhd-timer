"""Manage the current user's Windows login startup entry."""
import subprocess
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "FocusFlow"


def startup_command() -> str:
    executable = Path(sys.executable)
    windowless = executable.with_name("pythonw.exe")
    if windowless.exists():
        executable = windowless
    launcher = Path(__file__).resolve().parent.parent / "scripts" / "launch.py"
    return subprocess.list2cmdline([str(executable), str(launcher)])


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
        return bool(value)
    except FileNotFoundError:
        return False


def set_enabled(enabled: bool) -> None:
    if sys.platform != "win32":
        if enabled:
            raise OSError("Login startup is supported on Windows only.")
        return
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
