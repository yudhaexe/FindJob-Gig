"""Location and remote-scope parsing against config/regions.yaml (DESIGN-SYSTEM §5a)."""

from __future__ import annotations

import re
from functools import cache

from core import config
from core.models import Location, RemoteScope
from scraper.text import fold

_TZ_RE = re.compile(
    r"\b(?:UTC|GMT)\s?[+\-−]\s?\d{1,2}(?::?\d{2})?\b|\b(?:CET|CEST|EET|WET|BST|EST|EDT|CST|CDT|MST|MDT|PST|PDT|AEST|AEDT|SGT|WIB|WITA|WIT|IST|JST|KST)\b"
)


@cache
def _cfg() -> tuple[dict, dict, list[str]]:
    cfg = config.load("regions")
    return cfg.get("regions", {}), cfg.get("countries", {}), cfg.get("worldwide_aliases", [])


def _alias_regex(aliases: list[str]) -> re.Pattern[str]:
    alts = sorted({fold(a) for a in aliases}, key=len, reverse=True)
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(a) for a in alts) + r")(?![a-z0-9])")


@cache
def _country_index() -> tuple[re.Pattern[str], dict[str, str]]:
    _, countries, _ = _cfg()
    lookup: dict[str, str] = {}
    for code, c in countries.items():
        for a in [c.get("name", "")] + c.get("aliases", []):
            if a:
                lookup[fold(a)] = code
    return _alias_regex(list(lookup)), lookup


@cache
def _region_index() -> tuple[re.Pattern[str] | None, dict[str, str]]:
    regions, _, _ = _cfg()
    lookup = {fold(a): code for code, r in regions.items() for a in r.get("aliases", [])}
    return (_alias_regex(list(lookup)) if lookup else None), lookup


@cache
def _worldwide_re() -> re.Pattern[str]:
    return _alias_regex(_cfg()[2])


@cache
def region_countries(code: str) -> frozenset[str]:
    """All country codes inside a region (children expanded). A country code maps to itself."""
    regions, countries, _ = _cfg()
    if code in regions:
        r = regions[code]
        out = set(r.get("countries", []))
        for child in r.get("children", []):
            out |= region_countries(child)
        return frozenset(out)
    return frozenset({code}) if code in countries else frozenset()


@cache
def regions_for_country(cc: str | None) -> tuple[str, ...]:
    """Country plus every region that contains it: 'ID' → ('ID', 'SEA', 'APAC')."""
    if not cc:
        return ()
    regions, _, _ = _cfg()
    found = [code for code in regions if cc in region_countries(code)]
    return (cc, *found)


def country_label(cc: str) -> str:
    return _cfg()[1].get(cc, {}).get("name", cc)


def find_countries(text: str | None) -> list[str]:
    """Country codes mentioned in text, in order of appearance, unique."""
    if not text:
        return []
    pattern, lookup = _country_index()
    out: list[str] = []
    for m in pattern.finditer(fold(text)):
        cc = lookup[m.group(0)]
        if cc not in out:
            out.append(cc)
    return out


def find_regions(text: str | None) -> list[str]:
    if not text:
        return []
    pattern, lookup = _region_index()
    if pattern is None:
        return []
    out: list[str] = []
    for m in pattern.finditer(fold(text)):
        code = lookup[m.group(0)]
        if code not in out:
            out.append(code)
    return out


def country_code(name_or_code: str | None) -> str | None:
    """'Australia' / 'australia' / 'AU' → 'AU'."""
    if not name_or_code:
        return None
    s = name_or_code.strip()
    if len(s) == 2 and s.upper() in _cfg()[1]:
        return s.upper()
    found = find_countries(s)
    return found[0] if found else None


def parse_location(raw: str | None, country: str | None = None, city: str | None = None) -> Location:
    """Structured hints win; otherwise look up aliases in the raw string."""
    cc = (country or "").upper() or None
    if cc and cc not in _cfg()[1]:
        cc = None
    if not cc:
        found = find_countries(raw)
        cc = found[0] if found else None
    if not city and raw:
        first = raw.split(",")[0].strip()
        f = fold(first)
        is_country = bool(cc) and f == fold(country_label(cc))
        is_remote = "remote" in f or bool(_worldwide_re().search(f))
        if first and not is_country and not is_remote:
            city = first
    return Location(raw=raw or None, city=city, country=cc, regions=list(regions_for_country(cc)))


def parse_remote_scope(text: str | None) -> RemoteScope:
    """'Remote (Europe only)' → regions=[EU]; 'Anywhere' → worldwide; nothing found → unknown."""
    if not text:
        return RemoteScope()
    countries = find_countries(text)
    regions = [r for r in find_regions(text) if r not in ("ALL", "GLOBAL_REMOTE")]
    timezones = list(dict.fromkeys(m.group(0) for m in _TZ_RE.finditer(text)))
    if countries or regions:
        kind = "countries" if countries and not regions else "regions"
        return RemoteScope(type=kind, regions=regions, countries=countries, timezones=timezones, raw=text)
    if timezones:
        return RemoteScope(type="timezone", timezones=timezones, raw=text)
    if _worldwide_re().search(fold(text)):
        return RemoteScope(type="worldwide", raw=text)
    return RemoteScope(raw=text)


def utc_offsets_label(offsets: list[float]) -> list[str]:
    """[8, 9.5] → ['UTC+8', 'UTC+9:30']."""
    out = []
    for o in offsets:
        sign = "+" if o >= 0 else "-"
        h, rem = divmod(abs(o), 1)
        out.append(f"UTC{sign}{int(h)}" + (f":{int(round(rem * 60)):02d}" if rem else ""))
    return out


def source_matches_region(markets: list[str], region: str) -> bool:
    """Is a source with these markets relevant when scraping `region`?"""
    if region == "ALL" or "ALL" in markets or region in markets:
        return True
    wanted = region_countries(region)
    return any(wanted & region_countries(m) for m in markets)
