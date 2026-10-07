"""In-memory search index over data/jobs/*.jsonl (DESIGN-SYSTEM §5).

The index keeps a light copy of every job (no `raw`, no `description_html`) plus folded
token strings for search. It reloads itself when a jobs file changes (mtime/size), so the
CLI can scrape while the API is running. Full jobs are read from disk only by `get()`.

Query syntax: `react -wordpress "senior engineer" photo*`
    terms are ANDed · `-x` excludes · quotes make a phrase · `*` suffix is a prefix match.
"""

from __future__ import annotations

import re
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import cache
from typing import Any

from core import config
from core.models import Job, JobSummary
from scraper import regions
from scraper.dedup import group_duplicates
from scraper.text import fold
from storage.filestore import FileStore

# Field weights for relevance (title ×3, skills ×2, company ×2, description ×1).
_WEIGHTS = {"title": 3.0, "skills": 2.0, "company": 2.0, "desc": 1.0}
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#]*(?:\.[a-z0-9+#]+)*")
_QUERY_RE = re.compile(r'(-?)"([^"]*)"|(-?)(\S+)')
_STOP = frozenset(
    "a an and the of for in on at to with or by is are be as from "
    "dan di ke dari untuk yang dengan atau".split()
)

# Fixed period factors → per month (DESIGN-SYSTEM §5b). Period conversion only, never FX.
PER_MONTH = {"hour": 173.0, "day": 173.0 / 8, "week": 52.0 / 12, "month": 1.0, "year": 1 / 12}

FACETS = ("category", "type", "mode", "source", "country", "seniority", "currency")
SORTS = ("relevance", "newest", "salary_desc", "company")


def tokens(text: str | None) -> list[str]:
    return _TOKEN_RE.findall(fold(text)) if text else []


@cache
def _skill_aliases() -> dict[str, str]:
    """Folded alias (and canonical name) → canonical skill, from config/skills.yaml."""
    out: dict[str, str] = {}
    for canonical, aliases in (config.load("skills") or {}).items():
        for name in [canonical, *(aliases or [])]:
            out[" ".join(tokens(name))] = canonical
    return out


# ── documents ──────────────────────────────────────────────────────────────


@dataclass
class Doc:
    summary: dict[str, Any]  # JobSummary fields, JSON-ready
    fields: dict[str, str]  # field → " tok tok tok " (padded for phrase lookup)
    sets: dict[str, frozenset[str]]
    skills: frozenset[str]  # canonical skill names as stored on the job
    when: float  # posted_at, else first_seen_at (epoch seconds), 0 if unknown
    fetched: float
    countries: frozenset[str]
    currency: str | None
    money_period: str | None  # hour/day/week/month/year/fixed
    money_value: float | None  # max (or min) in its own period


def _ts(value: Any) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _money(d: dict[str, Any]) -> tuple[str | None, str | None, float | None]:
    if s := d.get("salary"):
        value = s.get("max") or s.get("min")
        return s.get("currency"), s.get("period") if s.get("period") != "unknown" else None, value
    if b := d.get("budget"):
        value = b.get("max") or b.get("min")
        period = {"hourly": "hour", "fixed": "fixed"}.get(b.get("type") or "")
        return b.get("currency"), period, value
    return None, None, None


def _doc(d: dict[str, Any], duplicates: list[str]) -> Doc:
    summary = {k: d.get(k) for k in JobSummary.model_fields if k != "duplicate_count"}
    summary["duplicate_count"] = len(duplicates)
    summary["duplicates"] = duplicates
    skills = [s for s in d.get("skills") or [] if s]
    texts = {
        "title": d.get("title"),
        "company": d.get("company"),
        "skills": " ".join(skills),
        "desc": d.get("description_text"),
    }
    fields, sets = {}, {}
    for name, text in texts.items():
        toks = tokens(text)
        fields[name] = f" {' '.join(toks)} "
        sets[name] = frozenset(toks)
    loc = d.get("location") or {}
    scope = d.get("remote_scope") or {}
    countries = {loc.get("country")} | set(scope.get("countries") or [])
    currency, period, value = _money(d)
    return Doc(
        summary=summary,
        fields=fields,
        sets=sets,
        skills=frozenset(fold(s) for s in skills),
        when=_ts(d.get("posted_at")) or _ts(d.get("first_seen_at")),
        fetched=_ts(d.get("fetched_at")),
        countries=frozenset(c for c in countries if c),
        currency=currency,
        money_period=period,
        money_value=value,
    )


