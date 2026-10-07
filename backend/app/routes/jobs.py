"""Jobs API (DESIGN-SYSTEM §8): list with filters/sort/paging/facets, detail, regions, sources."""

import csv
import io
import json
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from core import config
from core.models import Job, JobsPage
from scraper import regions as regions_mod
from storage.index import SORTS, Filters, JobIndex, default_index

router = APIRouter(tags=["jobs"])

IndexDep = Annotated[JobIndex, Depends(default_index)]


class JobStatusUpdate(BaseModel):
    status: Literal["keep", "removed"] | None = None


def _csv(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def filters(
    q: str | None = None,
    region: str = "ALL",
    include_worldwide: bool = True,
    hide_unclear: bool = False,
    category: str | None = Query(None, description="Comma-separated: job,gig"),
    type: str | None = Query(None, description="Comma-separated employment types"),
    mode: str | None = Query(None, description="Comma-separated: remote,hybrid,onsite,unknown"),
    source: str | None = None,
    country: str | None = None,
    seniority: str | None = None,
    currency: str | None = None,
    salary_min: float | None = Query(None, description="Ignored unless `currency` is set"),
    salary_period: str = "month",
    has_salary: bool = False,
    posted_within: int | None = Query(None, ge=1, description="Hours"),
    duration_max: float | None = Query(None, gt=0, description="Days"),
    scan_run_id: str | None = Query(None, description="Filter by scrape run ID"),
    user_status: str | None = Query(None, description="'keep', 'removed', 'all', or None for active"),
) -> Filters:
    return Filters(
        q=q, region=region.upper(), include_worldwide=include_worldwide, hide_unclear=hide_unclear,
        category=_csv(category), type=_csv(type), mode=_csv(mode), source=_csv(source),
        country=[c.upper() for c in _csv(country)], seniority=_csv(seniority),
        currency=[c.upper() for c in _csv(currency)], salary_min=salary_min, salary_period=salary_period,
        has_salary=has_salary, posted_within=posted_within, duration_max=duration_max,
        scan_run_id=scan_run_id, user_status=user_status,
    )


FiltersDep = Annotated[Filters, Depends(filters)]


@router.get("/jobs", response_model=JobsPage)
def list_jobs(
    index: IndexDep,
    f: FiltersDep,
    sort: str | None = Query(None, description=" | ".join(SORTS)),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict:
    if sort is not None and sort not in SORTS:
        raise HTTPException(422, f"sort must be one of: {', '.join(SORTS)}")
    return index.search(f, sort=sort, page=page, page_size=page_size)


CSV_COLUMNS = [
    "title", "company", "category", "employment_type", "work_mode", "seniority", "location", "country",
    "pay_min", "pay_max", "currency", "pay_period", "duration", "skills", "source", "posted_at",
    "first_seen_at", "user_status", "url",
]


def _csv_row(j: dict[str, Any]) -> dict[str, Any]:
    pay = j.get("salary") or j.get("budget") or {}
    loc = j.get("location") or {}
    dur = j.get("duration") or {}
    return {
        "title": j["title"], "company": j.get("company"), "category": j.get("category"),
        "employment_type": j.get("employment_type"), "work_mode": j.get("work_mode"),
        "seniority": j.get("seniority"), "location": loc.get("raw") or loc.get("city"),
        "country": loc.get("country"), "pay_min": pay.get("min"), "pay_max": pay.get("max"),
        "currency": pay.get("currency"), "pay_period": pay.get("period") or pay.get("type"),
        "duration": dur.get("raw") or (f"{dur['value']:g} {dur.get('unit')}" if dur.get("value") else None),
        "skills": "; ".join(j.get("skills") or []), "source": j.get("source_name"),
        "posted_at": j.get("posted_at"), "first_seen_at": j.get("first_seen_at"),
        "user_status": j.get("user_status"), "url": j.get("source_url"),
    }


@router.get("/export")
def export_jobs(
    index: IndexDep,
    f: FiltersDep,
    format: Literal["csv", "json"] = "csv",
    sort: str | None = Query(None, description=" | ".join(SORTS)),
) -> Response:
    """Every job matching the filters (no paging), as a download."""
    if sort is not None and sort not in SORTS:
        raise HTTPException(422, f"sort must be one of: {', '.join(SORTS)}")
    items = index.search(f, sort=sort, page=1, page_size=10**9)["items"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    headers = {"Content-Disposition": f'attachment; filename="findjobgig-{stamp}.{format}"'}
    if format == "json":
        body = json.dumps(items, ensure_ascii=False, indent=2, default=str)
        return Response(body, media_type="application/json", headers=headers)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS)
    w.writeheader()
    w.writerows(_csv_row(j) for j in items)
    # BOM so Excel reads UTF-8 correctly
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)


@router.get("/facets")
def facets(index: IndexDep, f: FiltersDep) -> dict[str, dict[str, int]]:
    return index.search(f, page_size=1)["facets"]


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str, index: IndexDep) -> Job:
    job = index.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


@router.post("/jobs/{job_id}/status", response_model=Job)
@router.patch("/jobs/{job_id}/status", response_model=Job)
def set_job_status(job_id: str, body: JobStatusUpdate, index: IndexDep) -> Job:
    job = index.store.update_job_user_status(job_id, body.status)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    index.refresh(force=True)
    return job


@router.get("/regions")
def list_regions(index: IndexDep, include_worldwide: bool = True, hide_unclear: bool = False) -> dict:
    """Region tree (regions.yaml) with job counts; each region lists its countries."""
    cfg = config.load("regions")
    counts = index.region_counts(include_worldwide, hide_unclear)
    out = []
    for code, r in cfg.get("regions", {}).items():
        out.append({
            "code": code,
            "label": r.get("label", code),
            "children": r.get("children", []),
            "countries": sorted(regions_mod.region_countries(code)),
            "count": counts.get(code, 0),
        })
    countries = {
        code: {"name": c.get("name", code), "count": counts.get(code, 0)}
        for code, c in cfg.get("countries", {}).items()
    }
    return {"regions": out, "countries": countries}


@router.get("/sources")
def list_sources(index: IndexDep) -> dict:
    """Configured sources plus how many jobs each has on disk."""
    stats = index.stats()
    out = []
    for name, s in (config.load("sources").get("sources") or {}).items():
        st = stats["sources"].get(name, {})
        out.append({
            "name": name,
            "display_name": s.get("display_name", name),
            "category": s.get("category"),
            "markets": s.get("markets", []),
            "enabled": s.get("enabled", True),
            "attribution": s.get("attribution"),
            "jobs": st.get("jobs", 0),
            "last_fetched": st.get("last_fetched"),
        })
    return {"sources": out, "total": stats["total"], "last_fetched": stats["last_fetched"]}
