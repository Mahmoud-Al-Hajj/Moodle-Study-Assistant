# Moodle Study Assistant: rules for Claude

Full spec: PLAN.md (CLI). Web UI: `.claude/skills/web-ui/SKILL.md`. Scraper details (manifest format, folder layout): `.claude/skills/moodle-scraper/SKILL.md`.

- **Never ask for, read, store, or log the Moodle password.** Authentication is a manual login in a visible browser (`login.py`), saved with Playwright `storage_state` to `auth/state.json`.
- **Build every URL from `MOODLE_URL` in `.env`.** Never hardcode the domain (the site lives under a `/moodle` subpath).
- **Throttle requests to 1-2 seconds, no parallel requests.** Use `common.Throttle` / `common.goto`.
- **Reruns must be idempotent:** skip already-downloaded items, never duplicate. Items are matched by their manifest `id`.
- **Keep all CSS/DOM selectors and URL patterns in `moodle_selectors.py`.** (Not `selectors.py`: that name shadows Python's built-in `selectors` module, which Playwright depends on.) After changing selectors, run `python tests/run_tests.py`.
- **Invalid or expired session:** every script stops with a clear message to rerun `login.py` (exit code 2).
- **Selectors failing to match:** don't guess. Save the page HTML to `data/debug/` and tell the user.
- **Errors:** log clearly and exit without a stack trace (use `common.run`).
- **No paid services or AI API dependencies.**
- **Work one stage at a time.** After each stage, stop, show the user how to test it, and wait for their confirmation.

## Manifest (`data/manifest.json`)

- Each item has: `section_number`, `section_name`, `title`, `type`, `url`, `local_path`, `status`, plus `id`, `module`, `note`, `files` and `target_url`.
- `status: "unavailable"` means the item is restricted and has no link. Stage 3 skips it without ever requesting it, and `note` holds the restriction text.
- Stage 3 statuses: `downloaded`, `failed` (retried on the next run) and `skipped`.
- The full format is in the skill.

## Progress

- Done: Step 0, Stage 1 (`login.py`, `check_session.py`), Stage 2 (`scrape.py` crawl and manifest), Stage 3 (`downloader.py`, run by `scrape.py`), Stage 4 (`extract.py`, text extraction + `index.html`; details in `.claude/skills/text-extraction/SKILL.md`).
- `update.py` (run via `update.bat`) chains: session check, login if expired (only with a terminal), `scrape.main`, `extract.main`, then opens `index.html`. All in one process; each step opens and closes its own Playwright, and only `update.main` goes through `common.run`. Add new flags in `scrape.add_arguments` / `extract.add_arguments`.
- Web UI (stages A-F, review stop after each): Stage A done (API + app shell + Dashboard with session, login and Scrape). Next: Stage B (Course content). Only start a stage when the user says so.
- PLAN.md's CLI Stage 5 (`search.py`, `cards.py`, `quiz.py`) is superseded by web stages D-E. Ask the user before building a CLI version.

## Web UI (`api/` + `web/`)

Endpoints, job states, security middleware, `data/ui/` files, layout and test commands: `.claude/skills/web-ui/SKILL.md`. Load it before touching `api/`, `web/` or `dev.py`.

- **The API runs the CLI scripts as child processes** (`api/jobs.py`). Leave CLI logic as it is; the UI gets progress from log lines and outcomes from exit codes.
- `api/` imports no Playwright and never opens `auth/state.json` (only `exists()`). The password never passes through the UI.
- Bind to 127.0.0.1 only. One job at a time (409 otherwise).
- After any change to `api/models.py` or a route: `python -m api.export_openapi`, then `cd web; npm run gen:api`. A drift test enforces it.
- Colours, sizes and spacing come from `web/src/theme/theme.ts` tokens only.

## Shared helpers

- `common.py` holds the local layout and atomic writes: `course_dir`, `section_dir`, `write_text`, `write_bytes`, `write_json_atomic`, `GENERATED_FILES`.
- Reuse these instead of rebuilding paths.
- `extract.py` must not import `downloader.py` or Playwright.
