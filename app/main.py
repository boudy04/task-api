from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from sqlalchemy import func, select, text, update

from app.auth import BOOTSTRAP_USERNAME
from app.db import SessionLocal, engine
from app.models import Base, Task, User
from app.auth import router as identity_router
from app.routers import members, tasks


# Demo workspace trio (decision R25): seeded once the DB holds only the
# bootstrap owner, so fresh installs get a team to manage in the app.
DEMO_MEMBERS = ("alice", "bob", "carol")


def init_db() -> None:
    """Idempotent startup schema setup: create_all for fresh DBs, then ALTER
    TABLE backfills for pre-existing v1 databases (create_all does not add
    columns to existing tables), then bootstrap user + orphan-task attach."""
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS due_at TIMESTAMPTZ"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS token_hash VARCHAR"))
        # create_all only builds indexes for brand-new tables; enforce the
        # per-user case-insensitive uniqueness on existing ones too.
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_tags_user_lower_name "
            "ON tags (user_id, lower(name))"
        ))
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == BOOTSTRAP_USERNAME))
        if user is None:
            user = User(
                username=BOOTSTRAP_USERNAME,
                # Placeholder hash - accounts deferred, see tag api-v2-auth-deferred.
                password_hash="",
            )
            db.add(user)
            db.flush()
        # Orphan tasks (v1 rows) attach to the bootstrap user.
        db.execute(update(Task).where(Task.user_id.is_(None)).values(user_id=user.id))
        # Demo members: only when the workspace is still owner-only.
        user_count = db.scalar(select(func.count()).select_from(User))
        if user_count == 1:
            db.add_all(
                User(username=name, password_hash="") for name in DEMO_MEMBERS
            )
        db.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Task API", version="0.2.0", lifespan=lifespan)
app.include_router(tasks.router)
app.include_router(members.router)


@app.get("/health")
def health() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="db unavailable")
    return {"status": "ok"}



app.include_router(identity_router)
