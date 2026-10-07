"""Reddit RSS & OAuth connector for freelance & gig communities.

Subreddits supported:
- r/forhire
- r/slavelabour
- r/PhotoshopRequest
- r/VideoEditingRequests
- r/freelance_forhire

Notes:
- Reddit blocks anonymous JSON (403), RSS works with custom User-Agent and throttled requests.
- Rate limits: Reddit RSS is sensitive, so min_interval is set to 3.0s or higher.
- Posts with [HIRING], [TASK], [PAID] are gigs / hiring posts.
- Posts with [FOR HIRE], [OFFER] are job seeker posts and are filtered out.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from core.models import Budget, Duration, Job, Location, RemoteScope, ScrapeQuery
from scraper.base import BROWSER_UA, Http, Source, SourceBlocked, SourceError
from scraper.money import find_money
from scraper.normalize import stable_id
from scraper.text import html_to_text

# Subreddit mapping: name -> default category
DEFAULT_SUBREDDITS = [
    "forhire",
    "slavelabour",
    "PhotoshopRequest",
    "VideoEditingRequests",
    "freelance_forhire",
]

# Patterns for HIRING / BUYER posts
HIRING_RE = re.compile(
    r"^\s*\[(hiring|task|paid|request)\]|"
    r"\b\[(hiring|task|paid|request)\]\b|"
    r"^\s*(hiring|task|paid|request):",
    re.I,
)

# Patterns for FOR HIRE / SELLER posts to discard
FOR_HIRE_RE = re.compile(
    r"^\s*\[(for[ -]?hire|offer)\]|"
    r"\b\[(for[ -]?hire|offer)\]\b|"
    r"^\s*(for[ -]?hire|offer):",
    re.I,
)

# Strip bracket tag from title: "[Hiring] Need video editor" -> "Need video editor"
CLEAN_TITLE_RE = re.compile(r"^\s*\[[^\]]+\]\s*[:-]?\s*", re.I)


class Reddit(Source):
    name = "reddit"
    display_name = "Reddit Gigs"
    category = "gig"
    default_page_size = 25
    supports_keyword = True

    def __init__(self, settings: dict[str, Any] | None = None) -> None:
        super().__init__(settings)
        self.subreddits: list[str] = self.settings.get("subreddits", DEFAULT_SUBREDDITS)
        self.min_interval = max(self.min_interval, 2.5)

    def headers(self) -> dict[str, str]:
        return {
            "User-Agent": BROWSER_UA,
            "Accept": "application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
        }

    async def search(self, keyword: str | None, q: ScrapeQuery, limit: int, http: Http) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        kw_lower = keyword.lower() if keyword else None

        errors: list[str] = []
        for sub in self.subreddits:
            if len(items) >= limit:
                break
            url = f"https://www.reddit.com/r/{sub}.rss"
            try:
                resp = await http.get(url, headers=self.headers())
            except SourceBlocked as e:
                errors.append(f"r/{sub} blocked: {e}")
                continue
            except SourceError as e:
                errors.append(f"r/{sub} error: {e}")
                continue

            entries = self._parse_rss(resp.text, sub)
            for entry in entries:
                if len(items) >= limit:
                    break
                # Keyword check if provided
                if kw_lower:
                    full_text = f"{entry.get('title', '')} {entry.get('content_text', '')}".lower()
                    if kw_lower not in full_text:
                        continue
                items.append(entry)

        if errors and not items:
            raise SourceError("; ".join(errors))
        return items[:limit]

    def _parse_rss(self, xml_text: str, subreddit: str) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
        except Exception:
            return entries

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for node in root.findall("atom:entry", ns):
            title = node.findtext("atom:title", default="", namespaces=ns).strip()
            # Skip seeker / offer posts
            if FOR_HIRE_RE.search(title):
                continue

            # In subreddits like forhire and slavelabour, require hiring/task tag
            # In PhotoshopRequest or VideoEditingRequests, posts are requests by default unless marked for hire
            is_request_sub = subreddit.lower() in ("photoshoprequest", "videoeditingrequests")
            if not is_request_sub and not HIRING_RE.search(title):
                # Also check slavelabour / forhire meta announcements
                continue

            entry_id = node.findtext("atom:id", default="", namespaces=ns).strip()
            link_elem = node.find("atom:link", ns)
            link = link_elem.attrib.get("href", "") if link_elem is not None else ""
            content_html = node.findtext("atom:content", default="", namespaces=ns).strip()
            updated_str = node.findtext("atom:updated", default="", namespaces=ns) or node.findtext("atom:published", default="", namespaces=ns)
            author_elem = node.find("atom:author/atom:name", ns)
            author = author_elem.text.strip() if author_elem is not None and author_elem.text else ""

            content_text = html_to_text(html.unescape(content_html))

            entries.append({
                "id": entry_id,
                "title": title,
                "url": link,
                "content_html": content_html,
                "content_text": content_text,
                "author": author,
                "subreddit": subreddit,
                "updated": updated_str,
            })
        return entries

    def external_id(self, raw: dict[str, Any]) -> str:
        # raw['id'] is like 't3_1wzxoif' or full URL
        raw_id = raw.get("id") or ""
        if raw_id.startswith("t3_"):
            return raw_id[3:]
        return raw_id.rsplit("/", 1)[-1] or stable_id(self.name, raw.get("url"))

    def to_job(self, raw: dict[str, Any], fetched_at: datetime) -> Job:
        raw_title = raw.get("title") or "(untitled)"
        clean_title = CLEAN_TITLE_RE.sub("", raw_title).strip() or raw_title
        url = raw.get("url") or f"https://www.reddit.com/r/{raw.get('subreddit')}"
        sub = raw.get("subreddit", "reddit")

        posted_at = None
        if raw.get("updated"):
            try:
                posted_at = datetime.fromisoformat(raw["updated"].replace("Z", "+00:00"))
            except ValueError:
                pass

        # Parse budget from title or description
        budget = None
        money = find_money(raw_title) or find_money(raw.get("content_text"))
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

        tags = [f"r/{sub}"]
        if raw.get("author"):
            tags.append(raw["author"])

        return Job(
            id=stable_id(self.name, self.external_id(raw), url),
            source=self.name,
            source_name=f"Reddit (r/{sub})",
            provider=self.provider,
            source_url=url,
            apply_url=url,
            title=clean_title,
            category="gig",
            employment_type="freelance",
            work_mode="remote",  # Vast majority of reddit gigs are remote
            location=Location(),
            remote_scope=RemoteScope(type="worldwide"),
            budget=budget,
            tags=tags,
            description_text=raw.get("content_text"),
            description_html=raw.get("content_html"),
            posted_at=posted_at,
            fetched_at=fetched_at,
            raw=raw,
        )
