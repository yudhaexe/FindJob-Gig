"""Public Telegram job channels connector (Indonesia).

Scrapes public channels via t.me/s/<channel> HTML preview without needing MTProto or bot token.
Channels supported:
- loker_id
- lokerindonesia
- idrecruitments
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Any

from core.models import Job, Location, RemoteScope, Salary, ScrapeQuery
from scraper.base import BROWSER_UA, Http, Source
from scraper.money import find_money
from scraper.normalize import stable_id
from scraper.regions import parse_location, parse_remote_scope
from scraper.text import html_to_text

DEFAULT_CHANNELS = ["loker_id", "idrecruitments"]


class _TelegramHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.posts: list[dict[str, Any]] = []
        self._current_text: list[str] = []
        self._current_link: str | None = None
        self._current_time: str | None = None
        self._in_text = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        classes = attr.get("class", "") or ""

        if tag == "div" and "tgme_widget_message_text" in classes:
            self._in_text = True
            self._current_text = []
        elif self._in_text and tag == "br":
            self._current_text.append("\n")
        elif tag == "a" and "tgme_widget_message_date" in classes:
            self._current_link = attr.get("href")
        elif tag == "time" and "datetime" in attr:
            self._current_time = attr.get("datetime")

    def handle_endtag(self, tag: str) -> None:
        if self._in_text and tag == "div":
            self._in_text = False
            raw_body = "".join(self._current_text).strip()
            if raw_body and self._current_link:
                self.posts.append({
                    "url": self._current_link,
                    "body": raw_body,
                    "time": self._current_time,
                })
            self._current_link = None
            self._current_time = None

    def handle_data(self, data: str) -> None:
        if self._in_text:
            self._current_text.append(data)


class Telegram(Source):
    name = "telegram"
    display_name = "Telegram Job Channels (ID)"
    category = "job"
    default_page_size = 25
    supports_keyword = True

    def __init__(self, settings: dict[str, Any] | None = None) -> None:
        super().__init__(settings)
        self.channels: list[str] = self.settings.get("channels", DEFAULT_CHANNELS)

    def headers(self) -> dict[str, str]:
        return {
            "User-Agent": BROWSER_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    async def search(self, keyword: str | None, q: ScrapeQuery, limit: int, http: Http) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        kw_lower = keyword.lower() if keyword else None

        errors: list[str] = []
        for chan in self.channels:
            if len(items) >= limit:
                break
            url = f"https://t.me/s/{chan}"
            try:
                resp = await http.get(url, headers=self.headers())
            except Exception as e:
                errors.append(f"@{chan}: {e}")
                continue

            parser = _TelegramHTMLParser()
            parser.feed(resp.text)

            for post in reversed(parser.posts):  # newest first
                if len(items) >= limit:
                    break
                body = post["body"]
                if kw_lower and kw_lower not in body.lower():
                    continue
                items.append({
                    "id": post["url"].rstrip("/").split("/")[-1],
                    "channel": chan,
                    "url": post["url"],
                    "body": body,
                    "time": post.get("time"),
                })

        if errors and not items:
            from scraper.base import SourceError
            raise SourceError("; ".join(errors))

        return items[:limit]

    def external_id(self, raw: dict[str, Any]) -> str:
        return f"{raw.get('channel')}_{raw.get('id')}"

    def to_job(self, raw: dict[str, Any], fetched_at: datetime) -> Job:
        url = raw.get("url") or f"https://t.me/s/{raw.get('channel')}"
        chan = raw.get("channel") or "telegram"
        body = raw.get("body") or ""

        # First line is usually title or company
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        title = lines[0] if lines else "Lowongan Kerja Telegram"
        company = lines[1] if len(lines) > 1 and len(lines[1]) < 60 else None

        # Clean title if too long
        if len(title) > 90:
            title = title[:87] + "..."

        posted_at = None
        if raw.get("time"):
            try:
                posted_at = datetime.fromisoformat(raw["time"].replace("Z", "+00:00"))
            except ValueError:
                pass

        money = find_money(body)
        salary = None
        if money and money.period not in ("unknown", "fixed"):
            salary = Salary(
                min=money.min,
                max=money.max,
                currency=money.currency,
                period=money.period,
                raw=money.raw,
                estimated=True,
            )

        return Job(
            id=stable_id(self.name, self.external_id(raw), url),
            source=self.name,
            source_name=f"Telegram (@{chan})",
            provider=self.provider,
            source_url=url,
            apply_url=url,
            title=title,
            company=company,
            category="job",
            employment_type="unknown",
            work_mode="unknown",
            location=Location(country="ID", regions=["ID", "SEA", "APAC"]),
            salary=salary,
            tags=[f"@{chan}", "telegram"],
            description_text=body,
            posted_at=posted_at,
            fetched_at=fetched_at,
            raw=raw,
        )
