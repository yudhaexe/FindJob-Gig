"""Himalayas remote jobs search API (no auth). Attribution requested: link back to himalayas.app.

Docs: https://himalayas.app/api — search endpoint pages 20 jobs at a time via `page`.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from core.models import Job, Location, RemoteScope, Salary, ScrapeQuery
from scraper.base import Http, Source
from scraper.money import norm_period
from scraper.regions import country_code, country_label, regions_for_country, utc_offsets_label

API = "https://himalayas.app/jobs/api/search"

_EMPLOYMENT = {
    "full time": "fulltime",
    "part time": "parttime",
    "contractor": "contract",
    "contract": "contract",
    "temporary": "temporary",
    "intern": "internship",
    "internship": "internship",
    "freelance": "freelance",
}
_SENIORITY = {
    "entry-level": "junior", "junior": "junior", "mid-level": "mid",
    "senior": "senior", "manager": "lead", "director": "lead", "executive": "lead", "lead": "lead",
}


class Himalayas(Source):
    name = "himalayas"
    display_name = "Himalayas"
    category = "job"
    default_page_size = 20

    async def search(self, keyword: str | None, q: ScrapeQuery, limit: int, http: Http) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if keyword:
            params["q"] = keyword
        # A single-country region narrows the search; wider regions are filtered later by the index.
        if len(q.region) == 2 and country_code(q.region) == q.region:
            params["country"] = country_label(q.region)
        items: list[dict[str, Any]] = []
        page = 1
        while len(items) < limit:
            data = await http.get_json(API, params={**params, "page": page}, headers=self.headers())
            batch = data.get("jobs") or []
            items.extend(batch)
            total = data.get("totalCount") or 0
            if not batch or len(items) >= total:
                break
            page += 1
        return items[:limit]

    def external_id(self, raw: dict[str, Any]) -> str:
        guid = raw.get("guid") or raw.get("applicationLink") or ""
        tail = guid.rstrip("/").rsplit("-", 1)[-1]
        return tail if tail.isdigit() else hashlib.sha1(guid.encode()).hexdigest()[:16]

    def to_job(self, raw: dict[str, Any], fetched_at: datetime) -> Job:
        url = raw.get("applicationLink") or raw.get("guid") or "https://himalayas.app/jobs"

        restrictions = [r for r in raw.get("locationRestrictions") or [] if r]
        countries = [cc for cc in (country_code(r) for r in restrictions) if cc]
        timezones = utc_offsets_label(raw.get("timezoneRestrictions") or [])
        if countries:
            scope = RemoteScope(type="countries", countries=countries, timezones=timezones, raw=", ".join(restrictions))
        elif timezones:
            scope = RemoteScope(type="timezone", timezones=timezones, raw=", ".join(timezones))
        else:
            scope = RemoteScope(type="worldwide", raw="Worldwide")
        single = countries[0] if len(countries) == 1 else None
        location = Location(
            raw=", ".join(restrictions) or "Remote",
            country=single,
            regions=list(regions_for_country(single)),
        )

        salary = None
        if raw.get("minSalary") or raw.get("maxSalary"):
            salary = Salary(min=raw.get("minSalary"), max=raw.get("maxSalary"), currency=raw.get("currency"),
                            period=norm_period(raw.get("salaryPeriod")))

        seniority = next(
            (_SENIORITY[s.lower()] for s in raw.get("seniority") or [] if s.lower() in _SENIORITY), "unknown"
        )
        pub, exp = raw.get("pubDate"), raw.get("expiryDate")
        return Job(
            id=f"{self.name}:{self.external_id(raw)}",
            source=self.name,
            source_name=self.display_name,
            provider=self.provider,
            source_url=raw.get("guid") or url,
            apply_url=url,
            title=raw.get("title") or "(untitled)",
            company=raw.get("companyName"),
            company_url=f"https://himalayas.app/companies/{raw['companySlug']}" if raw.get("companySlug") else None,
            company_logo=raw.get("companyLogo"),
            category="job",
            employment_type=_EMPLOYMENT.get((raw.get("employmentType") or "").lower(), "unknown"),
            work_mode="remote",
            seniority=seniority,
            location=location,
            remote_scope=scope,
            salary=salary,
            tags=[*(raw.get("categories") or []), *(raw.get("parentCategories") or [])],
            description_html=raw.get("description"),
            posted_at=datetime.fromtimestamp(pub, timezone.utc) if pub else None,
            expires_at=datetime.fromtimestamp(exp, timezone.utc) if exp else None,
            fetched_at=fetched_at,
            raw=raw,
        )
