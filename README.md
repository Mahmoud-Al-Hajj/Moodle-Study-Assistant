# Moodle Study Assistant

A personal tool that collects the material from one Moodle course into a local, searchable study folder.

- It drives a real browser with Playwright, because the site's web services API is disabled.
- Everything runs locally and uses no paid services.
- The full plan is in [PLAN.md](PLAN.md). The rules for Claude are in [CLAUDE.md](CLAUDE.md).

**Status:** Stage 1 (login, session check) and Stage 2 (course crawl → `data/manifest.json`) are done. Downloading is Stage 3.

## Setup (once, in PowerShell)

```powershell
cd C:\Users\user\Desktop\moodle-study
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium
copy .env.example .env                      # then edit .env
```

In `.env`, keep `MOODLE_URL=https://haigmoodle.haigazian.edu.lb/moodle` and set `COURSE_ID`. That's the number after `?id=` when you open the course in your browser. Your password never goes in `.env`, or anywhere else.

If PowerShell blocks `Activate.ps1`, skip activation and type `.venv\Scripts\python` instead of `python` in every command below.

## Stage 1: log in and check the session

```powershell
python login.py
```

1. A Chromium window opens on the Moodle login page. Log in there.
2. Once your dashboard has loaded, press Enter in the terminal.
3. The session is saved to `auth\state.json`.

If you press Enter before you're logged in, the script says so and waits for Enter again.

```powershell
python check_session.py
```

This prints whether the saved session is still valid. Moodle sessions expire after a few hours. When that happens, every script stops with "Run: python login.py" and exit code 2.

## Stage 2: crawl a course (no downloading yet)

```powershell
python scrape.py                  # course from .env
python scrape.py --course 5678    # another course
python scrape.py --save-html      # also save the page to data\debug\course_page.html
python scrape.py --headed         # watch the browser
python scrape.py --verbose        # detailed logging
```

The script walks every section, writes `data\manifest.json`, and prints the total and per-type and per-section counts.

**Types** come from each item's URL: `resource` (a file), `folder`, `page`, `url`, `assign`, and `other` for everything else. For `other` items, the `module` field says what they really are: `forum`, `quiz`, or `inline_file` for a file linked straight from a label or section text.

**Restricted items** get `status: "unavailable"`, with the restriction text in `note`. Stage 3 skips them.

**Rerunning** never duplicates items. It also keeps any progress Stage 3 has recorded.

**Switching courses** first saves the old manifest as `data\manifest-course-<id>.json`. Crawling that course again picks up where it left off.

**If the page doesn't match the selectors**, the script never guesses. It saves the page to `data\debug\course_page.html` and tells you. Share that file, which contains your name and course content, so the selectors in `moodle_selectors.py` can be fixed.

The format of every field is in `.claude/skills/moodle-scraper/SKILL.md`.

## Testing against a fake Moodle

```powershell
python tests\run_tests.py
```

This runs 19 tests against a local imitation of Moodle (Boost and Classic themes, `/moodle` subpath, expired and guest sessions, restricted items, unknown markup). It never touches your real `.env`, `auth\` or `data\`.

One test opens a browser window for about 10 seconds. To skip it, run `$env:SKIP_HEADED=1` first.

Rerun the tests after any change to `moodle_selectors.py`.

## Exit codes

| Code | Meaning                                    |
| ---- | ------------------------------------------ |
| 0    | OK                                         |
| 1    | Error, with one clear line explaining it   |
| 2    | Session missing or expired: run `login.py` |
| 130  | Cancelled with Ctrl+C                      |

## Privacy

`.env`, `auth/`, `downloads/` and `data/` are excluded from git.

`auth\state.json` works like a logged-in browser, so don't share it.
