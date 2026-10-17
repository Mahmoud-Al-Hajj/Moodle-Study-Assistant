"""Bring the local copy of a course up to date with one command.

Runs, in order and in one process:
  1. check the saved session (check_session.py)
  2. if it expired: log in in a visible browser (login.py), then carry on
  3. crawl the course and download new or failed items (scrape.py)
  4. extract text and rebuild the course viewer (extract.py)
then opens downloads/<course>/index.html.

    update                     # update.bat: same as .venv\\Scripts\\python update.py
    update --no-open           # don't open the viewer at the end
    update --course 5678       # another course
    update --force             # re-extract every file
    update --no-download       # crawl only, then extract what is already on disk

Each step opens and closes its own browser before the next one starts (Playwright
instances are never nested). The first step that fails stops the run.
Exit codes: 0 ok, 1 error, 2 session expired and no terminal to log in from, 130 cancelled.
"""

import json
import sys
import time
import webbrowser

import check_session
import extract
import login
import scrape
from common import (MANIFEST_FILE, ROOT, SessionExpired, base_parser,
                    course_dir, load_config, log, run)

STEPS = 4


def step(n: int, title: str) -> None:
    print()
    print(f"=== Step {n}/{STEPS}: {title} ===")


def ensure_session(cfg) -> None:
    """Check the saved session; log in interactively when it is missing or expired."""
    try:
        ok, landed = check_session.check(cfg)
        reason = f"Moodle sent the browser to {landed}"
    except SessionExpired as e:  # no session file, or an unreadable one
        ok, reason = False, str(e)
    if ok:
        log.info("Session is valid.")
        return
    if not sys.stdin.isatty():
        raise SessionExpired(f"The session is not valid ({reason}) and there is no terminal to log in from. "
                             "Run:  python login.py")
    log.warning("The session is not valid (%s). Opening the login browser.", reason)
    login.interactive_login(cfg)


def main(args) -> int:
    started = time.monotonic()
    cfg = load_config(require_course=True, course_override=args.course)

    step(1, "check the session")
    ensure_session(cfg)

    step(2, "crawl the course and download")
    scrape.main(args)

    step(3, "extract text")
    extract.main(args)

    step(4, "course viewer")
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    index_html = course_dir(manifest) / "index.html"
    if args.no_open:
        log.info("Viewer: %s", index_html.relative_to(ROOT))
    else:
        log.info("Opening %s", index_html.relative_to(ROOT))
        webbrowser.open(index_html.as_uri())

    print()
    print(f"Update finished in {time.monotonic() - started:.0f} s.")
    return 0


if __name__ == "__main__":
    parser = base_parser("Check the session, crawl, download, extract and open the course viewer.")
    scrape.add_arguments(parser)
    extract.add_arguments(parser)
    parser.add_argument("--no-open", action="store_true", help="don't open the course viewer at the end")
    run(main, parser.parse_args())
