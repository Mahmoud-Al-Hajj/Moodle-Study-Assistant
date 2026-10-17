---
name: text-extraction
description: Output formats, rules and flags of the Moodle study tool's Stage 4 text extraction (extract.py) - the per-file .md layout, passages.jsonl schema used by search/flashcards/quiz, extract_state.json caching, .ppt conversion via PowerPoint, and the offline index.html. Use when working on extract.py, on anything that reads data/text/, or when building Stage 5 (search.py, cards.py, quiz.py).
---

# Text extraction (Stage 4)

`python extract.py` reads `data/manifest.json` and turns every downloaded file into text. It never contacts Moodle. `--force` re-extracts everything.

## Rules

- **No paid services and no network.** Libraries: `pymupdf` (PDF), `python-pptx` (PPTX), `python-docx` (DOCX), stdlib for `.md`/`.html`/`.txt`.
- **Everything traceable.** Every block keeps its location (`page N`, `slide N`, `¶N`), so any study aid can point back to the source.
- **One broken file never stops the run.** Exceptions are caught per file and recorded as the `error` flag. Exit code 1 only for setup problems such as a missing manifest.
- **Idempotent.** A file is re-extracted only when it changed or when it carries a retry flag (see below). `.md` files are only rewritten when their content differs, so mtimes stay stable.
- **Bump `EXTRACTOR_VERSION`** in `extract.py` whenever extraction output changes. That invalidates the cache, and the next run re-extracts everything.
- **Run the tests** after changes: `python tests/run_tests.py`. The Stage 4 tests are in `tests/test_extract.py` and generate their sample documents at run time.

## Output layout

```
data/text/<course>/
├── _index.md                      # course index: sections, file counts, words, "Needs attention"
├── passages.jsonl                 # search passages (schema below)
├── extract_state.json             # cache (schema below)
└── <NN-section>/
    ├── _index.md                  # files table + outlines (slide titles / headings)
    ├── <file>.<ext>.md            # e.g. Communism.pptx.md (full source name kept, so names can't clash)
    └── <title> - instructions.md  # .md sources keep their own name
data/converted/<course>/<NN-section>/<name>.pptx   # .ppt converted by PowerPoint (cache)
downloads/<course>/index.html                       # offline reading view
```

`<course>` and `<NN-section>` mirror `downloads/` (the paths come from `common.course_dir` and `common.section_dir`). Files inside folder activities keep their subfolders.

## Per-file `.md`

1. `# <title>`, then a two-column table: Section, Source (path), Moodle URL, Type, Pages/Slides/Paragraphs, Words, Flags.
2. One `> **flag:** advice` line per flag.
3. The body:
   - **PDF:** `## Page N`, then the page text. Words hyphenated across a line break are re-joined.
   - **PPTX/PPT:** `## Slide N: <title>`. The slide text follows as bullets, indented by level, in reading order (top to bottom, then left to right, descending into groups). Tables become Markdown tables, SmartArt text is included, and speaker notes go under `### Notes`. Slide number, date and footer placeholders are skipped. A slide with no text reads `*(No text on this slide: images or diagrams only.)*`.
   - **DOCX:** document headings become `##`/`###`, each followed by ` [¶N]`. Paragraphs end with ` [¶N]`, and a table gets its `[¶N]` on its own line just above it. List paragraphs start with `- `. **Bold runs become `**bold**`**: candidate terms for Stage 5 flashcards. Headers, footers and text boxes are not extracted.
   - **md/html/txt:** the text as one block.

## `passages.jsonl` (one JSON object per line; Stage 5's input)

```json
{"source": "downloads/<course>/02-.../Communism.pptx", "md": "data/text/<course>/02-.../Communism.pptx.md",
 "section_number": 2, "section_name": "...", "title": "Communism and Human Happiness", "kind": "pptx",
 "location": "slide 3", "heading": "<slide title or nearest Word heading>", "text": "<plain text, no ** markers>"}
```

- **PDF, PPTX:** one passage per page or slide that has text.
- **DOCX:** paragraphs are grouped under their heading into passages of up to about 1200 characters, with `location` like `¶5-¶9` (or `¶5` for one paragraph).
- **Links:** each `url` item adds `kind: "link"`, `location: "link"`, `md: ""`, and `text` = title plus target URL.

## `extract_state.json`

```json
{"version": 3, "sources": {"<source path>": {
  "kind": "pptx", "size": 123, "mtime_ns": 0, "sha1": "...", "output": "data/text/...md",
  "converted": "data/converted/...pptx or empty", "flags": [], "note": "", "outline": ["..."],
  "words": 0, "blocks": [{"loc": "slide 1", "n": 1, "heading": "", "level": 0, "md": "...", "text": "..."}]}}}
```

- **Re-extraction:** a file is unchanged when its size and mtime match, or its size and sha1 match after a touch. Changed files are extracted again.
- **Cached text:** `blocks` holds the extracted content. Indexes, `passages.jsonl` and `index.html` are rebuilt from it on every run without re-reading the files.
- **Clean-up:** sources that disappear from the manifest lose their `.md` and converted copy.

## Flags

| Flag | Meaning | Retried each run? |
|---|---|---|
| `needs_ocr` | PDF: at least half the pages have fewer than 25 characters of text plus an image. The advice is to run `ocrmypdf` (needs Tesseract, not installed). | no |
| `mostly_images` | PPTX: more than half the slides have no text | no |
| `needs_conversion` | `.ppt` that PowerPoint couldn't convert, or `.doc`/`.xls`/`.pps`, which are never auto-converted | yes |
| `error` | the file couldn't be read; `note` has the reason | yes |
| `unsupported` | unknown file type | no |
| `no_text` | video, audio or image: listed, nothing to extract (informational) | no |

## `.ppt` conversion

- **How:** `convert_ppt` runs PowerShell with an encoded script that drives the installed PowerPoint through COM: `Presentations.Open(src, ReadOnly, Untitled=false, WithWindow=false)`, then `SaveAs(dst, 24)` for `.pptx`.
- **Safety:** PowerPoint is quit afterwards only if it had no presentations open before, so the user's own work is never closed.
- **Limits:** 120 s timeout. The result is cached in `data/converted/` and reused while the `.ppt` is unchanged.
- **In tests:** the env var `MOODLE_STUDY_POWERSHELL` overrides the PowerShell executable. Tests set it to a missing program, so they never launch Office.

## `index.html`

- **Self-contained:** one file with inline CSS and about 20 lines of JS, no external requests, and it works by double-click.
- **Content:** sections in course order. Each downloaded file gets a card with its type, size, flags and links to the original, its `.md` and Moodle. The extracted text sits in `<details>`. Links are listed per section, and failed, unavailable or skipped items are greyed out with their reason.
- **Filter box:** hides non-matching cards, opens matching text and highlights matches using the CSS Custom Highlight API. Highlighting is skipped in browsers without that API.
- **Escaping:** every course string goes through `html.escape`. There is a test for a `<script>` title.
- **Display:** light and dark through `prefers-color-scheme`, with no horizontal scroll at 390 px wide.
- **Not counted as course material:** `index.html` and `links.md` are in `common.GENERATED_FILES`, so Stage 3's "Files on disk" count leaves them out.
