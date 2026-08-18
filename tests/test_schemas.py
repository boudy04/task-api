from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect

from app.models import Task
from app.schemas import TaskCreate, TaskRead, TaskUpdate


class TestTaskCreate:
    def test_valid_with_defaults(self):
        task = TaskCreate(title="Write report")
        assert task.title == "Write report"
        assert task.description is None
        assert task.status == "todo"
        assert task.priority == "medium"

    def test_all_fields_accepted(self):
        task = TaskCreate(
            title="Ship feature",
            description="more context",
            status="in_progress",
            priority="high",
        )
        assert task.title == "Ship feature"
        assert task.description == "more context"
        assert task.status == "in_progress"
        assert task.priority == "high"

    def test_missing_title_rejected(self):
        with pytest.raises(ValidationError):
            TaskCreate()

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            TaskCreate(title="x", status="urgent")

    def test_invalid_priority_rejected(self):
        with pytest.raises(ValidationError):
            TaskCreate(title="x", priority="critical")


class TestTaskUpdate:
    def test_empty_subset_accepted(self):
        task = TaskUpdate()
        assert task.model_dump(exclude_unset=True) == {}

    def test_partial_subset(self):
        task = TaskUpdate(status="done")
        assert task.status == "done"
        assert task.title is None

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            TaskUpdate(status="urgent")


class TestTaskRead:
    def test_full_fields(self):
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        task = TaskRead(
            id=1,
            title="t",
            description="d",
            status="done",
            priority="high",
            created_at=when,
            updated_at=when,
        )
        assert task.id == 1
        assert task.title == "t"
        assert task.created_at == when

    def test_from_model_instance(self):
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        model = Task(
            id=1,
            title="t",
            description=None,
            status="todo",
            priority="medium",
            created_at=when,
            updated_at=when,
        )
        read = TaskRead.model_validate(model)
        assert read.id == 1
        assert read.description is None


class TestTaskModel:
    def test_tasks_table_created(self, db_engine):
        tables = inspect(db_engine).get_table_names()
        assert "tasks" in tables

    def test_round_trip_applies_defaults(self, db_session, clean_tables):
        db_session.add(Task(title="hello", description="desc"))
        db_session.commit()
        db_session.refresh(db_session.query(Task).one())
        task = db_session.query(Task).one()
        assert task.id is not None
        assert task.title == "hello"
        assert task.description == "desc"
        assert task.status == "todo"
        assert task.priority == "medium"
        assert task.created_at is not None
        assert task.updated_at is not None

    def test_clean_tables_truncates(self, db_session, clean_tables):
        db_session.add(Task(title="x"))
        db_session.commit()
        assert db_session.query(Task).count() == 1

    def test_table_empty_after_clean(self, db_session, clean_tables):
        assert db_session.query(Task).count() == 0
