"""API tests: the FastAPI app driving the real CLI scripts against the fake Moodle.

    .venv\\Scripts\\python -m pytest tests\\test_api.py        ($env:SKIP_HEADED=1 skips the visible-browser test)

Each test gets a throwaway copy of the scripts with its own .env, auth/ and data/,
so your real files are never touched.
"""

import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(Path(__file__).parent))
import fake_moodle  # noqa: E402
from api.export_openapi import OUT as OPENAPI_FILE, schema_text  # noqa: E402
from api.jobs import parse_line, parse_progress  # noqa: E402
from api.main import create_app  # noqa: E402

SCRIPTS = ["common.py", "moodle_selectors.py", "login.py", "check_session.py", "scrape.py", "downloader.py"]
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
