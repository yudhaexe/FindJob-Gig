"""Rule-based classification (DESIGN-SYSTEM §6). No LLM.

`classify(job)` only fills fields that are still unknown/empty, so whatever a connector took
from the source's structured data always wins over regex guesses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache

from core import config
from core.models import Duration, Job, Salary
from scraper import regions
from scraper.money import find_money


@dataclass(frozen=True)
class _Rule:
    value: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class _Topic:
    key: str
    include: tuple[re.Pattern[str], ...]
    exclude: tuple[re.Pattern[str], ...]


def _rules(name: str) -> tuple[_Rule, ...]:
    return tuple(_Rule(r["value"], re.compile(r["pattern"], re.I)) for r in config.load("rules").get(name, []))


@cache
def _compiled() -> dict:
    rules = config.load("rules")
    dur = rules.get("duration", {})
    unit_of = {w: unit for unit, words in dur.get("units", {}).items() for w in words}
    return {
        "employment_type": _rules("employment_type"),
        "work_mode": _rules("work_mode"),
        "seniority": _rules("seniority"),
        "gig": re.compile(rules["gig"], re.I) if rules.get("gig") else None,
        "dur_number": re.compile(dur["number_unit"], re.I) if dur.get("number_unit") else None,
        "dur_context": re.compile(dur.get("context", r"(?!)"), re.I),
        "dur_reject": re.compile(dur.get("reject", r"(?!)"), re.I),
        "dur_units": unit_of,
    }


@cache
def _skills() -> tuple[re.Pattern[str] | None, dict[str, str]]:
    lookup: dict[str, str] = {}
    for canonical, aliases in (config.load("skills") or {}).items():
        for a in [canonical, *(aliases or [])]:
            lookup[str(a).lower()] = canonical
    if not lookup:
        return None, {}
    alts = sorted(lookup, key=len, reverse=True)
    pattern = re.compile(r"(?<![\w+#.])(?:" + "|".join(re.escape(a) for a in alts) + r")(?![\w+#])", re.I)
    return pattern, lookup


@cache
def _topics() -> tuple[_Topic, ...]:
    out = []
    for key, t in (config.load("topics") or {}).items():
        out.append(_Topic(
            key=key,
            include=tuple(re.compile(p, re.I) for p in t.get("include", [])),
            exclude=tuple(re.compile(p, re.I) for p in t.get("exclude", [])),
        ))
    return tuple(out)


def first_match(rules: tuple[_Rule, ...], *texts: str | None) -> str | None:
    """Try each text in order (title before description); within a text the first rule wins."""
    for text in texts:
        if not text:
            continue
        for rule in rules:
            if rule.pattern.search(text):
                return rule.value
    return None


def find_skills(*texts: str | None) -> list[str]:
    pattern, lookup = _skills()
    if pattern is None:
        return []
    found: list[str] = []
    for text in texts:
        for m in pattern.finditer(text or ""):
            s = lookup[m.group(0).lower()]
            if s not in found:
                found.append(s)
    return found


def find_topics(*texts: str | None) -> list[str]:
    out = []
    for topic in _topics():
        for text in texts:
            if not text:
                continue
            for ex in topic.exclude:
                text = ex.sub(" ", text)
            if any(p.search(text) for p in topic.include):
                out.append(topic.key)
                break
    return out


def find_duration(text: str | None) -> Duration | None:
    c = _compiled()
    if not text or c["dur_number"] is None:
        return None
    for m in c["dur_number"].finditer(text):
        before = text[max(0, m.start() - 40) : m.start()]
        after = text[m.end() : m.end() + 40]
        if c["dur_reject"].match(after):
            continue
        if not (c["dur_context"].search(before) or c["dur_context"].search(after)):
            continue
        unit = c["dur_units"].get(m.group(3).lower())
        if not unit:
            continue
        values = [float(v.replace(",", ".")) for v in (m.group(1), m.group(2)) if v]
        value = max(values)
        return Duration(value=int(value) if value.is_integer() else value, unit=unit, raw=m.group(0).strip())
    return None


def classify(job: Job) -> Job:
    c = _compiled()
    title = job.title
    tags = " · ".join(job.tags) if job.tags else None
    desc = job.description_text

    if job.employment_type == "unknown":
        job.employment_type = first_match(c["employment_type"], title, tags, desc) or "unknown"

    if job.work_mode == "unknown":
        job.work_mode = first_match(c["work_mode"], title, job.location.raw, tags, desc) or "unknown"

    if job.seniority == "unknown":
        job.seniority = first_match(c["seniority"], title) or (
            "intern" if job.employment_type == "internship" else "unknown"
        )

    if job.category == "job" and c["gig"] is not None and c["gig"].search(title):
        job.category = "gig"

    if job.location.raw and not job.location.country:
        job.location = regions.parse_location(job.location.raw, city=job.location.city)

    if job.work_mode in ("remote", "hybrid") and job.remote_scope is None:
        job.remote_scope = regions.parse_remote_scope(" · ".join(t for t in (job.location.raw, title) if t))

    if job.duration is None:
        job.duration = find_duration(title) or find_duration(desc)

    if job.salary is None and job.budget is None:
        money = find_money(title)
        if money is None and (m := find_money(desc)) and m.period not in ("unknown", "fixed"):
            money = m  # free text is full of funding rounds and prices; trust it only with a pay period
        if money:
            if job.category == "gig":
                from core.models import Budget
                b_type = "hourly" if money.period == "hour" else ("fixed" if money.period in ("fixed", "day", "week") else "unknown")
                job.budget = Budget(
                    min=money.min, max=money.max, currency=money.currency,
                    currency_guessed=money.currency_guessed, type=b_type,
                    raw=money.raw,
                )
            else:
                job.salary = Salary(
                    min=money.min, max=money.max, currency=money.currency,
                    currency_guessed=money.currency_guessed, period=money.period,
                    raw=money.raw, estimated=True,
                )

    job.skills = list(dict.fromkeys([*job.skills, *find_skills(title, tags, desc)]))
    job.topics = list(dict.fromkeys([*job.topics, *find_topics(title, tags, desc)]))
    return job
