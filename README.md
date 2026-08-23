# Task API

FastAPI + Postgres task-tracker REST API with per-user JWT auth. `/api/auth/*`
issues tokens; all endpoints under `/api/tasks` require
`Authorization: Bearer <jwt>` and only ever see the calling user's tasks.
`/health` is public.

## Configuration

Both paths read the same env vars (defaults shown):

| Variable            | Default                                                         |
|---------------------|-----------------------------------------------------------------|
| `DATABASE_URL`      | `postgresql+psycopg://postgres:postgres@localhost:5432/taskapi` |
| `JWT_SECRET`        | _(empty = random per boot, warning logged; set in production)_   |
| `BOOTSTRAP_PASSWORD`| `change-me-now`                                                 |
| `AUTH_TOKEN`        | _(retired v1 static token — ignored, logged once if set)_        |

On startup the app creates missing tables/columns (`tasks.user_id`,
`tasks.due_at`), ensures the bootstrap account `boudy04` exists (password from
`BOOTSTRAP_PASSWORD`), and attaches any pre-existing orphan tasks to it.

## Path 1 — Native local Postgres (this machine)

Requires the local Postgres 16 service (`postgresql-x64-16`) running with
databases `taskapi` (dev) and `taskapi_test` (tests).

```bash
uv run uvicorn app.main:app --reload
```

Run the test suite (uses `taskapi_test`):

```bash
uv run pytest
```

## Path 2 — Docker Compose (everyone else)

Requires Docker + Docker Compose. Starts Postgres 16 and the API (schema is
created automatically on API startup).

```bash
docker compose up --build
```

API is at `http://localhost:8000`, Postgres at the internal host `postgres:5432`
(not published to the host).

## Using the API

### Register / login (public)

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"boudy04","password":"at-least-8-chars"}'
# 201 {"token":"<jwt>"}   (409 if username taken, 422 on validation)

curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"boudy04","password":"at-least-8-chars"}'
# 200 {"token":"<jwt>"}   (401 on bad credentials)
```

Usernames are >=3 chars, passwords >=8 chars. Tokens are JWT HS256 with 30-day
expiry; send them as `Authorization: Bearer $TOKEN` on every task call.

### Health (public, no auth)

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### Create a task

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Write README","description":"Document both dev paths","status":"todo","priority":"medium","due_at":"2026-09-01T12:00:00Z"}'
# 201 {"id":1,"title":"Write README",...,"due_at":"2026-09-01T12:00:00Z",...}
```

`status` is one of `todo` | `in_progress` | `done`; `priority` one of
`low` | `medium` | `high`; `due_at` is ISO-8601 UTC or null.

### List tasks (newest first, optional `status` filter)

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/tasks
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/tasks?status=done"
```

### Get one task

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/tasks/1
# 404 {"detail":"Task not found"} for unknown ids
```

### Update a task

Full replace (PUT) and partial update (PATCH) both accept any subset of
`title`, `description`, `status`, `priority`, `due_at`
(`due_at: null` clears it):

```bash
curl -X PUT http://localhost:8000/api/tasks/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Write README","status":"done"}'

curl -X PATCH http://localhost:8000/api/tasks/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"in_progress"}'
```

### Delete a task

```bash
curl -X DELETE http://localhost:8000/api/tasks/1 -H "Authorization: Bearer $TOKEN"
# 204 No Content
```

### Tags

Tasks carry per-user string tags (categories in the app map onto these). The
server normalizes them: trimmed, deduplicated case-insensitively, stored
lowercase; responses return them alphabetized. Deleting a task (or removing its
tags) removes tag rows that no longer have any references.

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Ship v2","tags":[" Work ","work","urgent"]}'
# 201 {..., "tags":["urgent","work"]}
```

Filter by one or more tags — multiple `?tag=` params are ANDed:

```bash
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/tasks?tag=work"
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/tasks?tag=work&tag=urgent"
```

Missing/wrong/expired token → `401`; invalid body → `422`; another user's task
is indistinguishable from a nonexistent one (`404`).