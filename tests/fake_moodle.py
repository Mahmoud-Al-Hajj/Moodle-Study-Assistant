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
from urllib.parse import parse_qs, unquote, urlparse

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "/moodle"

# (path, ?id=) -> fixture file. Course ids: 100 Boost 4.x, 200 Classic 3.x,
# 300 one-section-per-page, 400 unknown theme, 500 stray links, 700 download
# edge cases, 800 whole update pipeline, 999 error page.
ROUTES = {
    ("/my/", ""): "dashboard.html",
    ("/course/view.php", "100"): "course_boost.html",
    ("/course/resources.php", "100"): "resources_100.html",
    ("/course/section.php", "903"): "section_903.html",
    ("/course/view.php", "200"): "course_classic.html",
    ("/course/view.php", "300"): "course_onepage.html",
    ("/course/view.php", "400"): "course_custom_theme.html",
    ("/course/view.php", "500"): "course_stray_links.html",
    ("/course/view.php", "700"): "course_downloads.html",
    ("/course/view.php", "800"): "course_update.html",
    ("/course/view.php", "999"): "error_no_course.html",
    # Activity pages (Stage 3)
    ("/mod/folder/view.php", "12"): "folder_12.html",
    ("/mod/assign/view.php", "14"): "assign_14.html",
    ("/mod/page/view.php", "17"): "page_17.html",
    ("/mod/resource/view.php", "71"): "resource_71_embedded.html",
    ("/enrol/index.php", "600"): "enrol.html",
}
REDIRECTS = {("/course/view.php", "600"): "/enrol/index.php?id=600"}

# resource id -> where /mod/resource/view.php?id=X&redirect=1 sends you. Resource 71 has
# no entry: it answers with its embedded-viewer page instead (tests the fallback).
RESOURCE_FILES = {
    "11": "/pluginfile.php/111/mod_resource/content/1/Lecture%201%20slides.pdf",
    "72": "/pluginfile.php/172/mod_resource/content/1/missing.pdf",
    "73": "/pluginfile.php/173/mod_resource/content/1/notes.pdf",
    "74": "/pluginfile.php/174/mod_resource/content/1/notes.pdf",
    "81": "/pluginfile.php/181/mod_resource/content/1/Nietzsche%20notes.docx",
    "82": "/pluginfile.php/182/mod_resource/content/1/Human%20rights.pdf",
}
# url id -> external target of /mod/url/view.php?id=X&redirect=1
URL_TARGETS = {"18": "http://example.org/visualgo", "83": "http://example.org/nietzsche"}
MISSING_FILES = {"/pluginfile.php/172/mod_resource/content/1/missing.pdf"}

# Shown on the login page when auto_login is on: plays the user typing their credentials.
AUTO_LOGIN_JS = ("<script>setTimeout(() => { document.cookie = 'MoodleSession=good; path=/';"
                 f" location.href = '{BASE}/my/'; }}, 3000)</script>")


class Handler(http.server.BaseHTTPRequestHandler):
    auto_login = False
    requests: list[str] = []
    # pluginfile paths that act as if the session expired (redirect to login)
    expire_files: set[str] = set()
    # decoded pluginfile path -> real file bytes (tests that need extractable documents set this)
    real_files: dict[str, bytes] = {}

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

        if path.startswith("/pluginfile.php/"):
            return self.pluginfile(path)
        if q.get("redirect") == ["1"]:
            if path == "/mod/resource/view.php" and cid in RESOURCE_FILES:
                return self.redirect(RESOURCE_FILES[cid])
            if path == "/mod/url/view.php" and cid in URL_TARGETS:
                return self.redirect(URL_TARGETS[cid], absolute=True)
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

    def pluginfile(self, path: str):
        """Serve fake file bytes, like Moodle's pluginfile.php."""
        if path in Handler.expire_files:
            return self.redirect("/login/index.php")
        if path in MISSING_FILES:
            return self.status(404)
        body = Handler.real_files.get(unquote(path)) or f"fake contents of {unquote(path)}".encode("utf-8")
        self.send_response(200)
        ctype = "application/pdf" if path.endswith(".pdf") else "application/octet-stream"
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Disposition", "inline")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, path: str, absolute: bool = False):
        self.send_response(303)
        self.send_header("Location", path if absolute else BASE + path)
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
