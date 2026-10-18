"""Local web API for the Moodle study tool.

    python dev.py                    # API on http://127.0.0.1:8765 plus the web app (see README)

Security: listens on 127.0.0.1 only (dev.py), accepts only localhost Host headers
(blocks DNS rebinding), and every non-GET request needs the X-Moodle-Study header
(blocks other websites from triggering jobs). It never reads auth/state.json and
never handles the Moodle password: login happens in the visible Playwright window.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import models
from .jobs import Busy, Job, JobManager
from .store import Store, now

ROOT = Path(__file__).resolve().parents[1]
CSRF_HEADER = "x-moodle-study"
LOCAL_HOSTS = {"127.0.0.1", "localhost"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
ERRORS = {400: {"model": models.ErrorBody}, 403: {"model": models.ErrorBody}, 404: {"model": models.ErrorBody},
          409: {"model": models.ErrorBody}}

log = logging.getLogger("moodle.api")


def create_app(root: Path = ROOT) -> FastAPI:
    store = Store(root)

    def on_finish(job: Job, state: str) -> None:
        if job.action in ("check_session", "login", "scrape"):
            if state == "succeeded":
                store.set_session("valid", "You are logged in.")
            elif state == "session_expired":
                store.set_session("expired", "Your session has expired. Log in again.")
        if job.action == "scrape":
            course = store.course_summary()
            counts = {"items": course["items"], **course["by_status"]}
            store.record_run("scrape", {"action": "scrape", "state": state, "started_at": job.started_at,
                                        "finished_at": job.finished_at or now(), "message": job.message,
                                        "counts": counts if state == "succeeded" else {}})

    jobs = JobManager(root, on_finish)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        jobs.shutdown()

    app = FastAPI(title="Moodle Study Assistant", version="1.0", lifespan=lifespan)

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]").lower()
        if host not in LOCAL_HOSTS:
            return JSONResponse({"error": "This server only answers on 127.0.0.1."}, status_code=400)
        if request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != "1":
            return JSONResponse({"error": "Missing X-Moodle-Study header."}, status_code=403)
        return await call_next(request)

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def bad_request(_request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        return JSONResponse({"error": f"Invalid request: {first.get('msg', 'bad input')}"}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, exc: Exception):
        log.exception("Unexpected API error")  # details stay in the server console
        return JSONResponse({"error": "Something went wrong in the local server. Try again."}, status_code=500)

    def start(action: str) -> dict:
        try:
            return jobs.start(action).view()
        except Busy as e:
            raise HTTPException(409, str(e))

    def find(job_id: str) -> Job:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(404, "That job doesn't exist (the server may have restarted).")
        return job

    @app.get("/api/health", response_model=models.Health)
    def health():
        return {"ok": True}

    @app.get("/api/session", response_model=models.Session)
    def session():
        return store.session()

    @app.post("/api/session/check", response_model=models.Job, status_code=202, responses=ERRORS)
    def check_session():
        return start("check_session")

    @app.post("/api/session/login", response_model=models.Job, status_code=202, responses=ERRORS)
    def login():
        return start("login")

    @app.get("/api/course", response_model=models.CourseSummary)
    def course():
        return store.course_summary()

    @app.get("/api/runs", response_model=models.Runs)
    def runs():
        return store.runs()

    @app.post("/api/jobs", response_model=models.Job, status_code=202, responses=ERRORS)
    def start_job(body: models.StartJob):
        if not store.course_summary()["configured"]:
            raise HTTPException(400, "Set MOODLE_URL and COURSE_ID in .env first.")
        return start(body.action)

    @app.get("/api/jobs/current", response_model=models.Job | None)
    def current_job():
        return jobs.current.view() if jobs.current else None

    @app.get("/api/jobs/{job_id}", response_model=models.Job, responses=ERRORS)
    def get_job(job_id: str, after: int = 0):
        return find(job_id).view(after)

    @app.post("/api/jobs/{job_id}/cancel", response_model=models.Job, responses=ERRORS)
    def cancel_job(job_id: str):
        find(job_id)
        return jobs.cancel(job_id).view()

    @app.post("/api/jobs/{job_id}/enter", response_model=models.Job, responses=ERRORS)
    def press_enter(job_id: str):
        job = find(job_id)
        if job.action != "login":
            raise HTTPException(400, "Only the login job waits for you.")
        return jobs.press_enter(job_id).view()

    return app


app = create_app()
