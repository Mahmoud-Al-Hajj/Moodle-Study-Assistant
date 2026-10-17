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

- Each item has: `section_number`, `section_name`, `title`, `type`, `url`, `local_path`, `status`, plus `id`, `module` and `note`.
- `status: "unavailable"` means the item is restricted and has no link. Stage 3 must skip it, and `note` holds the restriction text.
- The full format is in the skill.

## Progress

- Done: Step 0, Stage 1 (`login.py`, `check_session.py`), Stage 2 (`scrape.py`, manifest only).
- Next: Stage 3 (downloads). Only start it when the user says so.
