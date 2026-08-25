import re
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


# Demo workspace members: username-only rows, no passwords (decision R25).
_USERNAME_RE = re.compile(r"[a-z0-9_.-]{3,24}")


class MemberCreate(BaseModel):
    username: str

    @field_validator("username", mode="before")
    @classmethod
    def _normalize(cls, v):
        return v.strip().lower() if isinstance(v, str) else v

    @field_validator("username")
    @classmethod
    def _charset(cls, v: str) -> str:
        if not _USERNAME_RE.fullmatch(v):
            raise ValueError(
                "username must be 3-24 chars of a-z, 0-9, dot, dash or underscore"
            )
        return v


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


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
    assignee_ids: list[int] = []

    _strip_title = field_validator("title", mode="before")(_strip_title)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_at: datetime | None = None
    tags: list[str] | None = None
    # Full replacement semantics (like tags); null/absent leaves untouched.
    assignee_ids: list[int] | None = None

    _strip_title = field_validator("title", mode="before")(_strip_title)




class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=500)


class NoteRead(BaseModel):
    author: str
    body: str
    created_at: str

class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_at: datetime | None = None
    tags: list[str] = []
    assignees: list[MemberRead] = []
    notes: list[NoteRead] = []
    created_at: datetime
    updated_at: datetime

    @field_validator("tags", mode="before")
    @classmethod
    def _tag_names(cls, v):
        # Accept ORM Tag objects (from_attributes) or plain strings; always
        # return names alphabetized.
        return sorted(getattr(t, "name", t) for t in (v or []))

    @field_validator("notes", mode="before")
    @classmethod
    def _none_notes_to_empty(cls, v):
        return v or []

    @field_validator("assignees", mode="before")
    @classmethod
    def _sorted_assignees(cls, v):
        # ORM User rows (or dicts); always alphabetized by username.
        return sorted(v or [], key=lambda u: getattr(u, "username", ""))

    @field_serializer("due_at")
    def _due_at_utc(self, v: datetime | None) -> str | None:
        # Contract: due_at is always ISO-8601 UTC (or null), regardless of the
        # DB session timezone Postgres hands back.
        if v is None:
            return None
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


