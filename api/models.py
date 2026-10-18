"""Response and request models. web/src/api/schema.ts is generated from these (npm run gen:api)."""

from typing import Literal

from pydantic import BaseModel

SessionStatus = Literal["valid", "expired", "missing", "unknown"]
JobState = Literal["running", "succeeded", "failed", "session_expired", "cancelled"]
JobAction = Literal["scrape", "download", "check_session", "login"]
LineLevel = Literal["info", "warning", "error", "output"]


class ErrorBody(BaseModel):
    error: str


class Ok(BaseModel):
    ok: bool


class Session(BaseModel):
    status: SessionStatus
    checked_at: str | None
    message: str


class CourseSummary(BaseModel):
    configured: bool
    course_id: str | None
    course_url: str | None
    scraped: bool
    name: str | None
    crawled_at: str | None
    sections: int
    items: int
    by_status: dict[str, int]
    by_type: dict[str, int]


class RunInfo(BaseModel):
    action: str
    state: JobState
    started_at: str
    finished_at: str
    message: str
    counts: dict[str, int]


class Runs(BaseModel):
    scrape: RunInfo | None = None
    download: RunInfo | None = None
    extract: RunInfo | None = None


class Progress(BaseModel):
    done: int
    total: int
    item: str


class JobLine(BaseModel):
    seq: int
    level: LineLevel
    text: str


class Job(BaseModel):
    id: str
    action: JobAction
    label: str
    state: JobState
    started_at: str
    finished_at: str | None
    exit_code: int | None
    message: str
    progress: Progress | None
    waiting_for_input: bool
    lines: list[JobLine]
    next: int


class StartJob(BaseModel):
    action: Literal["scrape", "download"]


class ItemFile(BaseModel):
    path: str  # relative to the project root, for /api/files/{path}
    name: str
    ext: str
    size: int | None
    exists: bool
    text_path: str | None  # extracted .md (Stage 4), if any
    flags: list[str]
    openable: bool  # may be opened with the default Windows app


class CourseItem(BaseModel):
    id: str
    title: str
    type: str
    module: str
    status: str
    note: str
    url: str
    target_url: str
    section_name: str
    files: list[ItemFile]


class CourseSection(BaseModel):
    number: int
    name: str
    items: list[CourseItem]


class CourseContent(BaseModel):
    scraped: bool
    course_id: str | None
    name: str | None
    crawled_at: str | None
    sections: list[CourseSection]


class FileRequest(BaseModel):
    path: str
