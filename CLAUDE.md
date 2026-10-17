# Moodle Study Assistant: rules for Claude

Full spec: PLAN.md. Scraper details (manifest format, folder layout): `.claude/skills/moodle-scraper/SKILL.md`.

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
- Next: Stage 5 (`search.py`, `cards.py`, `quiz.py`), built on `data/text/<course>/passages.jsonl`. Only start it when the user says so.

## Shared helpers

- `common.py` holds the local layout and atomic writes: `course_dir`, `section_dir`, `write_text`, `write_bytes`, `write_json_atomic`, `GENERATED_FILES`.
- Reuse these instead of rebuilding paths.
- `extract.py` must not import `downloader.py` or Playwright.
