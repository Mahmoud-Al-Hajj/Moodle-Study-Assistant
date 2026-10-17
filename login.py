"""Stage 1: log in to Moodle yourself in a visible browser and save the session.

You type your credentials into the browser window. This script never asks for,
sees, stores or logs your password. When your dashboard has loaded, press Enter
in this terminal and the browser's session is saved to auth/state.json for the
other scripts to reuse.

    python login.py
"""

from playwright.sync_api import sync_playwright

from common import (AUTH_DIR, STATE_FILE, ROOT, ConfigError, base_parser, goto,
                    is_logged_in, load_config, log, run, where)


def wait_for_enter(prompt: str) -> None:
    try:
        input(prompt)
    except EOFError:
        raise KeyboardInterrupt  # no terminal input available: treat as cancel


def main(args) -> int:
    cfg = load_config(require_course=False)
    AUTH_DIR.mkdir(exist_ok=True)
    login_url = cfg.url("/login/index.php")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        try:
            context = browser.new_context()
            page = context.new_page()
            log.info("Opening %s in a browser window", login_url)
            goto(page, login_url)

            print()
            print("  1. Log in to Moodle in the browser window.")
            print("  2. Wait until your Moodle dashboard has loaded.")
            print("  3. Come back here and press Enter.")
            print()
            while True:
                wait_for_enter("Press Enter when your dashboard has loaded (Ctrl+C to cancel)... ")
                if not browser.is_connected():
                    raise ConfigError("The browser was closed before the session was saved. Run login.py again.")
                open_pages = [pg for pg in context.pages if not pg.is_closed()]
                if not open_pages:
                    raise ConfigError("The browser window was closed before the session was saved. Run login.py again.")
                # Let Playwright catch up on everything the browser did while we waited for Enter.
                open_pages[0].wait_for_timeout(500)
                # The login may have happened in another tab; any logged-in tab will do.
                page = next((pg for pg in reversed(open_pages) if is_logged_in(pg, cfg)), None)
                if page:
                    break
                log.warning("You don't look logged in yet (browser is on %s).", where(open_pages[-1]))
                print("Finish logging in in the browser, then press Enter again.")

            # Confirm on the dashboard itself before saving.
            goto(page, cfg.url("/my/"))
            if not is_logged_in(page, cfg):
                raise ConfigError("Moodle's dashboard says you are not logged in. Nothing was saved; run login.py again.")
            context.storage_state(path=str(STATE_FILE))
        finally:
            if browser.is_connected():
                browser.close()

    log.info("Logged in. Session saved to %s", STATE_FILE.relative_to(ROOT))
    print("Keep auth/state.json private: it works like a logged-in browser. It is excluded from git.")
    print("Next:  python check_session.py")
    return 0


if __name__ == "__main__":
    run(main, base_parser("Log in to Moodle in a visible browser and save the session.").parse_args())
