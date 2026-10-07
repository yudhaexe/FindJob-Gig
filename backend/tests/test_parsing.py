"""Money, region and classification rules — pure functions, no network."""

from datetime import datetime, timezone

import pytest

from core.models import Job, Location
from scraper import dedup
from scraper.classify import classify, find_duration, find_skills, find_topics
from scraper.money import find_money
from scraper.regions import (
    parse_location,
    parse_remote_scope,
    regions_for_country,
    source_matches_region,
)
from scraper.text import html_to_text


@pytest.mark.parametrize(
    ("text", "lo", "hi", "cur", "period", "guessed"),
    [
        ("Rp 6.000.000 – Rp 9.000.000 per month", 6e6, 9e6, "IDR", "month", False),
        ("Rp\xa05.000.000 – Rp\xa05.500.000 per month", 5e6, 5.5e6, "IDR", "month", False),
        ("Rp 8 - 12 juta / bulan", 8e6, 12e6, "IDR", "month", False),
        ("Rp 500rb/hari", 5e5, 5e5, "IDR", "day", False),
        ("IDR 5–6M/monthly", 5e6, 6e6, "IDR", "month", False),
        ("$50 - $100 per hour", 50, 100, "USD", "hour", True),
        ("Upto $60/hr", 60, 60, "USD", "hour", True),
        ("USD 45–65/hourly", 45, 65, "USD", "hour", False),
        ("$80k-$100k a year", 8e4, 1e5, "USD", "year", True),
        ("S$ 4,500 - 6,000 monthly", 4500, 6000, "SGD", "month", False),
        ("€3,000/month", 3000, 3000, "EUR", "month", False),
        ("£25.50 per hour", 25.5, 25.5, "GBP", "hour", False),
    ],
)
def test_find_money(text, lo, hi, cur, period, guessed):
    m = find_money(text)
    assert m is not None
    assert (m.min, m.max, m.currency, m.period, m.currency_guessed) == (lo, hi, cur, period, guessed)


@pytest.mark.parametrize("text", ["2+ years experience", "Team of 50 people", "", None])
def test_find_money_ignores_amounts_without_currency(text):
    assert find_money(text) is None


def test_location_and_regions():
    loc = parse_location("East Jakarta, Jakarta", country="ID")
    assert (loc.city, loc.country) == ("East Jakarta", "ID")
    assert set(loc.regions) == {"ID", "SEA", "APAC"}
    assert parse_location("Bekasi, West Java").country == "ID"
    assert parse_location("Remote").country is None
    assert regions_for_country("IN") == ("IN", "APAC", "SAS")


@pytest.mark.parametrize(
    ("text", "kind", "regions", "countries"),
    [
        ("Remote (Europe only)", "regions", ["EU"], []),
        ("Anywhere in the world", "worldwide", [], []),
        ("Remote - US only", "countries", [], ["US"]),
        ("UTC+7 ± 3 hours", "timezone", [], []),
        ("Remote", "unknown", [], []),
    ],
)
def test_remote_scope(text, kind, regions, countries):
    s = parse_remote_scope(text)
    assert (s.type, s.regions, s.countries) == (kind, regions, countries)


def test_source_matches_region():
    assert source_matches_region(["ID", "SEA", "APAC"], "SG")
    assert source_matches_region(["ID"], "APAC")
    assert not source_matches_region(["ID", "SEA", "APAC"], "EU")
    assert source_matches_region(["ALL"], "EU")


def test_duration():
    assert find_duration("This is a 3 months contract").model_dump() == {"value": 3, "unit": "month", "raw": "3 months"}
    assert find_duration("kontrak 6 bulan").unit == "month"
    assert find_duration("2-4 week project").value == 4
    assert find_duration("3+ years of experience on project work") is None
    assert find_duration("We shipped 3 products last year") is None


def test_topics_respect_excludes():
    assert find_topics("Solar Photovoltaik Installer") == []
    assert find_topics("Video Games QA Tester") == []
    assert find_topics("Wedding Videographer") == ["video"]
    assert "photo" in find_topics("Photo Retoucher needed")
    assert "video" in find_topics("Video Games trailer video editor")
    assert set(find_topics("Creative Producer for Photo & Video")) >= {"photo", "video"}


def test_skills_dictionary():
    assert find_skills("Premiere Pro + After Effects, DaVinci") == [
        "adobe premiere pro", "adobe after effects", "davinci resolve",
    ]


def _job(**kw) -> Job:
    base = dict(id="x:1", source="x", source_name="X", source_url="https://x", title="T",
                fetched_at=datetime.now(timezone.utc))
    return Job(**(base | kw))


def test_classify_title_beats_description_and_keeps_structured_fields():
    job = classify(_job(title="Freelance Video Editor (Remote)", description_text="Full-time hours expected."))
    assert job.employment_type == "freelance"
    assert job.work_mode == "remote"
    assert "video" in job.topics

    structured = classify(_job(title="Freelance Video Editor", employment_type="contract"))
    assert structured.employment_type == "contract"


def test_classify_salary_from_text_needs_a_period_in_description():
    funded = classify(_job(title="Video Editor", description_text="We raised US$218M from top investors."))
    assert funded.salary is None
    paid = classify(_job(title="Video Editor", description_text="Pay: $25 - $35 per hour"))
    assert paid.salary.estimated and paid.salary.period == "hour"


def test_classify_seniority_from_title_only():
    assert classify(_job(title="Senior Videographer")).seniority == "senior"
    assert classify(_job(title="Videographer", description_text="report to the senior manager")).seniority == "unknown"


def test_html_to_text_keeps_structure():
    assert html_to_text("<p>Hello <b>there</b></p><ul><li>one</li><li>two</li></ul>") == "Hello there\n\n• one\n• two"


def test_dedup_groups_across_sources_only():
    now = datetime.now(timezone.utc).isoformat()
    jobs = [
        {"id": "a:1", "source": "a", "fingerprint": dedup.fingerprint("Video Editor", "PT Acme"), "posted_at": now},
        {"id": "b:9", "source": "b", "fingerprint": dedup.fingerprint("video editor ", "Acme"), "posted_at": now,
         "salary": {"min": 1}},
        {"id": "a:2", "source": "a", "fingerprint": dedup.fingerprint("Video Editor", "Acme"), "posted_at": now},
        {"id": "c:1", "source": "c", "fingerprint": dedup.fingerprint("Video Editor", None), "posted_at": now},
    ]
    groups = dedup.group_duplicates(jobs)
    assert groups["a:1"] == ["b:9"]
    assert set(groups["b:9"]) == {"a:1", "a:2"}
    assert "c:1" not in groups
    assert Location().regions == []