# ── query parsing ──────────────────────────────────────────────────────────


def _variants(tok: str) -> frozenset[str]:
    """Naive singular/plural forms: editor ↔ editors, class ↔ classes."""
    out = {tok, f"{tok}s", f"{tok}es"}
    if len(tok) > 3 and tok.endswith("s"):
        out.add(tok[:-1])
        if tok.endswith("es"):
            out.add(tok[:-2])
    return frozenset(out)


@dataclass
class Term:
    text: str  # space-joined folded tokens
    prefix: bool = False
    skill: str | None = None  # canonical skill this term is an alias of
    forms: frozenset[str] = frozenset()

    @property
    def is_phrase(self) -> bool:
        return " " in self.text


@dataclass
class ParsedQuery:
    include: list[Term] = field(default_factory=list)
    exclude: list[Term] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.include or self.exclude)


def parse_query(q: str | None) -> ParsedQuery:
    out = ParsedQuery()
    for m in _QUERY_RE.finditer(q or ""):
        neg = bool(m.group(1) or m.group(3))
        raw = m.group(2) if m.group(2) is not None else m.group(4)
        prefix = m.group(4) is not None and raw.endswith("*")
        toks = tokens(raw)
        if not toks:
            continue
        if m.group(2) is None and len(toks) == 1 and toks[0] in _STOP:
            continue
        text = " ".join(toks)
        canonical = _skill_aliases().get(text)
        term = Term(text=text, prefix=prefix and len(toks) == 1, skill=fold(canonical) if canonical else None,
                    forms=_variants(text) if len(toks) == 1 else frozenset())
        (out.exclude if neg else out.include).append(term)
    return out


# ── filters ────────────────────────────────────────────────────────────────


@dataclass
class Filters:
    q: str | None = None
    region: str = "ALL"
    include_worldwide: bool = True
    hide_unclear: bool = False
    category: list[str] = field(default_factory=list)
    type: list[str] = field(default_factory=list)
    mode: list[str] = field(default_factory=list)
    source: list[str] = field(default_factory=list)
    country: list[str] = field(default_factory=list)
    seniority: list[str] = field(default_factory=list)
    currency: list[str] = field(default_factory=list)
    salary_min: float | None = None
    salary_period: str = "month"
    has_salary: bool = False
    posted_within: int | None = None  # hours
    duration_max: float | None = None  # days


_DURATION_DAYS = {"hour": 1 / 8, "day": 1.0, "week": 7.0, "month": 30.0, "year": 365.0}


def region_match(s: dict[str, Any], region: str, include_worldwide: bool = True, hide_unclear: bool = False) -> bool:
    """DESIGN-SYSTEM §5a. Unknown remote scope counts as worldwide unless hidden."""
    remote = s.get("work_mode") == "remote"
    scope = s.get("remote_scope") or {}
    kind = scope.get("type") or "unknown"
    if remote and kind in ("unknown", "timezone") and not (scope.get("regions") or scope.get("countries")):
        kind = "unknown"
    if hide_unclear and remote and kind == "unknown":
        return False
    if region == "ALL":
        return True
    worldwide = remote and (kind == "worldwide" or kind == "unknown")
    if region == "GLOBAL_REMOTE":
        return worldwide
    loc = s.get("location") or {}
    if region in (loc.get("regions") or []):
        return True
    if remote:
        wanted = regions.region_countries(region)
        if wanted & set(scope.get("countries") or []):
            return True
        if any(r == region or wanted & regions.region_countries(r) for r in scope.get("regions") or []):
            return True
        if worldwide and include_worldwide:
            return True
    return False


def _period_ok(doc: Doc, f: Filters) -> float | None:
    """Doc's money value expressed in f.salary_period, or None when not comparable."""
    if doc.money_value is None or doc.money_period is None:
        return None
    if f.salary_period == "fixed" or doc.money_period == "fixed":
        return doc.money_value if f.salary_period == doc.money_period else None
    if f.salary_period not in PER_MONTH:
        return None
    return doc.money_value * PER_MONTH[doc.money_period] / PER_MONTH[f.salary_period]


