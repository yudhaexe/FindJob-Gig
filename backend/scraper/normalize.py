"""Shared post-processing after a connector's `to_job()`: text cleanup, fingerprint, classify."""

from __future__ import annotations

import hashlib

from core.models import Job
from scraper import dedup
from scraper.classify import classify
from scraper.text import clean_text, html_to_text, looks_like_html


def stable_id(source: str, external_id: str | int | None, url: str) -> str:
    if external_id not in (None, ""):
        return f"{source}:{external_id}"
    return f"{source}:{hashlib.sha1(url.encode()).hexdigest()[:16]}"


def finalize(job: Job) -> Job:
    job.title = " ".join(job.title.split())
    job.company = clean_text(job.company)
    if job.description_html and not job.description_text:
        job.description_text = html_to_text(job.description_html)
    elif job.description_text and looks_like_html(job.description_text):
        job.description_html = job.description_html or job.description_text
        job.description_text = html_to_text(job.description_text)
    else:
        job.description_text = clean_text(job.description_text)
    job.tags = list(dict.fromkeys(t.strip() for t in job.tags if t and t.strip()))
    job.apply_url = job.apply_url or job.source_url
    job.fingerprint = dedup.fingerprint(job.title, job.company)
    return classify(job)
