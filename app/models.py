from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Table, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    # Member session token (SHA-256 hex). NULL = no active member session;
    # the admin row never carries one (admin auth is the static workspace key).
    token_hash: Mapped[str | None] = mapped_column(String, nullable=True)


task_tags = Table(
    "task_tags",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)

# Many-to-many task assignments. Every workspace member (any users row) can be
# assigned; the admin token holder is the only one who writes tasks.
task_assignees = Table(
    "task_assignees",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id"), primary_key=True),
    Column("user_id", ForeignKey("users.id"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)

    tasks: Mapped[list["Task"]] = relationship(
        secondary=task_tags, back_populates="tags"
    )


# UNIQUE(user_id, lower(name)): tag names are unique per user,
# case-insensitively. Declared after the class so the expression binds to the
# real column (inside __table_args__, func.lower("name") renders a string
# literal, not the column).
Index(
    "uq_tags_user_lower_name",
    Tag.__table__.c.user_id,
    func.lower(Tag.__table__.c.name),
    unique=True,
)



class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None]
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="todo", server_default="todo"
    )
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default="medium", server_default="medium"
    )
    due_at: Mapped[datetime | None]
    # Nullable at the DB level so the startup backfill can attach pre-existing
    # rows; every route sets it on create (logically NOT NULL).
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    tags: Mapped[list[Tag]] = relationship(
        secondary=task_tags, back_populates="tasks", lazy="selectin"
    )
    assignees: Mapped[list["User"]] = relationship(
        secondary=task_assignees, lazy="selectin"
    )


