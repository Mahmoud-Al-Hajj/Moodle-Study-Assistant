# Moodle Study Assistant

A personal tool that collects the material from one Moodle course into a local, searchable study folder.

- It drives a real browser with Playwright, because the site's web services API is disabled.
- Everything runs locally and uses no paid services.
- The full plan is in [PLAN.md](PLAN.md). The rules for Claude are in [CLAUDE.md](CLAUDE.md).

**Status:** Stages 1-4 are done: login and session check, course crawl to `data/manifest.json`, downloads to `downloads/<course>/`, and text extraction with a browsable `index.html`. `update` runs all of it in one command. A local web UI is being built on top of the same scripts: the Dashboard (session, login, scrape) and the Course content screen work now. See [Web UI](#web-ui).

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

## Update everything with one command

```powershell
.\update                    # check session, log in if needed, crawl, download, extract, open the viewer
.\update --no-open          # same, without opening the viewer
.\update --course 5678      # another course
.\update --force            # re-extract every file
.\update --no-download      # crawl only, then extract what's already on disk
.\update --verbose          # detailed logging (also --headed, --save-html)
```

`update.bat` runs `update.py` with the project's `.venv`, so you don't need to activate anything or type `.venv\Scripts\python`. It also works from any folder: `C:\Users\user\Desktop\moodle-study\update`.

It runs four steps and stops at the first one that fails:

1. **Check the session.** If it has expired, the login browser opens, as with `login.py`. Log in, press Enter, and the update carries on.
2. **Crawl and download** (`scrape.py`): only new or failed items are fetched.
3. **Extract** (`extract.py`): only new or changed files.
4. **Open** `downloads\<course>\index.html` in your browser.

A run with nothing new looks like this (timings vary):

```
=== Step 1/4: check the session ===
... INFO    Session is valid.

=== Step 2/4: crawl the course and download ===
...
  downloaded now      0
  already present    62
  ...
  failed              1
    - Article Presentation Schedule [resource]: HTTP 404

=== Step 3/4: extract text ===
...
Files: 32   extracted now 0, unchanged 32, removed 0
...

=== Step 4/4: course viewer ===
... INFO    Opening downloads\<course>\index.html

Update finished in 20 s.
```

The individual scripts below still work on their own.

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
python download.py                # download only: what the manifest lists, without crawling again
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

## Web UI

A local web app that drives the same scripts from the browser. It runs them unchanged as background processes, so the terminal commands above keep working and produce the same files.

**Status:** Stages A-B of A-F. The Dashboard and Course content screens work; the others (search, reader, flashcards, quiz, settings) are greyed out in the menu until they're built.

### Setup (once)

You need [Node.js](https://nodejs.org) LTS as well as the Python setup above.

```powershell
cd C:\Users\user\Desktop\moodle-study
.venv\Scripts\python -m pip install -r requirements-dev.txt
cd web
npm install
cd ..
```

npm may warn about esbuild's install script (`allowScripts`). The app still works.

### Run it

```powershell
.\dev              # starts the API and the app, then opens http://127.0.0.1:5173
.\dev --no-open    # same, without opening the browser
```

Ctrl+C in that terminal stops both. The two servers are:

- **API:** http://127.0.0.1:8765
- **App:** http://127.0.0.1:5173

### The Dashboard

- **Session:** checked automatically when the page opens, then shows *Logged in*, *Session expired* or *Not logged in*.
  - **Log in to Moodle** opens the same visible Chromium window as `login.py`. Log in there, then click **I'm logged in** in the app (it presses Enter for you).
  - **Check now** checks the session again.
- **Course:** name, id, last crawl time, and item counts by status (found, downloaded, failed, unavailable, pending).
- **Scrape course:** runs `scrape.py --no-download`. If the course was already scraped, it asks first; progress is always kept. While it runs you get a progress bar, a live log you can expand, and **Cancel**. Afterwards the card shows the last run time and counts.
- Only one job runs at a time, so Moodle never gets parallel requests.
- The sun/moon button switches light and dark mode. It follows your system until you pick one, and remembers your choice. On a phone, the menu moves to the bottom of the screen.

### Course content

Every section of the course, with its items in a table:

- **Each item** shows a type icon, its title, a status chip (Downloaded, Failed, Skipped, Unavailable, Pending) and any note: why it failed, or the restriction on an unavailable item.
- **Filter** with the search box (titles; case and accents don't matter) and the Type and Status chips. The filters stay in the address, so a reload keeps them. **Expand all** / **Collapse all** open or close every section.
- **Links** open their real address in a new tab. The arrow button opens any item in Moodle.
- **Click a file's title** (or the eye button) to preview it in a side panel:
  - PDFs, pictures, videos and text files show as they are.
  - Word and PowerPoint files show their extracted text (from `extract.py`), with headings and slide titles. Open the file for its layout and pictures.
  - **Open in app** opens the file in its usual Windows program (documents and media only, never programs). **Show in folder** opens File Explorer with the file selected. **New tab** shows PDFs and pictures in a full browser tab.
- **Retry N failed** runs `download.py`: it downloads the failed items again, plus anything new in the list, without re-reading the course page. You get the same progress, log and Cancel as for Scrape.

### Security

- Both servers listen on **127.0.0.1 only**, so no other computer can reach them.
- The API only answers requests addressed to `127.0.0.1` or `localhost`, and every request that changes something needs a header the app adds. Other websites open in your browser can't start jobs.
- Your password never goes through the app. You type it into the Moodle page in the Chromium window, as with `login.py`.
- `auth\state.json` is never read or served by the API: it only checks that the file exists.
- The app only shows files from `downloads\`, `data\text\` and `data\converted\`. Everything else (`auth\`, `.env`, `data\ui\`, `data\debug\`) is refused, including tricks like `..` or folder links. Saved Moodle pages are shown with their scripts turned off.

### Tests

```powershell
.venv\Scripts\python -m pytest tests\test_api.py    # API against the fake Moodle; $env:SKIP_HEADED=1 skips the browser test
cd web
npm test           # screen and component tests
npm run lint       # ESLint + Prettier
npm run build      # type check + production build
```

## Testing against a fake Moodle

```powershell
python tests\run_tests.py
```

This runs 34 tests: 28 against a local imitation of Moodle (including the whole `update.py` pipeline on generated `.docx` and PDF files), plus 6 for text extraction on sample documents generated at run time. They cover Boost and Classic themes, the `/moodle` subpath, expired and guest sessions, restricted items, unknown markup, and downloads (embedded viewers, folders, assignments, links, 404s, name clashes, session expiry mid-run, reruns). The full run takes about 3 minutes. It never touches your real `.env`, `auth\` or `data\`.

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

`.env`, `auth/`, `downloads/` and `data/` (including the web UI's own `data\ui\`) are excluded from git.

`auth\state.json` works like a logged-in browser, so don't share it.
