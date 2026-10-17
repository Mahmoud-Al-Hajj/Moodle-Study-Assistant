"""Stages 2 and 3: crawl one course, write data/manifest.json, download everything.

Opens {MOODLE_URL}/course/view.php?id=<COURSE_ID> with the session saved by
login.py, walks every section, and records each item with its section, title,
type, URL and status. Then downloads the material into downloads/<course>/
(downloader.py). Reruns only fetch what is missing.

    python scrape.py                 # crawl + download COURSE_ID from .env
    python scrape.py --no-download   # crawl and write the manifest only
    python scrape.py --course 5678   # another course
    python scrape.py --save-html     # also save the course page to data/debug/course_page.html
    python scrape.py --headed        # watch the browser while it works

Manifest format and rerun rules: .claude/skills/moodle-scraper/SKILL.md
Exit codes: 0 ok (warnings may be printed), 1 error, 2 session expired.
"""

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

import moodle_selectors as SEL
from common import (DATA_DIR, DEBUG_DIR, MANIFEST_FILE, ROOT, ConfigError,
                    SessionExpired, Throttle, base_parser, course_dir, goto,
                    is_logged_in, load_config, log, new_session_context, run,
                    write_json_atomic)
from downloader import download_all, files_on_disk

# Statuses written by Stage 3; a recrawl keeps them (with local_path and note).
SETTLED_STATUSES = {"downloaded", "failed", "skipped"}

