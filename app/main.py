from fastapi import FastAPI, HTTPException, status
from sqlalchemy import text

from app.db import engine
from app.routers import tasks


app = FastAPI(title="Task API", version="0.1.0")
app.include_router(tasks.router)


@app.get("/health")
def health() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="db unavailable")
    return {"status": "ok"}
