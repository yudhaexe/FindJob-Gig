"""Scheduled scrapes (DESIGN-SYSTEM §5c).

One implementation serves both the in-app loop and `fjg schedule run-due` (Windows Task Scheduler).
A schedule is *claimed* (next_run_at pushed forward under a file lock) before it runs, so the two
callers never run the same schedule twice, and a missed slot runs once instead of catching up.
"""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

from core.models import Run, Schedule
from scraper.runner import run_scrape
from storage.filestore import FileStore

log = logging.getLogger(__name__)

MIN_INTERVAL =timedelta(minutes=30)
MAX_FAILURES = 3
_EVERY = re.compile(r"(\d+)([mhd])")
_UNITS = {"m": "minutes", "h": "hours", "d": "days"}


def parse_every(every: str) -> timedelta:
    m = _EVERY.fullmatch(every.strip().lower())
    if not m:
        raise ValueError(f"Invalid interval '{every}'. Use e.g. 30m, 6h, 1d.")
    delta = timedelta(**{_UNITS[m[2]]: int(m[1])})
    if delta < MIN_INTERVAL:
        raise ValueError("Interval must be at least 30m (sources rate-limit aggressively).")
    return delta


def new_schedule_id() -> str:
    return f"sched_{secrets.token_hex(3)}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def claim_due(store: FileStore, now: datetime | None = None, only: str | None = None) -> list[Schedule]:
    """Pick due schedules (or `only` regardless of due-ness) and push next_run_at so nobody else takes them."""
    now = now or _now()

    def fn(items: list[Schedule]) -> list[Schedule]:
        claimed = []
        for s in items:
            if only is not None:
                if s.id != only:
                    continue
            elif not s.enabled or (s.next_run_at and s.next_run_at > now):
                continue
            s.next_run_at = now + parse_every(s.every)
            claimed.append(s.model_copy(deep=True))
        return claimed

    return store.update_schedules(fn)


def record_result(store: FileStore, schedule_id: str, run: Run | None, error: str | None = None) -> None:
    def fn(items: list[Schedule]) -> None:
        for s in items:
            if s.id != schedule_id:
                continue
            s.last_run_at = _now()
            if run is not None:
                s.last_run_id, s.last_status = run.id, run.status
            failed = run is None or run.status == "failed"
            s.consecutive_failures = s.consecutive_failures + 1 if failed else 0
            if failed and s.consecutive_failures >= MAX_FAILURES:
                s.enabled = False
                s.paused_reason = f"Paused after {MAX_FAILURES} failures in a row" + (f": {error}" if error else "")
            elif not failed:
                s.paused_reason = None

    store.update_schedules(fn)


async def execute(store: FileStore, s: Schedule) -> Run | None:
    try:
        run = await run_scrape(s.query, store=store, trigger="schedule", schedule_id=s.id)
    except Exception as e:  # noqa: BLE001 — a bad schedule must not kill the loop
        record_result(store, s.id, None, f"{type(e).__name__}: {e}")
        return None
    record_result(store, s.id, run)
    return run


async def run_due(store: FileStore, now: datetime | None = None) -> list[Run]:
    runs = []
    for s in claim_due(store, now):
        run = await execute(store, s)
        if run:
            runs.append(run)
    return runs


async def run_now(store: FileStore, schedule_id: str) -> Run | None:
    claimed = claim_due(store, only=schedule_id)
    return await execute(store, claimed[0]) if claimed else None


async def loop(store_factory=FileStore, tick: float = 30) -> None:
    """In-app scheduler: poll for due schedules while the API is up."""
    while True:
        try:
            await run_due(store_factory())
        except Exception:  # noqa: BLE001 — keep ticking, but never silently
            log.exception("Scheduler tick failed")
        await asyncio.sleep(tick)
