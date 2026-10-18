"""Read the CLI's files (relative to a project root) and keep the UI's own small state in data/ui/.

Never opens auth/state.json: only checks whether it exists.
"""

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, root: Path):
        self.root = root
        self.manifest_file = root / "data" / "manifest.json"
        self.ui_dir = root / "data" / "ui"
        self.runs_file = self.ui_dir / "runs.json"
        self.session_file = self.ui_dir / "session.json"
        self.state_file = root / "auth" / "state.json"

    # --- the CLI's files (read only) ---

    def env(self) -> dict[str, str]:
        env_file = self.root / ".env"
        if not env_file.exists():
            return {}
        return {k: (v or "").strip() for k, v in dotenv_values(env_file).items()}

    def manifest(self) -> dict | None:
        try:
            return json.loads(self.manifest_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def course_summary(self) -> dict:
        env = self.env()
        course_id = env.get("COURSE_ID") or None
        moodle_url = (env.get("MOODLE_URL") or "").rstrip("/") or None
        manifest = self.manifest()
        scraped = bool(manifest and course_id and str(manifest.get("course_id")) == course_id)
        items = manifest["items"] if scraped else []
        return {
            "configured": bool(course_id and moodle_url),
            "course_id": course_id,
            "course_url": f"{moodle_url}/course/view.php?id={course_id}" if course_id and moodle_url else None,
            "scraped": scraped,
            "name": manifest.get("course_name") if scraped else None,
            "crawled_at": manifest.get("crawled_at") if scraped else None,
            "sections": len(manifest.get("sections", [])) if scraped else 0,
            "items": len(items),
            "by_status": dict(Counter(it.get("status", "") for it in items)),
            "by_type": dict(Counter(it.get("type", "") for it in items)),
        }

    # --- the UI's own state (data/ui/, git-ignored with the rest of data/) ---

    def _read(self, path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _write(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def runs(self) -> dict:
        return self._read(self.runs_file)

    def record_run(self, action: str, info: dict) -> None:
        runs = self.runs()
        runs[action] = info
        self._write(self.runs_file, runs)

    def session(self) -> dict:
        if not self.state_file.exists():
            return {"status": "missing", "checked_at": None, "message": "You haven't logged in yet."}
        saved = self._read(self.session_file)
        if saved.get("status") in ("valid", "expired"):
            return {"status": saved["status"], "checked_at": saved.get("checked_at"), "message": saved.get("message", "")}
        return {"status": "unknown", "checked_at": None, "message": "Not checked yet."}

    def set_session(self, status: str, message: str) -> None:
        self._write(self.session_file, {"status": status, "checked_at": now(), "message": message})
