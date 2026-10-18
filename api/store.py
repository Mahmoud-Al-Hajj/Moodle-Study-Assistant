"""Read the CLI's files (relative to a project root) and keep the UI's own small state in data/ui/.

Never opens auth/state.json: only checks whether it exists.
"""

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

from .files import openable


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
        self._extract_cache: tuple[tuple | None, dict[str, dict]] = (None, {})

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

    def course_items(self) -> dict:
        """Sections with their items and each item's files on disk, for the Course content screen."""
        summary = self.course_summary()
        base = {"scraped": summary["scraped"], "course_id": summary["course_id"], "name": summary["name"],
                "crawled_at": summary["crawled_at"], "sections": []}
        if not summary["scraped"]:
            return base
        manifest = self.manifest() or {}
        items = manifest.get("items", [])
        extracted = self._extracted(items)
        by_section: dict[int, list[dict]] = {}
        for it in items:
            by_section.setdefault(it["section_number"], []).append(self._item(it, extracted))
        sections = [(s["section_number"], s["section_name"]) for s in manifest.get("sections", [])]
        for number in by_section.keys() - {n for n, _ in sections}:  # an item's section missing from the list
            sections.append((number, by_section[number][0]["section_name"]))
        base["sections"] = [{"number": n, "name": name, "items": by_section.get(n, [])}
                            for n, name in sorted(sections)]
        return base

    def _item(self, it: dict, extracted: dict[str, dict]) -> dict:
        # Links share one generated links.md: their content is target_url, not a file.
        paths = [] if it.get("type") == "url" else (it.get("files") or [it.get("local_path")])
        files = []
        for p in dict.fromkeys(p for p in paths if p):
            path = self.root / p
            if path.is_dir():
                continue
            text = extracted.get(p, {})
            output = text.get("output") or None
            files.append({
                "path": p, "name": path.name, "ext": path.suffix.lower().lstrip("."),
                "size": path.stat().st_size if path.is_file() else None, "exists": path.is_file(),
                "text_path": output if output and (self.root / output).is_file() else None,
                "flags": text.get("flags", []), "openable": openable(p),
            })
        return {
            "id": it["id"], "title": it["title"], "type": it.get("type", "other"), "module": it.get("module", ""),
            "status": it.get("status", ""), "note": it.get("note", ""), "url": it.get("url", ""),
            "target_url": it.get("target_url", ""), "section_name": it.get("section_name", ""), "files": files,
        }

    def _extracted(self, items: list[dict]) -> dict[str, dict]:
        """Stage 4's per-source record (output .md, flags) from data/text/<course>/extract_state.json."""
        paths = (it.get("local_path") or "" for it in items)
        course = next((p.split("/")[1] for p in paths if p.startswith("downloads/") and p.count("/") >= 2), None)
        if not course:
            return {}
        state_file = self.root / "data" / "text" / course / "extract_state.json"
        try:
            mtime = state_file.stat().st_mtime_ns
        except OSError:
            return {}
        if self._extract_cache[0] != (state_file, mtime):  # ~1 MB with full text: parse only when it changes
            sources = self._read(state_file).get("sources", {})
            self._extract_cache = ((state_file, mtime), {k: {"output": v.get("output", ""), "flags": v.get("flags", [])}
                                                          for k, v in sources.items()})
        return self._extract_cache[1]

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
