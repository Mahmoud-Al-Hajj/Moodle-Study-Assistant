"""Stage 3: download what data/manifest.json lists. Called from scrape.py.

What happens per item (details in .claude/skills/moodle-scraper/SKILL.md):
  resource     ?redirect=1 -> the file (fallback: file embedded in the resource page)
  inline_file  the pluginfile.php URL directly
  folder       every file listed on the folder page, keeping subfolders
  assign       the teacher's instructions as Markdown, plus attached files
  page         the page content as HTML
  url          the real target address, collected in <course>/links.md
  anything else is skipped; "unavailable" items are never requested.

Requests go one at a time through the shared Throttle. The manifest is saved
after every item, and files are written as .part then renamed, so an
interrupted run loses nothing and a rerun continues where it stopped.
"""

import hashlib
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

from playwright.sync_api import Error as PlaywrightError

import moodle_selectors as SEL
from common import (DEBUG_DIR, GENERATED_FILES, ROOT, SessionExpired,
                    course_dir, goto, is_logged_in, log, sanitize_name,
                    section_dir, write_bytes, write_text)

REQUEST_TIMEOUT_MS = 120_000
EXPIRED_MESSAGE = ("Your Moodle session expired during the download. Progress so far is saved. "
                   "Run:  python login.py   then  python scrape.py  to continue.")

FIRST_URL_JS = r"""(list) => {
  for (const s of list) for (const el of document.querySelectorAll(s)) {
    const u = el.getAttribute('data') || el.getAttribute('src') || el.getAttribute('href');
    if (u) return new URL(u, location.href).href;
  }
  return '';
}"""
ALL_LINKS_JS = r"""(list) => {
  for (const s of list) {
    const links = [...document.querySelectorAll(s)].map(a => a.href).filter(Boolean);
    if (links.length) return [...new Set(links)];
  }
  return [];
}"""
TEXT_JS = r"""(list) => {
  for (const s of list) { const el = document.querySelector(s); if (el) return el.innerText.trim(); }
  return '';
}"""
HTML_JS = r"""(list) => {
  for (const s of list) { const el = document.querySelector(s); if (el) return el.innerHTML; }
  return '';
}"""
EXTERNAL_LINK_JS = r"""(list) => {
  for (const s of list) for (const a of document.querySelectorAll(s)) {
    try { if (a.href && new URL(a.href).host !== location.host) return a.href; } catch (e) {}
  }
  return '';
}"""


class ItemFailed(Exception):
    """This item can't be downloaded; record it as failed and carry on."""


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def with_query(url: str, extra: str) -> str:
    return url + ("&" if "?" in url else "?") + extra


def safe_filename(name: str, fallback: str = "file") -> str:
    """sanitize_name for files: keeps the extension intact."""
    stem, dot, ext = name.rpartition(".")
    if not dot or not stem or len(ext) > 10:
        stem, ext = name, ""
    stem = sanitize_name(stem, max_len=100, fallback=fallback)
    ext = re.sub(r'[<>:"/\\|?*\x00-\x1f\s]', "", ext)
    return f"{stem}.{ext}" if ext else stem


