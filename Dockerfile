FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY app/ ./app/

RUN pip install --no-cache-dir .[prod]

ENV PORT=8000
EXPOSE 8000

# create_all is idempotent (checkfirst); the app has no migration tool.
CMD python -c "from app.models import Base; from app.db import engine; Base.metadata.create_all(engine)" && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}