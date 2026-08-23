# Task API v2 — Auth, User Scoping, Due Dates, Tags — Design Addendum

> Extends 2026-08-22-taskvault-offline-client-design.md (app) and the task-api service.
> Approved by user ("good") after identity-model decision R21: real accounts + JWT,
> string-tags normalized server-side. Also backfills the pending `due_at` contract from
> the 2026-08-23 addendum — REQUIRED because the deployed API drops unknown fields and
> current app payloads already carry due_at (silent data loss on every round-trip today).

## Auth & identity

- `users` table: `id PK`, `username TEXT UNIQUE NOT NULL`, `password_hash TEXT NOT NULL`
  (bcrypt via passlib[bcrypt]; never store plaintext).
- `POST /api/auth/register {username, password}` -> 201 `{token}`; 409 duplicate username;
  422 validation (username >=3 chars, password >=8).
- `POST /api/auth/login {username, password}` -> 200 `{token}`; 401 bad credentials.
- Token = JWT HS256 (`PyJWT`), claims `{sub: user_id, exp: +30d}`, secret from env
  `JWT_SECRET` (config default random-at-boot with warning log; Railway sets real value).
- FastAPI dependency `get_current_user` replaces static-token check on ALL `/api/tasks*`
  routes. Old `AUTH_TOKEN` env retired (kept ignored, logged once).
- Migration/bootstrap: `ALTER TABLE tasks ADD COLUMN IF NOT EXISTS user_id INTEGER`;
  ensure bootstrap user `boudy04` exists at startup; orphan tasks (user_id NULL)
  attach to bootstrap user; then `NOT NULL` is enforced logically (new rows always set).
- Also backfills `ALTER TABLE tasks ADD COLUMN IF NOT EXISTS due_at TIMESTAMPTZ`.

## User scoping

- `tasks.user_id FK -> users.id`. Every query filters by current user.
- Cross-user access is structurally impossible (no route accepts a user id).

## Due dates (contract catch-up)

- `Task.due_at: datetime | None`; JSON `due_at` ISO-8601 UTC or null; accepted by
  POST/PUT/PATCH subsets; returned everywhere; `?due_before=` optional filter omitted (YAGNI).

## Tags

- `tags` table: `id PK`, `user_id FK`, `name TEXT NOT NULL`, UNIQUE(user_id, lower(name)).
- `task_tags` join: `task_id FK`, `tag_id FK`, PK(task_id, tag_id).
- Task JSON carries `tags: [string]` (ordered alphabetically). Create/update accepts
  `tags` list; server normalizes (trim, dedupe case-insensitively, lowercase canonical);
  deleting last reference removes tag row. `GET /api/tasks?tag=work` filters.
- Categories-in-app map 1:1 onto these tags.

## App impact (T19)

- Login/register screen on first launch (or on 401); token stored in DataStore replacing
  manual token field (server URL stays); 401 during use -> logout -> login screen.
- TaskPayload gains `tags: List<String>`; DTO `@SerialName("tags") val tags: List<String> = emptyList()`.
- Edit screen chip input; Tasks screen filter chips + search (title/description/tag);
  Statistics optionally per-tag counts.

## Tests (API)

Rewrite fixtures: register/login helpers; ~10 new cases (register dup, login bad,
401 no/expired token, cross-user isolation, due_at round-trip, tag normalize/dedupe/
filter/cleanup). Existing 45 adapted to authenticated client fixture. Target >=55.

## Non-goals

Password reset/email, refresh tokens, OAuth, admin roles, tag colors.