# Runs inside the page. All selectors and patterns come from moodle_selectors.py.
PARSE_COURSE_JS = r"""
({ sel, pat, courseId }) => {
  const root = sel.main_region.map(s => document.querySelector(s)).find(Boolean) || document.body;
  const squash = s => (s || '').replace(/\s+/g, ' ').trim();
  const cleanText = el => {
    if (!el) return '';
    const c = el.cloneNode(true);
    c.querySelectorAll(sel.hidden_text).forEach(n => n.remove());
    return squash(c.textContent);
  };
  const activityRe = new RegExp(pat.activity_url, 'i');
  const activityIdRe = new RegExp(pat.activity_id_attr);
  const moduleClassRe = new RegExp(pat.module_class, 'i');
  const sectionIdRe = new RegExp(pat.section_id_attr);
  const sectionLinkRe = new RegExp(pat.section_page_url.replace('{course_id}', courseId));
  const outermost = els => els.filter(el => !els.some(o => o !== el && o.contains(el)));
  // For priority lists: the first selector that matches anything inside `scope` wins.
  const firstOf = (scope, list) => list.map(s => scope.querySelector(s)).find(Boolean) || null;

  const seenCm = new Set();
  const seenFiles = new Set();

  const fileTitle = a => {
    const t = cleanText(a);
    if (t) return t;
    try { return decodeURIComponent(new URL(a.href).pathname.split('/').pop()); } catch (e) { return a.href; }
  };

  // Direct file links (labels, section summaries, activity descriptions).
  const collectFiles = (scope, items, skipInside) => {
    scope.querySelectorAll(sel.inline_file_link).forEach(a => {
      if (skipInside && a.closest(skipInside)) return;
      const url = a.href.split('#')[0];
      const key = url.split('?')[0];
      if (seenFiles.has(key)) return;
      seenFiles.add(key);
      items.push({ cmid: null, module: 'inline_file', title: fileTitle(a), url, available: true, note: '' });
    });
  };

  const parseActivity = el => {
    const out = [];
    const idm = (el.id || '').match(activityIdRe);
    let cmid = idm ? idm[1] : (el.dataset.id || null);
    const cm = (el.className || '').match(moduleClassRe);
    let module = cm ? cm[1].toLowerCase() : null;

    if (module === 'subsection') return out;   // its activities are parsed on their own
    if (module === 'label') { collectFiles(el, out, null); return out; }

    const a = Array.from(el.querySelectorAll('a[href]')).find(x => activityRe.test(x.href));
    if (a) {
      const m = a.href.match(activityRe);
      module = m[1].toLowerCase();             // the URL decides the type
      cmid = cmid || m[2];
    }
    if (!cmid || seenCm.has(cmid)) return out;
    seenCm.add(cmid);

    const holder = el.querySelector(sel.activity_name_attr_holder);
    const title = cleanText(firstOf(el, sel.activity_name))
      || (holder && squash(holder.dataset.activityname)) || cleanText(a) || ('Item ' + cmid);
    const restriction = squash((el.querySelector(sel.restriction_info) || {}).textContent);
    out.push({
      cmid, module: module || 'unknown', title,
      url: a ? a.href.split('#')[0] : '',
      available: !!a,
      note: a ? '' : (restriction || 'Restricted: no link on the course page'),
    });
    if (module !== 'resource') collectFiles(el, out, null);
    return out;
  };

  const sectionInfo = (el, idx) => {
    let number = el.dataset.number ?? el.dataset.sectionnumber;
    if (number == null) {
      const m = (el.id || '').match(sectionIdRe);
      number = m ? m[1] : (el.dataset.sectionid ?? idx);
    }
    number = parseInt(number, 10);
    if (Number.isNaN(number)) number = idx;
    return { number, name: cleanText(firstOf(el, sel.section_name)) || el.getAttribute('aria-label') || '' };
  };

  const sectionEls = outermost(Array.from(root.querySelectorAll(sel.section)));
  const sections = [];
  const sectionLinks = [];

  sectionEls.forEach((el, idx) => {
    const info = sectionInfo(el, idx);
    const items = [];
    let acts = Array.from(el.querySelectorAll(sel.activity));
    // Keep activities nested in a subsection; drop any other nested match.
    const moduleOf = o => ((o.className || '').match(moduleClassRe) || [])[1];
    acts = acts.filter(a => !acts.some(o => o !== a && o.contains(a) && moduleOf(o) !== 'subsection'));
    acts.forEach(act => items.push(...parseActivity(act)));
    collectFiles(el, items, sel.activity);    // files in the section summary
    el.querySelectorAll('a[href]').forEach(a => {
      if (sectionLinkRe.test(a.href)) sectionLinks.push({ url: a.href.split('#')[0], number: info.number, empty: acts.length === 0 });
    });
    sections.push({ ...info, items });
  });

  // Activity links the selectors could not place in a section: reported, never guessed.
  const unmatched = [];
  root.querySelectorAll('a[href]').forEach(a => {
    const m = a.href.match(activityRe);
    if (!m || seenCm.has(m[2]) || m[1] === 'subsection' || a.closest(sel.not_content)) return;
    seenCm.add(m[2]);
    unmatched.push({ cmid: m[2], module: m[1].toLowerCase(), title: cleanText(a), url: a.href.split('#')[0] });
  });

  const err = document.querySelector(sel.error_box);
  return {
    courseName: cleanText(document.querySelector(sel.course_title)) || squash(document.title.split(/[:|]/)[0]),
    errorText: err ? cleanText(err) : '',
    sections, sectionLinks, unmatched,
  };
}
"""

# /course/resources.php: Moodle core's plain list of resource-type activities,
# used only to report items the course page crawl did not find.
PARSE_RESOURCE_INDEX_JS = r"""
({ sel, pat }) => {
  const activityRe = new RegExp(pat.activity_url, 'i');
  const out = [];
  document.querySelectorAll(sel.rows).forEach(tr => {
    if (tr.querySelector(sel.header_cell) || tr.parentElement.tagName === 'THEAD') return;
    tr.querySelectorAll('a[href]').forEach(a => {
      const m = a.href.match(activityRe);
      if (m) out.push({ cmid: m[2], module: m[1].toLowerCase(), title: a.textContent.replace(/\s+/g, ' ').trim() });
    });
  });
  return out;
}
"""


