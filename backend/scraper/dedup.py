"""Duplicate detection (DESIGN-SYSTEM §7).

Within a source jobs are unique by `id`. Across sources the same posting shares a
`fingerprint` (normalised title + company). Duplicates are kept on disk and grouped at read
time, so `duplicates` is always consistent with what is currently stored.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

from scraper.text import norm_key

WINDOW = timedelta(days=14)


def fingerprint(title: str | None, company: str | None) -> str | None:
    """None when the company is unknown: titles alone ('Video Editor') collide too often."""
    t, c = norm_key(title), norm_key(company)
    if not t or not c:
        return None
    return hashlib.sha1(f"{t}|{c}".encode()).hexdigest()


def _when(job: dict[str, Any]) -> datetime | None:
    value = job.get("posted_at") or job.get("first_seen_at") or job.get("fetched_at")
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _completeness(job: dict[str, Any]) -> int:
    keys = ("salary", "budget", "description_text", "company_logo", "posted_at", "duration")
    return sum(1 for k in keys if job.get(k)) + len(job.get("skills") or [])


def group_duplicates(jobs: Iterable[dict[str, Any]]) -> dict[str, list[str]]:
    """Map each job id → ids of the same posting on *other* sources (posted within WINDOW).

    The most complete job in a group is listed first in its peers' lists, so the UI can pick it
    as the primary row.
    """
    by_fp: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for j in jobs:
        if j.get("fingerprint"):
            by_fp[j["fingerprint"]].append(j)

    out: dict[str, list[str]] = {}
    for group in by_fp.values():
        if len({j["source"] for j in group}) < 2:
            continue
        group.sort(key=_completeness, reverse=True)
        for j in group:
            when = _when(j)
            peers = []
            for other in group:
                if other["source"] == j["source"]:
                    continue
                other_when = _when(other)
                if when and other_when and abs(when - other_when) > WINDOW:
                    continue
                peers.append(other["id"])
            if peers:
                out[j["id"]] = peers
    return out
