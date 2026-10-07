"""Data contracts shared by scraper, storage and API. See DESIGN-SYSTEM.md §3."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Category = Literal["job", "gig"]
EmploymentType = Literal[
    "fulltime", "parttime", "contract", "freelance", "internship", "temporary", "unknown"
]
WorkMode = Literal["remote", "hybrid", "onsite", "unknown"]
Seniority = Literal["intern", "junior", "mid", "senior", "lead", "unknown"]
SalaryPeriod = Literal["hour", "day", "week", "month", "year", "fixed", "unknown"]
DurationUnit = Literal["hour", "day", "week", "month", "year"]
RemoteScopeType = Literal["worldwide", "regions", "countries", "timezone", "unknown"]
RunStatus = Literal["queued", "running", "done", "failed", "partial"]
SourceStatus = Literal["queued", "running", "done", "error", "skipped"]


class Location(BaseModel):
    raw: str | None = None
    city: str | None = None
    country: str | None = None  # ISO-3166 alpha-2
    regions: list[str] = Field(default_factory=list)


class RemoteScope(BaseModel):
    type: RemoteScopeType = "unknown"
    regions: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    timezones: list[str] = Field(default_factory=list)
    raw: str | None = None


class Salary(BaseModel):
    """Always in the original currency — never converted."""

    min: float | None = None
    max: float | None = None
    currency: str | None = None
    currency_guessed: bool = False
    period: SalaryPeriod = "unknown"
    raw: str | None = None
    estimated: bool = False  # parsed from free text rather than a structured field


class Budget(BaseModel):
    min: float | None = None
    max: float | None = None
    currency: str | None = None
    currency_guessed: bool = False
    type: Literal["fixed", "hourly", "unknown"] = "unknown"
    raw: str | None = None


class Duration(BaseModel):
    value: float | None = None
    unit: DurationUnit | None = None
    raw: str | None = None


class RawRef(BaseModel):
    file: str
    line: int


class Job(BaseModel):
    id: str  # "<source>:<external_id>" or "<source>:sha1(url)"
    fingerprint: str | None = None
    source: str
    source_name: str
    provider: str | None = None  # implementation that fetched it (DESIGN-SYSTEM §12)
    source_url: str
    apply_url: str | None = None
    duplicates: list[str] = Field(default_factory=list)

    title: str
    company: str | None = None
    company_url: str | None = None
    company_logo: str | None = None

    category: Category = "job"
    employment_type: EmploymentType = "unknown"
    work_mode: WorkMode = "unknown"
    seniority: Seniority = "unknown"
    location: Location = Field(default_factory=Location)
    remote_scope: RemoteScope | None = None

    salary: Salary | None = None
    budget: Budget | None = None
    duration: Duration | None = None

    skills: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)  # keys of config/topics.yaml, e.g. "photo"
    tags: list[str] = Field(default_factory=list)  # original tags from the source
    description_text: str | None = None
    description_html: str | None = None

    posted_at: datetime | None = None
    expires_at: datetime | None = None
    fetched_at: datetime
    first_seen_at: datetime | None = None
    updated_at: datetime | None = None

    matched_queries: list[str] = Field(default_factory=list)
    raw_ref: RawRef | None = None
    raw: dict[str, Any] | None = None
    scan_run_id: str | None = None
    user_status: Literal["keep", "removed"] | None = None


class JobSummary(BaseModel):
    """Lightweight list item for the results table (no raw / html)."""

    id: str
    source: str
    source_name: str
    provider: str | None = None  # e.g. indeed / linkedin for the JobSpy source
    source_url: str
    title: str
    company: str | None = None
    company_logo: str | None = None
    category: Category
    employment_type: EmploymentType
    work_mode: WorkMode
    seniority: Seniority
    location: Location
    remote_scope: RemoteScope | None = None
    salary: Salary | None = None
    budget: Budget | None = None
    duration: Duration | None = None
    skills: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    posted_at: datetime | None = None
    first_seen_at: datetime | None = None
    duplicate_count: int = 0
    scan_run_id: str | None = None
    user_status: Literal["keep", "removed"] | None = None

    @classmethod
    def from_job(cls, job: Job) -> "JobSummary":
        data = job.model_dump(include=set(cls.model_fields) - {"duplicate_count"})
        return cls(**data, duplicate_count=len(job.duplicates))


class ScrapeQuery(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    types: list[EmploymentType] = Field(default_factory=list)
    category: Literal["job", "gig", "any"] = "any"
    sources: list[str] = Field(default_factory=list)  # empty = sources matching region
    region: str = "ALL"
    location: str | None = None
    remote_only: bool = False
    since_hours: int = 72
    max_per_source: int = 100


class SourceRunResult(BaseModel):
    status: SourceStatus = "queued"
    fetched: int = 0
    new: int = 0
    updated: int = 0
    skipped: int = 0
    ms: int | None = None
    error: str | None = None
    logs: list[str] = Field(default_factory=list)



class Run(BaseModel):
    id: str
    query: ScrapeQuery
    trigger: Literal["manual", "schedule", "cli"] = "manual"
    schedule_id: str | None = None
    status: RunStatus = "queued"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    stopped: bool = False  # the user pressed Stop; whatever was fetched by then was still saved
    sources: dict[str, SourceRunResult] = Field(default_factory=dict)


class Schedule(BaseModel):
    id: str
    name: str
    enabled: bool = True
    query: ScrapeQuery
    every: str = "6h"  # <n>m | <n>h | <n>d, at least 30m
    created_at: datetime | None = None
    last_run_id: str | None = None
    last_run_at: datetime | None = None
    last_status: RunStatus | None = None
    next_run_at: datetime | None = None
    consecutive_failures: int = 0
    paused_reason: str | None = None


class JobsPage(BaseModel):
    items: list[JobSummary]
    total: int
    page: int
    page_size: int
    sort: str = "newest"
    facets: dict[str, dict[str, int]] = Field(default_factory=dict)
