"""Exercise the frozen app without reading or saving real planner data."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from PySide6 import __version__ as qt_version
from PySide6.QtCore import QTimer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication

from focus_flow.app import MainWindow
from focus_flow.model import Planner, Task


def run(report_path: str) -> int:
    report = Path(report_path)
    result = {"ok": False, "frozen": bool(getattr(sys, "frozen", False)), "qt_version": qt_version}
    try:
        with tempfile.TemporaryDirectory(prefix="focus-flow-smoke-") as state_dir:
            class SmokeWindow(MainWindow):
                def _load_planner(self) -> Planner:
                    return Planner()

                def _state_path(self) -> Path:
                    return Path(state_dir) / "planner.json"

                def _save(self) -> None:
                    pass

            app = QApplication([sys.argv[0]])
            app.setStyle("Fusion")
            window = SmokeWindow()
            window.clock.stop()
            window.show()
            source = Path(window.notification_player.source().toLocalFile())
            if not source.is_file():
                raise RuntimeError("Bundled notification.mp3 was not found")
            result["audio_source"] = str(source)
            task = Task.create("Smoke test", duration_seconds=60)
            window.floating.update_timer(task, 31, False, show_time=False)
            if window.floating._should_show_time():
                raise RuntimeError("Countdown appeared before the final 30 seconds")
            window.floating.update_timer(task, 30, False, show_time=False)
            if not window.floating._should_show_time():
                raise RuntimeError("Final countdown did not appear")
            window.floating.show()
            player = window.notification_player
            window.notification_audio.setMuted(True)
            player.play()

            def check_audio() -> None:
                if player.error() != QMediaPlayer.Error.NoError:
                    result["error"] = player.errorString()
                    app.quit()
                elif player.duration() > 0 and player.position() > 0:
                    result["audio_duration_ms"] = player.duration()
                    result["audio_position_ms"] = player.position()
                    result["ok"] = True
                    app.quit()

            def timed_out() -> None:
                result["error"] = "Audio backend did not decode and advance the MP3 within 12 seconds"
                app.quit()

            poll = QTimer()
            poll.timeout.connect(check_audio)
            poll.start(100)
            watchdog = QTimer()
            watchdog.setSingleShot(True)
            watchdog.timeout.connect(timed_out)
            watchdog.start(12000)
            app.exec()
            player.stop()
            window._force_exit = True
            window.close()
    except Exception as exc:
        result["error"] = str(exc)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1
