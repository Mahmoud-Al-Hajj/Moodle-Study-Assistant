"""Stage 3 on its own: download what data/manifest.json lists, without crawling the course again.

Fetches every item that isn't done yet (pending and failed ones, and files deleted from
disk), exactly as scrape.py does after its crawl. Items are matched by their manifest id,
so reruns never duplicate anything. Used by the web UI's "Retry failed" and Download actions.

    python download.py               # course from .env (must already be scraped)
    python download.py --headed      # watch the browser while it works

Exit codes: 0 ok, 1 error (e.g. course not scraped yet), 2 session expired.
"""

import json

from playwright.sync_api import sync_playwright

from common import (MANIFEST_FILE, ConfigError, Throttle, base_parser,
                    load_config, new_session_context, run, write_json_atomic)
from downloader import download_all
from scrape import print_download_summary


def load_manifest(course_id: str) -> dict:
    try:
        manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest = None
    if not manifest or str(manifest.get("course_id")) != course_id:
        raise ConfigError(f"Course {course_id} hasn't been scraped yet. Run:  python scrape.py")
    return manifest


def main(args) -> int:
    cfg = load_config(require_course=True)
    manifest = load_manifest(cfg.course_id)
    with sync_playwright() as p:
        browser, context = new_session_context(p, headless=not args.headed)
        try:
            results = download_all(context, cfg, manifest, Throttle(),
                                   lambda m: write_json_atomic(MANIFEST_FILE, m))
        finally:
            browser.close()
    print_download_summary(manifest, results)
    return 0


if __name__ == "__main__":
    parser = base_parser("Download the items listed in data/manifest.json (no crawl).")
    parser.add_argument("--headed", action="store_true", help="show the browser window")
    run(main, parser.parse_args())
