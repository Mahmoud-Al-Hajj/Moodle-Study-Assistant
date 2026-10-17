# Moodle Study Assistant: Project Plan

> Guide for Claude Code. Build one stage at a time, test it, and stop for review before moving to the next stage.

## The idea

A personal tool that logs into my university's Moodle, collects all the material from one chosen course, and turns it into an organized, searchable study folder with simple study tools for the exam. Moodle's web services API is disabled on my university's site, so the tool uses browser automation (Playwright) instead of the API. Everything runs locally on my machine, for courses I'm enrolled in, for personal study only.

**No paid services.** The core tool uses no AI API and costs nothing. An AI layer (free tier or local model) is an optional add-on for later.

**Goal:** go from "course page full of scattered files" to "every lecture as clean text, searchable, with flashcards and a quiz mode" with minimal manual work.

## Tech stack

- Python 3.11+
- Playwright (Chromium) for login and crawling
- `pymupdf` or `pdfplumber`, `python-pptx`, `python-docx` for text extraction
- `python-dotenv` for config
- SQLite or plain JSON for the search index and quiz progress (SQLite FTS5 gives free full-text search)
- Optional later: free-tier API (e.g. Gemini, Groq) or a local model via Ollama

## Project structure

```
moodle-study/
├── .env                 # MOODLE_URL, COURSE_ID (never the Moodle password)
├── .gitignore           # .env, auth/, downloads/, data/
├── auth/state.json      # saved browser session
├── downloads/<course>/<NN-section>/...   # raw files
├── data/                # extracted text, search index, flashcards, quiz progress
├── login.py             # one-time manual login, saves session
├── scrape.py            # crawl course, write manifest, download files
├── extract.py           # files -> clean text
├── search.py            # keyword search across all lectures
├── cards.py             # flashcard builder + Anki/CSV export
├── quiz.py              # local quiz mode
├── PLAN.md
└── README.md
```

## What it must do

### 1. Authenticate safely
- Open a visible browser so I log in myself (works with SSO and 2FA).
- Save the session with Playwright's `storage_state` and reuse it on later runs.
- Never ask for, store, or log my password.
- Detect an expired session and tell me to rerun `login.py`.

### 2. Discover the course content
- Open `/course/view.php?id=<COURSE_ID>` and walk every section or week.
- Identify each item by type: resource (file), folder, page, url, assign.
- Produce `manifest.json` listing everything found: section, title, type, URL, local path, download status.

### 3. Download the material
- Download all files into `downloads/<course>/<NN-section>/`, keeping sanitized original filenames.
- Handle both direct downloads and resources that open in an embedded viewer.
- For folders, use the "Download folder" zip or list the files inside.
- Skip items already downloaded so reruns are fast and safe.
- Log failures in the manifest and keep going instead of crashing.
- Throttle requests (1-2 seconds apart), no parallel requests.

### 4. Extract readable text
- Convert PDF, PPTX, and DOCX to clean text, keeping the source file and page or slide number.
- Save one `.md` per source file plus a per-section index.
- Flag scanned files with no text layer so I can decide on OCR (`ocrmypdf`/Tesseract).

### 5. Study tools (no AI required)
- **Keyword search:** `search.py "term"` shows matching passages with file, section, and page or slide number.
- **Flashcard builder:** I mark text or enter Q/A pairs; export to CSV/Anki. Optional rule-based suggestions: slide titles as topics, "X is defined as..." patterns and bolded terms as candidate cards.
- **Quiz mode:** `quiz.py` runs from a question file I write or collect (past exams, textbook questions), tracks right and wrong answers, and prioritizes weak topics next time.

### 6. Optional later: AI layer (only if free)
- Pluggable backend: a free-tier API or a local model through Ollama, switchable in `.env`.
- Generates per-lecture summaries, key terms, flashcards, and practice questions from the extracted text.
- Processes one lecture at a time and caches results so nothing runs twice.
- Every output references its source lecture and slide. Before using a hosted free tier, check its current limits and data terms, since my course material would be sent to that provider.

## Constraints and rules

- **Cost:** nothing in stages 1 to 5 may require a paid service or API key.
- **Privacy:** credentials and session files stay local and out of version control.
- **Scope:** only my enrolled courses, personal use only, within the university's IT policy.
- **Reliability:** survive small changes in Moodle's layout and report clearly when something can't be read.
- **Accuracy:** any AI-generated or rule-extracted material may contain errors, so it always points back to the original slide or page.

## Build order

1. Login and session saving (`login.py`)
2. Course crawling and manifest (`scrape.py`)
3. File downloading (`scrape.py`)
4. Text extraction (`extract.py`)
5. Search, flashcards, quiz mode (`search.py`, `cards.py`, `quiz.py`)
6. Optional AI layer (free tier or local)

Each stage is tested before the next begins. Stages 1 to 4 are the priority: they deliver all the material, organized and readable.

## Success criteria

- One command downloads everything from a course, and the file count matches what I see in the browser.
- Every file has a clean text version, and I can search across the whole course in seconds.
- I can export flashcards and run a quiz session that shows which topics I'm weakest in.

## Notes for Claude Code

- Moodle themes differ (Boost, Classic, custom). If selectors fail, ask me for a saved HTML copy of the course page.
- Start with Stages 1 and 2 only, then show me how to test them.
