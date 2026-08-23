from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class TaskStatus(StrEnum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class TaskPriority(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


def _strip_title(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip()


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: TaskStatus = TaskStatus.todo
    priority: TaskPriority = TaskPriority.medium
    due_at: datetime | None = None
    tags: list[str] = []

    _strip_title = field_validator("title", mode="before")(_strip_title)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_at: datetime | None = None
    tags: list[str] | None = None

    _strip_title = field_validator("title", mode="before")(_strip_title)


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_at: datetime | None = None
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime

    @field_validator("tags", mode="before")
    @classmethod
    def _tag_names(cls, v):
        # Accept ORM Tag objects (from_attributes) or plain strings; always
        # return names alphabetized.
        return sorted(getattr(t, "name", t) for t in (v or []))

    @field_serializer("due_at")
    def _due_at_utc(self, v: datetime | None) -> str | None:
        # Contract: due_at is always ISO-8601 UTC (or null), regardless of the
        # DB session timezone Postgres hands back.
        if v is None:
            return None
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
