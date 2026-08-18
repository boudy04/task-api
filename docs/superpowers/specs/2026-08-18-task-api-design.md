# Task API — Design Document

> Project #4 of the CV plan (headline repo). A FastAPI task-tracker CRUD API with
> Postgres, simple token auth, Docker, CI, and a Railway deployment.

## Purpose

Deliver a public, live CRUD API to close CV gaps G1 (shipped repo), G3 (deployed
artifact), G4 (backend/API with real DB), G5 (tests), G6 (CI/CD), and M4
(quantified). This is the API the Week 6–7 Kotlin app will consume.

## Stack

- **Framework:** FastAPI + Uvicorn (Python 3.12)
- **Data layer:** SQLAlchemy ORM + psycopg (binary), Postgres 16
- **Auth:** single static bearer token (`AUTH_TOKEN` env var), no user tables
- **Testing:** pytest + FastAPI `TestClient` against a real Postgres
- **Packaging:** `pyproject.toml` (pip-installable), Dockerfile, docker-compose
- **CI:** GitHub Actions, runs pytest with a Postgres service container
- **Deploy:** Railway (Dockerfile), Postgres plugin, `DATABASE_URL` + `AUTH_TOKEN`

## Data model

Single table `tasks`:

| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | auto |
| title | TEXT NOT NULL | required |
| description | TEXT | nullable |
| status | VARCHAR(16) NOT NULL | `todo` \| `in_progress` \| `done`, default `todo` |
| priority | VARCHAR(16) NOT NULL | `low` \| `medium` \| `high`, default `medium` |
| created_at | TIMESTAMPTZ NOT NULL | server default now() |
| updated_at | TIMESTAMPTZ NOT NULL | server default now() |

No users, no FK relationships. Status/priority validated at the API boundary.

## Endpoints

Base path `/api`. All `/api` routes require `Authorization: Bearer <AUTH_TOKEN>`;
401 with JSON body on missing/invalid token. `/health` is public.

| Method | Path | Body → Response |
|---|---|---|
| GET | `/api/tasks` | query `?status=` (optional) → `200` list of tasks, newest first |
| POST | `/api/tasks` | `{title, description?, status?, priority?}` → `201` task |
| GET | `/api/tasks/{id}` | → `200` task, `404` JSON error |
| PUT | `/api/tasks/{id}` | full update (title, description, status, priority) → `200` task, `404` |
| PATCH | `/api/tasks/{id}` | partial update (any subset) → `200` task, `404` |
| DELETE | `/api/tasks/{id}` | → `204`, `404` |
| GET | `/health` | public → `200 {"status":"ok"}` |

Validation errors return FastAPI's default `422`. Missing id returns `404` with
JSON `{"detail": "Task not found"}`.

PATCH supports the common "mark done" flow: `{"status": "done"}`.

## Project layout

```
p3/
  app/
    __init__.py
    main.py          # FastAPI app, router wiring, /health
    config.py        # pydantic-settings: DATABASE_URL, AUTH_TOKEN
    db.py            # engine, SessionLocal, Base, get_db dependency
    models.py        # SQLAlchemy Task model
    schemas.py       # pydantic: TaskCreate, TaskUpdate, TaskRead
    auth.py          # get_current_token dependency
    routers/
      __init__.py
      tasks.py       # /api/tasks CRUD router
  tests/
    conftest.py      # engine/client/auth fixtures
    test_auth.py
    test_tasks.py
  Dockerfile
  docker-compose.yml
  pyproject.toml
  .github/workflows/ci.yml
  README.md
```

## Error handling

- Invalid body → FastAPI 422 (automatic).
- Missing/invalid auth → 401 `{"detail": "Invalid or missing token"}`.
- Unknown task id → 404 `{"detail": "Task not found"}`.
- DB connection failure at startup → app fails fast (no lazy reconnect).

## Testing strategy

- `tests/test_auth.py`: 401 for missing token, 401 for wrong token, 200 for
  valid token on a protected route; `/health` open.
- `tests/test_tasks.py`: CRUD happy paths, 404s, 422s, status filter, PATCH
  partial update, ordering (newest first).
- Tests run against real Postgres. Local: native Postgres 16 installed as a
  Windows service (localhost:5432; the dev machine's custom build blocks
  WSL2/Docker, so the container path is CI-only). CI: GitHub Actions Postgres
  service container. Schema created per test session, data truncated between
  tests.
- `docker-compose.yml` (api + postgres) and the Dockerfile ship for anyone
  with Docker; both are verified via the CI build and the Railway deploy.

## Definition of done

- [ ] Postgres 16 installed as a local Windows service; local pytest connects
- [ ] Public GitHub repo `task-api`, pinned
- [ ] README: what, stack, run locally (compose), curl examples, test commands
- [ ] ≥5 unit tests passing
- [ ] `.github/workflows/ci.yml` runs pytest on push
- [ ] Dockerfile + docker-compose work locally
- [ ] Deployed live on Railway with Postgres, `/health` reachable