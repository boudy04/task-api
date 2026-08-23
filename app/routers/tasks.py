from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth import User, get_current_user
from app.db import get_db
from app.models import Tag, Task
from app.schemas import TaskCreate, TaskRead, TaskStatus, TaskUpdate

router = APIRouter(
    prefix="/api/tasks",
    tags=["tasks"],
    dependencies=[Depends(get_current_user)],
)

_NON_NULLABLE = ("title", "status", "priority")
_INT4_MAX = 2_147_483_647


def _get_or_404(db: Session, user: User, task_id: int) -> Task:
    task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user.id))
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    return task


def _apply_update(task: Task, data: dict) -> None:
    for field, value in data.items():
        if value is None and field in _NON_NULLABLE:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{field} cannot be null",
            )
        setattr(task, field, value)


def _normalize_tags(raw: list[str]) -> list[str]:
    """Trim, drop empties, dedupe case-insensitively, lowercase canonical."""
    out: list[str] = []
    for name in raw:
        name = name.strip().lower()
        if name and name not in out:
            out.append(name)
    return out


def _set_task_tags(db: Session, user: User, task: Task, names: list[str]) -> None:
    task.tags.clear()
    for name in names:
        tag = db.scalar(
            select(Tag).where(Tag.user_id == user.id, func.lower(Tag.name) == name)
        )
        if tag is None:
            tag = Tag(user_id=user.id, name=name)
            db.add(tag)
        if tag not in task.tags:
            task.tags.append(tag)


def _cleanup_orphan_tags(db: Session, user: User) -> None:
    # Deleting the last reference to a tag removes its row.
    db.execute(delete(Tag).where(Tag.user_id == user.id, ~Tag.tasks.any()))


@router.get("", response_model=list[TaskRead])
def list_tasks(
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    tag_filter: list[str] | None = Query(default=None, alias="tag"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Task).where(Task.user_id == user.id)
    stmt = stmt.order_by(Task.created_at.desc(), Task.id.desc())
    if task_status is not None:
        stmt = stmt.where(Task.status == task_status.value)
    # Choice: multiple ?tag= params are ANDed (task must carry every listed tag).
    for name in tag_filter or []:
        stmt = stmt.where(Task.tags.any(func.lower(Tag.name) == name.strip().lower()))
    return db.scalars(stmt).all()


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = Task(user_id=user.id, **payload.model_dump(exclude={"tags"}))
    db.add(task)
    _set_task_tags(db, user, task, _normalize_tags(payload.tags))
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: int = Path(ge=1, le=_INT4_MAX),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_or_404(db, user, task_id)


@router.patch("/{task_id}", response_model=TaskRead)
@router.put("/{task_id}", response_model=TaskRead)
def update_task(
    payload: TaskUpdate,
    task_id: int = Path(ge=1, le=_INT4_MAX),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_or_404(db, user, task_id)
    data = payload.model_dump(exclude_unset=True)
    tags = data.pop("tags", None)
    _apply_update(task, data)
    if tags is not None:
        _set_task_tags(db, user, task, _normalize_tags(tags))
    db.commit()
    db.refresh(task)
    _cleanup_orphan_tags(db, user)
    db.commit()
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int = Path(ge=1, le=_INT4_MAX),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_or_404(db, user, task_id)
    db.delete(task)
    db.commit()
    _cleanup_orphan_tags(db, user)
    db.commit()
