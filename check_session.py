"""Stage 1: check whether the saved Moodle session (auth/state.json) still works.

Opens your dashboard headlessly with the saved session and reports whether
Moodle still treats you as logged in.

    python check_session.py

Exit codes: 0 valid, 2 missing or expired (rerun login.py).
"""

from playwright.sync_api import sync_playwright

from common import (SessionExpired, base_parser, goto, is_logged_in,
                    load_config, log, new_session_context, run, where)


def check(cfg) -> tuple[bool, str]:
    """Open the dashboard with the saved session. Returns (logged in?, URL the browser landed on).

    Raises SessionExpired only when there is no usable session file.
    """
    dashboard = cfg.url("/my/")
    with sync_playwright() as p:
        browser, context = new_session_context(p)
        try:
            page = context.new_page()
            log.info("Opening %s with the saved session", dashboard)
            goto(page, dashboard)
            return is_logged_in(page, cfg), where(page)
        finally:
            browser.close()


def main(args) -> int:
    cfg = load_config(require_course=False)
    ok, landed = check(cfg)
    if not ok:
        raise SessionExpired(f"Session is NOT valid (Moodle sent the browser to {landed}). Run:  python login.py")
    log.info("Session is valid: you are logged in to %s", cfg.host)
    return 0


if __name__ == "__main__":
    run(main, base_parser("Check whether the saved Moodle session is still valid.").parse_args())
