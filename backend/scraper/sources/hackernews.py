"""Hacker News Freelancer monthly threads connector via Algolia HN Search API.

Source: Algolia API (https://hn.algolia.com/api)
Targets comments under "Ask HN: Freelancer? Seeking freelancer?" threads starting with:
"SEEKING FREELANCER" (clients hiring freelancers).

Notes:
- Completely public, no auth required, fast response times.
- "SEEKING WORK" comments are job seekers and are filtered out.
- Comments are parsed for company name, role/title, remote status, location, and rates.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any

from core.models import Budget, Duration, Job, Location, RemoteScope, ScrapeQuery
from scraper.base import Http, Source
from scraper.money import find_money
from scraper.normalize import stable_id
from scraper.regions import parse_location, parse_remote_scope
from scraper.text import html_to_text

ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"

SEEKING_FREELANCER_RE = re.compile(r"^\s*SEEKING\s+FREELANCER\b", re.I)


class HackerNews(Source):
    name = "hackernews"
    display_name = "Hacker News Freelancer"
    category = "gig"
    default_page_size = 30
    supports_keyword = True

    async def search(self, keyword: str | None, q: ScrapeQuery, limit: int, http: Http) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 0
        hits_per_page = min(50, limit)

        # Algolia query
        # We query comments that match "SEEKING FREELANCER"
        query_str = f'"SEEKING FREELANCER" {keyword}' if keyword else '"SEEKING FREELANCER"'

        while len(items) < limit:
            params: dict[str, Any] = {
                "query": query_str,
                "tags": "comment",
                "hitsPerPage": hits_per_page,
                "page": page,
            }
            if q.since_hours:
                min_created = int(datetime.now(timezone.utc).timestamp() - (q.since_hours * 3600))
                params["numericFilters"] = f"created_at_i>{min_created}"

            data = await http.get_json(ALGOLIA_SEARCH_URL, params=params, headers=self.headers())
            hits = data.get("hits") or []
            if not hits:
                break

            for hit in hits:
                raw_text = hit.get("comment_text") or ""
                # Verify that it is indeed a hiring post (SEEKING FREELANCER)
                clean_txt = html_to_text(html.unescape(raw_text)) or ""
                if not SEEKING_FREELANCER_RE.search(clean_txt):
                    continue

                items.append({
                    "id": str(hit.get("objectID")),
                    "story_id": str(hit.get("story_id")),
                    "story_title": hit.get("story_title"),
                    "author": hit.get("author"),
                    "created_at": hit.get("created_at"),
                    "comment_html": raw_text,
                    "comment_text": clean_txt,
                })
                if len(items) >= limit:
                    break

            if page >= (data.get("nbPages", 1) - 1):
                break
            page += 1

        return items[:limit]

    def external_id(self, raw: dict[str, Any]) -> str:
        return str(raw["id"])

    def to_job(self, raw: dict[str, Any], fetched_at: datetime) -> Job:
        comment_id = raw["id"]
        url = f"https://news.ycombinator.com/item?id={comment_id}"
        full_text = raw.get("comment_text") or ""

        # First line usually contains metadata:
        # e.g.: "SEEKING FREELANCER | Company | Role | Location | REMOTE"
        first_line = full_text.splitlines()[0] if full_text else ""
        parts = [p.strip() for p in first_line.split("|") if p.strip()]

        title = "Freelance Project"
        company = None
        location_raw = None
        work_mode = "remote"

        # Try to parse header pipes
        if len(parts) >= 2:
            # parts[0] is SEEKING FREELANCER
            rem = parts[1:]
            if len(rem) == 1:
                title = rem[0]
            elif len(rem) >= 2:
                raw_co = rem[0]
                # If company has parens like "Tiger Tracks (REMOTE, US/EU timezones)", split them
                if "(" in raw_co and raw_co.endswith(")"):
                    co_name, paren = raw_co[:-1].split("(", 1)
                    company = co_name.strip()
                    location_raw = paren.strip()
                else:
                    company = raw_co

                title = rem[1]
                if len(rem) >= 3:
                    rest_loc = " | ".join(rem[2:])
                    location_raw = f"{location_raw} | {rest_loc}" if location_raw else rest_loc
        else:
            # No pipes, first line after SEEKING FREELANCER
            cleaned_first = SEEKING_FREELANCER_RE.sub("", first_line).strip(" :-–|")
            if cleaned_first:
                title = cleaned_first

        # Remote determination
        if location_raw and ("onsite" in location_raw.lower() or "on-site" in location_raw.lower()) and "remote" not in location_raw.lower():
            work_mode = "onsite"
        elif "hybrid" in (location_raw or "").lower():
            work_mode = "hybrid"

        posted_at = None
        if raw.get("created_at"):
            try:
                posted_at = datetime.fromisoformat(raw["created_at"].replace("Z", "+00:00"))
            except ValueError:
                pass

        money = find_money(title) or find_money(full_text)
        budget = None
        if money:
            b_type = "hourly" if money.period == "hour" else ("fixed" if money.period in ("fixed", "day", "week") else "unknown")
            budget = Budget(
                min=money.min,
                max=money.max,
                currency=money.currency,
                currency_guessed=money.currency_guessed,
                type=b_type,
                raw=money.raw,
            )

        loc = parse_location(location_raw) if location_raw else Location()
        remote_scope = parse_remote_scope(location_raw or "remote") if work_mode in ("remote", "hybrid") else None

        tags = ["HN", "whoishiring"]
        if raw.get("author"):
            tags.append(f"user:{raw['author']}")

        return Job(
            id=stable_id(self.name, comment_id, url),
            source=self.name,
            source_name=self.display_name,
            provider=self.provider,
            source_url=url,
            apply_url=url,
            title=title,
            company=company,
            category="gig",
            employment_type="freelance",
            work_mode=work_mode,
            location=loc,
            remote_scope=remote_scope,
            budget=budget,
            tags=tags,
            description_text=full_text,
            description_html=raw.get("comment_html"),
            posted_at=posted_at,
            fetched_at=fetched_at,
            raw=raw,
        )
