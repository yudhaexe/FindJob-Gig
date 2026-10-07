"""Freelancer.com public projects API (no auth). Gigs with budget in the client's currency.

Docs: https://developers.freelancer.com/docs/projects/projects#projects-search-active
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from core.models import Budget, Duration, Job, Location, RemoteScope, ScrapeQuery
from scraper.base import Http, Source
from scraper.normalize import stable_id
from scraper.regions import country_code, parse_location

API = "https://www.freelancer.com/api/projects/0.1/projects/active/"

# hourly_project_info.duration_enum → upper bound of the range
_DURATION = {
    "less_than_one_week": (1, "week"),
    "one_to_four_weeks": (4, "week"),
    "one_to_three_months": (3, "month"),
    "three_to_six_months": (6, "month"),
    "over_six_months": (6, "month"),
}


class Freelancer(Source):
    name = "freelancer"
    display_name = "Freelancer.com"
    category = "gig"
    default_page_size = 50

    async def search(self, keyword: str | None, q: ScrapeQuery, limit: int, http: Http) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        params: dict[str, Any] = {"full_description": "true", "job_details": "true", "location_details": "true", "compact": "true"}
        if keyword:
            params["query"] = keyword
        if q.since_hours:
            params["from_time"] = int(time.time() - q.since_hours * 3600)
        offset = 0
        while len(items) < limit:
            page = min(self.page_size, limit - len(items))
            data = await http.get_json(API, params={**params, "limit": page, "offset": offset}, headers=self.headers())
            projects = (data.get("result") or {}).get("projects") or []
            items.extend(projects)
            if len(projects) < page:
                break
            offset += len(projects)
        return items[:limit]

    def to_job(self, raw: dict[str, Any], fetched_at: datetime) -> Job:
        url = f"https://www.freelancer.com/projects/{raw.get('seo_url') or raw['id']}"
        currency = (raw.get("currency") or {}).get("code")
        b = raw.get("budget") or {}
        kind = raw.get("type") if raw.get("type") in ("fixed", "hourly") else "unknown"
        lo, hi = b.get("minimum"), b.get("maximum")
        budget = None
        if lo is not None or hi is not None:
            amount = f"{lo:g}–{hi:g}" if lo is not None and hi is not None else f"{lo or hi:g}"
            budget = Budget(min=lo, max=hi, currency=currency, type=kind,
                            raw=f"{currency} {amount} {'/hr' if kind == 'hourly' else kind}".strip())

        duration = None
        hourly = raw.get("hourly_project_info") or {}
        if hourly.get("duration_enum") in _DURATION:
            value, unit = _DURATION[hourly["duration_enum"]]
            duration = Duration(value=value, unit=unit, raw=hourly["duration_enum"].replace("_", " "))

        loc = raw.get("location") or {}
        country_name = (loc.get("country") or {}).get("name")
        place = ", ".join(p for p in (loc.get("vicinity"), loc.get("administrative_area"), country_name) if p)
        local = bool(raw.get("local"))

        submitted = raw.get("submitdate") or raw.get("time_submitted")
        return Job(
            id=stable_id(self.name, raw.get("id"), url),
            source=self.name,
            source_name=self.display_name,
            provider=self.provider,
            source_url=url,
            title=raw.get("title") or "(untitled)",
            category="gig",
            employment_type="freelance",
            work_mode="onsite" if local else "remote",
            location=parse_location(place, country=country_code(country_name), city=loc.get("vicinity")) if place else Location(),
            remote_scope=None if local else RemoteScope(type="worldwide"),
            budget=budget,
            duration=duration,
            tags=[j["name"] for j in raw.get("jobs") or [] if j.get("name")],
            description_text=raw.get("description") or raw.get("preview_description"),
            posted_at=datetime.fromtimestamp(submitted, timezone.utc) if submitted else None,
            fetched_at=fetched_at,
            raw=raw,
        )
