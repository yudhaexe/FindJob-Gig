"""Scrape from the UI (DESIGN-SYSTEM §8): start a run in the background, then poll /runs/{id}."""

import asyncio
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from core import config
from core.models import Run, ScrapeQuery, SourceRunResult
from scraper.base import Source
from scraper.regions import source_matches_region
from scraper.runner import new_run_id, pick_sources, run_scrape
from scraper.sources import load_sources
from storage.filestore import FileStore

router = APIRouter(tags=["scrape"])

# Strong refs: the event loop only keeps weak ones, and a collected task would stop mid-run.
_active: dict[str, asyncio.Task] = {}


def get_store() -> FileStore:
    return FileStore()


def get_sources() -> dict[str, Source]:
    return load_sources()


StoreDep = Annotated[FileStore, Depends(get_store)]
SourcesDep = Annotated[dict[str, Source], Depends(get_sources)]


@router.get("/scrape/sources")
def scrape_sources(available: SourcesDep, region: str = "ALL", category: str = "any") -> dict:
    """Every connector plus whether it would be picked automatically for this region/category, and the presets."""
    region = region.upper()
    auto = {s.name for s in pick_sources(ScrapeQuery(region=region, category=category), available)} \
        if category in ("job", "gig", "any") else set()
    return {"sources": [
        {
            "name": s.name,
            "display_name": s.display_name,
            "category": s.category,
            "markets": s.markets,
            "enabled": s.enabled,
            "in_region": source_matches_region(s.markets, region),
            "selected": s.name in auto,
        }
        for s in available.values()
    ], "presets": [
        {"name": name, "label": p.get("label", name),
         "query": {k: v for k, v in p.items() if k in ScrapeQuery.model_fields}}
        for name, p in (config.load("sources").get("presets") or {}).items()
    ]}


@router.post("/scrape", status_code=202)
async def start_scrape(q: ScrapeQuery, store: StoreDep, available: SourcesDep) -> dict:
    q.keywords = list(dict.fromkeys(k.strip() for k in q.keywords if k.strip()))
    q.region = q.region.upper()
    try:
        sources = pick_sources(q, available)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    if not sources:
        raise HTTPException(422, "No source matches this region/category. Pick sources manually.")

    run_id = new_run_id()
    # Written before answering so the first poll never 404s.
    store.save_run(Run(id=run_id, query=q, trigger="manual", status="queued",
                       started_at=datetime.now(timezone.utc),
                       sources={s.name: SourceRunResult() for s in sources}))
    task = asyncio.create_task(run_scrape(q, store=store, trigger="manual", run_id=run_id, sources=sources))
    _active[run_id] = task
    task.add_done_callback(lambda _: _active.pop(run_id, None))
    return {"run_id": run_id}


@router.get("/runs", response_model=list[Run])
def list_runs(store: StoreDep, limit: int = Query(20, ge=1, le=200)) -> list[Run]:
    return store.list_runs(limit)


@router.get("/runs/{run_id}", response_model=Run)
def get_run(run_id: str, store: StoreDep) -> Run:
    run = store.load_run(run_id)
    if run is None:
        raise HTTPException(404, f"Run not found: {run_id}")
    return run
