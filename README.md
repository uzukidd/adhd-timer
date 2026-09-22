# Focus Flow

Focus Flow is a PySide6 desktop time-management app for arranging tasks into a repeating focus schedule.

## Features

- Add multiple tasks with vivid color choices.
- Set task duration in hours, minutes, and seconds.
- Choose repeating or one-time execution.
- Drag tasks between the task pool and schedule, then reorder them.
- Run tasks in order and automatically move one-time tasks back to the pool when they finish.
- Use an always-on-top, draggable floating timer with pause and skip controls.
- Hide the main window to the Windows notification area without stopping the timer.
- Left-click the tray icon to open the main UI.
- Right-click the tray icon to choose `Open main UI` or `Exit`.
- Change the UI language between English and Chinese from the main window. English is the default.
- Toggle the floating progress bar and remaining-time display in Settings.
- When the main UI is hidden, seconds are shown only during the final 30 seconds.
- Persist tasks, schedule order, display settings, and language selection.

## Environment

The project uses the dedicated Miniconda environment `adhd-timer`. Do not use the `base` environment or the system Python.

```powershell
& "D:\miniconda3\Scripts\conda.exe" create -n adhd-timer python=3.12 pip -y
& "D:\miniconda3\Scripts\conda.exe" run -n adhd-timer python -m pip install pytest "PySide6-Essentials==6.8.2"
```

## Run

PowerShell:

```powershell
.\scripts\run.bat
```

Or directly:

```powershell
& "D:\miniconda3\Scripts\conda.exe" run -n adhd-timer python -m focus_flow.app
```

Git Bash or a Unix-like shell:

```sh
./scripts/run.sh
```

## Test

PowerShell:

```powershell
.\scripts\test.bat
```

Unix-like shell:

```sh
./scripts/test.sh
```

The application stores its local state under the platform-specific Qt application-data directory.

See [README_zh.md](README_zh.md) for the Chinese documentation.