def _predicates(f: Filters, now: float) -> dict[str, Callable[[Doc], bool]]:
    """One predicate per filter group; facet counts skip their own group (disjunctive facets)."""
    p: dict[str, Callable[[Doc], bool]] = {}
    if f.region != "ALL" or f.hide_unclear:
        p["region"] = lambda d: region_match(d.summary, f.region, f.include_worldwide, f.hide_unclear)
    simple = {"category": "category", "type": "employment_type", "mode": "work_mode",
              "source": "source", "seniority": "seniority"}
    for key, attr in simple.items():
        values = set(getattr(f, key))
        if values:
            p[key] = lambda d, a=attr, v=values: d.summary.get(a) in v
    if f.country:
        wanted = set(f.country)
        p["country"] = lambda d: bool(d.countries & wanted)
    if f.currency:
        wanted_cur = set(f.currency)
        p["currency"] = lambda d: d.currency in wanted_cur
    if f.has_salary:
        p["has_salary"] = lambda d: d.money_value is not None
    if f.salary_min is not None and f.currency:
        p["salary_min"] = lambda d: (v := _period_ok(d, f)) is not None and v >= f.salary_min
    if f.posted_within:
        cutoff = now - f.posted_within * 3600
        p["posted_within"] = lambda d: d.when >= cutoff
    if f.duration_max is not None:
        def dur_ok(d: Doc) -> bool:
            dur = d.summary.get("duration") or {}
            if not dur.get("value") or not dur.get("unit"):
                return True  # unknown duration passes
            return dur["value"] * _DURATION_DAYS[dur["unit"]] <= f.duration_max
        p["duration_max"] = dur_ok
    return p


# ── matching & scoring ─────────────────────────────────────────────────────


def _term_score(doc: Doc, term: Term, vocab_prefix: Callable[[str], frozenset[str]]) -> float:
    score = 0.0
    for name, weight in _WEIGHTS.items():
        if term.is_phrase:
            hit = f" {term.text} " in doc.fields[name]
        elif term.prefix:
            hit = bool(doc.sets[name] & vocab_prefix(term.text.rstrip("*")))
        else:
            hit = not doc.sets[name].isdisjoint(term.forms)
        if hit:
            score += weight
    if term.skill and term.skill in doc.skills and not score:
        score += _WEIGHTS["skills"]
    return score


# ── the index ──────────────────────────────────────────────────────────────


