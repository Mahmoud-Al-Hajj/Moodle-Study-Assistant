---
name: moodle-scraper
description: Rules, manifest format and folder layout for the Moodle study tool's login, crawler and downloader (login.py, check_session.py, scrape.py, downloader.py, moodle_selectors.py). Use whenever working on scraping, selectors, the manifest, downloads or session handling in this project.
---

# Moodle scraper

The spec is PLAN.md. This skill holds the rules and data formats that every change to the scraper must respect.

## Rules

- **Password:** never ask for, read, store, or log it. The user logs in by hand in a visible Chromium window (`login.py`). They press Enter once the dashboard has loaded, and the session is saved with Playwright `storage_state` to `auth/state.json`.
- **URLs:** build every one from `MOODLE_URL` in `.env` with `Config.url(path)`. Never hardcode the domain. The site is `https://haigmoodle.haigazian.edu.lb/moodle`, under a `/moodle` subpath.
- **Throttling:** 1-2 seconds between requests (`common.Throttle`, default 1.5 s), no parallel requests.
- **Idempotent reruns:** skip already-downloaded items and never duplicate them. Items are matched across runs by `id`.
- **Selectors:** all CSS/DOM selectors and URL patterns live in `moodle_selectors.py`, and nowhere else. The browser-side JavaScript receives them as arguments. Don't name the file `selectors.py`: that shadows a Python standard-library module that Playwright's asyncio uses.
- **Selector failures:** don't guess. Save the page HTML to `data/debug/` (the course page goes to `data/debug/course_page.html`), tell the user, and ask them to share it so `moodle_selectors.py` can be fixed. Never put unmatched links into made-up sections.
- **Session checks:** every script that loads `auth/state.json` checks the session (`common.is_logged_in`) after each navigation. If the session is invalid, expired or a guest session, it raises `SessionExpired`, which prints "rerun login.py" and exits with code 2.
- **Errors:** run every script's `main` through `common.run`. It logs one clear line per error with no stack trace, unless `--verbose` is passed.
- **Stages:** work one stage at a time. After each stage, stop, show the user how to test it, and wait for confirmation.
- **Tests:** after any selector or parsing change, run `python tests/run_tests.py`. When the user shares a real page, add it to `tests/fixtures/`, replacing the site prefix with `__BASE__`.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | OK. Warnings may still have been printed. |
| 1 | Error: config, browser, page or selector failure |
| 2 | Session missing or expired: rerun `login.py` |
| 130 | Cancelled with Ctrl+C |

## Folder layout

```
moodle-study/
├── .env                       # MOODLE_URL, COURSE_ID (never the password)
├── auth/state.json            # saved browser session (private)
├── data/
│   ├── manifest.json          # manifest of the current course
│   ├── manifest-course-<id>.json   # parked manifest of a previously crawled course
│   └── debug/course_page.html # saved when selectors fail, or with --save-html
├── downloads/<course name>/
│   ├── links.md               # all url items, grouped by section (regenerated each run)
│   ├── index.html             # Stage 4 reading view (extract.py); not course material
│   └── <NN-section name>/<original filename>   # also <folder title>/<subpath>/, <title> - instructions.md
├── common.py                  # config, session check, throttle, logging, run(), course_dir/section_dir, atomic writes
├── moodle_selectors.py        # every selector and URL pattern
├── login.py / check_session.py / scrape.py
├── downloader.py              # Stage 3 handlers, called by scrape.py
├── update.py / update.bat     # one command: check session → login if expired → scrape.main → extract.main → open viewer
└── tests/                     # fake-Moodle tests: python tests/run_tests.py
```

- `<course name>` and `<NN-section name>` go through `common.sanitize_name`. `NN` is the zero-padded section number, e.g. `00-General`, `03-Week 3`.
- Original filenames are kept, after sanitizing.

## Manifest format (`data/manifest.json`)

```json
{
  "moodle_url": "https://haigmoodle.haigazian.edu.lb/moodle",
  "course_id": "1234",
  "course_name": "Data Structures (CS201)",
  "crawled_at": "2026-10-17T12:00:00+00:00",
  "sections": [
    {"section_number": 0, "section_name": "General", "item_count": 2}
  ],
  "items": [
    {
      "section_number": 1,
      "section_name": "Week 1",
      "title": "Lecture 1 slides",
      "type": "resource",
      "url": "https://haigmoodle.haigazian.edu.lb/moodle/mod/resource/view.php?id=11",
      "local_path": "",
      "status": "pending",
      "id": "cm:11",
      "module": "resource",
      "note": "",
      "files": [],
      "target_url": ""
    }
  ]
}
```

### Fields