class CourseCrawl:
    """Sections and items in page order, de-duplicated across pages by id."""

    def __init__(self):
        self.course_name = ""
        self.sections: dict[int, dict] = {}
        self.ids: set[str] = set()
        self.unmatched: list[dict] = []

    def section(self, number: int, name: str) -> dict:
        if number not in self.sections:
            self.sections[number] = {"number": number, "name": name, "items": []}
        elif name and not self.sections[number]["name"]:
            self.sections[number]["name"] = name
        return self.sections[number]

    def merge_page(self, parsed: dict) -> None:
        self.course_name = self.course_name or parsed["courseName"]
        for sec in parsed["sections"]:
            target = self.section(sec["number"], sec["name"])
            for item in sec["items"]:
                item_id = f"cm:{item['cmid']}" if item["cmid"] else f"file:{item['url'].split('?')[0]}"
                if item_id not in self.ids:
                    self.ids.add(item_id)
                    target["items"].append({"id": item_id, **item})
        self.unmatched.extend(parsed["unmatched"])

    def unplaced(self) -> list[dict]:
        """Unmatched links not found as a proper item on any page, de-duplicated."""
        out, seen = [], set()
        for link in self.unmatched:
            key = f"cm:{link['cmid']}"
            if key not in self.ids and key not in seen:
                seen.add(key)
                out.append(link)
        return out

    def item_count(self) -> int:
        return sum(len(s["items"]) for s in self.sections.values())


def evaluate(page, script: str, **extra):
    return page.evaluate(script, {"sel": SEL.COURSE, "pat": SEL.PATTERNS, **extra})


def save_debug_html(html: str, name: str = "course_page.html") -> Path:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    path = DEBUG_DIR / name
    path.write_text(html, encoding="utf-8")
    return path


def open_course_page(page, cfg, url: str, throttle: Throttle) -> None:
    response = goto(page, url, throttle)
    if not is_logged_in(page, cfg):
        raise SessionExpired("Your Moodle session has expired. Run:  python login.py")
    if "/enrol/" in urlparse(page.url).path:
        raise ConfigError(f"Moodle sent you to the enrolment page for course {cfg.course_id}. "
                          "Check COURSE_ID and that you are enrolled in this course.")
    if response is not None and response.status >= 500:
        raise ConfigError(f"Moodle returned an error ({response.status}) for {url}. Try again later.")