class JobIndex:
    def __init__(self, store: FileStore | None = None, check_every: float = 1.0) -> None:
        self.store = store or FileStore()
        self.check_every = check_every
        self._lock = threading.Lock()
        self._sig: tuple = ()
        self._checked = 0.0
        self.docs: list[Doc] = []
        self.by_id: dict[str, Doc] = {}
        self._vocab: list[str] = []
        self._prefix_cache: dict[str, frozenset[str]] = {}
        self._region_cache: dict[tuple, dict[str, int]] = {}
        self.loaded_at: datetime | None = None

    # loading
    def _signature(self) -> tuple:
        out = []
        for p in sorted(self.store.jobs_dir.glob("*.jsonl")):
            try:
                st = p.stat()
            except FileNotFoundError:
                continue
            out.append((p.name, st.st_mtime_ns, st.st_size))
        return tuple(out)

    def refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._checked < self.check_every:
            return
        with self._lock:
            self._checked = now
            sig = self._signature()
            if sig == self._sig and not force:
                return
            dicts = [d for src in self.store.sources() for d in self.store.iter_job_dicts(src) if d.get("id")]
            dupes = group_duplicates(dicts)
            docs = [_doc(d, dupes.get(d["id"], [])) for d in dicts]
            vocab: set[str] = set()
            for doc in docs:
                for s in doc.sets.values():
                    vocab |= s
            self.docs = docs
            self.by_id = {d.summary["id"]: d for d in docs}
            self._vocab = sorted(vocab)
            self._prefix_cache = {}
            self._sig = sig
            self.loaded_at = datetime.now(timezone.utc)

    def _vocab_prefix(self, prefix: str) -> frozenset[str]:
        if prefix not in self._prefix_cache:
            self._prefix_cache[prefix] = frozenset(t for t in self._vocab if t.startswith(prefix))
        return self._prefix_cache[prefix]

    # querying
    def search(
        self, f: Filters, sort: str | None = None, page: int = 1, page_size: int = 50
    ) -> dict[str, Any]:
        self.refresh()
        docs = self.docs
        now = time.time()
        pq = parse_query(f.q)

        scores: dict[int, float] = {}
        if pq:
            matched: list[Doc] = []
            for doc in docs:
                if any(_term_score(doc, t, self._vocab_prefix) for t in pq.exclude):
                    continue
                total = 0.0
                for t in pq.include:
                    s = _term_score(doc, t, self._vocab_prefix)
                    if not s:
                        break
                    total += s
                else:
                    age_days = (now - doc.when) / 86400 if doc.when else 60
                    scores[id(doc)] = total + max(0.0, 1 - age_days / 30)
                    matched.append(doc)
            docs = matched

        preds = _predicates(f, now)
        flags = [{k: p(d) for k, p in preds.items()} for d in docs]
        hits = [d for d, fl in zip(docs, flags) if all(fl.values())]

        facets = {name: Counter() for name in FACETS}
        for d, fl in zip(docs, flags):
            failed = [k for k, ok in fl.items() if not ok]
            if len(failed) > 1:
                continue
            for name in FACETS:
                if failed and failed[0] != name:
                    continue
                for value in _facet_values(d, name):
                    facets[name][value] += 1

        sort = sort or ("relevance" if pq.include else "newest")
        if sort == "salary_desc" and not f.currency:
            sort = "newest"
        _sort(hits, sort, scores)

        start = (page - 1) * page_size
        return {
            "items": [d.summary for d in hits[start : start + page_size]],
            "total": len(hits),
            "page": page,
            "page_size": page_size,
            "sort": sort,
            "facets": {k: dict(v.most_common()) for k, v in facets.items()},
        }

    def region_counts(self, include_worldwide: bool = True, hide_unclear: bool = False) -> dict[str, int]:
        """Matching job count for every region and country code in regions.yaml."""
        self.refresh()
        key = (self._sig, include_worldwide, hide_unclear)
        if key not in self._region_cache:
            cfg = config.load("regions")
            codes = list(cfg.get("regions", {})) + list(cfg.get("countries", {}))
            self._region_cache = {key: {
                code: sum(1 for d in self.docs if region_match(d.summary, code, include_worldwide, hide_unclear))
                for code in codes
            }}
        return self._region_cache[key]

    def get(self, job_id: str) -> Job | None:
        self.refresh()
        job = self.store.get_job(job_id)
        if job and (doc := self.by_id.get(job_id)):
            job.duplicates = doc.summary["duplicates"]
        return job

    def stats(self) -> dict[str, Any]:
        self.refresh()
        per_source: dict[str, dict[str, Any]] = {}
        for d in self.docs:
            s = per_source.setdefault(d.summary["source"], {"jobs": 0, "last_fetched": 0.0})
            s["jobs"] += 1
            s["last_fetched"] = max(s["last_fetched"], d.fetched)
        for s in per_source.values():
            s["last_fetched"] = _iso(s["last_fetched"])
        last = max((d.fetched for d in self.docs), default=0.0)
        return {"total": len(self.docs), "last_fetched": _iso(last), "sources": per_source}


def _iso(ts: float) -> str | None:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z") if ts else None


def _facet_values(d: Doc, name: str) -> Iterable[str]:
    s = d.summary
    if name == "category":
        return [s["category"]]
    if name == "type":
        return [s["employment_type"]]
    if name == "mode":
        return [s["work_mode"]]
    if name == "source":
        return [s["source"]]
    if name == "seniority":
        return [s["seniority"]]
    if name == "country":
        return d.countries
    if name == "currency":
        return [d.currency] if d.currency else []
    return []


def _sort(hits: list[Doc], sort: str, scores: dict[int, float]) -> None:
    if sort == "relevance":
        hits.sort(key=lambda d: (scores.get(id(d), 0.0), d.when), reverse=True)
    elif sort == "salary_desc":
        monthly = Filters(salary_period="month")
        hits.sort(key=lambda d: (v if (v := _period_ok(d, monthly)) is not None else -1, d.when), reverse=True)
    elif sort == "company":
        hits.sort(key=lambda d: (not d.summary.get("company"), fold(d.summary.get("company") or ""), -d.when))
    else:
        hits.sort(key=lambda d: d.when, reverse=True)


_default: JobIndex | None = None


def default_index() -> JobIndex:
    global _default
    if _default is None:
        _default = JobIndex()
    return _default