| Field | Meaning |
|---|---|
| `section_number`, `section_name` | Section the item appears in. Items inside Moodle 4.5 subsections belong to the parent section. |
| `title` | Visible name, with screen-reader text such as " File" removed |
| `type` | Taken from the URL: `resource` (a file), `folder`, `page`, `url`, `assign`, or `other` for everything else |
| `url` | Activity URL, or the direct file URL for inline files. Empty for unavailable items. |
| `local_path` | Empty until Stage 3 handles the item. Then it's the path relative to the project root: the file, or a folder's directory, an assignment's instructions `.md`, or `links.md` for links. |
| `status` | See the statuses below |
| `id` | Stable identity for de-duplication across reruns. `cm:<course module id>` for activities, `file:<url without query>` for inline files. |
| `module` | The real Moodle module name: `resource`, `forum`, `quiz`, `book`... For files linked directly from a label, section summary or activity description, it's `inline_file`. Use it to understand `other` items. |
| `note` | Extra information, otherwise empty. For unavailable items, the restriction text. For failed items, the error. For skipped items, the reason. |
| `files` | Every local path an item produced, for folders and assignments. Empty otherwise. |
| `target_url` | For `url` items, the real external address, resolved in Stage 3. Empty otherwise. |

### Statuses

| Status | Set by | Meaning |
|---|---|---|
| `pending` | Stage 2 | Found, not yet handled |
| `unavailable` | Stage 2 | Restricted: shown on the course page but with no link, with the restriction text in `note`. **Stage 3 must skip these.** A later crawl turns them into `pending` once the restriction lifts. |
| `downloaded` | Stage 3 | Content captured locally: the file or files, the instructions, or the link entry. |
| `failed` | Stage 3 | The error is in `note`. Retried on every run. |
| `skipped` | Stage 3 | Nothing to download (forum, quiz...), with the reason in `note`. Re-evaluated each run, without any requests. |

Recrawls keep Stage 3 statuses together with `local_path`, `files`, `target_url` and `note`, so reruns don't redo work.

### Rerun and course-switch rules

- **Same course:** items are matched by `id`. Stage 3 statuses and `local_path` are kept, new items are added as `pending`, and items that disappeared from Moodle are dropped.
- **Different course:** the existing `data/manifest.json` is first moved to `data/manifest-course-<old id>.json`. Crawling that old course again restores its progress from the parked file, then removes the parked copy.

### What isn't in the manifest

- Labels and subsection containers, though files linked inside labels are recorded as `inline_file`.
- Links the selectors couldn't place in a section. These are reported as a warning and the debug HTML is saved.
- Items found only in Moodle's resource index (`/course/resources.php`). They're reported as a warning, since they're usually hidden from the course page by the teacher.

## Stage 3: downloading (`downloader.py`, run by `scrape.py`)

`python scrape.py` crawls, writes the manifest, then calls `downloader.download_all`. `--no-download` stops after the manifest. Items are handled in manifest order, one request at a time, through the shared `Throttle`.

| `module` | Handling | Saved to |
|---|---|---|
| `resource` | GET `view.php?id=X&redirect=1`. Moodle core redirects to the file whatever the display setting. If an HTML page comes back, open it and take the file from `RESOURCE["file_element"]`. | `<NN-section>/<original filename>` |
| `inline_file` | GET the pluginfile URL | `<NN-section>/<original filename>` |
| `folder` | Open the folder page and fetch each `FOLDER["file_link"]`. The subpath comes from `PATTERNS["folder_file_subpath"]`. Files already on disk aren't fetched again. | `<NN-section>/<folder title>/<subpath>/<file>` |
| `assign` | Open the page. Write the dates and instructions (`ASSIGN[...]`, innerText) to Markdown, and fetch the attachments. Never read submission areas. | `<NN-section>/<title> - instructions.md`, with attachments next to it |
| `page` | Save the innerHTML of `PAGE["content"]` | `<NN-section>/<title>.html` |
| `url` | GET `view.php?id=X&redirect=1` without following redirects, and use `Location` as `target_url`. Fall back to `URL["external_link"]` on the page. | an entry in `<course>/links.md`, regenerated every run |
| anything else | `status: skipped`, with the reason in `note` | none |
| status `unavailable` | never requested | none |

- **Filenames:** taken from the pluginfile URL, then `Content-Disposition`, then the URL. They go through `downloader.safe_filename`, which keeps the extension.
- **Name clash:** a second item wanting the same path gets ` (cm<id>)` before the extension. This is deterministic, because downloaded items' paths are claimed first.
- **Writes are atomic:** files are written to `name.part`, then renamed. Leftover `.part` files are removed at the start of a run.
- **Progress:** the manifest is saved after every item, and again in a `finally` block on Ctrl+C or session expiry.
- **Done check:** an item is done when its status is `downloaded` and `local_path` plus every path in `files` exist. For links, it's when `target_url` is set. Anything else is fetched, including `failed` items and deleted files.
- **Session expiry:** a final URL, or a `Location`, on Moodle's `/login/` raises `SessionExpired` (exit 2).
- **Failures:** HTTP ≥ 400, network errors and missing selectors make the item `failed`, with the message in `note`, and the run continues. A selector failure also saves the page to `data/debug/<module>_cm<id>.html`.
- **Side effect:** opening activities marks them as viewed in Moodle, just as a click would.
