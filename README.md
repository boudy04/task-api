# Task API

FastAPI + Postgres task-tracker REST API with a single static admin bearer
token. All endpoints under `/api/tasks` require
`Authorization: Bearer <AUTH_TOKEN>` and only ever see that token's owner's
tasks. `/health` is public.

> Accounts (register/login) are **deferred**: the full JWT auth design is
> preserved at git tag `api-v2-auth-deferred`. The `users` table and all
> per-user scoping stay; only the credential layer was reduced to one token.

## Configuration

Both paths read the same env vars (defaults shown):

| Variable            | Default                                                         |
|---------------------|-----------------------------------------------------------------|
| `DATABASE_URL`      | `postgresql+psycopg://postgres:postgres@localhost:5432/taskapi` |
| `AUTH_TOKEN`        | `dev-token`                                                     |

On startup the app creates missing tables/columns (`tasks.user_id`,
`tasks.due_at`), ensures the bootstrap account `boudy04` exists (placeholder
password hash - accounts deferred), and attaches any pre-existing orphan tasks
to it.

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

### Authentication

One static token, set via `AUTH_TOKEN` (default `dev-token`). Send it on every
task call:

```bash
export TASK_TOKEN="dev-token"   # match the server's AUTH_TOKEN
# Authorization: Bearer $TASK_TOKEN
```

### Health (public, no auth)

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### Create a task

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $TASK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Write README","description":"Document both dev paths","status":"todo","priority":"medium","due_at":"2026-09-01T12:00:00Z"}'
# 201 {"id":1,"title":"Write README",...,"due_at":"2026-09-01T12:00:00Z",...}
```

`status` is one of `todo` | `in_progress` | `done`; `priority` one of
`low` | `medium` | `high`; `due_at` is ISO-8601 UTC or null.

### List tasks (newest first, optional `status` filter)

```bash
curl -H "Authorization: Bearer $TASK_TOKEN" http://localhost:8000/api/tasks
curl -H "Authorization: Bearer $TASK_TOKEN" "http://localhost:8000/api/tasks?status=done"
```

### Get one task

```bash
curl -H "Authorization: Bearer $TASK_TOKEN" http://localhost:8000/api/tasks/1
# 404 {"detail":"Task not found"} for unknown ids
```

### Update a task

Full replace (PUT) and partial update (PATCH) both accept any subset of
`title`, `description`, `status`, `priority`, `due_at`
(`due_at: null` clears it):

```bash
curl -X PUT http://localhost:8000/api/tasks/1 \
  -H "Authorization: Bearer $TASK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Write README","status":"done"}'

curl -X PATCH http://localhost:8000/api/tasks/1 \
  -H "Authorization: Bearer $TASK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"in_progress"}'
```

### Delete a task

```bash
curl -X DELETE http://localhost:8000/api/tasks/1 -H "Authorization: Bearer $TASK_TOKEN"
# 204 No Content
```

### Tags

Tasks carry per-user string tags (categories in the app map onto these). The
server normalizes them: trimmed, deduplicated case-insensitively, stored
lowercase; responses return them alphabetized. Deleting a task (or removing its
tags) removes tag rows that no longer have any references.

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $TASK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Ship v2","tags":[" Work ","work","urgent"]}'
# 201 {..., "tags":["urgent","work"]}
```

Filter by one or more tags — multiple `?tag=` params are ANDed:

```bash
curl -H "Authorization: Bearer $TASK_TOKEN" "http://localhost:8000/api/tasks?tag=work"
curl -H "Authorization: Bearer $TASK_TOKEN" "http://localhost:8000/api/tasks?tag=work&tag=urgent"
```

Missing/wrong token → `401`; invalid body → `422`; another user's task
is indistinguishable from a nonexistent one (`404`).

## Demo workspace

The server boots as a small demo team so the TaskVault app's Settings → Team
card has something real to manage. The admin account is `boudy04`; fresh
workspaces are also seeded with members `alice`, `bob` and `carol` - plain
username rows with no passwords, exactly because there is no login yet.

- **Solo use:** ignore members entirely. Nothing requires them; delete them in
  the app or via the API and get on with your own tasks.
- **Team use:** share the `AUTH_TOKEN` with teammates (it *is* the workspace
  key) and give each other context by tagging tasks, e.g. `?tag=bob` for Bob's
  queue.

Members are managed under `/api/members`, same bearer token as tasks:

```bash
curl -H "Authorization: Bearer $TASK_TOKEN" http://localhost:8000/api/members
# [{"id":1,"username":"alice"},...]

curl -X POST http://localhost:8000/api/members \
  -H "Authorization: Bearer $TASK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"Dave_Dev"}'
# 201 {"id":5,"username":"dave_dev"}   (3-24 chars a-z 0-9 _ . -, lowercased)
# 409 if taken (case-insensitive), 422 if invalid

curl -X DELETE http://localhost:8000/api/members/5 -H "Authorization: Bearer $TASK_TOKEN"
# 204 (404 unknown id, 400 for boudy04 - the owner cannot be removed)
```

### Assignees

Tasks can be assigned to workspace members. Send `assignee_ids` on create or
update (full replacement semantics, like tags; `[]` clears):

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $TASK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Ship v2","assignee_ids":[2,3]}'
# 201 {..., "assignees":[{"id":2,"username":"bob"},{"id":3,"username":"carol"}]}
```

Responses list assignees alphabetized by username. Filter by assignee with
`?assignee=<member id>`. Any unknown member id is rejected with `422`.

### Permission model

While accounts are deferred, the workspace token holder **is** the
administrator: only the admin creates/updates/deletes tasks and assigns them to
members. Members receive and view all workspace tasks but have no credentials -
there are no member-scoped writes. Server-side scoping still routes every read
and write through the token's owning user row (`tasks.user_id`), so when real
accounts return, per-user enforcement slots back in without route changes.

Future note: external identity (Google login and friends) stays deferred along
with accounts - see git tag `api-v2-auth-deferred`. When it lands, these
member rows become the handles it attaches to.