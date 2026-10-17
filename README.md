# Moodle Study Assistant

A personal tool that collects the material from one Moodle course into a local, searchable study folder.

- It drives a real browser with Playwright, because the site's web services API is disabled.
- Everything runs locally and uses no paid services.
- The full plan is in [PLAN.md](PLAN.md). The rules for Claude are in [CLAUDE.md](CLAUDE.md).

**Status:** Stages 1-4 are done: login and session check, course crawl to `data/manifest.json`, downloads to `downloads/<course>/`, and text extraction with a browsable `index.html`. Stage 5 (search, flashcards, quiz) is next.

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

## Stage 2: crawl a course

```powershell
python scrape.py --no-download    # crawl only (Stage 3 adds the download)
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

## Stage 3: download everything

```powershell
python scrape.py                  # crawl, then download
python scrape.py --no-download    # manifest only
```

`scrape.py` crawls the course, then downloads its material into `downloads\<course>\<NN-section>\`:

| Item | What's saved |
|---|---|
| Files (`resource`, `inline_file`) | the file, with its original name |
| Folders | each file, keeping subfolders: `<NN-section>\<folder>\...` |
| Assignments | `<title> - instructions.md` with the dates and instructions, plus any attached files. Your submissions are never read. |
| Pages | `<title>.html` |
| Links (`url`) | one `links.md` in the course folder, grouped by section, with each link's real address |
| Forums, quizzes, other | skipped (`status: "skipped"`) |
| Restricted (`unavailable`) | never requested |

At the end it prints how many items were downloaded, already present, skipped, unavailable and failed, plus "Files on disk" to compare with the browser.

- **Reruns** only fetch what's missing: new items, failed items, and files you deleted. A rerun with nothing new takes seconds.
- **A failure never stops the run.** The item is marked `failed`, with the reason in `note`, and retried on the next run. If you get a 404, the file is usually missing on Moodle itself.
- **If the session expires mid-run**, progress is saved. Run `login.py`, then `scrape.py` again, and it continues.
- **Note:** downloading opens each item on Moodle's side, just like clicking it. Teachers who track completion will see the items as viewed.

## Stage 4: extract the text and browse the course

```powershell
python extract.py           # after scrape.py; only processes new or changed files
python extract.py --force   # re-extract everything
start "downloads\<course>\index.html"
```

`extract.py` turns every downloaded file into clean text, offline. It never contacts Moodle.

- **`downloads\<course>\index.html`** opens in any browser and works offline:
  - every section with its files, assignments and links
  - each file's text, expandable, with slide and page numbers
  - a filter box that finds and highlights a word across the whole course
  - a "Needs attention" list at the top
- **`data\text\<course>\`** holds one `.md` per file:
  - PowerPoint files are split as `## Slide N: title`, with speaker notes, tables and SmartArt
  - PDFs as `## Page N`
  - Word files keep their headings, with each paragraph tagged `[¶N]`
  - bold text stays `**bold**`

  Each section also gets an `_index.md` with its files and slide titles. `passages.jsonl` is what the Stage 5 search and quiz tools will use.
- **Old `.ppt` files** are converted automatically with your installed PowerPoint. It runs in the background with no window, and is only closed if you didn't already have it open. The original file isn't changed.
- **Flags** in the summary and in `index.html`:
  - `mostly_images`: slides that are pictures, with no searchable text
  - `needs_ocr`: a scanned PDF. Make it searchable with `ocrmypdf`, which needs Tesseract (free, not installed).
  - `needs_conversion`: an old Office file that couldn't be converted
  - videos are listed but have no text

Rerunning `scrape.py` then `extract.py` keeps everything up to date. Files that haven't changed are skipped, so a rerun takes under a second.

## Testing against a fake Moodle

```powershell
python tests\run_tests.py
```

This runs 31 tests: 25 against a local imitation of Moodle, plus 6 for text extraction on sample documents generated at run time. They cover Boost and Classic themes, the `/moodle` subpath, expired and guest sessions, restricted items, unknown markup, and downloads (embedded viewers, folders, assignments, links, 404s, name clashes, session expiry mid-run, reruns). The full run takes about 3 minutes. It never touches your real `.env`, `auth\` or `data\`.

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
