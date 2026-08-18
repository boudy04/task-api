from fastapi import FastAPI

from app.routers import tasks

app = FastAPI(title="Task API", version="0.1.0")
app.include_router(tasks.router)


@app.get("/health")
def health():
    return {"status": "ok"}
