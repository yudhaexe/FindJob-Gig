"""JobSpy multi-board connector (Indeed, Glassdoor, ZipRecruiter, LinkedIn).

Integrates python-jobspy (speedyapply/JobSpy) for large job board scraping.
Google Jobs is excluded due to upstream breakage in 1.2.0.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from core.models import Duration, Job, Location, RemoteScope, Salary, ScrapeQuery
from scraper.base import Http, Source
from scraper.money import norm_period
from scraper.normalize import stable_id
from scraper.regions import country_code, country_label, parse_location, parse_remote_scope


class JobSpy(Source):
    name = "jobspy"
    display_name = "JobSpy (Indeed / Glassdoor / LinkedIn)"
    category = "job"
    default_page_size = 20
    supports_keyword = True

    def __init__(self, settings: dict[str, Any] | None = None) -> None:
        super().__init__(settings)
        # Default sites: indeed, glassdoor, zip_recruiter, linkedin (no google)
        self.sites: list[str] = self.settings.get("sites", ["indeed", "glassdoor", "zip_recruiter", "linkedin"])

    async def search(self, keyword: str | None, q: ScrapeQuery, limit: int, http: Http) -> list[dict[str, Any]]:
        # Run blocking scrape_jobs in a thread executor
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._scrape_sync, keyword, q, limit)

    def _scrape_sync(self, keyword: str | None, q: ScrapeQuery, limit: int) -> list[dict[str, Any]]:
        from jobspy import scrape_jobs

        search_term = keyword or "software"
        country_indeed = None
        location = q.location

        # If region is an ISO 2-letter country code, map to country_indeed
        if len(q.region) == 2 and country_code(q.region) == q.region:
            country_indeed = country_label(q.region)
            if not location:
                location = country_indeed
        elif q.region == "ID":
            country_indeed = "Indonesia"
            if not location:
                location = "Indonesia"
        elif q.region in ("NA", "US"):
            country_indeed = "USA"
            if not location:
                location = "USA"

        # Map scrape types
        job_type = None
        if q.types:
            if "contract" in q.types or "freelance" in q.types:
                job_type = "contract"
            elif "parttime" in q.types:
                job_type = "parttime"
            elif "internship" in q.types:
                job_type = "internship"
            elif "fulltime" in q.types:
                job_type = "fulltime"

        hours_old = q.since_hours if q.since_hours and q.since_hours > 0 else None

        # Filter out sites that are incompatible or failing for certain regions
        active_sites = list(self.sites)
        if "google" in active_sites:
            active_sites.remove("google")

        # ZipRecruiter is primarily US/UK/CA
        if country_indeed and country_indeed.lower() not in ("usa", "united states", "canada", "united kingdom") and "zip_recruiter" in active_sites:
            active_sites.remove("zip_recruiter")

        try:
            df = scrape_jobs(
                site_name=active_sites,
                search_term=search_term,
                location=location,
                country_indeed=country_indeed,
                is_remote=q.remote_only,
                job_type=job_type,
                results_wanted=limit,
                hours_old=hours_old,
                verbose=0,
                description_format="markdown",
            )
        except Exception:
            return []

        if df is None or df.empty:
            return []

        records = df.to_dict("records")
        clean_records = []
        for r in records:
            clean_records.append({
                k: (str(v) if v is not None and str(v) not in ("None", "nan") else None)
                for k, v in r.items()
            })
        return clean_records[:limit]

    def external_id(self, raw: dict[str, Any]) -> str:
        return str(raw.get("id") or raw.get("job_url") or "")

    def to_job(self, raw: dict[str, Any], fetched_at: datetime) -> Job:
        site = raw.get("site") or "jobspy"
        url = raw.get("job_url") or raw.get("job_url_direct") or ""
        title = raw.get("title") or "(untitled)"
        company = raw.get("company")
        loc_str = raw.get("location")
        desc = raw.get("description")
        is_remote = str(raw.get("is_remote", "")).lower() in ("true", "1")

        posted_at = None
        if raw.get("date_posted"):
            try:
                posted_at = datetime.fromisoformat(str(raw["date_posted"]).replace("Z", "+00:00"))
            except ValueError:
                pass

        # Parse salary if structured
        salary = None
        min_amt = float(raw["min_amount"]) if raw.get("min_amount") else None
        max_amt = float(raw["max_amount"]) if raw.get("max_amount") else None
        currency = raw.get("currency")
        interval = norm_period(raw.get("interval"))
        if min_amt is not None or max_amt is not None:
            raw_sal = f"{currency or ''} {min_amt or ''}-{max_amt or ''} {interval}".strip()
            salary = Salary(
                min=min_amt,
                max=max_amt,
                currency=currency,
                period=interval,
                raw=raw_sal,
                estimated=False,
            )

        # Work mode
        work_mode = "remote" if is_remote else ("unknown" if not loc_str else "onsite")

        # Location and remote scope
        loc = parse_location(loc_str) if loc_str else Location()
        remote_scope = parse_remote_scope(loc_str or "remote") if is_remote else None

        job_type = (raw.get("job_type") or "").lower()
        emp_type = "unknown"
        if "contract" in job_type:
            emp_type = "contract"
        elif "part" in job_type:
            emp_type = "parttime"
        elif "full" in job_type:
            emp_type = "fulltime"
        elif "intern" in job_type:
            emp_type = "internship"

        return Job(
            id=stable_id(self.name, f"{site}:{raw.get('id')}", url),
            source=self.name,
            source_name=f"{self.display_name} ({site.title()})",
            provider=site,
            source_url=url,
            apply_url=raw.get("job_url_direct") or url,
            title=title,
            company=company,
            company_url=raw.get("company_url") or raw.get("company_url_direct"),
            company_logo=raw.get("company_logo"),
            category="job",
            employment_type=emp_type,
            work_mode=work_mode,
            location=loc,
            remote_scope=remote_scope,
            salary=salary,
            tags=[site],
            description_text=desc,
            posted_at=posted_at,
            fetched_at=fetched_at,
            raw=raw,
        )
