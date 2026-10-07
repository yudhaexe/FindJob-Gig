"""Connector mapping against real responses saved in tests/fixtures/ (captured 2026-10-07)."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scraper.normalize import finalize
from scraper.sources import load_sources

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)
SOURCES = load_sources()


def jobs_for(name: str):
    src = SOURCES[name]
    raws = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return [finalize(src.to_job(raw, NOW)) for raw in raws]


@pytest.mark.parametrize("name", ["freelancer", "jobstreet", "himalayas"])
def test_every_fixture_maps_to_a_valid_job(name):
    for job in jobs_for(name):
        assert job.id.startswith(f"{name}:")
        assert job.source == name and job.provider == name
        assert job.source_url.startswith("https://")
        assert job.title and job.title != "(untitled)"
        assert job.raw is not None
        assert job.posted_at is not None


def test_freelancer():
    fixed, hourly, local = jobs_for("freelancer")
    assert fixed.category == "gig" and fixed.employment_type == "freelance"
    assert fixed.budget.type == "fixed" and fixed.budget.currency == "USD"
    assert fixed.budget.min == 30 and fixed.budget.max == 250
    assert fixed.work_mode == "remote" and fixed.remote_scope.type == "worldwide"
    assert fixed.company is None and fixed.fingerprint is None
    assert "video" in fixed.topics

    assert hourly.budget.type == "hourly"

    assert local.work_mode == "onsite"
    assert local.location.country == "SE"
    assert "EU" in local.location.regions


def test_jobstreet():
    with_salary, without_salary = jobs_for("jobstreet")
    assert with_salary.salary.currency == "IDR"
    assert (with_salary.salary.min, with_salary.salary.max) == (5_000_000, 5_500_000)
    assert with_salary.salary.period == "month" and not with_salary.salary.estimated
    assert with_salary.location.country == "ID" and "SEA" in with_salary.location.regions
    assert with_salary.company and with_salary.fingerprint
    assert with_salary.employment_type != "unknown" and with_salary.work_mode == "onsite"
    assert without_salary.salary is None


def test_himalayas():
    salaried, worldwide, uk = jobs_for("himalayas")
    assert salaried.salary.currency == "USD" and salaried.salary.period == "year"
    assert salaried.remote_scope.type == "countries" and salaried.remote_scope.countries == ["US"]
    assert salaried.location.country == "US"
    assert salaried.description_text and "<" not in salaried.description_text[:50]

    assert worldwide.remote_scope.type in ("worldwide", "timezone")
    assert uk.remote_scope.countries == ["GB"]
    assert all(j.work_mode == "remote" for j in (salaried, worldwide, uk))
