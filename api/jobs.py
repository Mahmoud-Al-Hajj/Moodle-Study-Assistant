"""Run the CLI scripts as child processes, one at a time, and collect their output.

The scripts are not changed: progress comes from their existing log lines
("HH:MM:SS LEVEL message", and "[n/m] item" while downloading or extracting),
and the outcome from their exit codes (0 ok, 1 error, 2 session expired, 130 cancelled).
"""

import os
import re
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .store import now

# action -> (script and arguments, label shown in the UI, timeout in seconds or None)
ACTIONS: dict[str, tuple[list[str], str, int | None]] = {
    "scrape": (["scrape.py", "--no-download"], "Scrape course", None),
    "check_session": (["check_session.py"], "Check session", 180),
    "login": (["login.py"], "Log in to Moodle", 15 * 60),
}

MAX_LINES = 5000
_LOG_LINE = re.compile(r"(\d\d:\d\d:\d\d) (DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+(.*)$")
_PROGRESS = re.compile(r"^\[(\d+)/(\d+)\] (.*)$")
_LEVELS = {"DEBUG": "info", "INFO": "info", "WARNING": "warning", "ERROR": "error", "CRITICAL": "error"}


class Busy(Exception):
    """Another job is running."""


def parse_line(raw: str) -> list[tuple[str, str]]:
    """Split one output line into (level, text) pairs.

    A prompt printed without a newline (login.py's "Press Enter...") ends up in front of
    the next log line, so text before the timestamp becomes its own "output" line.
    """
    raw = raw.rstrip("\r\n")
    m = _LOG_LINE.search(raw)
    if not m:
        return [("output", raw)] if raw.strip() else []
    out = []
    before = raw[: m.start()].strip()
    if before:
        out.append(("output", before))
    out.append((_LEVELS[m.group(2)], m.group(3)))
    return out


def parse_progress(text: str) -> tuple[int, int, str] | None:
    m = _PROGRESS.match(text)
    return (int(m.group(1)), int(m.group(2)), m.group(3)) if m else None


@dataclass
class Job:
    id: str
    action: str
    label: str
    started_at: str
    proc: subprocess.Popen
    state: str = "running"
    finished_at: str | None = None
    exit_code: int | None = None
    message: str = ""
    progress: dict | None = None
    lines: list[dict] = field(default_factory=list)
    cancelled: bool = False

    def view(self, after: int = 0) -> dict:
        return {
            "id": self.id, "action": self.action, "label": self.label, "state": self.state,
            "started_at": self.started_at, "finished_at": self.finished_at, "exit_code": self.exit_code,
            "message": self.message, "progress": self.progress,
            "waiting_for_input": self.action == "login" and self.state == "running",
            "lines": [ln for ln in self.lines if ln["seq"] > after],
            "next": self.lines[-1]["seq"] if self.lines else after,
        }


def kill_tree(proc: subprocess.Popen) -> None:
    """Stop the script and everything it started (Playwright's driver and Chromium)."""
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        import signal
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


class JobManager:
    def __init__(self, root: Path, on_finish: Callable[[Job, str], None]):
        self.root = root
        self.on_finish = on_finish
        self.jobs: dict[str, Job] = {}
        self.current: Job | None = None
        self._lock = threading.Lock()

    def start(self, action: str) -> Job:
        args, label, timeout = ACTIONS[action]
        with self._lock:
            if self.current and self.current.state == "running":
                raise Busy(f"{self.current.label} is still running. Wait for it to finish or cancel it.")
            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
            kwargs = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32"
                      else {"start_new_session": True})
            proc = subprocess.Popen([sys.executable, "-u", *args], cwd=self.root, env=env, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    encoding="utf-8", errors="replace", **kwargs)
            job = Job(id=uuid.uuid4().hex[:12], action=action, label=label, started_at=now(), proc=proc)
            self.jobs[job.id] = job
            self.current = job
        threading.Thread(target=self._read, args=(job,), daemon=True).start()
        if timeout:
            timer = threading.Timer(timeout, self._time_out, args=(job,))
            timer.daemon = True
            timer.start()
        return job

    def _add(self, job: Job, level: str, text: str) -> None:
        seq = job.lines[-1]["seq"] + 1 if job.lines else 1
        job.lines.append({"seq": seq, "level": level, "text": text})
        if len(job.lines) > MAX_LINES:
            del job.lines[: len(job.lines) - MAX_LINES]
        p = parse_progress(text)
        if p:
            job.progress = {"done": p[0], "total": p[1], "item": p[2]}

    def _read(self, job: Job) -> None:
        assert job.proc.stdout is not None
        for raw in job.proc.stdout:
            for level, text in parse_line(raw):
                self._add(job, level, text)
        code = job.proc.wait()
        errors = [ln["text"] for ln in job.lines if ln["level"] == "error"]
        if job.cancelled or code == 130:
            state, message = "cancelled", "Cancelled. Everything finished so far is saved."
        elif code == 0:
            state, message = "succeeded", "Done."
        elif code == 2:
            state, message = "session_expired", "Your Moodle session has expired or is missing. Log in again."
        else:
            state = "failed"
            message = errors[-1] if errors else f"{job.label} stopped with an error (exit code {code})."
        job.exit_code, job.finished_at, job.message = code, now(), message
        try:
            self.on_finish(job, state)  # record the run before anyone can see the job as finished
        finally:
            job.state = state
            if job.proc.stdin:
                try:
                    job.proc.stdin.close()
                except OSError:
                    pass

    def _time_out(self, job: Job) -> None:
        if job.state == "running":
            self._add(job, "error", f"{job.label} took too long and was stopped.")
            self.cancel(job.id)

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def cancel(self, job_id: str) -> Job | None:
        job = self.jobs.get(job_id)
        if job and job.state == "running":
            job.cancelled = True
            kill_tree(job.proc)
        return job

    def press_enter(self, job_id: str) -> Job | None:
        """Send the Enter that login.py waits for after the user has logged in."""
        job = self.jobs.get(job_id)
        if job and job.state == "running" and job.proc.stdin and not job.proc.stdin.closed:
            try:
                job.proc.stdin.write("\n")
                job.proc.stdin.flush()
            except OSError:
                pass
        return job

    def shutdown(self) -> None:
        if self.current and self.current.state == "running":
            self.cancel(self.current.id)
