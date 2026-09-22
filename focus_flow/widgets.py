"""UI widgets for Focus Flow."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QMimeData, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from .i18n import tr
from .model import COLOR_SWATCHES, Task

TASK_MIME = "application/x-focus-flow-task"


def contrast_color(hex_color: str) -> QColor:
    color = QColor(hex_color)
    luminance = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
    return QColor("#14202b" if luminance > 170 else "#ffffff")


def format_task_duration(task: Task, language: str = "en") -> str:
    hours, remainder = divmod(task.duration_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return tr("duration_hms" if seconds else "duration_hm", language, hours=hours, minutes=minutes, seconds=seconds)
    if minutes:
        return tr("duration_ms" if seconds else "duration_m", language, minutes=minutes, seconds=seconds)
    return tr("duration_s", language, seconds=seconds)


class TaskDelegate(QStyledItemDelegate):
    def __init__(self, parent: QListWidget, get_task, get_current, get_language=lambda: "en") -> None:
        super().__init__(parent)
        self.get_task = get_task
        self.get_current = get_current
        self.get_language = get_language

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), 78)

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        task = self.get_task(index.data(Qt.ItemDataRole.UserRole))
        if task is None:
            painter.restore()
            return
        rect = option.rect.adjusted(5, 5, -5, -5)
        is_current = task.id == self.get_current()
        fill = QColor("#263646" if is_current else "#1c2935")
        if option.state & QStyle.StateFlag.State_Selected:
            fill = QColor("#2b3e4f")
        painter.setBrush(fill)
        painter.setPen(QPen(QColor(task.color if is_current else "#2e4251"), 1.2))
        painter.drawRoundedRect(rect, 9, 9)
        painter.setBrush(QColor(task.color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRect(rect.left(), rect.top(), 6, rect.height()), 3, 3)

        text_color = QColor("#f4f7fa")
        muted = QColor("#94a7b5")
        painter.setPen(text_color)
        title_font = QFont("Segoe UI", 10)
        title_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(title_font)
        painter.drawText(QRect(rect.left() + 19, rect.top() + 13, rect.width() - 90, 22), Qt.AlignmentFlag.AlignLeft, task.title)
        painter.setPen(muted)
        painter.setFont(QFont("Segoe UI", 9))
        mode = tr("mode_once" if task.is_one_shot else "mode_loop", self.get_language())
        painter.drawText(QRect(rect.left() + 19, rect.bottom() - 25, 100, 18), Qt.AlignmentFlag.AlignLeft, mode)
        painter.setPen(QColor(task.color))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(QRect(rect.right() - 105, rect.top() + 13, 92, 22), Qt.AlignmentFlag.AlignRight, format_task_duration(task, self.get_language()))
        painter.restore()


class TaskListWidget(QListWidget):
    task_dropped = Signal(str, int)
    task_activated = Signal(str)

    def __init__(self, role: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.role = role
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSpacing(0)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setStyleSheet(
            "QListWidget { background: transparent; border: none; outline: none; }"
            "QListWidget::item { border: none; padding: 0; }"
            "QListWidget::item:selected { background: transparent; }"
        )

    def startDrag(self, supported_actions) -> None:
        item = self.currentItem()
        if item is None:
            return
        mime = QMimeData()
        mime.setData(TASK_MIME, item.data(Qt.ItemDataRole.UserRole).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(TASK_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(TASK_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasFormat(TASK_MIME):
            event.ignore()
            return
        task_id = bytes(event.mimeData().data(TASK_MIME)).decode("utf-8")
        row = self.indexAt(event.position().toPoint()).row()
        if row < 0:
            row = self.count()
        self.task_dropped.emit(task_id, row)
        event.acceptProposedAction()

    def mouseDoubleClickEvent(self, event) -> None:
        item = self.itemAt(event.position().toPoint())
        if item:
            self.task_activated.emit(item.data(Qt.ItemDataRole.UserRole))
        super().mouseDoubleClickEvent(event)


class TaskDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, task: Task | None = None, language: str = "en") -> None:
        super().__init__(parent)
        self.language = language
        self.setWindowTitle(tr("edit_task" if task else "add_task", language))
        self.setModal(True)
        self.setMinimumWidth(420)
        self.task = task
        self.selected_color = task.color if task else COLOR_SWATCHES[0]

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(18)
        heading = QLabel(tr("edit_task" if task else "add_task_heading", language))
        heading.setObjectName("dialogHeading")
        root.addWidget(heading)

        form = QFormLayout()
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(14)
        self.title_edit = QLineEdit(task.title if task else "")
        self.title_edit.setPlaceholderText(tr("task_placeholder", language))
        self.title_edit.setClearButtonEnabled(True)
        form.addRow(tr("task_name", language), self.title_edit)
        self.hours = QSpinBox()
        self.hours.setRange(0, 999)
        self.hours.setValue(task.hours_part if task else 0)
        self.hours.setSuffix(tr("hour_suffix", language))
        form.addRow(tr("hours", language), self.hours)
        self.minutes = QSpinBox()
        self.minutes.setRange(0, 59)
        self.minutes.setValue(task.minutes_part if task else 25)
        self.minutes.setSuffix(tr("minute_suffix", language))
        form.addRow(tr("minutes", language), self.minutes)
        self.seconds = QSpinBox()
        self.seconds.setRange(0, 59)
        self.seconds.setValue(task.seconds_part if task else 0)
        self.seconds.setSuffix(tr("second_suffix", language))
        form.addRow(tr("seconds", language), self.seconds)
        root.addLayout(form)

        root.addWidget(self._section_label(tr("color", language)))
        swatches = QHBoxLayout()
        swatches.setSpacing(10)
        self.color_group = QButtonGroup(self)
        for color in COLOR_SWATCHES:
            button = QPushButton()
            button.setCheckable(True)
            button.setFixedSize(30, 30)
            button.setProperty("swatch", color)
            button.setStyleSheet(
                f"QPushButton {{ background: {color}; border: 2px solid transparent; border-radius: 15px; }}"
                f"QPushButton:checked {{ border: 3px solid #f5f8fb; }}"
            )
            if color == self.selected_color:
                button.setChecked(True)
            button.clicked.connect(lambda checked, value=color: self._choose_color(value))
            self.color_group.addButton(button)
            swatches.addWidget(button)
        swatches.addStretch(1)
        root.addLayout(swatches)

        root.addWidget(self._section_label(tr("execution_mode", language)))
        modes = QHBoxLayout()
        self.loop_radio = QRadioButton(tr("loop_mode", language))
        self.once_radio = QRadioButton(tr("once_mode", language))
        (self.once_radio if task and task.is_one_shot else self.loop_radio).setChecked(True)
        modes.addWidget(self.loop_radio)
        modes.addWidget(self.once_radio)
        modes.addStretch(1)
        root.addLayout(modes)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.title_edit.setFocus()

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("dialogSection")
        return label

    def _choose_color(self, color: str) -> None:
        self.selected_color = color

    def _accept(self) -> None:
        if not self.title_edit.text().strip():
            self.title_edit.setFocus()
            return
        if self.hours.value() == 0 and self.minutes.value() == 0 and self.seconds.value() == 0:
            self.seconds.setFocus()
            return
        self.accept()

    def result_task(self) -> Task:
        old_id = self.task.id if self.task else None
        task = Task.create(
            title=self.title_edit.text(),
            minutes=self.minutes.value(),
            color=self.selected_color,
            mode="once" if self.once_radio.isChecked() else "loop",
            hours=self.hours.value(),
            seconds=self.seconds.value(),
        )
        if old_id:
            task.id = old_id
        return task


class SettingsDialog(QDialog):
    def __init__(self, settings: dict[str, Any], language: str = "en", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.language = language
        self.setWindowTitle(tr("display_settings", language))
        self.setModal(True)
        self.setMinimumWidth(430)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(16)
        heading = QLabel(tr("floating_display", language))
        heading.setObjectName("dialogHeading")
        root.addWidget(heading)
        hint = QLabel(tr("settings_hint", language))
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        root.addWidget(hint)
        self.progress_check = QCheckBox(tr("show_progress", language))
        self.progress_check.setChecked(settings.get("show_progress", True))
        root.addWidget(self.progress_check)
        self.time_check = QCheckBox(tr("show_time", language))
        self.time_check.setChecked(settings.get("show_time", True))
        root.addWidget(self.time_check)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def result_settings(self) -> dict[str, bool]:
        return {
            "show_progress": self.progress_check.isChecked(),
            "show_time": self.time_check.isChecked(),
        }


class FloatingTimer(QWidget):
    open_requested = Signal()
    pause_clicked = Signal()
    skip_clicked = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(360, 72)
        self.resize(420, 78)
        self._color = "#00a6fb"
        self._language = "en"
        self._title = tr("ready_to_start", self._language)
        self._remaining = 0
        self._total = 1
        self._paused = False
        self._show_progress = True
        self._show_time = True
        self._language = "en"
        self._drag_offset: QPoint | None = None
        self._drag_moved = False

    def update_timer(
        self,
        task: Task | None,
        remaining: float,
        paused: bool,
        show_progress: bool = True,
        show_time: bool = True,
        language: str = "en",
    ) -> None:
        if task is None:
            return
        self._title = task.title
        self._color = task.color
        self._remaining = max(0, int(remaining))
        self._total = max(1, task.duration_seconds)
        self._paused = paused
        self._show_progress = show_progress
        self._show_time = show_time
        self._language = language
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        color = QColor(self._color)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 14, 14)
        progress = min(1, max(0, self._remaining / self._total))
        if self._show_progress and progress < 1:
            overlay = QColor(0, 0, 0, 38)
            painter.setBrush(overlay)
            painter.drawRoundedRect(QRect(rect.left(), rect.top(), int(rect.width() * (1 - progress)), rect.height()), 14, 14)
        text = contrast_color(self._color)
        muted = QColor(text)
        muted.setAlpha(190)
        painter.setPen(text)
        title_font = QFont("Segoe UI", 11)
        title_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(title_font)
        painter.drawText(QRect(20, 12, self.width() - 150, 22), Qt.AlignmentFlag.AlignLeft, self._title)
        painter.setPen(muted)
        painter.setFont(QFont("Segoe UI", 9))
        state = tr("paused" if self._paused else "focusing", self._language)
        painter.drawText(QRect(20, 38, 100, 18), Qt.AlignmentFlag.AlignLeft, state)
        painter.setPen(text)
        painter.setFont(QFont("Segoe UI", 15))
        if self._should_show_time():
            time_text = self._format_time(self._remaining, self._language)
            painter.drawText(QRect(self.width() - 137, 20, 72, 28), Qt.AlignmentFlag.AlignRight, time_text)
        self._draw_button(painter, self.width() - 58, 17, "▶" if self._paused else "Ⅱ", self.pause_clicked)
        self._draw_button(painter, self.width() - 31, 17, "›", self.skip_clicked)

    def _draw_button(self, painter: QPainter, x: int, y: int, text: str, signal) -> None:
        del signal
        painter.setPen(contrast_color(self._color))
        painter.setFont(QFont("Segoe UI", 11))
        painter.drawText(QRect(x, y, 24, 28), Qt.AlignmentFlag.AlignCenter, text)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            x = event.position().x()
            if x >= self.width() - 62 and x < self.width() - 34:
                self.pause_clicked.emit()
                return
            if x >= self.width() - 34:
                self.skip_clicked.emit()
                return
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._drag_moved = False
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            position = event.globalPosition().toPoint()
            if (position - (self.frameGeometry().topLeft() + self._drag_offset)).manhattanLength() > 4:
                self._drag_moved = True
            self.move(position - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None and not self._drag_moved:
            self.open_requested.emit()
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def _should_show_time(self) -> bool:
        return self._show_time or (self._total > 30 and 0 < self._remaining <= 30)

    @staticmethod
    def _format_time(seconds: int, language: str = "en") -> str:
        minutes, seconds = divmod(seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"