def crawl(page, cfg, throttle: Throttle, save_html: bool) -> tuple[CourseCrawl, list[str]]:
    warnings: list[str] = []
    result = CourseCrawl()
    course_url = cfg.url(f"/course/view.php?id={cfg.course_id}")

    log.info("Opening %s", course_url)
    open_course_page(page, cfg, course_url, throttle)
    course_html = page.content()
    debug_path = save_debug_html(course_html) if save_html else None
    if debug_path:
        log.info("Saved course page HTML to %s", debug_path.relative_to(ROOT))

    parsed = evaluate(page, PARSE_COURSE_JS, courseId=cfg.course_id)
    if not parsed["sections"]:
        if parsed["errorText"]:
            raise ConfigError(f"Moodle says: {parsed['errorText']}  (check COURSE_ID={cfg.course_id})")
        debug_path = save_debug_html(course_html)
        raise ConfigError("No course sections matched the selectors in moodle_selectors.py, so nothing was "
                          f"recorded. Page saved to {debug_path.relative_to(ROOT)}; share that file so the "
                          "selectors can be fixed.")
    result.merge_page(parsed)
    log.info("Found %d sections on the course page", len(parsed["sections"]))

    # "One section per page" courses (and some empty sections) only show a link; open those.
    to_visit = {}
    for link in parsed["sectionLinks"]:
        if link["empty"]:
            to_visit.setdefault(link["url"], link["number"])
    if to_visit:
        log.info("Opening %d section page(s) that showed no items on the course page", len(to_visit))
    for url, number in to_visit.items():
        try:
            open_course_page(page, cfg, url, throttle)
            sub = evaluate(page, PARSE_COURSE_JS, courseId=cfg.course_id)
            if not sub["sections"]:
                path = save_debug_html(page.content(), f"section_page_{number}.html")
                warnings.append(f"Section page {number} matched no sections; saved it to {path.relative_to(ROOT)}.")
                continue
            result.merge_page(sub)
        except PlaywrightError as e:
            warnings.append(f"Could not read section page {url}: {e.message.splitlines()[0]}")

    unplaced = result.unplaced()
    if unplaced:
        path = save_debug_html(course_html)
        names = "; ".join(f"{u['title'] or '(no title)'} [{u['module']}]" for u in unplaced[:10])
        warnings.append(f"{len(unplaced)} activity link(s) were outside any recognised section/activity and "
                        f"were NOT added: {names}. Page saved to {path.relative_to(ROOT)}; share it so "
                        "moodle_selectors.py can be fixed.")

    # Report-only cross-check against Moodle's own resource list.
    try:
        goto(page, cfg.url(f"/course/resources.php?id={cfg.course_id}"), throttle)
        if is_logged_in(page, cfg):
            rows = page.evaluate(PARSE_RESOURCE_INDEX_JS, {"sel": SEL.RESOURCE_INDEX, "pat": SEL.PATTERNS})
            missing = [r for r in rows if f"cm:{r['cmid']}" not in result.ids and r["module"] not in SEL.IGNORED_MODULES]
            log.info("Cross-checked with the course resource index (%d entries)", len(rows))
            if missing:
                path = save_debug_html(course_html)
                names = "; ".join(f"{r['title']} [{r['module']}]" for r in missing[:10])
                warnings.append(f"{len(missing)} item(s) are in Moodle's resource index but not on the course page, "
                                f"and were NOT added: {names}. Usually the teacher hid them from the course page; "
                                f"if you can see them there, share {path.relative_to(ROOT)}.")
    except PlaywrightError as e:
        warnings.append(f"Skipped the resource index cross-check: {e.message.splitlines()[0]}")

    if result.item_count() == 0 and not unplaced:
        warnings.append("The course page has sections but no items. If you see items in the browser, rerun with "
                        "--save-html and share data/debug/course_page.html.")
    return result, warnings


def to_type(module: str) -> str:
    return module if module in SEL.KNOWN_TYPES else "other"


