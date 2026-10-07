"""Connector contract (DESIGN-SYSTEM §11).

A connector is one file in `scraper/sources/` with a `Source` subclass. It only knows how to
talk to its site (`search`) and how to map one raw item to a `Job` (`to_job`). Keyword loops,
raw storage, classification, filtering and upserts are the runner's job.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any, ClassVar, Literal

import httpx

from core.models import Job, ScrapeQuery

USER_AGENT = "FindJobGig/0.1 (personal job aggregator; local use)"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0 Safari/537.36"
)


class SourceError(RuntimeError):
    """A failure worth showing in the run log (blocked, bad response, ...)."""


class SourceBlocked(SourceError):
    """403/429 that retries did not fix — the provider should be skipped for now."""


class Http:
    """Per-source HTTP helper: waits `min_interval` between requests and retries transient errors."""

    def __init__(self, client: httpx.AsyncClient, min_interval: float, retries: int = 3) -> None:
        self.client = client
        self.min_interval = min_interval
        self.retries = retries
        self.requests = 0
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def _throttle(self) -> None:
        async with self._lock:
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        delay = 2.0
        for attempt in range(1, self.retries + 1):
            await self._throttle()
            self.requests += 1
            try:
                r = await self.client.get(url, **kwargs)
            except httpx.TransportError as e:  # DNS hiccups, resets, timeouts
                if attempt == self.retries:
                    raise SourceError(f"{type(e).__name__}: {e}") from e
                await asyncio.sleep(delay)
                delay *= 2
                continue
            if r.status_code == 429 or r.status_code >= 500:
                if attempt == self.retries:
                    if r.status_code == 429:
                        raise SourceBlocked("429 Too Many Requests")
                    raise SourceError(f"HTTP {r.status_code}")
                retry_after = r.headers.get("retry-after", "")
                await asyncio.sleep(min(float(retry_after), 30) if retry_after.isdigit() else delay)
                delay *= 2
                continue
            if r.status_code == 403:
                raise SourceBlocked("403 Forbidden")
            if r.status_code >= 400:
                raise SourceError(f"HTTP {r.status_code} for {r.url}")
            return r
        raise SourceError("unreachable")

    async def get_json(self, url: str, **kwargs: Any) -> Any:
        r = await self.get(url, **kwargs)
        try:
            return r.json()
        except ValueError as e:
            raise SourceError(f"Invalid JSON from {r.url}") from e


class Source:
    name: ClassVar[str]
    display_name: ClassVar[str]
    category: ClassVar[Literal["job", "gig", "mixed"]] = "job"
    supports_keyword: ClassVar[bool] = True
    default_page_size: ClassVar[int] = 30

    def __init__(self, settings: dict[str, Any] | None = None) -> None:
        s = settings or {}
        self.settings = s
        self.display_name = s.get("display_name", self.display_name)
        self.markets: list[str] = s.get("markets", ["ALL"])
        self.min_interval: float = float(s.get("min_interval", 1.0))
        self.page_size: int = int(s.get("page_size", self.default_page_size))
        self.attribution: str | None = s.get("attribution")
        self.enabled: bool = bool(s.get("enabled", True))
        self.provider = self.name

    async def search(self, keyword: str | None, q: ScrapeQuery, limit: int, http: Http) -> list[dict[str, Any]]:
        """Return up to `limit` raw items for one keyword (None = no keyword)."""
        raise NotImplementedError

    def external_id(self, raw: dict[str, Any]) -> str:
        return str(raw["id"])

    def to_job(self, raw: dict[str, Any], fetched_at: datetime) -> Job:
        raise NotImplementedError

    def headers(self) -> dict[str, str]:
        return {"User-Agent": USER_AGENT, "Accept": "application/json"}