class Downloader:
    def __init__(self, context, cfg, manifest: dict, throttle):
        self.context = context
        self.cfg = cfg
        self.manifest = manifest
        self.throttle = throttle
        self._page = None
        # Local path (lower-case: Windows is case-insensitive) -> id of the item that owns it.
        self.claimed: dict[str, str] = {}
        for it in manifest["items"]:
            if it["status"] == "downloaded":
                for p in [it["local_path"], *it.get("files", [])]:
                    if p and it["type"] != "url":
                        self.claimed.setdefault(p.lower(), it["id"])

    # --- requests ---------------------------------------------------------------

    @property
    def page(self):
        if self._page is None or self._page.is_closed():
            self._page = self.context.new_page()
        return self._page

    def _is_login(self, url: str) -> bool:
        u = urlparse(url)
        return u.netloc.lower() == self.cfg.host and "/login/" in u.path

    def get(self, url: str, follow: bool = True):
        """GET with the session cookies. Raises SessionExpired if Moodle sends us to the login page."""
        self.throttle.wait()
        log.debug("GET %s", url)
        try:
            resp = self.context.request.get(url, max_redirects=20 if follow else 0, timeout=REQUEST_TIMEOUT_MS)
        except PlaywrightError as e:
            raise ItemFailed(f"network error: {e.message.strip().splitlines()[0]}")
        location = urljoin(url, resp.headers.get("location", ""))
        if self._is_login(resp.url) or (300 <= resp.status < 400 and self._is_login(location)):
            raise SessionExpired(EXPIRED_MESSAGE)
        if resp.status >= 400:
            raise ItemFailed(f"HTTP {resp.status} for {resp.url}")
        return resp

    def open(self, url: str):
        """Load a Moodle page in the browser and check we're still logged in."""
        resp = goto(self.page, url, self.throttle)
        if not is_logged_in(self.page, self.cfg):
            raise SessionExpired(EXPIRED_MESSAGE)
        if resp is not None and resp.status >= 400:
            raise ItemFailed(f"HTTP {resp.status} for {resp.url}")
        return self.page

    @staticmethod
    def is_web_page(resp) -> bool:
        """A Moodle HTML page rather than a file (an uploaded .html file still comes from pluginfile.php)."""
        return resp.headers.get("content-type", "").startswith("text/html") and "/pluginfile.php/" not in resp.url

    @staticmethod
    def filename(resp) -> str:
        """Original filename: from the pluginfile URL, else Content-Disposition, else the URL."""
        path = urlparse(resp.url).path
        if "/pluginfile.php/" in path:
            return unquote(path.rsplit("/", 1)[-1])
        cd = resp.headers.get("content-disposition", "")
        m = re.search(r"filename\*\s*=\s*[\w-]+''([^;]+)", cd, re.I)
        if m:
            return unquote(m.group(1).strip().strip('"'))
        m = re.search(r'filename\s*=\s*"([^"]+)"', cd, re.I) or re.search(r"filename\s*=\s*([^;]+)", cd, re.I)
        if m:
            name = m.group(1).strip()
            try:
                return name.encode("latin-1").decode("utf-8")  # raw UTF-8 bytes in the header
            except (UnicodeEncodeError, UnicodeDecodeError):
                return name
        return unquote(path.rsplit("/", 1)[-1]) or "file"

    # --- local paths ------------------------------------------------------------

    def claim(self, path: Path, item: dict) -> Path:
        """Reserve a path for this item. If another item already owns it, add ' (cm<id>)' (deterministic)."""
        key = rel(path).lower()
        owner = self.claimed.get(key)
        if owner is not None and owner != item["id"]:
            tag = item["id"].replace("cm:", "cm") if item["id"].startswith("cm:") else \
                "f" + hashlib.sha1(item["id"].encode()).hexdigest()[:6]
            path = path.with_name(f"{path.stem} ({tag}){path.suffix}")
            key = rel(path).lower()
        self.claimed[key] = item["id"]
        return path

    def save_response(self, resp, folder: Path, item: dict) -> Path:
        path = self.claim(folder / safe_filename(self.filename(resp)), item)
        write_bytes(path, resp.body())
        return path

    # --- per-type handlers: each fills local_path/files/target_url/note -----------

    def resource(self, item: dict) -> None:
        resp = self.get(with_query(item["url"], "redirect=1"))
        if self.is_web_page(resp):
            # Embedded-viewer style page: find the file on it.
            page = self.open(item["url"])
            file_url = page.evaluate(FIRST_URL_JS, SEL.RESOURCE["file_element"])
            if not file_url:
                raise ItemFailed(self.debug_failure(item, "no file found on the resource page"))
            resp = self.get(file_url)
            if self.is_web_page(resp):
                raise ItemFailed("the resource's file link returned a web page, not a file")
        item["local_path"] = rel(self.save_response(resp, section_dir(self.manifest, item), item))

    def inline_file(self, item: dict) -> None:
        resp = self.get(item["url"])
        if self.is_web_page(resp):
            raise ItemFailed("Moodle returned a web page instead of the file")
        item["local_path"] = rel(self.save_response(resp, section_dir(self.manifest, item), item))

    def folder(self, item: dict) -> None:
        page = self.open(item["url"])
        links = page.evaluate(ALL_LINKS_JS, SEL.FOLDER["file_link"])
        if not links:
            raise ItemFailed(self.debug_failure(item, "no files found on the folder page"))
        base = section_dir(self.manifest, item) / sanitize_name(item["title"], max_len=60, fallback="folder")
        files = []
        for url in links:
            m = re.search(SEL.PATTERNS["folder_file_subpath"], urlparse(url).path)
            parts = [unquote(p) for p in (m.group(1) if m else urlparse(url).path.rsplit("/", 1)[-1]).split("/") if p]
            dest = base.joinpath(*[sanitize_name(p, max_len=60) for p in parts[:-1]], safe_filename(parts[-1]))
            dest = self.claim(dest, item)
            if not dest.exists():  # a rerun after a partly failed folder only fetches what's missing
                write_bytes(dest, self.get(url).body())
            files.append(rel(dest))
        item["local_path"], item["files"] = rel(base), files

    def assign(self, item: dict) -> None:
        page = self.open(item["url"])
        text = page.evaluate(TEXT_JS, SEL.ASSIGN["instructions"])
        dates = page.evaluate(TEXT_JS, SEL.ASSIGN["dates"])
        attachments = page.evaluate(ALL_LINKS_JS, SEL.ASSIGN["attachment_link"])

        folder = section_dir(self.manifest, item)
        saved = [self.save_response(self.get(url), folder, item) for url in attachments]
        md = self.claim(folder / f"{sanitize_name(item['title'], max_len=80)} - instructions.md", item)
        lines = [f"# {item['title']}", "", f"Source: {item['url']}  ", f"Section: {item['section_name']}", ""]
        if dates:
            lines += [dates, ""]
        lines += [text or "(No instructions text on the assignment page.)", ""]
        if saved:
            lines += ["## Attached files", ""] + [f"- {p.name}" for p in saved] + [""]
        write_text(md, "\n".join(lines))
        item["local_path"], item["files"] = rel(md), [rel(md)] + [rel(p) for p in saved]
        item["note"] = "" if text else "No instructions text found on the assignment page."

    def page_item(self, item: dict) -> None:
        page = self.open(item["url"])
        content = page.evaluate(HTML_JS, SEL.PAGE["content"])
        if not content:
            raise ItemFailed(self.debug_failure(item, "no content found on the page"))
        path = self.claim(section_dir(self.manifest, item) / f"{sanitize_name(item['title'], max_len=100)}.html", item)
        write_text(path, f'<!doctype html><meta charset="utf-8"><title>{item["title"]}</title>\n'
                         f'<!-- Source: {item["url"]} -->\n{content}\n')
        item["local_path"] = rel(path)

    def url(self, item: dict) -> None:
        resp = self.get(with_query(item["url"], "redirect=1"), follow=False)
        target = ""
        if 300 <= resp.status < 400 and resp.headers.get("location"):
            target = urljoin(item["url"], resp.headers["location"])
        else:
            page = self.open(item["url"])
            target = page.evaluate(EXTERNAL_LINK_JS, SEL.URL["external_link"])
        if not target:
            raise ItemFailed(self.debug_failure(item, "couldn't find where the link points"))
        item["target_url"] = target
        item["local_path"] = rel(course_dir(self.manifest) / "links.md")

    def debug_failure(self, item: dict, reason: str) -> str:
        """Save the current page for selector fixing and return the failure message."""
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        path = DEBUG_DIR / f"{item['module']}_{item['id'].replace(':', '')}.html"
        try:
            path.write_text(self.page.content(), encoding="utf-8")
            return f"{reason} (page saved to {rel(path)}; share it so moodle_selectors.py can be fixed)"
        except PlaywrightError:
            return reason

    HANDLERS = {"resource": resource, "inline_file": inline_file, "folder": folder,
                "assign": assign, "page": page_item, "url": url}

    # --- bookkeeping --------------------------------------------------------------

    def is_done(self, item: dict) -> bool:
        if item["status"] != "downloaded":
            return False
        if item["type"] == "url":
            return bool(item.get("target_url"))
        paths = [item["local_path"], *item.get("files", [])]
        return all(p and (ROOT / p).exists() for p in paths)

    def write_links(self) -> Path | None:
        links = [it for it in self.manifest["items"] if it["type"] == "url" and it.get("target_url")]
        if not links:
            return None
        esc = lambda s: s.replace("[", "\\[").replace("]", "\\]")
        lines = [f"# Links: {self.manifest['course_name']}", "",
                 "External links from the course page. Regenerated by scrape.py on every run.", ""]
        current = None
        for it in links:
            if it["section_number"] != current:
                current = it["section_number"]
                lines += ["", f"## {current:02d} {it['section_name']}", ""]
            lines.append(f"- [{esc(it['title'])}]({it['target_url']})  ([Moodle]({it['url']}))")
        path = course_dir(self.manifest) / "links.md"
        write_text(path, "\n".join(lines) + "\n")
        return path