def load_previous(course_id: str) -> dict | None:
    """Return the earlier manifest for this course (current or parked), parking another course's manifest."""
    parked = DATA_DIR / f"manifest-course-{course_id}.json"
    if MANIFEST_FILE.exists():
        try:
            current = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("Existing %s is unreadable; starting a fresh one.", MANIFEST_FILE.relative_to(ROOT))
            current = None
        if current and str(current.get("course_id")) == str(course_id):
            return current
        if current:
            other = DATA_DIR / f"manifest-course-{current.get('course_id')}.json"
            MANIFEST_FILE.replace(other)
            log.info("Kept the previous course's manifest as %s", other.relative_to(ROOT))
    if parked.exists():
        try:
            log.info("Restoring earlier progress for this course from %s", parked.relative_to(ROOT))
            return json.loads(parked.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("%s is unreadable; ignoring it.", parked.relative_to(ROOT))
    return None


def build_manifest(result: CourseCrawl, cfg, previous: dict | None) -> dict:
    old_items = {it["id"]: it for it in (previous or {}).get("items", []) if "id" in it}
    sections, items = [], []
    for number in sorted(result.sections):
        sec = result.sections[number]
        name = sec["name"] or ("General" if number == 0 else f"Section {number}")
        kept = [it for it in sec["items"] if it["module"] not in SEL.IGNORED_MODULES]
        sections.append({"section_number": number, "section_name": name, "item_count": len(kept)})
        for it in kept:
            old = old_items.get(it["id"], {})
            settled = old.get("status") in SETTLED_STATUSES
            if not it["available"]:
                status, note = "unavailable", it["note"]
            elif settled:
                status, note = old["status"], old.get("note", "")
            else:
                status, note = "pending", it["note"]
            items.append({
                "section_number": number,
                "section_name": name,
                "title": it["title"],
                "type": to_type(it["module"]),
                "url": it["url"],
                "local_path": old.get("local_path", "") if settled else "",
                "status": status,
                "id": it["id"],
                "module": it["module"],
                "note": note,
                "files": old.get("files", []) if settled else [],
                "target_url": old.get("target_url", "") if settled else "",
            })
    return {
        "moodle_url": cfg.moodle_url,
        "course_id": cfg.course_id,
        "course_name": result.course_name or f"Course {cfg.course_id}",
        "crawled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sections": sections,
        "items": items,
    }




def print_summary(manifest: dict, warnings: list[str]) -> None:
    items = manifest["items"]
    print()
    print(f"Course: {manifest['course_name']}  (id {manifest['course_id']})")
    print(f"Total items: {len(items)}")
    print()
    print("By type:")
    for t, n in Counter(it["type"] for it in items).most_common():
        print(f"  {t:<10} {n:>4}")
    print()
    print("By section:")
    per_section: dict[int, Counter] = {}
    for it in items:
        per_section.setdefault(it["section_number"], Counter())[it["type"]] += 1
    for sec in manifest["sections"]:
        counts = per_section.get(sec["section_number"], Counter())
        detail = ", ".join(f"{t} {n}" for t, n in counts.most_common()) or "empty"
        print(f"  {sec['section_number']:>2}  {sec['section_name'][:40]:<40} {sum(counts.values()):>4}   ({detail})")
    print()
    print("Status: " + ", ".join(f"{s} {n}" for s, n in Counter(it["status"] for it in items).most_common()))
    print(f"Manifest: {MANIFEST_FILE.relative_to(ROOT)}")
    for w in warnings:
        print()
        log.warning("%s", w)


def main(args) -> int:
    cfg = load_config(require_course=True, course_override=args.course)
    throttle = Throttle()
    with sync_playwright() as p:
        browser, context = new_session_context(p, headless=not args.headed)
        try:
            result, warnings = crawl(context.new_page(), cfg, throttle, args.save_html)
            manifest = build_manifest(result, cfg, load_previous(cfg.course_id))
            write_json_atomic(MANIFEST_FILE, manifest)
            parked = DATA_DIR / f"manifest-course-{cfg.course_id}.json"
            if parked.exists():
                parked.unlink()  # its progress now lives in manifest.json
            print_summary(manifest, warnings)
            if args.no_download:
                return 0
            print()
            results = download_all(context, cfg, manifest, throttle, lambda m: write_json_atomic(MANIFEST_FILE, m))
        finally:
            browser.close()
    print_download_summary(manifest, results)
    return 0


def print_download_summary(manifest: dict, results: dict[str, list[dict]]) -> None:
    print()
    print(f"Downloads: {course_dir(manifest).relative_to(ROOT)}")
    labels = [("new", "downloaded now"), ("present", "already present"), ("skipped", "skipped"),
              ("unavailable", "unavailable"), ("failed", "failed")]
    for key, label in labels:
        group = results[key]
        detail = ""
        if key == "skipped" and group:
            detail = "   (" + ", ".join(f"{m} {n}" for m, n in Counter(it["module"] for it in group).most_common()) + ")"
        print(f"  {label:<16} {len(group):>4}{detail}")
    for it in results["failed"]:
        print(f"    - {it['title']} [{it['module']}]: {it['note']}")
    links = sum(1 for it in manifest["items"] if it["type"] == "url" and it.get("target_url"))
    print(f"  Files on disk: {files_on_disk(manifest)}" + (f"   (+ links.md with {links} links)" if links else ""))
    if results["failed"]:
        print("Rerun python scrape.py to retry the failed items.")


if __name__ == "__main__":
    parser = base_parser("Crawl a Moodle course, write data/manifest.json and download its material.")
    parser.add_argument("--course", help="course id (overrides COURSE_ID in .env)")
    parser.add_argument("--headed", action="store_true", help="show the browser window")
    parser.add_argument("--no-download", action="store_true", help="crawl and write the manifest only")
    parser.add_argument("--save-html", action="store_true", help="save the course page to data/debug/course_page.html")
    run(main, parser.parse_args())
