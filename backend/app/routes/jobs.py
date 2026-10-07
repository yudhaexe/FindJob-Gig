"""Jobs API. M0 stub: returns an empty page until FileStore + Index land in M1/M2."""

from fastapi import APIRouter, HTTPException, Query

from core.models import Job, JobsPage

router = APIRouter(tags=["jobs"])


@router.get("/jobs", response_model=JobsPage)
def list_jobs(
    q: str | None = None,
    region: str = "ALL",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> JobsPage:
    return JobsPage(items=[], total=0, page=page, page_size=page_size)


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
