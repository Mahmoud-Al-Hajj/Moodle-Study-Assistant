"""API tests: the FastAPI app driving the real CLI scripts against the fake Moodle.

    .venv\\Scripts\\python -m pytest tests\\test_api.py        ($env:SKIP_HEADED=1 skips the visible-browser test)

Each test gets a throwaway copy of the scripts with its own .env, auth/ and data/,
so your real files are never touched.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(Path(__file__).parent))
import fake_moodle  # noqa: E402
from api import files  # noqa: E402
from api.export_openapi import OUT as OPENAPI_FILE, schema_text  # noqa: E402
from api.jobs import parse_line, parse_progress  # noqa: E402
from api.main import create_app  # noqa: E402

SCRIPTS = ["common.py", "moodle_selectors.py", "login.py", "check_session.py", "scrape.py", "downloader.py",
           "download.py"]
BASE = "http://127.0.0.1:8765"
HEADERS = {"X-Moodle-Study": "1"}


@pytest.fixture(scope="module")
def site():
    server, url = fake_moodle.start()
    yield url
    server.shutdown()


@pytest.fixture
def workspace(tmp_path, site):
    fake_moodle.Handler.auto_login = False
    for name in SCRIPTS:
        shutil.copy(PROJECT / name, tmp_path / name)
    (tmp_path / ".env").write_text(f"MOODLE_URL={site}\nCOURSE_ID=100\n", encoding="utf-8")
    set_cookie(tmp_path, "good")
    return tmp_path


@pytest.fixture
def client(workspace):
    with TestClient(create_app(workspace), base_url=BASE) as c:
        yield c


def set_cookie(root: Path, value: str | None) -> None:
    state = root / "auth" / "state.json"
    if value is None:
        state.unlink(missing_ok=True)
        return
    state.parent.mkdir(exist_ok=True)
    state.write_text(json.dumps({"cookies": [{
        "name": "MoodleSession", "value": value, "domain": "127.0.0.1", "path": "/",
        "expires": -1, "httpOnly": True, "secure": False, "sameSite": "Lax"}], "origins": []}))


def post(client, url: str, **kw):
    return client.post(url, headers=HEADERS, **kw)


def wait(client, job: dict, timeout: float = 120) -> dict:
    end = time.monotonic() + timeout
    lines = list(job["lines"])
    while True:
        job = client.get(f"/api/jobs/{job['id']}", params={"after": lines[-1]["seq"] if lines else 0}).json()
        lines += job["lines"]
        if job["state"] != "running":
            job["lines"] = lines
            return job
        assert time.monotonic() < end, "job did not finish in time"
        time.sleep(0.3)


def wait_for_line(client, job: dict, text: str, timeout: float = 60) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        current = client.get(f"/api/jobs/{job['id']}").json()
        if any(text in ln["text"] for ln in current["lines"]):
            return
        time.sleep(0.2)
    raise AssertionError(f"never saw {text!r}")


# --- pure parsing ---

def test_parse_log_and_progress_lines():
    assert parse_line("12:01:02 INFO    Opening http://x/course\n") == [("info", "Opening http://x/course")]
    assert parse_line("12:01:02 WARNING Something odd") == [("warning", "Something odd")]
    assert parse_line("Total items: 12") == [("output", "Total items: 12")]
    assert parse_line("   \n") == []
    # login.py's prompt has no newline, so it arrives glued to the next log line
    assert parse_line("Press Enter when ready... 12:01:02 WARNING You don't look logged in yet.") == [
        ("output", "Press Enter when ready..."), ("warning", "You don't look logged in yet.")]
    assert parse_progress("[3/12] resource: Lecture 1 slides") == (3, 12, "resource: Lecture 1 slides")
    assert parse_progress("Opening x") is None


# --- security ---

def test_only_localhost_and_csrf_header(workspace):
    with TestClient(create_app(workspace), base_url="http://evil.example:8765") as c:
        r = c.get("/api/health")
        assert r.status_code == 400
    with TestClient(create_app(workspace), base_url=BASE) as c:
        assert c.get("/api/health").json() == {"ok": True}
        r = c.post("/api/jobs", json={"action": "scrape"})  # no X-Moodle-Study header
        assert r.status_code == 403
        assert "error" in r.json()
        assert c.get("/api/jobs/current").json() is None  # nothing was started


def test_session_file_is_never_served(client):
    for path in ("/auth/state.json", "/api/../auth/state.json", "/api/auth/state.json", "/api/files/auth/state.json"):
        r = client.get(path)
        assert r.status_code == 404, path
        assert "MoodleSession" not in r.text


def test_unknown_action_and_job(client):
    assert post(client, "/api/jobs", json={"action": "delete_everything"}).status_code == 422
    r = client.get("/api/jobs/nope")
    assert r.status_code == 404
    assert "doesn't exist" in r.json()["error"]


# --- session ---

def test_session_states(client, workspace):
    assert client.get("/api/session").json()["status"] == "unknown"
    job = wait(client, post(client, "/api/session/check").json())
    assert job["state"] == "succeeded", job
    s = client.get("/api/session").json()
    assert s["status"] == "valid" and s["checked_at"]

    set_cookie(workspace, "stale")
    job = wait(client, post(client, "/api/session/check").json())
    assert job["state"] == "session_expired"
    assert "Log in again" in job["message"]
    assert client.get("/api/session").json()["status"] == "expired"

    set_cookie(workspace, None)
    assert client.get("/api/session").json()["status"] == "missing"


# --- scrape ---

def test_scrape_job(client, workspace):
    course = client.get("/api/course").json()
    assert course["configured"] and not course["scraped"]
    assert course["course_url"].endswith("/course/view.php?id=100")

    r = post(client, "/api/jobs", json={"action": "scrape"})
    assert r.status_code == 202
    job = wait(client, r.json())
    assert job["state"] == "succeeded", job
    text = "\n".join(ln["text"] for ln in job["lines"])
    assert "Traceback" not in text
    assert "sections on the course page" in text

    manifest = json.loads((workspace / "data" / "manifest.json").read_text(encoding="utf-8"))
    course = client.get("/api/course").json()
    assert course["scraped"] and course["name"] == manifest["course_name"]
    assert course["items"] == len(manifest["items"])
    assert course["by_status"]["pending"] == sum(1 for it in manifest["items"] if it["status"] == "pending")
    assert not (workspace / "downloads").exists()  # Scrape only crawls; downloading is a separate action

    run = client.get("/api/runs").json()["scrape"]
    assert run["state"] == "succeeded" and run["counts"]["items"] == len(manifest["items"])
    assert client.get("/api/session").json()["status"] == "valid"


def test_scrape_with_expired_session(client, workspace):
    set_cookie(workspace, "stale")
    job = wait(client, post(client, "/api/jobs", json={"action": "scrape"}).json())
    assert job["state"] == "session_expired"
    assert job["exit_code"] == 2
    assert client.get("/api/session").json()["status"] == "expired"
    assert client.get("/api/runs").json()["scrape"]["state"] == "session_expired"


def test_scrape_failure_has_a_friendly_message(client, workspace):
    (workspace / ".env").write_text(f"MOODLE_URL={fake_moodle_url(workspace)}\nCOURSE_ID=999\n", encoding="utf-8")
    job = wait(client, post(client, "/api/jobs", json={"action": "scrape"}).json())
    assert job["state"] == "failed"
    assert "Moodle says" in job["message"]


def fake_moodle_url(workspace: Path) -> str:
    return (workspace / ".env").read_text(encoding="utf-8").split("MOODLE_URL=")[1].split("\n")[0]


def use_course(workspace: Path, course_id: str) -> None:
    (workspace / ".env").write_text(f"MOODLE_URL={fake_moodle_url(workspace)}\nCOURSE_ID={course_id}\n", encoding="utf-8")


# --- download (download.py: no crawl) ---

def test_download_job_fetches_what_the_manifest_lists(client, workspace):
    use_course(workspace, "800")
    assert wait(client, post(client, "/api/jobs", json={"action": "scrape"}).json())["state"] == "succeeded"
    job = wait(client, post(client, "/api/jobs", json={"action": "download"}).json())
    assert job["state"] == "succeeded", job
    text = "\n".join(ln["text"] for ln in job["lines"])
    assert "Traceback" not in text and "downloaded now" in text
    assert job["progress"]["done"] == job["progress"]["total"] > 0

    items = [it for s in client.get("/api/course/items").json()["sections"] for it in s["items"]]
    files = [f for it in items for f in it["files"]]
    assert files and all(f["exists"] and f["path"].startswith("downloads/") for f in files)
    assert client.get("/api/runs").json()["download"]["state"] == "succeeded"
    # nothing left to do: a rerun succeeds without fetching anything
    again = wait(client, post(client, "/api/jobs", json={"action": "download"}).json())
    assert again["state"] == "succeeded" and "downloaded now      0" in "\n".join(ln["text"] for ln in again["lines"])


def test_download_before_scraping_fails_clearly(client):
    job = wait(client, post(client, "/api/jobs", json={"action": "download"}).json())
    assert job["state"] == "failed"
    assert "hasn't been scraped yet" in job["message"]


# --- course content ---

COURSE = "downloads/Test Course"
TEXT = "data/text/Test Course"


def write_course(root: Path) -> None:
    """A small scraped, downloaded and extracted course, written directly (no Moodle needed)."""
    def item(n, title, type_, module, status, local_path="", files=(), note="", target_url=""):
        return {"section_number": n, "section_name": f"Week {n}", "title": title, "type": type_,
                "url": f"https://moodle.example/mod/{module}/view.php?id={len(title)}", "local_path": local_path,
                "status": status, "id": f"cm:{title}", "module": module, "note": note, "files": list(files),
                "target_url": target_url}
    manifest = {
        "moodle_url": "https://moodle.example", "course_id": "100", "course_name": "Test Course",
        "crawled_at": "2026-10-17T12:00:00+00:00",
        "sections": [{"section_number": 0, "section_name": "General", "item_count": 1},
                     {"section_number": 1, "section_name": "Week 1", "item_count": 6}],
        "items": [
            item(0, "Syllabus", "resource", "resource", "downloaded", f"{COURSE}/00-General/Syllabus.docx"),
            item(1, "Slides", "resource", "resource", "downloaded", f"{COURSE}/01-Week 1/Slides.pdf"),
            item(1, "Reading", "url", "url", "downloaded", f"{COURSE}/links.md", target_url="https://example.org/r"),
            item(1, "Essay", "assign", "assign", "downloaded", f"{COURSE}/01-Week 1/Essay - instructions.md",
                 files=[f"{COURSE}/01-Week 1/Essay - instructions.md", f"{COURSE}/01-Week 1/rubric.pdf"]),
            item(1, "Schedule", "resource", "resource", "failed", note="HTTP 404"),
            item(1, "Final exam", "other", "quiz", "unavailable", note="Not available unless: date"),
            item(1, "Deleted", "resource", "resource", "downloaded", f"{COURSE}/01-Week 1/gone.pptx"),
        ],
    }
    (root / "data").mkdir(exist_ok=True)
    (root / "data" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for rel, data in {
        f"{COURSE}/00-General/Syllabus.docx": b"PK fake docx",
        f"{COURSE}/01-Week 1/Slides.pdf": b"%PDF-1.4 fake",
        f"{COURSE}/01-Week 1/Essay - instructions.md": b"# Essay\nWrite 500 words.",
        f"{COURSE}/01-Week 1/rubric.pdf": b"%PDF-1.4 rubric",
        f"{COURSE}/01-Week 1/saved page.html": b"<script>alert(1)</script>",
        f"{COURSE}/01-Week 1/tool.exe": b"MZ",
        f"{COURSE}/links.md": b"# Links",
        f"{TEXT}/00-General/Syllabus.docx.md": "# Syllabus\nWeek 1: Adam Smith".encode(),
        "data/ui/runs.json": b"{}",
        "data/debug/course_page.html": b"sesskey=SECRET",
    }.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    state = {"version": 3, "sources": {
        f"{COURSE}/00-General/Syllabus.docx": {"output": f"{TEXT}/00-General/Syllabus.docx.md", "flags": []},
        f"{COURSE}/01-Week 1/Slides.pdf": {"output": f"{TEXT}/01-Week 1/Slides.pdf.md", "flags": ["needs_ocr"]}}}
    (root / TEXT / "extract_state.json").write_text(json.dumps(state), encoding="utf-8")


def test_course_items(client, workspace):
    assert client.get("/api/course/items").json() == {
        "scraped": False, "course_id": "100", "name": None, "crawled_at": None, "sections": []}
    write_course(workspace)
    data = client.get("/api/course/items").json()
    assert data["scraped"] and data["name"] == "Test Course"
    assert [(s["number"], s["name"], len(s["items"])) for s in data["sections"]] == [(0, "General", 1), (1, "Week 1", 6)]
    items = {it["title"]: it for s in data["sections"] for it in s["items"]}

    syllabus = items["Syllabus"]["files"][0]
    assert syllabus == {"path": f"{COURSE}/00-General/Syllabus.docx", "name": "Syllabus.docx", "ext": "docx",
                        "size": 12, "exists": True, "text_path": f"{TEXT}/00-General/Syllabus.docx.md",
                        "flags": [], "openable": True}
    slides = items["Slides"]["files"][0]
    assert slides["flags"] == ["needs_ocr"] and slides["text_path"] is None  # its .md isn't on disk
    assert items["Reading"]["files"] == [] and items["Reading"]["target_url"] == "https://example.org/r"
    assert [f["name"] for f in items["Essay"]["files"]] == ["Essay - instructions.md", "rubric.pdf"]
    assert items["Schedule"]["files"] == [] and items["Schedule"]["note"] == "HTTP 404"
    assert items["Final exam"]["status"] == "unavailable" and items["Final exam"]["module"] == "quiz"
    gone = items["Deleted"]["files"][0]
    assert not gone["exists"] and gone["size"] is None


# --- file serving ---

def test_files_are_served_with_safe_headers(client, workspace):
    write_course(workspace)
    r = client.get(f"/api/files/{COURSE}/01-Week 1/Slides.pdf")
    assert r.status_code == 200 and r.content == b"%PDF-1.4 fake"
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-disposition"].startswith("inline")

    r = client.get(f"/api/files/{TEXT}/00-General/Syllabus.docx.md")
    assert r.text.startswith("# Syllabus") and r.headers["content-type"] == "text/plain; charset=utf-8"
    assert r.headers["content-security-policy"] == "sandbox"

    # a saved Moodle page must not run script in the app's origin
    r = client.get(f"/api/files/{COURSE}/01-Week%201/saved%20page.html")
    assert r.status_code == 200 and r.headers["content-security-policy"] == "sandbox"


def make_junction(link: Path, target: Path) -> bool:
    if sys.platform != "win32":
        try:
            link.symlink_to(target, target_is_directory=True)
            return True
        except OSError:
            return False
    r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
    return r.returncode == 0


def test_files_outside_the_allowed_folders_are_never_served(client, workspace):
    write_course(workspace)
    escape = workspace / COURSE / "escape"
    has_junction = make_junction(escape, workspace / "auth")
    bad = [
        "auth/state.json", ".env", "data/manifest.json", "data/ui/runs.json", "data/debug/course_page.html",
        "downloads/%2e%2e/auth/state.json", "downloads/..%2f..%2fauth%2fstate.json", "%2e%2e/.env",
        "downloads%5c..%5cauth%5cstate.json", "downloads/..%5cauth%5cstate.json", "C:/Windows/win.ini",
        "C:%5cWindows%5cwin.ini", "%2fetc%2fpasswd", f"{COURSE}/01-Week 1/Slides.pdf:secret",
        "downloads", COURSE, f"{COURSE}/01-Week 1/missing.pdf", "data/text", "api/main.py",
    ]
    if has_junction:
        bad.append(f"{COURSE}/escape/state.json")
    for path in bad:
        r = client.get(f"/api/files/{path}")
        assert r.status_code == 404, path
        assert "MoodleSession" not in r.text and "SECRET" not in r.text, path


def test_resolve_served_rejects_tricky_paths(workspace):
    write_course(workspace)
    for path in ["downloads/../auth/state.json", "downloads\\..\\.env", "/etc/passwd", "downloads/./x",
                 "downloads//x", f"{COURSE}/01-Week 1/Slides.pdf\x00.txt", ""]:
        with pytest.raises(files.NotServed):
            files.resolve_served(workspace, path)
    assert files.resolve_served(workspace, f"{COURSE}/01-Week 1/Slides.pdf").name == "Slides.pdf"


@pytest.fixture
def launched(monkeypatch):
    calls: list[tuple[str, Path]] = []
    monkeypatch.setattr(files, "open_with_default_app", lambda p: calls.append(("open", p)))
    monkeypatch.setattr(files, "show_in_folder", lambda p: calls.append(("reveal", p)))
    monkeypatch.setattr(files, "desktop_supported", lambda: True)
    return calls


def test_open_and_show_in_folder(client, workspace, launched):
    write_course(workspace)
    pdf = f"{COURSE}/01-Week 1/Slides.pdf"
    assert post(client, "/api/files/open", json={"path": pdf}).json() == {"ok": True}
    assert post(client, "/api/files/reveal", json={"path": pdf}).json() == {"ok": True}
    assert launched == [("open", (workspace / pdf).resolve()), ("reveal", (workspace / pdf).resolve())]

    launched.clear()
    exe = f"{COURSE}/01-Week 1/tool.exe"
    r = post(client, "/api/files/open", json={"path": exe})  # never run a program
    assert r.status_code == 400 and "Show in folder" in r.json()["error"]
    assert post(client, "/api/files/reveal", json={"path": exe}).status_code == 200  # only selects it in Explorer
    assert post(client, "/api/files/open", json={"path": "auth/state.json"}).status_code == 404
    assert post(client, "/api/files/reveal", json={"path": "downloads/../.env"}).status_code == 404
    assert client.post("/api/files/open", json={"path": pdf}).status_code == 403  # no X-Moodle-Study header
    assert launched == [("reveal", (workspace / exe).resolve())]


def test_one_job_at_a_time_and_cancel(client):
    first = post(client, "/api/jobs", json={"action": "scrape"}).json()
    r = post(client, "/api/session/check")
    assert r.status_code == 409
    assert "still running" in r.json()["error"]
    assert client.get("/api/jobs/current").json()["id"] == first["id"]

    wait_for_line(client, first, "Opening")
    post(client, f"/api/jobs/{first['id']}/cancel")
    job = wait(client, first, timeout=30)
    assert job["state"] == "cancelled"
    assert "saved" in job["message"]
    # a new job can start right away
    assert post(client, "/api/session/check").status_code == 202


def test_enter_only_for_login(client):
    job = post(client, "/api/session/check").json()
    r = post(client, f"/api/jobs/{job['id']}/enter")
    assert r.status_code == 400
    wait(client, job)


@pytest.mark.skipif(bool(os.environ.get("SKIP_HEADED")), reason="SKIP_HEADED is set")
def test_login_through_the_ui(client, workspace):
    """Opens a real browser window for ~10 s. The fake login page 'logs in' 3 s after loading."""
    set_cookie(workspace, None)
    fake_moodle.Handler.auto_login = True
    job = post(client, "/api/session/login").json()
    assert job["waiting_for_input"]
    wait_for_line(client, job, "Log in to Moodle in the browser window")
    time.sleep(6)
    post(client, f"/api/jobs/{job['id']}/enter")
    job = wait(client, job, timeout=60)
    assert job["state"] == "succeeded", job
    assert client.get("/api/session").json()["status"] == "valid"


# --- typed client contract ---

def test_openapi_schema_is_up_to_date():
    assert OPENAPI_FILE.read_text(encoding="utf-8") == schema_text(), \
        "API changed: run  .venv\\Scripts\\python -m api.export_openapi  then  cd web; npm run gen:api"
