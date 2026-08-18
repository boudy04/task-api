# Task API

FastAPI + Postgres task-tracker REST API with bearer-token auth. All endpoints
under `/api/tasks` require `Authorization: Bearer <AUTH_TOKEN>`; `/health` is
public.

## Configuration

Both paths read the same env vars (defaults shown):

| Variable      | Default                                                         |
|---------------|-----------------------------------------------------------------|
| `DATABASE_URL`| `postgresql+psycopg://postgres:postgres@localhost:5432/taskapi` |
| `AUTH_TOKEN`  | `dev-token`                                                      |

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

Set your token once (`dev-token` by default — override with `AUTH_TOKEN`):

```bash
TOKEN=dev-token
```

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
  -d '{"title":"Write README","description":"Document both dev paths","status":"todo","priority":"medium"}'
# 201 {"id":1,"title":"Write README",...,"status":"todo","priority":"medium","created_at":"...","updated_at":"..."}
```

`status` is one of `todo` | `in_progress` | `done`; `priority` one of
`low` | `medium` | `high`.

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
`title`, `description`, `status`, `priority`:

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

Missing or wrong token → `401 {"detail":"Invalid or missing token"}`; invalid body → `422`.