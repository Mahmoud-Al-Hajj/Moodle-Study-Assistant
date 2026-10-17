# Moodle Study Assistant

Personal tool that collects the material from one Moodle course into a local,
searchable study folder. Uses browser automation (Playwright) because the
site's web services API is disabled. See [PLAN.md](PLAN.md) for the full plan.

**Status:** Stage 1 (login) and Stage 2 (crawl + manifest) are built.

## Setup (once)

```powershell
cd C:\Users\user\Desktop\moodle-study
python -m venv .venv                        
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium
copy .env.example .env                      # then edit .env
```

In `.env`, set:

- `MOODLE_URL`: your Moodle site root, e.g. `https://moodle.myuni.edu`
- `COURSE_ID`: the number after `?id=` when you open the course page

Your password never goes in `.env`, or anywhere else.

## Stage 1: log in

```powershell
.venv\Scripts\python login.py
```

A Chromium window opens on the Moodle login page. Log in as you normally do
(SSO and 2FA work). The script detects when you're in, saves the session to
`auth\state.json` and closes the browser.

```powershell
.venv\Scripts\python login.py --check     # is the saved session still valid?
```

Moodle sessions expire after a few hours of inactivity (your university sets
the limit). When that happens, every script tells you to run `login.py` again
and exits with code 2.

## Stage 2: crawl a course

```powershell
.venv\Scripts\python scrape.py                  # course from .env
.venv\Scripts\python scrape.py --course 5678    # another course
.venv\Scripts\python scrape.py --headed         # watch the browser
.venv\Scripts\python scrape.py --save-html      # keep a copy of the page for debugging
```

The script prints a per-section summary and writes
`data\course-<id>\manifest.json`. Each item has: section, title, type
(`resource`, `folder`, `page`, `url`, `assign`, `inline_file`, ...), URL,
planned `local_dir`, `local_path` (filled in by Stage 3) and `status`.

How it finds content:

- Reads every section and activity on the course page using markup from Moodle
  core rather than the theme, so it should work with Boost, Classic and most
  custom themes.
- `inline_file`: files linked directly in section summaries, labels or
  activity descriptions, which are not separate activities.
- Restricted activities are listed with status `unavailable` and the
  restriction text in `note`.
- For courses that show one section per page, it opens each section page.
- It cross-checks against Moodle's own resource list (`/course/resources.php`)
  and adds anything the course page missed, with a `note` saying so.
- It waits 1.5 s between page loads and never sends requests in parallel.
- Rerunning is safe: download status recorded by Stage 3 is kept.

## Testing stages 1 and 2

1. Run `login.py` and log in. Expect "Logged in. Session saved".
2. Run `login.py --check`. Expect "Saved session is valid."
3. Run `scrape.py`. Compare the summary with the course page in your browser:
   - the same sections, in the same order, with sensible names
   - each section's item count matches what you see (labels are not counted)
   - item types look right (files show as `resource`, folders as `folder`)
4. Open `data\course-<id>\manifest.json` and spot-check a few titles and URLs.
5. Optional: delete `auth\state.json` and run `scrape.py`. It should tell you
   to run `login.py`.

If sections or items are missing or wrong, run
`scrape.py --save-html` and share `data\course-<id>\debug\course-page.html`
(it contains your name and course content, so share it only with the person
fixing the tool).

## Privacy

`.env`, `auth/`, `downloads/` and `data/` are in `.gitignore`.
`auth\state.json` works like a logged-in browser: don't share it.
