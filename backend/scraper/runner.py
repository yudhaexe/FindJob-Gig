"""Scrape runner (DESIGN-SYSTEM §2): sources in parallel → raw → to_job → finalize → filter → upsert.

Every step of a run is written to data/runs/<run_id>.json so the UI (M3) can poll progress.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx

from core.models import Job, Run, ScrapeQuery, SourceRunResult
from scraper.base import Http, Source, SourceBlocked, SourceError
from scraper.normalize import finalize
from scraper.regions import source_matches_region
from scraper.sources import load_sources
from storage.filestore import FileStore

ProgressFn = Callable[[str, SourceRunResult], None]


def new_run_id(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"{now:%Y-%m-%dT%H-%M-%S}_{secrets.token_hex(2)}"


def pick_sources(q: ScrapeQuery, available: dict[str, Source]) -> list[Source]:
    """Explicit `q.sources` win (even if disabled); otherwise enabled sources that fit region + category."""
    if q.sources:
        unknown = [n for n in q.sources if n not in available]
        if unknown:
            raise ValueError(f"Unknown source(s): {', '.join(unknown)}. Known: {', '.join(available)}")
        return [available[n] for n in q.sources]
    return [
        s for s in available.values()
        if s.enabled
        and source_matches_region(s.markets, q.region)
        and (q.category == "any" or s.category in (q.category, "mixed"))
    ]


def passes(job: Job, q: ScrapeQuery, now: datetime) -> bool:
    """Scrape-time filters. Unknown values pass: an honest 'unknown' beats dropping a real match."""
    if q.types and job.employment_type != "unknown" and job.employment_type not in q.types:
        return False
    if q.category != "any" and job.category != q.category:
        return False
    if q.remote_only and job.work_mode != "remote":
        return False
    if q.since_hours and job.posted_at and job.posted_at < now - timedelta(hours=q.since_hours):
        return False
    if not job.title.strip():
        return False
    return True


async def _fetch(src: Source, q: ScrapeQuery, http: Http) -> tuple[dict[str, tuple[dict, set[str]]], list[str]]:
    """All raw items for every keyword, unique by external id, remembering which keywords hit them."""
    found: dict[str, tuple[dict[str, Any], set[str]]] = {}
    errors: list[str] = []
    for kw in q.keywords or [None]:
        try:
            items = await src.search(kw, q, q.max_per_source, http)
        except SourceBlocked as e:
            errors.append(f"{kw or '*'}: {e}")
            break  # hammering a site that blocks us only makes it worse
        except SourceError as e:
            errors.append(f"{kw or '*'}: {e}")
            continue
        for raw in items:
            eid = src.external_id(raw)
            entry = found.setdefault(eid, (raw, set()))
            if kw:
                entry[1].add(kw)
    return found, errors


async def _run_source(
    src: Source, q: ScrapeQuery, client: httpx.AsyncClient, store: FileStore, run: Run, progress: ProgressFn | None
) -> None:
    res = run.sources[src.name]
    res.status = "running"
    res.logs.append(f"Started scrape for {src.display_name} with {len(q.keywords) or 1} keyword(s)")
    store.save_run(run)
    if progress:
        progress(src.name, res)
    t0 = time.monotonic()
    try:
        found, errors = await _fetch(src, q, Http(client, src.min_interval))
        for err in errors:
            res.logs.append(f"Warning/Error: {err}")
        if errors and not found:
            raise SourceError("; ".join(errors))

        res.logs.append(f"Fetched {len(found)} raw items from {src.display_name}")
        now = datetime.now(timezone.utc)
        records = [
            {"source": src.name, "provider": src.provider, "fetched_at": now.isoformat(),
             "keywords": sorted(kws), "raw": raw}
            for raw, kws in found.values()
        ]
        refs = await asyncio.to_thread(store.append_raw, src.name, records, now) if records else []

        jobs: list[Job] = []
        bad = 0
        for (raw, kws), ref in zip(found.values(), refs):
            try:
                job = finalize(src.to_job(raw, now))
            except Exception as e:  # one odd item must not sink the whole source
                bad += 1
                res.logs.append(f"Failed parsing item {src.external_id(raw)}: {e}")
                continue
            job.matched_queries = sorted(kws)
            job.raw_ref = ref
            job.scan_run_id = run.id
            if passes(job, q, now):
                jobs.append(job)

        stats = await asyncio.to_thread(store.upsert_jobs, src.name, jobs)
        res.fetched = len(found)
        res.new, res.updated = stats.new, stats.updated
        res.skipped = len(found) - len(jobs)
        res.status = "done"
        notes = errors + ([f"{bad} item(s) could not be parsed"] if bad else [])
        res.error = "; ".join(notes) or None
        res.logs.append(f"Completed: {res.new} new, {res.updated} updated, {res.skipped} skipped/filtered out")
    except SourceError as e:
        res.status, res.error = "error", str(e)
        res.logs.append(f"Failed with SourceError: {e}")
    except Exception as e:  # noqa: BLE001 — surface anything unexpected in the run log
        res.status, res.error = "error", f"{type(e).__name__}: {e}"
        res.logs.append(f"Unexpected error: {type(e).__name__}: {e}")
    finally:
        res.ms = int((time.monotonic() - t0) * 1000)
        store.save_run(run)
        if progress:
            progress(src.name, res)


async def run_scrape(
    q: ScrapeQuery,
    store: FileStore | None = None,
    trigger: Literal["manual", "schedule", "cli"] = "cli",
    progress: ProgressFn | None = None,
    available: dict[str, Source] | None = None,
    client: httpx.AsyncClient | None = None,
    run_id: str | None = None,
    sources: list[Source] | None = None,
) -> Run:
    """Run a scrape to completion. The API passes `run_id` + `sources` it already picked so it can answer at once."""
    store = store or FileStore()
    if sources is None:
        sources = pick_sources(q, available if available is not None else load_sources())
    run = Run(
        id=run_id or new_run_id(), query=q, trigger=trigger, status="running",
        started_at=datetime.now(timezone.utc),
        sources={s.name: SourceRunResult() for s in sources},
    )
    store.save_run(run)

    own_client = client is None
    client = client or httpx.AsyncClient(timeout=30, follow_redirects=True)
    try:
        await asyncio.gather(*(_run_source(s, q, client, store, run, progress) for s in sources))
    finally:
        if own_client:
            await client.aclose()

    statuses = {r.status for r in run.sources.values()}
    if not sources or statuses == {"error"}:
        run.status = "failed"
    elif "error" in statuses:
        run.status = "partial"
    else:
        run.status = "done"
    run.finished_at = datetime.now(timezone.utc)
    store.save_run(run)
    return run
