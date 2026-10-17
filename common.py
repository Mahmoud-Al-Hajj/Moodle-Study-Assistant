"""Shared config, logging, session checks, throttling and error handling."""

import argparse
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

import moodle_selectors as SEL

ROOT = Path(__file__).resolve().parent
AUTH_DIR = ROOT / "auth"
STATE_FILE = AUTH_DIR / "state.json"
DATA_DIR = ROOT / "data"
DEBUG_DIR = DATA_DIR / "debug"
DOWNLOADS_DIR = ROOT / "downloads"
MANIFEST_FILE = DATA_DIR / "manifest.json"
# Files the tool writes into downloads/<course>/ itself (not course material).
GENERATED_FILES = {"links.md", "index.html"}

THROTTLE_SECONDS = 1.5
NAV_TIMEOUT_MS = 60_000

log = logging.getLogger("moodle")

# Course names are often non-ASCII; never crash on a console that can't print them.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except AttributeError:
        pass


class ConfigError(Exception):
    """Something the user must fix (settings, course id, enrolment). Exit code 1."""


class SessionExpired(Exception):
    """No valid saved session. Exit code 2."""


@dataclass
class Config:
    moodle_url: str
    course_id: str | None

    @property
    def host(self) -> str:
        return urlparse(self.moodle_url).netloc.lower()

    def url(self, path: str) -> str:
        return f"{self.moodle_url}/{path.lstrip('/')}"


def load_config(require_course: bool = True, course_override: str | None = None) -> Config:
    env_file = ROOT / ".env"
    if not env_file.exists():
        raise ConfigError("No .env file found. Copy .env.example to .env and set COURSE_ID.")
    load_dotenv(env_file, override=True)

    url = os.getenv("MOODLE_URL", "").strip().rstrip("/")
    if not url:
        raise ConfigError("Set MOODLE_URL in .env, e.g. https://haigmoodle.haigazian.edu.lb/moodle")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    # Accept a pasted course or dashboard URL and keep only the site root.
    url = re.sub(r"/(course|my|login|mod)/.*$", "", url)

    course = (course_override or os.getenv("COURSE_ID", "")).strip() or None
    if require_course:
        if not course:
            raise ConfigError("Set COURSE_ID in .env (the number after ?id= in the course URL), or pass --course.")
        if not course.isdigit():
            raise ConfigError(f"COURSE_ID must be a number, got {course!r}.")
    return Config(moodle_url=url, course_id=course)


class Throttle:
    """Keep at least `seconds` between requests. We never run requests in parallel."""

    def __init__(self, seconds: float = THROTTLE_SECONDS):
        self.seconds = seconds
        self._last = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last
        if elapsed < self.seconds:
            time.sleep(self.seconds - elapsed)
        self._last = time.monotonic()


def goto(page, url: str, throttle: Throttle | None = None):
    """Navigate politely and return the response."""
    if throttle:
        throttle.wait()
    log.debug("GET %s", url)
    return page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)


_LOGIN_PROBE_JS = """(sel) => {
    const cls = document.body ? document.body.className.split(/\\s+/) : [];
    return {
        href: location.href,
        loggedOutClass: cls.includes(sel.body_class_logged_out),
        hasLogout: !!document.querySelector(sel.logout_link),
        hasLoginLink: !!document.querySelector(sel.login_link),
        hasLoginForm: !!document.querySelector(sel.login_form),
    };
}"""


def is_logged_in(page, cfg: Config) -> bool:
    """True if the current page is a Moodle page viewed by a logged-in (non-guest) user."""
    try:
        # Ask the page for its URL: page.url can be stale after the script was blocked (e.g. waiting for Enter).
        probe = page.evaluate(_LOGIN_PROBE_JS, SEL.LOGIN)
    except Exception:
        return False  # page is mid-navigation
    current = urlparse(probe["href"])
    if current.netloc.lower() != cfg.host:
        return False  # bounced to an external login page
    if "/login/" in current.path:
        return False
    if probe["loggedOutClass"] or probe["hasLoginForm"]:
        return False
    # Guests see a "Log in" link and no logout link.
    return probe["hasLogout"] or not probe["hasLoginLink"]


def where(page) -> str:
    """Current URL without query string (which can carry tokens), for messages."""
    try:
        href = page.evaluate("() => location.href")
    except Exception:
        href = page.url
    u = urlparse(href)
    return f"{u.scheme}://{u.netloc}{u.path}"


def require_session_file() -> None:
    if not STATE_FILE.exists():
        raise SessionExpired("No saved session yet. Run:  python login.py")


def new_session_context(playwright, headless: bool = True):
    """Launch Chromium with the saved session. Returns (browser, context)."""
    require_session_file()
    browser = playwright.chromium.launch(headless=headless)
    try:
        context = browser.new_context(storage_state=str(STATE_FILE))
    except Exception:
        browser.close()
        raise SessionExpired("The saved session file is unreadable. Run:  python login.py")
    return browser, context


_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def sanitize_name(name: str, max_len: int = 80, fallback: str = "untitled") -> str:
    """Make a string safe as a Windows/macOS/Linux file or folder name. Keeps non-ASCII letters."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", name)
    name = re.sub(r"\s+", " ", name).strip().strip(".").strip()
    if len(name) > max_len:
        name = name[:max_len].rstrip(" .")
    if not name:
        name = fallback
    if name.split(".")[0].upper() in _WINDOWS_RESERVED:
        name = "_" + name
    return name


# --- Local layout and atomic writes (shared by downloader.py and extract.py) ---

def course_dir(manifest: dict) -> Path:
    return DOWNLOADS_DIR / sanitize_name(manifest["course_name"], max_len=60, fallback=f"course-{manifest['course_id']}")


def section_dir(manifest: dict, item: dict) -> Path:
    name = sanitize_name(item["section_name"], max_len=50, fallback="section")
    return course_dir(manifest) / f"{item['section_number']:02d}-{name}"


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_bytes(data)
    part.replace(path)


def write_text(path: Path, text: str) -> None:
    write_bytes(path, text.encode("utf-8"))


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("-v", "--verbose", action="store_true", help="show detailed logging and error tracebacks")
    return parser


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    # Playwright's own logger is noisy at debug level.
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def run(main, args) -> None:
    """Run a script's main(args) and turn every failure into one clear line and an exit code."""
    setup_logging(args.verbose)
    from playwright.sync_api import Error as PlaywrightError

    try:
        code = main(args) or 0
    except SessionExpired as e:
        log.error("%s", e)
        code = 2
    except ConfigError as e:
        log.error("%s", e)
        code = 1
    except KeyboardInterrupt:
        log.error("Cancelled. Nothing more was saved.")
        code = 130
    except PlaywrightError as e:
        first = (e.message or str(e)).strip().splitlines()[0]
        if "Executable doesn't exist" in first:
            log.error("Chromium isn't installed. Run:  python -m playwright install chromium")
        elif "Target page, context or browser has been closed" in first:
            log.error("The browser window was closed. Nothing more was saved.")
        else:
            log.error("Browser error: %s", first)
        log.debug("Details:", exc_info=True)
        code = 1
    except Exception as e:  # last resort: still no stack trace unless --verbose
        log.error("Unexpected error: %s: %s (rerun with --verbose for details)", type(e).__name__, e)
        log.debug("Details:", exc_info=True)
        code = 1
    sys.exit(code)