def download_all(context, cfg, manifest: dict, throttle, save) -> dict[str, list[dict]]:
    """Download every pending/failed item. Calls save(manifest) after each item."""
    d = Downloader(context, cfg, manifest, throttle)
    for stale in course_dir(manifest).rglob("*.part"):
        stale.unlink()
    results: dict[str, list[dict]] = {k: [] for k in ("new", "present", "skipped", "unavailable", "failed")}
    items = manifest["items"]
    todo = [it for it in items if it["status"] != "unavailable" and it["module"] in d.HANDLERS and not d.is_done(it)]
    log.info("Downloading %d item(s) into %s", len(todo), rel(course_dir(manifest)))

    try:
        n = 0
        for item in items:
            if item["status"] == "unavailable":
                results["unavailable"].append(item)
                continue
            handler = d.HANDLERS.get(item["module"])
            if handler is None:
                item.update(status="skipped", local_path="", note=f"{item['module']}: nothing to download (open it in Moodle)")
                results["skipped"].append(item)
                continue
            if d.is_done(item):
                results["present"].append(item)
                continue
            n += 1
            log.info("[%d/%d] %s: %s", n, len(todo), item["module"], item["title"])
            item.update(note="", files=[], target_url="", local_path="")
            try:
                handler(d, item)
                item["status"] = "downloaded"
                results["new"].append(item)
            except (ItemFailed, PlaywrightError) as e:
                msg = str(e) if isinstance(e, ItemFailed) else e.message.strip().splitlines()[0]
                item.update(status="failed", note=msg)
                results["failed"].append(item)
                log.warning("  failed: %s", msg)
            save(manifest)
    finally:
        d.write_links()
        save(manifest)
    return results


def files_on_disk(manifest: dict) -> int:
    """Course files on disk, not counting the files the tool generates itself (links.md, index.html)."""
    root = course_dir(manifest)
    if not root.exists():
        return 0
    return sum(1 for p in root.rglob("*") if p.is_file() and not (p.parent == root and p.name in GENERATED_FILES))
