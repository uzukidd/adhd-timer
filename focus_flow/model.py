"""Core task and timer state, kept independent from Qt widgets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4


COLOR_SWATCHES = (
    "#ff4d6d",
    "#ff7a3d",
    "#f5b700",
    "#16c79a",
    "#00a6fb",
    "#3867ff",
    "#9b5de5",
    "#e64980",
)


@dataclass
class Task:
    id: str
    title: str
    duration_seconds: int
    color: str
    mode: str = "loop"

    @classmethod
    def create(
        cls,
        title: str,
        minutes: int = 25,
        color: str = COLOR_SWATCHES[0],
        mode: str = "loop",
        *,
        hours: int = 0,
        seconds: int = 0,
        duration_seconds: int | None = None,
    ) -> "Task":
        total_seconds = duration_seconds if duration_seconds is not None else hours * 3600 + minutes * 60 + seconds
        return cls(
            id=uuid4().hex,
            title=title.strip() or "Untitled task",
            duration_seconds=max(1, int(total_seconds)),
            color=color,
            mode="once" if mode == "once" else "loop",
        )

    @property
    def minutes(self) -> int:
        """Backward-compatible whole-minute duration."""
        return self.duration_seconds // 60

    @property
    def hours_part(self) -> int:
        return self.duration_seconds // 3600

    @property
    def minutes_part(self) -> int:
        return (self.duration_seconds % 3600) // 60

    @property
    def seconds_part(self) -> int:
        return self.duration_seconds % 60

    @property
    def is_one_shot(self) -> bool:
        return self.mode == "once"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Task":
        if "duration_seconds" in raw:
            total_seconds = int(raw.get("duration_seconds", 1500))
        else:
            total_seconds = int(raw.get("minutes", 25)) * 60
        return cls(
            id=str(raw.get("id") or uuid4().hex),
            title=str(raw.get("title") or "Untitled task"),
            duration_seconds=max(1, total_seconds),
            color=str(raw.get("color") or COLOR_SWATCHES[0]),
            mode="once" if raw.get("mode") == "once" else "loop",
        )


class Planner:
    """Owns task placement and deterministic timer transitions."""

    def __init__(self) -> None:
        self.tasks: dict[str, Task] = {}
        self.pool_ids: list[str] = []
        self.schedule_ids: list[str] = []
        self.settings: dict[str, Any] = {
            "show_progress": True,
            "show_time": True,
            "language": "en",
        }
        self.current_id: str | None = None
        self.remaining_seconds: float = 0
        self.running = False
        self.paused = False

    def add_task(self, task: Task, to_schedule: bool = False) -> None:
        self.tasks[task.id] = task
        target = self.schedule_ids if to_schedule else self.pool_ids
        if task.id not in target:
            target.append(task.id)

    def remove_task(self, task_id: str) -> None:
        if task_id == self.current_id:
            self.stop()
        self.tasks.pop(task_id, None)
        self._remove_id(self.pool_ids, task_id)
        self._remove_id(self.schedule_ids, task_id)

    def move_to_schedule(self, task_id: str, index: int | None = None) -> None:
        if task_id not in self.tasks:
            return
        self._remove_id(self.pool_ids, task_id)
        self._remove_id(self.schedule_ids, task_id)
        if index is None:
            self.schedule_ids.append(task_id)
        else:
            self.schedule_ids.insert(max(0, min(index, len(self.schedule_ids))), task_id)
        if self.current_id is None and self.running:
            self._select_first()

    def move_to_pool(self, task_id: str) -> None:
        if task_id not in self.tasks:
            return
        was_current = task_id == self.current_id
        self._remove_id(self.schedule_ids, task_id)
        self._remove_id(self.pool_ids, task_id)
        self.pool_ids.append(task_id)
        if was_current:
            self._select_next_after_removed()

    def reorder_schedule(self, ordered_ids: list[str]) -> None:
        allowed = set(self.schedule_ids)
        self.schedule_ids = [task_id for task_id in ordered_ids if task_id in allowed]
        self.schedule_ids.extend(task_id for task_id in allowed if task_id not in self.schedule_ids)

    def reorder_pool(self, ordered_ids: list[str]) -> None:
        allowed = set(self.pool_ids)
        self.pool_ids = [task_id for task_id in ordered_ids if task_id in allowed]
        self.pool_ids.extend(task_id for task_id in allowed if task_id not in self.pool_ids)

    def start(self) -> bool:
        if not self.schedule_ids:
            return False
        if self.current_id not in self.schedule_ids:
            self._select_first()
        self.running = True
        self.paused = False
        return True

    def pause(self) -> None:
        if self.running:
            self.paused = True

    def resume(self) -> None:
        if self.running:
            self.paused = False

    def stop(self) -> None:
        self.running = False
        self.paused = False
        self.current_id = None
        self.remaining_seconds = 0

    def skip(self) -> str | None:
        if self.current_id is None or not self.schedule_ids:
            return None
        return self._advance()

    def tick(self, seconds: float) -> list[str]:
        if not self.running or self.paused or self.current_id is None:
            return []
        transitions: list[str] = []
        self.remaining_seconds -= max(0, seconds)
        while self.running and self.remaining_seconds <= 0 and self.current_id is not None:
            transitions.append(self.current_id)
            self._advance()
        return transitions

    def update_task(self, task: Task) -> None:
        if task.id not in self.tasks:
            return
        old = self.tasks[task.id]
        self.tasks[task.id] = task
        if task.id == self.current_id and old.duration_seconds != task.duration_seconds:
            self.remaining_seconds = min(self.remaining_seconds, task.duration_seconds)

    def current_task(self) -> Task | None:
        return self.tasks.get(self.current_id) if self.current_id else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tasks": [task.to_dict() for task in self.tasks.values()],
            "pool": self.pool_ids,
            "schedule": self.schedule_ids,
            "settings": self.settings,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Planner":
        planner = cls()
        for item in raw.get("tasks", []):
            if isinstance(item, dict):
                task = Task.from_dict(item)
                planner.tasks[task.id] = task
        known = set(planner.tasks)
        planner.pool_ids = [str(task_id) for task_id in raw.get("pool", []) if str(task_id) in known]
        planner.schedule_ids = [str(task_id) for task_id in raw.get("schedule", []) if str(task_id) in known]
        saved_settings = raw.get("settings", {})
        if isinstance(saved_settings, dict):
            planner.settings["show_progress"] = bool(saved_settings.get("show_progress", True))
            planner.settings["show_time"] = bool(saved_settings.get("show_time", True))
            language = saved_settings.get("language", "en")
            planner.settings["language"] = language if language in ("en", "zh") else "en"
        placed = set(planner.pool_ids) | set(planner.schedule_ids)
        planner.pool_ids.extend(task_id for task_id in planner.tasks if task_id not in placed)
        return planner

    def _advance(self) -> str | None:
        if self.current_id is None:
            self._select_first()
            return self.current_id
        current_id = self.current_id
        if current_id in self.schedule_ids:
            index = self.schedule_ids.index(current_id)
            if self.tasks[current_id].is_one_shot:
                self.schedule_ids.pop(index)
                self.pool_ids.append(current_id)
                if not self.schedule_ids:
                    self.stop()
                    return None
                index %= len(self.schedule_ids)
            else:
                index = (index + 1) % len(self.schedule_ids)
        self.current_id = self.schedule_ids[index] if self.schedule_ids else None
        if self.current_id is None:
            self.stop()
        else:
            self.remaining_seconds = self.tasks[self.current_id].duration_seconds
        return self.current_id

    def _select_first(self) -> None:
        if self.schedule_ids:
            self.current_id = self.schedule_ids[0]
            self.remaining_seconds = self.tasks[self.current_id].duration_seconds

    def _select_next_after_removed(self) -> None:
        if not self.schedule_ids:
            self.stop()
            return
        self.current_id = self.schedule_ids[0]
        self.remaining_seconds = self.tasks[self.current_id].duration_seconds

    @staticmethod
    def _remove_id(items: list[str], task_id: str) -> None:
        try:
            items.remove(task_id)
        except ValueError:
            pass
