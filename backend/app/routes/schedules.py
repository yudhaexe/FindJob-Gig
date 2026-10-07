"""Schedule CRUD + run-now (DESIGN-SYSTEM §8)."""

import asyncio
import subprocess
import sys
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.routes.scrape import SourcesDep, StoreDep
from core.models import Schedule, ScrapeQuery
from scraper import scheduler
from scraper.runner import pick_sources

router = APIRouter(tags=["schedules"])

_active: set[asyncio.Task] = set()


class ScheduleIn(BaseModel):
    name: str
    query: ScrapeQuery
    every: str = "6h"
    enabled: bool = True


class SchedulePatch(BaseModel):
    name: str | None = None
    query: ScrapeQuery | None = None
    every: str | None = None
    enabled: bool | None = None


def _validate(q: ScrapeQuery, every: str, available) -> None:
    try:
        scheduler.parse_every(every)
        if not pick_sources(q, available):
            raise ValueError("No source matches this region/category. Pick sources manually.")
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


def _clean(q: ScrapeQuery) -> ScrapeQuery:
    q.keywords = list(dict.fromkeys(k.strip() for k in q.keywords if k.strip()))
    q.region = q.region.upper()
    return q


def _after(every: str) -> datetime:
    return datetime.now(timezone.utc) + scheduler.parse_every(every)


@router.get("/schedules", response_model=list[Schedule])
def list_schedules(store: StoreDep) -> list[Schedule]:
    return store.load_schedules()


@router.get("/schedules/task-status")
def task_status() -> dict:
    """Windows Task Scheduler entry from scripts/register-task.ps1: registered | not-registered | not-supported."""
    if sys.platform != "win32":
        return {"status": "not-supported"}
    r = subprocess.run(["schtasks", "/Query", "/TN", "FindJobGig"], capture_output=True, text=True)
    return {"status": "registered" if r.returncode == 0 else "not-registered"}


@router.post("/schedules", response_model=Schedule, status_code=201)
def create_schedule(body: ScheduleIn, store: StoreDep, available: SourcesDep) -> Schedule:
    q = _clean(body.query)
    _validate(q, body.every, available)
    every = body.every.strip().lower()
    s = Schedule(id=scheduler.new_schedule_id(), name=body.name.strip() or "Untitled", enabled=body.enabled,
                 query=q, every=every, created_at=datetime.now(timezone.utc), next_run_at=_after(every))
    store.update_schedules(lambda items: items.append(s))
    return s


@router.patch("/schedules/{schedule_id}", response_model=Schedule)
def patch_schedule(schedule_id: str, body: SchedulePatch, store: StoreDep, available: SourcesDep) -> Schedule:
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    current = next((s for s in store.load_schedules() if s.id == schedule_id), None)
    if current is None:
        raise HTTPException(404, f"Schedule not found: {schedule_id}")
    if body.query is not None:
        changes["query"] = _clean(body.query)
    if "every" in changes:
        changes["every"] = changes["every"].strip().lower()
    _validate(changes.get("query", current.query), changes.get("every", current.every), available)

    def fn(items: list[Schedule]) -> Schedule | None:
        for s in items:
            if s.id != schedule_id:
                continue
            for k, v in changes.items():
                setattr(s, k, v)
            if "every" in changes or changes.get("enabled"):
                s.next_run_at = _after(s.every)
            if changes.get("enabled"):  # resume: clear the failure streak
                s.consecutive_failures, s.paused_reason = 0, None
            return s
        return None

    updated = store.update_schedules(fn)
    if updated is None:
        raise HTTPException(404, f"Schedule not found: {schedule_id}")
    return updated


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: str, store: StoreDep) -> None:
    def fn(items: list[Schedule]) -> bool:
        keep = [s for s in items if s.id != schedule_id]
        found = len(keep) != len(items)
        items[:] = keep
        return found

    if not store.update_schedules(fn):
        raise HTTPException(404, f"Schedule not found: {schedule_id}")


@router.post("/schedules/{schedule_id}/run", status_code=202)
async def run_schedule_now(schedule_id: str, store: StoreDep) -> dict:
    if not any(s.id == schedule_id for s in store.load_schedules()):
        raise HTTPException(404, f"Schedule not found: {schedule_id}")
    task = asyncio.create_task(scheduler.run_now(store, schedule_id))
    _active.add(task)  # strong ref until done
    task.add_done_callback(_active.discard)
    return {"status": "started"}
