"""Desktop entry point for Focus Flow."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QFont, QIcon, QKeyEvent, QPainter, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QListWidgetItem,
    QPushButton,
    QSystemTrayIcon,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .i18n import SUPPORTED_LANGUAGES, tr
from .model import Planner, Task
from .widgets import FloatingTimer, SettingsDialog, TaskDelegate, TaskDialog, TaskListWidget

APP_STYLE = """
QMainWindow, QDialog { background: #111a23; color: #f4f7fa; }
QWidget { color: #f4f7fa; font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; font-size: 13px; }
QLabel#eyebrow { color: #6f8494; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
QLabel#headline { color: #f6f8fa; font-size: 27px; font-weight: 700; }
QLabel#sectionTitle { color: #f4f7fa; font-size: 16px; font-weight: 700; }
QLabel#sectionMeta, QLabel#hint, QLabel#emptyState { color: #748897; }
QLabel#emptyState { padding: 10px 4px; }
QLabel#chip { background: #1b2a36; border: 1px solid #2a3d4c; border-radius: 12px; padding: 5px 10px; color: #a9bbc6; }
QFrame#sidebar, QFrame#mainPanel { background: #16222d; border: 1px solid #243542; border-radius: 12px; }
QFrame#sidebar { background: #14202a; }
QFrame#separator { background: #233541; max-height: 1px; }
QPushButton { background: #223340; border: 1px solid #324958; border-radius: 7px; padding: 9px 13px; color: #e9f0f4; }
QPushButton:hover { background: #2b4251; border-color: #4a6575; }
QPushButton:pressed { background: #1b2a35; }
QPushButton#primary { background: #11a986; border: 1px solid #21c89f; color: #071a17; font-weight: 700; padding: 10px 18px; }
QPushButton#primary:hover { background: #22bd9c; }
QPushButton#danger { color: #ff9aa8; }
QLineEdit, QSpinBox { background: #172630; border: 1px solid #334956; border-radius: 6px; padding: 9px 10px; color: #f4f7fa; selection-background-color: #287a72; }
QLineEdit:focus, QSpinBox:focus { border-color: #18b892; }
QRadioButton { spacing: 7px; color: #b5c4cc; }
QRadioButton::indicator { width: 14px; height: 14px; }
QRadioButton::indicator:unchecked { border: 1px solid #556b79; border-radius: 7px; background: #172630; }
QRadioButton::indicator:checked { border: 4px solid #15b28c; border-radius: 7px; background: #d8fff3; }
QLabel#dialogHeading { font-size: 20px; font-weight: 700; }
QLabel#dialogSection { color: #8ea2af; font-size: 11px; font-weight: 700; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 3px; }
QScrollBar::handle:vertical { background: #38505e; border-radius: 4px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(980, 680)
        self.resize(1180, 760)
        self.setStyleSheet(APP_STYLE)
        self.planner = self._load_planner()
        self.language = self.planner.settings.get("language", "en") if self.planner.settings.get("language") in SUPPORTED_LANGUAGES else "en"
        self.setWindowTitle(tr("window_title", self.language))
        self.store_path = self._state_path()
        self.last_tick = time.monotonic()
        self.status_message = tr("status_initial", self.language)
        self._force_exit = False
        self._exit_scheduled = False

        self.pool_list = TaskListWidget("pool")
        self.schedule_list = TaskListWidget("schedule")
        self.pool_list.task_dropped.connect(lambda task_id, row: self._handle_drop("pool", task_id, row))
        self.schedule_list.task_dropped.connect(lambda task_id, row: self._handle_drop("schedule", task_id, row))
        self.pool_list.task_activated.connect(self._edit_task)
        self.schedule_list.task_activated.connect(self._edit_task)
        self.pool_list.setItemDelegate(TaskDelegate(self.pool_list, self._get_task, lambda: self.planner.current_id, lambda: self.language))
        self.schedule_list.setItemDelegate(TaskDelegate(self.schedule_list, self._get_task, lambda: self.planner.current_id, lambda: self.language))

        self.floating = FloatingTimer()
        self.notification_player = QMediaPlayer(self)
        self.notification_audio = QAudioOutput(self)
        self.notification_audio.setVolume(1.0)
        self.notification_player.setAudioOutput(self.notification_audio)
        notification_path = Path(__file__).resolve().parent.parent / "assets" / "notification.mp3"
        if notification_path.exists():
            self.notification_player.setSource(QUrl.fromLocalFile(str(notification_path)))
        self.floating.open_requested.connect(self._show_main_menu)
        self.floating.pause_clicked.connect(self._toggle_pause)
        self.floating.skip_clicked.connect(self._skip_task)

        self._build_ui()
        self._create_tray()
        self.refresh_lists()
        self._sync_controls()

        self.clock = QTimer(self)
        self.clock.setInterval(250)
        self.clock.timeout.connect(self._tick)
        self.clock.start()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(28, 24, 28, 22)
        root_layout.setSpacing(20)

        top = QHBoxLayout()
        top.setSpacing(14)
        heading_box = QVBoxLayout()
        heading_box.setSpacing(3)
        eyebrow = QLabel("FOCUS FLOW")
        eyebrow.setObjectName("eyebrow")
        heading_box.addWidget(eyebrow)
        self.headline = QLabel(tr("headline", self.language))
        self.headline.setObjectName("headline")
        heading_box.addWidget(self.headline)
        top.addLayout(heading_box)
        top.addStretch(1)
        self.pool_chip = QLabel()
        self.pool_chip.setObjectName("chip")
        self.done_chip = QLabel(tr("timer_ready", self.language))
        self.done_chip.setObjectName("chip")
        self.language_combo = QComboBox()
        self.language_combo.setAccessibleName(tr("language", self.language))
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("中文", "zh")
        self.language_combo.setCurrentIndex(0 if self.language == "en" else 1)
        self.language_combo.currentIndexChanged.connect(self._change_language)
        top.addWidget(self.language_combo)
        top.addWidget(self.pool_chip)
        top.addWidget(self.done_chip)
        self.settings_button = QPushButton(tr("settings", self.language))
        self.settings_button.clicked.connect(self._open_settings)
        top.addWidget(self.settings_button)
        self.add_button = QPushButton(tr("new_task", self.language))
        self.add_button.setObjectName("primary")
        self.add_button.clicked.connect(self._add_task)
        top.addWidget(self.add_button)
        root_layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(12)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(275)
        sidebar.setMaximumWidth(360)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(18, 18, 18, 18)
        side_layout.setSpacing(10)
        side_header = QHBoxLayout()
        self.pool_title = QLabel(tr("task_pool", self.language))
        self.pool_title.setObjectName("sectionTitle")
        side_header.addWidget(self.pool_title)
        side_header.addStretch(1)
        self.pool_caption = QLabel(tr("pool_caption", self.language))
        self.pool_caption.setObjectName("sectionMeta")
        side_header.addWidget(self.pool_caption)
        side_layout.addLayout(side_header)
        self.pool_hint = QLabel(tr("pool_hint", self.language))
        self.pool_hint.setObjectName("hint")
        side_layout.addWidget(self.pool_hint)
        side_layout.addWidget(self.pool_list, 1)
        self.pool_empty = QLabel(tr("pool_empty", self.language))
        self.pool_empty.setObjectName("emptyState")
        self.pool_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_layout.addWidget(self.pool_empty)
        self.remove_button = QPushButton(tr("delete_selected", self.language))
        self.remove_button.setObjectName("danger")
        self.remove_button.clicked.connect(self._remove_selected)
        side_layout.addWidget(self.remove_button)

        main_panel = QFrame()
        main_panel.setObjectName("mainPanel")
        main_layout = QVBoxLayout(main_panel)
        main_layout.setContentsMargins(22, 20, 22, 18)
        main_layout.setSpacing(12)
        schedule_header = QHBoxLayout()
        schedule_title_box = QVBoxLayout()
        schedule_title_box.setSpacing(3)
        self.schedule_title = QLabel(tr("today_schedule", self.language))
        self.schedule_title.setObjectName("sectionTitle")
        schedule_title_box.addWidget(self.schedule_title)
        self.schedule_meta = QLabel(tr("schedule_rule", self.language))
        self.schedule_meta.setObjectName("sectionMeta")
        schedule_title_box.addWidget(self.schedule_meta)
        schedule_header.addLayout(schedule_title_box)
        schedule_header.addStretch(1)
        self.start_button = QPushButton(tr("start_focus", self.language))
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self._toggle_start)
        schedule_header.addWidget(self.start_button)
        self.stop_button = QPushButton(tr("stop", self.language))
        self.stop_button.clicked.connect(self._stop_timer)
        schedule_header.addWidget(self.stop_button)
        main_layout.addLayout(schedule_header)
        main_layout.addWidget(self.schedule_list, 1)
        self.schedule_empty = QLabel(tr("schedule_empty", self.language))
        self.schedule_empty.setObjectName("emptyState")
        self.schedule_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.schedule_empty)
        divider = QFrame()
        divider.setObjectName("separator")
        main_layout.addWidget(divider)
        self.status_label = QLabel(self.status_message)
        self.status_label.setObjectName("hint")
        self.status_label.setWordWrap(True)
        main_layout.addWidget(self.status_label)

        splitter.addWidget(sidebar)
        splitter.addWidget(main_panel)
        splitter.setSizes([320, 760])
        root_layout.addWidget(splitter, 1)
        self.setCentralWidget(root)

    def _create_tray(self) -> None:
        self.tray = QSystemTrayIcon(self._tray_icon(), self)
        self.tray.setToolTip(tr("tray_tooltip", self.language))
        self.tray_menu = QMenu(self)
        self.open_action = self.tray_menu.addAction(tr("open_main_ui", self.language))
        self.open_action.triggered.connect(self._show_main_menu)
        self.tray_menu.addSeparator()
        self.exit_action = self.tray_menu.addAction(tr("exit", self.language))
        self.exit_action.triggered.connect(self._exit_from_tray)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    @staticmethod
    def _tray_icon() -> QIcon:
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.GlobalColor.darkCyan)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(3, 3, 26, 26, 8, 8)
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "F")
        painter.end()
        return QIcon(pixmap)

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self._show_main_menu()

    def _show_main_menu(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if self.planner.running:
            self._sync_controls()

    def _change_language(self, index: int) -> None:
        language = self.language_combo.itemData(index)
        if language not in SUPPORTED_LANGUAGES or language == self.language:
            return
        self.language = language
        self.planner.settings["language"] = language
        self.status_message = tr("status_initial", language)
        self._retranslate_ui()
        self._save()

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(tr("window_title", self.language))
        self.headline.setText(tr("headline", self.language))
        self.done_chip.setText(tr("timer_paused_chip" if self.planner.paused else "timer_active", self.language) if self.planner.running else tr("timer_ready", self.language))
        self.language_combo.setAccessibleName(tr("language", self.language))
        self.settings_button.setText(tr("settings", self.language))
        self.add_button.setText(tr("new_task", self.language))
        self.pool_title.setText(tr("task_pool", self.language))
        self.pool_caption.setText(tr("pool_caption", self.language))
        self.pool_hint.setText(tr("pool_hint", self.language))
        self.pool_empty.setText(tr("pool_empty", self.language))
        self.remove_button.setText(tr("delete_selected", self.language))
        self.schedule_title.setText(tr("today_schedule", self.language))
        self.schedule_meta.setText(tr("schedule_count", self.language, count=len(self.planner.schedule_ids)))
        self.stop_button.setText(tr("stop", self.language))
        self.schedule_empty.setText(tr("schedule_empty", self.language))
        self.status_label.setText(self.status_message)
        self.tray.setToolTip(tr("tray_tooltip", self.language))
        self.open_action.setText(tr("open_main_ui", self.language))
        self.exit_action.setText(tr("exit", self.language))
        self.refresh_lists()
        self._sync_controls()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.planner.settings, self.language, self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            self.planner.settings = dialog.result_settings()
            self.planner.settings["language"] = self.language
            self._save()
            self._sync_controls()
            self._set_status(tr("settings_saved", self.language))

    def _exit_from_tray(self) -> None:
        if self._exit_scheduled:
            return
        self._exit_scheduled = True
        self._force_exit = True
        self._save()
        self.tray.hide()
        self.floating.close()
        QApplication.quit()


    def _state_path(self) -> Path:
        base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        base.mkdir(parents=True, exist_ok=True)
        return base / "planner.json"

    def _load_planner(self) -> Planner:
        try:
            path = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)) / "planner.json"
            return Planner.from_dict(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else Planner()
        except (OSError, ValueError, TypeError):
            return Planner()

    def _save(self) -> None:
        try:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            self.store_path.write_text(json.dumps(self.planner.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            self._set_status(tr("save_failed", self.language))

    def _get_task(self, task_id: str) -> Task | None:
        return self.planner.tasks.get(task_id)

    def refresh_lists(self) -> None:
        self._fill_list(self.pool_list, self.planner.pool_ids)
        self._fill_list(self.schedule_list, self.planner.schedule_ids)
        self.pool_empty.setVisible(not self.planner.pool_ids)
        self.schedule_empty.setVisible(not self.planner.schedule_ids)
        self.pool_chip.setText(tr("pool_count", self.language, count=len(self.planner.pool_ids)))
        self.schedule_meta.setText(tr("schedule_count", self.language, count=len(self.planner.schedule_ids)))
        self.pool_list.viewport().update()
        self.schedule_list.viewport().update()

    @staticmethod
    def _fill_list(widget: TaskListWidget, ids: list[str]) -> None:
        widget.clear()
        for task_id in ids:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, task_id)
            item.setSizeHint(QSize(0, 78))
            widget.addItem(item)

    def _handle_drop(self, target: str, task_id: str, row: int) -> None:
        target_ids = self.planner.pool_ids if target == "pool" else self.planner.schedule_ids
        source_ids = self.planner.schedule_ids if target == "pool" else self.planner.pool_ids
        if task_id not in self.planner.tasks:
            return
        if task_id in target_ids:
            target_ids.remove(task_id)
        else:
            try:
                source_ids.remove(task_id)
            except ValueError:
                return
        row = max(0, min(row, len(target_ids)))
        target_ids.insert(row, task_id)
        if target == "pool" and task_id == self.planner.current_id:
            self.planner._select_next_after_removed()
        if target == "schedule" and self.planner.current_id is None and self.planner.running:
            self.planner._select_first()
        self.refresh_lists()
        self._save()
        self._set_status(tr("schedule_updated", self.language))

    def _add_task(self) -> None:
        dialog = TaskDialog(self, language=self.language)
        if dialog.exec() == TaskDialog.DialogCode.Accepted:
            self.planner.add_task(dialog.result_task())
            self.refresh_lists()
            self._save()
            self._set_status(tr("task_added", self.language))

    def _edit_task(self, task_id: str) -> None:
        task = self.planner.tasks.get(task_id)
        if task is None:
            return
        dialog = TaskDialog(self, task, self.language)
        if dialog.exec() == TaskDialog.DialogCode.Accepted:
            self.planner.update_task(dialog.result_task())
            self.refresh_lists()
            self._save()
            self._set_status(tr("task_updated", self.language, title=task.title))

    def _remove_selected(self) -> None:
        item = self.pool_list.currentItem() or self.schedule_list.currentItem()
        if item is None:
            return
        task_id = item.data(Qt.ItemDataRole.UserRole)
        task = self.planner.tasks.get(task_id)
        if task is None:
            return
        answer = QMessageBox.question(self, tr("delete_task", self.language), tr("delete_confirm", self.language, title=task.title))
        if answer == QMessageBox.StandardButton.Yes:
            self.planner.remove_task(task_id)
            self.refresh_lists()
            self._save()
            self._sync_controls()

    def _toggle_start(self) -> None:
        if self.planner.running:
            self._toggle_pause()
            return
        if not self.planner.start():
            self._set_status(tr("schedule_empty_status", self.language))
            return
        self.last_tick = time.monotonic()
        self._show_floating()
        self._set_status(tr("started_task", self.language, title=self.planner.current_task().title))
        self._sync_controls()
        self._save()

    def _toggle_pause(self) -> None:
        if not self.planner.running:
            return
        if self.planner.paused:
            self.planner.resume()
            self.last_tick = time.monotonic()
            self._set_status(tr("timer_resumed", self.language))
        else:
            self.planner.pause()
            self._set_status(tr("timer_paused", self.language))
        self._sync_controls()

    def _stop_timer(self) -> None:
        if self.planner.running:
            self.planner.stop()
            self.floating.hide()
            self._set_status(tr("timer_stopped", self.language))
            self._sync_controls()
            self.refresh_lists()
            self._save()

    def _skip_task(self) -> None:
        if not self.planner.running:
            return
        old = self.planner.current_task()
        next_id = self.planner.skip()
        self.refresh_lists()
        if next_id:
            next_task = self.planner.current_task()
            self._set_status(tr("task_skipped", self.language, old=old.title if old else tr("current_task", self.language), next=next_task.title))
            self._show_floating()
        else:
            self.floating.hide()
            self._set_status(tr("one_shots_complete", self.language))
        self._sync_controls()
        self._save()

    def _tick(self) -> None:
        if not self.planner.running:
            return
        now = time.monotonic()
        elapsed = min(2.0, max(0.0, now - self.last_tick))
        self.last_tick = now
        transitions = self.planner.tick(elapsed)
        if transitions:
            self.notification_player.setPosition(0)
            self.notification_player.play()
            finished = self.planner.tasks.get(transitions[-1])
            if self.planner.running and self.planner.current_task():
                self._set_status(tr("task_completed", self.language, finished=finished.title if finished else tr("generic_task", self.language), next=self.planner.current_task().title))
            else:
                self._set_status(tr("one_shots_complete", self.language))
            self.refresh_lists()
            self._save()
        self._sync_controls()

    def _show_floating(self) -> None:
        task = self.planner.current_task()
        if task is None:
            return
        self.floating.update_timer(
            task,
            self.planner.remaining_seconds,
            self.planner.paused,
            show_progress=self.planner.settings.get("show_progress", True),
            show_time=self.planner.settings.get("show_time", True),
            language=self.language,
        )
        if not self.floating.isVisible():
            screen = self.screen().availableGeometry()
            self.floating.move(screen.right() - self.floating.width() - 30, screen.top() + 34)
            self.floating.show()
        self.floating.raise_()

    def _sync_controls(self) -> None:
        if self.planner.running:
            self.start_button.setText(tr("resume_focus" if self.planner.paused else "pause_timer", self.language))
            self.done_chip.setText(tr("timer_paused_chip" if self.planner.paused else "timer_active", self.language))
            self._show_floating()
        else:
            self.start_button.setText(tr("start_focus", self.language))
            self.done_chip.setText(tr("timer_ready", self.language))
            self.floating.hide()
        self.schedule_list.viewport().update()

    def _set_status(self, text: str) -> None:
        self.status_message = text
        self.status_label.setText(text)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._toggle_start()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save()
        if not self._force_exit:
            self.hide()
            if self.planner.running:
                self._show_floating()
            self._set_status(tr("window_hidden", self.language))
            event.ignore()
            return
        self.tray.hide()
        self.floating.close()
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Focus Flow")
    app.setOrganizationName("Uzuki")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
