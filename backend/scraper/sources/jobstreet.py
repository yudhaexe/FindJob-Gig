"""JobStreet Indonesia via the JSON search API its own website uses (SEEK platform, no auth).

The search response has a teaser, not the full description; the full text needs a per-job
detail request, which is left for later to keep request counts low.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from core.models import Job, Salary, ScrapeQuery
from scraper.base import BROWSER_UA, Http, Source
from scraper.money import find_money
from scraper.normalize import stable_id
from scraper.regions import parse_location

_WORK_TYPES = {
    "full time": "fulltime",
    "part time": "parttime",
    "contract/temp": "contract",
    "contract": "contract",
    "casual/vacation": "temporary",
    "internship": "internship",
}
_ARRANGEMENTS = {"on-site": "onsite", "hybrid": "hybrid", "remote": "remote"}
_DATE_RANGES = (1, 3, 7, 14, 31)  # days the site accepts for `daterange`


class JobStreet(Source):
    name = "jobstreet"
    display_name = "JobStreet ID"
    category = "job"
    default_page_size = 30

    def __init__(self, settings: dict[str, Any] | None = None) -> None:
        super().__init__(settings)
        self.base_url = self.settings.get("base_url", "https://id.jobstreet.com").rstrip("/")
        self.site_key = self.settings.get("site_key", "ID-Main")

    def headers(self) -> dict[str, str]:
        return {"User-Agent": BROWSER_UA, "Accept": "application/json"}

    async def search(self, keyword: str | None, q: ScrapeQuery, limit: int, http: Http) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"siteKey": self.site_key, "locale": "en-ID", "keywords": keyword or ""}
        if q.location:
            params["where"] = q.location
        if q.since_hours:
            days = math.ceil(q.since_hours / 24)
            params["daterange"] = next((d for d in _DATE_RANGES if d >= days), _DATE_RANGES[-1])
        items: list[dict[str, Any]] = []
        page = 1
        while len(items) < limit:
            size = min(self.page_size, limit - len(items))
            data = await http.get_json(
                f"{self.base_url}/api/jobsearch/v5/search",
                params={**params, "page": page, "pageSize": size},
                headers=self.headers(),
            )
            batch = data.get("data") or []
            items.extend(batch)
            if len(batch) < size:
                break
            page += 1
        return items[:limit]

    def to_job(self, raw: dict[str, Any], fetched_at: datetime) -> Job:
        url = f"{self.base_url}/job/{raw['id']}"
        loc = (raw.get("locations") or [{}])[0]

        work_types = [str(w).strip().lower() for w in raw.get("workTypes") or []]
        employment = next((_WORK_TYPES[w] for w in work_types if w in _WORK_TYPES), "unknown")
        arrangements = [
            ((a.get("label") or {}).get("text") or "").lower()
            for a in (raw.get("workArrangements") or {}).get("data") or []
        ]
        mode = next((_ARRANGEMENTS[a] for a in arrangements if a in _ARRANGEMENTS), "unknown")

        salary = None
        if label := (raw.get("salaryLabel") or "").strip():
            money = find_money(label, default_currency="IDR")
            if money:
                salary = Salary(min=money.min, max=money.max, currency=money.currency,
                                currency_guessed=money.currency_guessed, period=money.period, raw=label)

        teaser = raw.get("teaser") or ""
        bullets = [b for b in raw.get("bulletPoints") or [] if b]
        description = "\n".join([teaser, *(f"• {b}" for b in bullets)]).strip() or None

        tags = []
        for c in raw.get("classifications") or []:
            for key in ("classification", "subclassification"):
                if d := (c.get(key) or {}).get("description"):
                    tags.append(d)

        employer = raw.get("employer") or {}
        listed = raw.get("listingDate")
        return Job(
            id=stable_id(self.name, raw.get("id"), url),
            source=self.name,
            source_name=self.display_name,
            provider=self.provider,
            source_url=url,
            title=raw.get("title") or "(untitled)",
            company=(raw.get("advertiser") or {}).get("description") or raw.get("companyName"),
            company_url=employer.get("companyUrl"),
            company_logo=(raw.get("branding") or {}).get("serpLogoUrl"),
            category="job",
            employment_type=employment,
            work_mode=mode,
            location=parse_location(loc.get("label"), country=loc.get("countryCode")),
            salary=salary,
            tags=tags,
            description_text=description,
            posted_at=datetime.fromisoformat(listed.replace("Z", "+00:00")) if listed else None,
            fetched_at=fetched_at,
            raw=raw,
        )
