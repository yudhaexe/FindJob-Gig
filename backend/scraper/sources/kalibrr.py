"""Kalibrr job board connector (Southeast Asia / Indonesia focus).

Uses Kalibrr search endpoint: https://www.kalibrr.com/kjs/job_board/search
Public API, no auth required, returns rich structured data including company details,
requirements, location, work from home status, and salary information when available.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.models import Duration, Job, Location, RemoteScope, Salary, ScrapeQuery
from scraper.base import BROWSER_UA, Http, Source
from scraper.money import norm_period
from scraper.normalize import stable_id
from scraper.regions import country_code, parse_location, parse_remote_scope
from scraper.text import html_to_text

API = "https://www.kalibrr.com/kjs/job_board/search"

_TENURE_MAP = {
    "full-time": "fulltime",
    "full time": "fulltime",
    "part-time": "parttime",
    "part time": "parttime",
    "contractual": "contract",
    "contract": "contract",
    "freelance": "freelance",
    "internship": "internship",
    "temporary": "temporary",
}


class Kalibrr(Source):
    name = "kalibrr"
    display_name = "Kalibrr (ID & SEA)"
    category = "job"
    default_page_size = 30
    supports_keyword = True

    def headers(self) -> dict[str, str]:
        return {
            "User-Agent": BROWSER_UA,
            "Accept": "application/json",
        }

    async def search(self, keyword: str | None, q: ScrapeQuery, limit: int, http: Http) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        offset = 0

        while len(items) < limit:
            page_size = min(self.page_size, limit - len(items))
            params: dict[str, Any] = {
                "limit": page_size,
                "offset": offset,
            }
            if keyword:
                params["text"] = keyword

            data = await http.get_json(API, params=params, headers=self.headers())
            jobs = data.get("jobs") or []
            if not jobs:
                break

            items.extend(jobs)
            if len(jobs) < page_size:
                break
            offset += len(jobs)

        return items[:limit]

    def external_id(self, raw: dict[str, Any]) -> str:
        return str(raw.get("id"))

    def to_job(self, raw: dict[str, Any], fetched_at: datetime) -> Job:
        job_id = str(raw.get("id"))
        co = raw.get("company") or {}
        co_slug = co.get("code") or ""
        slug = raw.get("slug") or job_id
        url = f"https://www.kalibrr.com/c/{co_slug}/jobs/{job_id}/{slug}" if co_slug else f"https://www.kalibrr.com/job/{job_id}"

        title = raw.get("name") or "(untitled)"
        company_name = raw.get("company_name") or co.get("name")
        company_url = co.get("url") or (f"https://www.kalibrr.com/c/{co_slug}" if co_slug else None)
        company_logo = co.get("logo_small") or co.get("logo")

        desc_html = raw.get("description") or ""
        qual_html = raw.get("qualifications") or ""
        combined_html = f"{desc_html}\n{qual_html}".strip() or None
        desc_text = html_to_text(combined_html)

        # Work mode & remote scope
        is_wfh = bool(raw.get("is_work_from_home"))
        is_hybrid = bool(raw.get("is_hybrid"))
        work_mode = "remote" if is_wfh else ("hybrid" if is_hybrid else "onsite")

        # Location parsing from google_location or raw components
        g_loc = raw.get("google_location") or {}
        addr = g_loc.get("address_components") or {}
        place_parts = [addr.get("city"), addr.get("region"), addr.get("country")]
        loc_str = ", ".join(p for p in place_parts if p) or None

        c_code = country_code(addr.get("country")) or "ID"
        loc = parse_location(loc_str, country=c_code, city=addr.get("city")) if loc_str else Location(country="ID", regions=["ID", "SEA", "APAC"])
        remote_scope = parse_remote_scope(loc_str or "Indonesia") if work_mode in ("remote", "hybrid") else None

        # Employment type
        tenure = str(raw.get("tenure", "")).lower()
        emp_type = _TENURE_MAP.get(tenure, "unknown")

        # Category: if tenure is freelance or title mentions project based
        category = "gig" if emp_type == "freelance" or "project based" in title.lower() else "job"

        # Salary parsing
        salary = None
        min_sal = raw.get("base_salary")
        max_sal = raw.get("maximum_salary")
        if min_sal is not None or max_sal is not None:
            cur = raw.get("salary_currency") or "IDR"
            interval = norm_period(raw.get("salary_interval") or "month")
            raw_sal = f"{cur} {min_sal or ''}-{max_sal or ''} per {interval}".strip()
            salary = Salary(
                min=float(min_sal) if min_sal is not None else None,
                max=float(max_sal) if max_sal is not None else None,
                currency=cur,
                period=interval,
                raw=raw_sal,
                estimated=False,
            )

        # Skills from job_sds_skills
        skills = []
        for s in raw.get("job_sds_skills") or []:
            name = (s.get("sds_skill") or {}).get("name")
            if name:
                skills.append(name.lower())

        posted_at = None
        for date_key in ("activation_date", "created_at"):
            if raw.get(date_key):
                try:
                    posted_at = datetime.fromisoformat(str(raw[date_key]).replace("Z", "+00:00"))
                    break
                except ValueError:
                    pass

        return Job(
            id=stable_id(self.name, job_id, url),
            source=self.name,
            source_name=self.display_name,
            provider=self.provider,
            source_url=url,
            apply_url=raw.get("apply_redirect_url") or url,
            title=title,
            company=company_name,
            company_url=company_url,
            company_logo=company_logo,
            category=category,
            employment_type=emp_type,
            work_mode=work_mode,
            location=loc,
            remote_scope=remote_scope,
            salary=salary,
            skills=skills,
            tags=[raw.get("function")] if raw.get("function") else [],
            description_text=desc_text,
            description_html=combined_html,
            posted_at=posted_at,
            fetched_at=fetched_at,
            raw=raw,
        )
