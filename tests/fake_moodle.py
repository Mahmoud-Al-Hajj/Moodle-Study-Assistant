"""A tiny fake Moodle site for testing login.py, check_session.py and scrape.py.

Serves the HTML in tests/fixtures/ under a /moodle prefix (like the real site),
replacing __BASE__ in each fixture with that prefix. The session cookie decides
who you are:

    MoodleSession=good   logged-in student
    MoodleSession=guest  guest (should count as NOT logged in)
    anything else        redirected to /moodle/login/index.php

To add a real page you saved: put it in fixtures/, replace the site URL
(https://haigmoodle.haigazian.edu.lb/moodle) with __BASE__, and add a route below.
"""

import http.server
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "/moodle"

# (path, ?id=) -> fixture file. Course ids: 100 Boost 4.x, 200 Classic 3.x,
# 300 one-section-per-page, 400 unknown theme, 500 stray links, 999 error page.
ROUTES = {
    ("/my/", ""): "dashboard.html",
    ("/course/view.php", "100"): "course_boost.html",
    ("/course/resources.php", "100"): "resources_100.html",
    ("/course/section.php", "903"): "section_903.html",
    ("/course/view.php", "200"): "course_classic.html",
    ("/course/view.php", "300"): "course_onepage.html",
    ("/course/view.php", "400"): "course_custom_theme.html",
    ("/course/view.php", "500"): "course_stray_links.html",
    ("/course/view.php", "999"): "error_no_course.html",
    ("/enrol/index.php", "600"): "enrol.html",
}
REDIRECTS = {("/course/view.php", "600"): "/enrol/index.php?id=600"}

# Shown on the login page when auto_login is on: plays the user typing their credentials.
AUTO_LOGIN_JS = ("<script>setTimeout(() => { document.cookie = 'MoodleSession=good; path=/';"
                 f" location.href = '{BASE}/my/'; }}, 3000)</script>")


class Handler(http.server.BaseHTTPRequestHandler):
    auto_login = False
    requests: list[str] = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        Handler.requests.append(self.path)
        u = urlparse(self.path)
        if not u.path.startswith(BASE + "/"):
            return self.status(404)
        path = u.path[len(BASE):]
        q = parse_qs(u.query)
        cid = q.get("id", [""])[0]

        if path.startswith("/login/"):
            html = self.fixture("login.html")
            if Handler.auto_login:
                html = html.replace("</body>", AUTO_LOGIN_JS + "</body>")
            return self.html(html)

        cookie = self.headers.get("Cookie") or ""
        if "MoodleSession=guest" in cookie:
            return self.html(self.fixture("guest.html"))
        if "MoodleSession=good" not in cookie:
            return self.redirect("/login/index.php")

        if path == "/course/view.php" and cid == "300" and "section" in q:
            return self.html(self.fixture(f"onepage_section{q['section'][0]}.html"))
        if (path, cid) in REDIRECTS:
            return self.redirect(REDIRECTS[(path, cid)])
        name = ROUTES.get((path, cid))
        if not name:
            return self.status(404)
        self.html(self.fixture(name))

    def fixture(self, name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8").replace("__BASE__", BASE)

    def html(self, text: str):
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, path: str):
        self.send_response(303)
        self.send_header("Location", BASE + path)
        self.end_headers()

    def status(self, code: int):
        self.send_response(code)
        self.end_headers()


def start() -> tuple[http.server.ThreadingHTTPServer, str]:
    """Start the server on a free port in a background thread. Returns (server, site root URL)."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}{BASE}"


if __name__ == "__main__":
    srv, url = start()
    print(f"Fake Moodle running at {url}  (Ctrl+C to stop)")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.shutdown()
