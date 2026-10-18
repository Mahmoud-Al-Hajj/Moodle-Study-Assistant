"""Serve and open course files, safely.

Only files under SERVED_DIRS are reachable. Paths come from the browser, so every one goes
through resolve_served(): plain relative POSIX paths only, resolved (following junctions and
symlinks) and required to stay inside an allowed folder. auth/, .env, data/ui/ and
data/debug/ (saved Moodle pages can hold the session key) are never reachable.
"""

import os
import subprocess
import sys
from pathlib import Path

# Relative to the project root. downloads/: course files; data/text/: extracted text;
# data/converted/: .ppt files converted to .pptx.
SERVED_DIRS = ("downloads", "data/text", "data/converted")

# What "Open in app" may hand to Windows: documents and media only, never anything that runs.
OPENABLE = {
    ".pdf", ".doc", ".docx", ".odt", ".rtf", ".ppt", ".pptx", ".pps", ".ppsx", ".odp",
    ".xls", ".xlsx", ".ods", ".csv", ".txt", ".md",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
    ".mp4", ".webm", ".mov", ".mkv", ".avi", ".mp3", ".m4a", ".wav", ".ogg",
}

# Explicit types: Windows' registry-based guesses vary between machines.
CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".md": "text/plain; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".csv": "text/plain; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
}


class NotServed(Exception):
    """The path is outside the allowed folders, malformed, or not a file."""


def resolve_served(root: Path, rel: str) -> Path:
    """Map a browser-supplied path like 'downloads/<course>/01-Week 1/x.pdf' to a file, or raise NotServed."""
    if not rel or "\\" in rel or ":" in rel or "\x00" in rel or rel.startswith("/"):
        raise NotServed(rel)
    if any(part in ("", ".", "..") for part in rel.split("/")):
        raise NotServed(rel)
    target = (root / rel).resolve()
    allowed = [(root / d).resolve() for d in SERVED_DIRS]
    if not any(target.is_relative_to(a) and target != a for a in allowed) or not target.is_file():
        raise NotServed(rel)
    return target


def content_type(path: Path) -> str:
    return CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


def response_headers(path: Path) -> dict[str, str]:
    """No sniffing; and every document except PDFs is sandboxed: a saved Moodle page (.html) or an
    SVG then runs no script and gets no access to this app's origin. Chrome refuses to show PDFs in
    a sandbox, and its PDF viewer doesn't run in the app's origin anyway."""
    headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache"}
    if path.suffix.lower() != ".pdf":
        headers["Content-Security-Policy"] = "sandbox"
    return headers


def openable(path: Path | str) -> bool:
    return Path(path).suffix.lower() in OPENABLE


# --- Windows integration (tests replace these two) ---

def open_with_default_app(path: Path) -> None:
    os.startfile(path)  # type: ignore[attr-defined]  # Windows only; callers check sys.platform


def show_in_folder(path: Path) -> None:
    # Separate "/select," and path arguments: Explorer handles spaces and commas in the path this way.
    subprocess.Popen(["explorer", "/select,", str(path)])


def desktop_supported() -> bool:
    return sys.platform == "win32"
