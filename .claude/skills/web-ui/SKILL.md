---
name: web-ui
description: Endpoints, job model, security middleware, UI state files, folder layout and test commands for the Moodle study tool's local web UI (FastAPI api/, React + MUI web/, dev.py). Use when working on api/, web/, dev.py, tests/test_api.py, or adding a web UI stage (A-F).
---

# Web UI

A local web app on top of the CLI. `api/` (FastAPI) wraps the CLI scripts; `web/` (Vite + React 19 + TS strict + MUI v7 + React Router + TanStack Query) is the app. Built in stages A-F with a user review after each:

| Stage | Scope | Status |
|---|---|---|
| A | API, app shell, Dashboard (session, login, Scrape) | done |
| B | Course content: sections, status chips, filters, retry failed, open file/folder | next |
| C | Download and Extract actions with live progress | |
| D | Search + Reader (reuse the `viewer-prototype` branch's image pipeline) | |
| E | Flashcards + Quiz | |
| F | Settings, polish, accessibility pass, production mode (FastAPI serves `web/dist`), code-splitting | |

## Rules

- **Wrap, don't change.** Every Moodle action is a CLI script run as a child process. The CLI files keep their logic; the UI reads their log lines and exit codes.
- **No Playwright in `api/`.** `auth/state.json` is only checked with `exists()`; never open, return or log it.
- **Password:** the UI never asks for it. Login happens in the visible Chromium window that `login.py` opens.
- **Network:** uvicorn and Vite bind to `127.0.0.1` only (hardcoded in `dev.py` and `web/vite.config.ts`).
- **One job at a time.** `JobManager.start` raises `Busy` → HTTP 409. This keeps Moodle requests serial; the scripts throttle themselves.
- **Errors:** every error response is `{"error": "<friendly sentence>"}`. Unexpected exceptions log server-side and return a generic 500. No tracebacks reach the browser.
- **Theme tokens only:** colours, sizes, spacing and layout widths come from `web/src/theme/theme.ts` (`theme.layout` holds layout sizes). No raw values in components.
- **Every async view** has loading, empty (with a next step) and error (with Retry) states (`components/states.tsx`).
- **Schema sync:** after changing `api/models.py` or a route, run `python -m api.export_openapi`, then `cd web; npm run gen:api`. `test_openapi_schema_is_up_to_date` fails otherwise. `web/src/api/openapi.json` is in `.prettierignore` because the test compares it byte for byte.

## Security middleware (`api/main.py`)

| Check | Reject |
|---|---|
| `Host` header must be `127.0.0.1` or `localhost` (any port) | 400: blocks DNS rebinding |
| Every non-GET/HEAD/OPTIONS request needs `X-Moodle-Study: 1` | 403: blocks cross-site requests (no CORS middleware, so other origins can't send it) |

`web/src/api/client.ts` adds the header. In tests, `TestClient` needs `base_url="http://127.0.0.1:8765"`; its default `testserver` host is rejected.

## Endpoints

| Method + path | Returns | Notes |
|---|---|---|
| `GET /api/health` | `{ok}` | |
| `GET /api/session` | `Session` | `status`: `valid`, `expired`, `missing` (no state file), `unknown` (never checked) |
| `POST /api/session/check` | 202 `Job` | runs `check_session.py` |
| `POST /api/session/login` | 202 `Job` | runs `login.py` (15 min timeout) |
| `GET /api/course` | `CourseSummary` | for `COURSE_ID` in `.env`; `scraped: false` when the manifest is missing or for another course |
| `GET /api/runs` | `Runs` | last run per action (`scrape`, `download`, `extract`) |
| `POST /api/jobs` `{action}` | 202 `Job` | 400 if `.env` isn't configured, 409 if busy, 422 for unknown actions |
| `GET /api/jobs/current` | `Job` or `null` | lets the app pick up a running job after reload |
| `GET /api/jobs/{id}?after=N` | `Job` | only lines with `seq > N`; `next` is the cursor for the next poll |
| `POST /api/jobs/{id}/cancel` | `Job` | kills the process tree |
| `POST /api/jobs/{id}/enter` | `Job` | login only: writes `\n` to stdin, the Enter `login.py` waits for |

The app polls the job every second while it runs (no SSE).

## Jobs (`api/jobs.py`)

- `ACTIONS` maps an action to `(script + args, UI label, timeout)`. To add one: extend `ACTIONS`, the `JobAction`/`StartJob` literals in `models.py`, and `on_finish` in `main.py` if it records a run. Then regenerate the schema.
- **Lines:** `parse_line` splits `HH:MM:SS LEVEL message` into `info`/`warning`/`error`; anything else is `output`. Text in front of a timestamp becomes its own `output` line (`login.py`'s prompt has no newline). The last 5000 lines are kept.
- **Progress:** `parse_progress` reads `[n/m] item` (downloader and extractor format) into `{done, total, item}`.
- **States** from the exit code:

| Exit code | State | `message` |
|---|---|---|
| 0 | `succeeded` | "Done." |
| 1 | `failed` | last ERROR line, or a generic sentence |
| 2 | `session_expired` | "Log in again." |
| 130, or cancelled/timed out | `cancelled` | "Everything finished so far is saved." |
| (still running) | `running` | |

- `on_finish(job, state)` runs **before** `job.state` changes, so a client that sees the finished state also sees the updated `runs.json` / `session.json`.
- **Cancel:** `kill_tree` uses `taskkill /PID n /T /F` on Windows (`os.killpg` elsewhere), so Playwright's driver and Chromium die too. The in-flight item is redone on the next run.
- Job history is in memory only; it's lost when the API restarts.

## UI state files (`data/ui/`, git-ignored)

| File | Written by | Content |
|---|---|---|
| `runs.json` | `on_finish` | `{action: RunInfo}`: state, started/finished, message, counts (`items` + counts by status) |
| `session.json` | `on_finish` for check_session, login and scrape | `{status: valid|expired, checked_at, message}`. Exit 0 → valid, exit 2 → expired. |

Written atomically (`.tmp` then `replace`) by `api/store.py`. `Store` reads `.env`, the manifest and these files relative to the root it's given, so tests use a temp root.

## Layout

```
api/
├── main.py            # create_app(root): middleware, error handlers, routes, on_finish
├── jobs.py            # ACTIONS, JobManager, parse_line/parse_progress, kill_tree
├── store.py           # .env, manifest summary, data/ui/*.json
├── models.py          # Pydantic models → openapi.json → web/src/api/schema.ts
└── export_openapi.py  # python -m api.export_openapi
web/src/
├── api/               # client.ts (fetch + header + ApiError), queries.ts (TanStack hooks),
│                      # ActiveJob.tsx (the one active job, shared by all cards), schema.ts + openapi.json (generated)
├── components/        # AppLayout (drawer / bottom nav), JobPanel, StatusChip, states, ConfirmDialog,
│                      # SnackbarProvider, PageHeader, Stat, format.ts
├── features/<screen>/ # one folder per screen; dashboard/ so far
├── theme/             # theme.ts (all tokens, light/dark, reduced motion), ColorModeToggle
└── test/              # render.tsx (providers for tests), setup.ts
dev.py / dev.bat       # starts both servers; .\dev
```

Reuse `JobPanel` (progress, current item, collapsible live log, Cancel) for every long job, and `StatusChip` for every status.

## Tests

```powershell
.venv\Scripts\python -m pytest tests\test_api.py   # $env:SKIP_HEADED=1 skips the headed login test
cd web
npx prettier --write src   # the user's editor also formats on save
npm test                   # Vitest + Testing Library, mocked fetch
npm run lint               # ESLint + prettier --check
npm run build              # tsc + vite build
python tests\run_tests.py  # CLI suite (~3.5 min); must stay green
```

- `tests/test_api.py` copies the CLI scripts listed in its `SCRIPTS` into a temp root, points `.env` at `tests/fake_moodle.py`, and writes a cookie state file. New CLI modules the API runs must be added to `SCRIPTS`.
- Add an API test for every new route, and a component test for every new screen (loading, empty, error, main path).
