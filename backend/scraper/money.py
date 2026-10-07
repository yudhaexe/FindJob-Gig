"""Find salary/budget amounts in text. Recognition only — amounts are never converted (D13).

    find_money("Rp 6.000.000 – Rp 9.000.000 per month")
    → Money(min=6000000, max=9000000, currency="IDR", period="month", ...)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache

from core import config

_MULT = {
    "k": 1e3, "rb": 1e3, "ribu": 1e3, "thousand": 1e3,
    "m": 1e6, "mio": 1e6, "jt": 1e6, "juta": 1e6, "million": 1e6,
}

_PERIODS = {
    "hour": ["hourly", "hours", "hour", "hrs", "hr", "h", "jam"],
    "day": ["daily", "days", "day", "hari", "harian"],
    "week": ["weekly", "weeks", "week", "wk", "minggu", "mingguan"],
    "month": ["monthly", "months", "month", "mth", "mo", "bulanan", "bulan", "bln"],
    "year": ["yearly", "annually", "annual", "annum", "years", "year", "yr", "tahunan", "tahun", "thn", "p.a.", "pa"],
}
_PERIOD_OF = {w: p for p, words in _PERIODS.items() for w in words}
_PERIOD_RE = re.compile(
    r"^\s*(?:/|per\b|a\b|an\b|each\b|·|-)?\s*("
    + "|".join(re.escape(w) for w in sorted(_PERIOD_OF, key=len, reverse=True))
    + r")(?![a-z])",
    re.I,
)
_FIXED_RE = re.compile(r"^\s*(?:\(|-|·)?\s*(fixed|flat|one[- ]off|per project|total)\b", re.I)

_AMT = r"(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d+)?)\s*((?i:k|rb|ribu|thousand|mio|jt|juta|million|m))?(?![a-zA-Z])"
_SEP = r"\s*(?:-|–|—|to|sampai|s/d|~|until)\s*"


@dataclass
class Money:
    min: float | None
    max: float | None
    currency: str | None
    currency_guessed: bool
    period: str  # hour | day | week | month | year | fixed | unknown
    raw: str


@cache
def _patterns() -> tuple[re.Pattern[str], dict[str, str], set[str]]:
    cfg = config.load("currencies")
    symbols: dict[str, str] = cfg.get("symbols", {})
    codes: list[str] = cfg.get("codes", [])
    guessed = set(cfg.get("guessed_symbols", ["$"]))
    alts = []
    for sym in sorted(symbols, key=len, reverse=True):
        if sym == "Rp":
            alts.append(r"(?i:rp)\.?")
        else:
            alts.append(re.escape(sym))
    alts.append(r"\b(?:" + "|".join(codes) + r")\b")
    cur = "(?:" + "|".join(alts) + ")"
    pattern = re.compile(
        rf"(?P<c1>{cur})?\s*{_AMT}(?:{_SEP}(?P<c2>{cur})?\s*{_AMT})?(?:\s*(?P<c3>{cur}))?"
    )
    lookup = {k.lower(): v for k, v in symbols.items()} | {c.lower(): c for c in codes}
    return pattern, lookup, guessed


def _to_number(s: str, suffix: str | None) -> float:
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", s):
        value = float(re.sub(r"[.,]", "", s))
    elif "." in s and "," in s:
        dec = max(s.rfind("."), s.rfind(","))
        value = float(re.sub(r"[.,]", "", s[:dec]) + "." + s[dec + 1 :])
    elif re.fullmatch(r"\d+[.,]\d{1,2}", s):
        value = float(s.replace(",", "."))
    else:
        value = float(re.sub(r"[.,]", "", s))
    return value * _MULT.get((suffix or "").lower(), 1)


def _currency(token: str | None, lookup: dict[str, str]) -> str | None:
    if not token:
        return None
    t = token.strip().rstrip(".").lower()
    return lookup.get(t)


def find_money(text: str | None, default_currency: str | None = None) -> Money | None:
    """First amount in `text` that carries a currency (or any amount if default_currency is set)."""
    if not text:
        return None
    pattern, lookup, guessed = _patterns()
    for m in pattern.finditer(text):
        a1, s1, a2, s2 = m.group(2), m.group(3), m.group(5), m.group(6)
        cur_token = m.group("c1") or m.group("c2") or m.group("c3")
        currency = _currency(cur_token, lookup) or default_currency
        if not currency:
            continue
        if s2 and not s1:
            s1 = s2  # "Rp 8 - 12 juta", "$80-100k"
        lo = _to_number(a1, s1)
        hi = _to_number(a2, s2) if a2 else None
        if lo == 0 and not hi:
            continue
        tail = text[m.end() : m.end() + 30]
        period = "unknown"
        end = m.end()
        if pm := _PERIOD_RE.match(tail):
            period = _PERIOD_OF[pm.group(1).lower()]
            end += pm.end()
        elif _FIXED_RE.match(tail):
            period = "fixed"
        if hi is not None and hi < lo:
            lo, hi = hi, lo
        return Money(
            min=lo,
            max=hi if hi is not None else lo,
            currency=currency,
            currency_guessed=cur_token is not None and cur_token.strip() in guessed,
            period=period,
            raw=text[m.start() : end].strip(),
        )
    return None


PERIOD_ALIASES = {
    "hourly": "hour", "hour": "hour", "daily": "day", "day": "day", "weekly": "week", "week": "week",
    "monthly": "month", "month": "month", "annual": "year", "annually": "year", "yearly": "year", "year": "year",
}


def norm_period(value: str | None) -> str:
    """Map a source's period word ('hourly', 'annual', 'MONTH') to our SalaryPeriod."""
    if not value:
        return "unknown"
    return PERIOD_ALIASES.get(value.strip().lower(), "unknown")
