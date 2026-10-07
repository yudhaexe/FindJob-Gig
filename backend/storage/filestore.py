"""JSONL file storage (DESIGN-SYSTEM §4).

Layout under DATA_DIR:
    raw/<source>/<YYYY-MM-DD>.jsonl   append-only, one source item per line
    jobs/<source>.jsonl               normalised Job per line, unique by id
    runs/<run_id>.json                one scrape run
    state/schedules.json              scrape schedules (API, CLI and scheduler share it)
    state/locks/<name>.lock           cross-process locks (CLI and API may run together)

Every rewrite goes to a temp file first and is swapped in with os.replace, so a reader
never sees a half-written file.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

import orjson

from core import paths
from core.models import Job, RawRef, Run, Schedule

T = TypeVar("T")

# Fields ignored when deciding whether a posting changed. `raw` is excluded because sources
# embed per-request noise in it (bid counts, tracking tokens); it is still stored.
_SAFE_NAME = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*")
_VOLATILE = {"fetched_at", "first_seen_at", "updated_at", "raw_ref", "matched_queries", "duplicates", "raw", "user_status", "scan_run_id"}


class LockTimeout(RuntimeError):
    pass


class FileLock:
    """Lock file created with O_EXCL. A lock older than `stale` seconds is assumed dead."""

    def __init__(self, path: Path, timeout: float = 60, stale: float = 600) -> None:
        self.path = path
        self.timeout = timeout
        self.stale = stale

    def __enter__(self) -> FileLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > self.stale:
                        self.path.unlink(missing_ok=True)
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() > deadline:
                    raise LockTimeout(f"Could not lock {self.path} within {self.timeout}s") from None
                time.sleep(0.1)

    def __exit__(self, *exc: object) -> None:
        self.path.unlink(missing_ok=True)


@dataclass
class UpsertStats:
    new: int = 0
    updated: int = 0
    unchanged: int = 0


def _dumps(obj: Any) -> bytes:
    return orjson.dumps(obj, option=orjson.OPT_UTC_Z)


def _atomic_write(path: Path, lines: Iterable[bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(tmp, "wb") as f:
        for line in lines:
            f.write(line)
            f.write(b"\n")
        f.flush()
        os.fsync(f.fileno())
    # Windows refuses to replace a file another process has open; retry briefly.
    for attempt in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 19:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(0.1)


def _content(job: Job) -> dict[str, Any]:
    return job.model_dump(mode="json", exclude=_VOLATILE)


class FileStore:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.root = Path(data_dir) if data_dir else paths.DATA_DIR
        self.raw_dir = self.root / "raw"
        self.jobs_dir = self.root / "jobs"
        self.runs_dir = self.root / "runs"
        self.state_dir = self.root / "state"
        for d in (self.raw_dir, self.jobs_dir, self.runs_dir, self.state_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ── locks ──────────────────────────────────────────────────────────────
    def lock(self, name: str) -> FileLock:
        return FileLock(self.state_dir / "locks" / f"{name}.lock")

    # ── raw ────────────────────────────────────────────────────────────────
    def raw_path(self, source: str, day: datetime) -> Path:
        return self.raw_dir / source / f"{day:%Y-%m-%d}.jsonl"

    def append_raw(self, source: str, records: list[dict[str, Any]], when: datetime) -> list[RawRef]:
        """Append records (one line each) and return where each one landed (1-based line)."""
        path = self.raw_path(source, when)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock(f"raw-{source}"):
            start = path.read_bytes().count(b"\n") if path.exists() else 0
            with open(path, "ab") as f:
                for rec in records:
                    f.write(_dumps(rec))
                    f.write(b"\n")
        rel = path.relative_to(self.root).as_posix()
        return [RawRef(file=rel, line=start + i + 1) for i in range(len(records))]

    # ── jobs ───────────────────────────────────────────────────────────────
    def jobs_path(self, source: str) -> Path:
        return self.jobs_dir / f"{source}.jsonl"

    def sources(self) -> list[str]:
        return sorted(p.stem for p in self.jobs_dir.glob("*.jsonl"))

    def iter_job_dicts(self, source: str) -> Iterator[dict[str, Any]]:
        """Raw dicts straight from disk (fast path for the index). Skips corrupt lines."""
        path = self.jobs_path(source)
        if not path.exists():
            return
        with open(path, "rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield orjson.loads(line)
                except orjson.JSONDecodeError:
                    continue

    def read_jobs(self, source: str) -> dict[str, Job]:
        out: dict[str, Job] = {}
        for d in self.iter_job_dicts(source):
            try:
                job = Job.model_validate(d)
            except ValueError:
                continue
            out[job.id] = job
        return out

    def get_job(self, job_id: str) -> Job | None:
        source = job_id.split(":", 1)[0]
        if not _SAFE_NAME.fullmatch(source):  # ids come from URLs; never let them pick a path
            return None
        for d in self.iter_job_dicts(source):
            if d.get("id") == job_id:
                return Job.model_validate(d)
        return None

    def upsert_jobs(self, source: str, jobs: list[Job]) -> UpsertStats:
        """Merge jobs into jobs/<source>.jsonl. Keeps first_seen_at; bumps updated_at only on real change."""
        stats = UpsertStats()
        now = datetime.now(timezone.utc)
        with self.lock(f"jobs-{source}"):
            existing = self.read_jobs(source)
            for job in jobs:
                old = existing.get(job.id)
                if old is None:
                    job.first_seen_at = job.first_seen_at or job.fetched_at or now
                    job.updated_at = job.fetched_at or now
                    stats.new += 1
                else:
                    job.first_seen_at = old.first_seen_at or old.fetched_at
                    job.matched_queries = sorted(set(old.matched_queries) | set(job.matched_queries))
                    if job.user_status is None and old.user_status is not None:
                        job.user_status = old.user_status
                    if job.scan_run_id is None and old.scan_run_id is not None:
                        job.scan_run_id = old.scan_run_id
                    if _content(old) == _content(job):
                        job.updated_at = old.updated_at
                        stats.unchanged += 1
                    else:
                        job.updated_at = job.fetched_at or now
                        stats.updated += 1
                existing[job.id] = job
            _atomic_write(
                self.jobs_path(source),
                (_dumps(j.model_dump(mode="json")) for j in existing.values()),
            )
        return stats

    def update_job_user_status(self, job_id: str, status: str | None) -> Job | None:
        source = job_id.split(":", 1)[0]
        if not _SAFE_NAME.fullmatch(source):
            return None
        with self.lock(f"jobs-{source}"):
            existing = self.read_jobs(source)
            job = existing.get(job_id)
            if job is None:
                return None
            job.user_status = status  # 'keep', 'removed', or None
            job.updated_at = datetime.now(timezone.utc)
            existing[job.id] = job
            _atomic_write(
                self.jobs_path(source),
                (_dumps(j.model_dump(mode="json")) for j in existing.values()),
            )
            return job

    # ── schedules ──────────────────────────────────────────────────────────
    @property
    def schedules_path(self) -> Path:
        return self.state_dir / "schedules.json"

    def load_schedules(self) -> list[Schedule]:
        if not self.schedules_path.exists():
            return []
        return [Schedule.model_validate(x) for x in orjson.loads(self.schedules_path.read_bytes())]

    def update_schedules(self, fn: Callable[[list[Schedule]], T]) -> T:
        """Read-modify-write under the cross-process lock; `fn` mutates the list in place."""
        with FileLock(self.state_dir / "locks" / "schedules.lock", timeout=30):
            items = self.load_schedules()
            result = fn(items)
            _atomic_write(self.schedules_path, [orjson.dumps([x.model_dump(mode="json") for x in items], option=orjson.OPT_INDENT_2)])
            return result

    # ── runs ───────────────────────────────────────────────────────────────
    def save_run(self, run: Run) -> None:
        path = self.runs_dir / f"{run.id}.json"
        _atomic_write(path, [orjson.dumps(run.model_dump(mode="json"), option=orjson.OPT_INDENT_2)])

    def load_run(self, run_id: str) -> Run | None:
        if not _SAFE_NAME.fullmatch(run_id):
            return None
        path = self.runs_dir / f"{run_id}.json"
        if not path.exists():
            return None
        return Run.model_validate_json(path.read_bytes())

    def list_runs(self, limit: int = 50) -> list[Run]:
        files = sorted(self.runs_dir.glob("*.json"), reverse=True)[:limit]
        return [Run.model_validate_json(p.read_bytes()) for p in files]
