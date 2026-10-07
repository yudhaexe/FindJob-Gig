"""Search index (storage/index.py) and the jobs API on a temp data dir."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from core.models import Budget, Duration, Job, Location, RemoteScope, Salary
from storage.filestore import FileStore
from storage.index import Filters, JobIndex, parse_query, region_match

NOW = datetime.now(timezone.utc)


def _job(source: str, n: int, title: str, **kw) -> Job:
    return Job(id=f"{source}:{n}", source=source, source_name=source.title(),
               source_url=f"https://{source}/{n}", title=title,
               fetched_at=kw.pop("fetched_at", NOW), **kw)


@pytest.fixture
def index(tmp_path) -> JobIndex:
    store = FileStore(tmp_path)
    store.upsert_jobs("alpha", [
        _job("alpha", 1, "Senior Video Editor", company="Acme Inc", fingerprint="fp-acme",
             skills=["video editing", "adobe premiere pro"], employment_type="fulltime",
             work_mode="remote", remote_scope=RemoteScope(type="worldwide"),
             salary=Salary(min=3000, max=4000, currency="USD", period="month"),
             posted_at=NOW - timedelta(hours=2)),
        _job("alpha", 2, "Photographer", company="Studio ID", employment_type="freelance",
             work_mode="onsite", location=Location(raw="Jakarta", city="Jakarta", country="ID",
                                                   regions=["ID", "SEA", "APAC"]),
             salary=Salary(min=8_000_000, max=12_000_000, currency="IDR", period="month"),
             description_text="Wedding photography in Jakarta. WordPress not needed.",
             posted_at=NOW - timedelta(days=2)),
        _job("alpha", 3, "Retoucher", work_mode="remote",
             remote_scope=RemoteScope(type="regions", regions=["EU"]),
             salary=Salary(min=20, currency="USD", period="hour"),
             posted_at=NOW - timedelta(days=10)),
    ])
    store.upsert_jobs("beta", [
        _job("beta", 1, "Senior Video Editor", company="ACME", fingerprint="fp-acme",
             work_mode="remote", posted_at=NOW - timedelta(hours=5)),
        _job("beta", 2, "Logo design", category="gig", work_mode="remote",
             budget=Budget(min=100, max=250, currency="USD", type="fixed"),
             duration=Duration(value=2, unit="week"), posted_at=NOW - timedelta(hours=1)),
    ])
    return JobIndex(store, check_every=0)


def ids(result) -> list[str]:
    return [i["id"] for i in result["items"]]


def test_parse_query():
    pq = parse_query('video -wordpress "senior editor" photo* the')
    assert [t.text for t in pq.include] == ["video", "senior editor", "photo"]
    assert pq.include[2].prefix and [t.text for t in pq.exclude] == ["wordpress"]
    assert parse_query("photoshop").include[0].skill == "adobe photoshop"


def test_search_terms_phrase_exclude_prefix(index):
    assert set(ids(index.search(Filters(q="video editor")))) == {"alpha:1", "beta:1"}
    assert ids(index.search(Filters(q='"senior video"', source=["alpha"]))) == ["alpha:1"]
    assert ids(index.search(Filters(q="photograph*"))) == ["alpha:2"]
    assert ids(index.search(Filters(q="wedding -wordpress"))) == []
    # skill alias: "premiere" → canonical "adobe premiere pro" on the job
    assert ids(index.search(Filters(q="premiere"))) == ["alpha:1"]
    # title outranks description; plural matches
    assert ids(index.search(Filters(q="editors"))) == ["alpha:1", "beta:1"]


def test_filters_and_sort(index):
    assert ids(index.search(Filters(category=["gig"]))) == ["beta:2"]
    assert ids(index.search(Filters(), sort="newest"))[:2] == ["beta:2", "alpha:1"]
    assert set(ids(index.search(Filters(posted_within=24)))) == {"alpha:1", "beta:1", "beta:2"}
    # salary_min needs a currency; hourly 20 USD ≈ 3460/mo
    assert index.search(Filters(salary_min=3500))["total"] == 5
    usd = index.search(Filters(currency=["USD"], salary_min=3500), sort="salary_desc")
    assert ids(usd) == ["alpha:1"]
    assert ids(index.search(Filters(currency=["USD"]), sort="salary_desc"))[:2] == ["alpha:1", "alpha:3"]
    assert "beta:2" not in ids(index.search(Filters(duration_max=7)))


def test_region_rules(index):
    sea = set(ids(index.search(Filters(region="SEA"))))
    # onsite Jakarta + worldwide remote + unknown-scope remote; EU-only remote excluded
    assert sea == {"alpha:1", "alpha:2", "beta:1", "beta:2"}
    assert set(ids(index.search(Filters(region="SEA", include_worldwide=False)))) == {"alpha:2"}
    assert set(ids(index.search(Filters(region="DE")))) >= {"alpha:3"}
    assert "beta:1" not in ids(index.search(Filters(region="SEA", hide_unclear=True)))
    assert set(ids(index.search(Filters(region="GLOBAL_REMOTE", hide_unclear=True)))) == {"alpha:1"}
    counts = index.region_counts()
    assert counts["ID"] == 4 and counts["EU"] == 4 and counts["ALL"] == 5
    assert region_match({"work_mode": "remote", "remote_scope": {"type": "regions", "regions": ["APAC"]}}, "ID")


def test_facets_are_disjunctive(index):
    r = index.search(Filters(type=["fulltime"]))
    assert r["total"] == 1
    # the type facet ignores the type filter itself, other facets respect it
    assert r["facets"]["type"]["freelance"] == 1
    assert r["facets"]["source"] == {"alpha": 1}
    assert r["facets"]["currency"] == {"USD": 1}


def test_duplicates_and_reload(index, tmp_path):
    r = index.search(Filters(q="video editor"))
    assert all(i["duplicate_count"] == 1 for i in r["items"])
    job = index.get("beta:1")
    assert job.duplicates == ["alpha:1"]
    FileStore(tmp_path).upsert_jobs("beta", [_job("beta", 3, "Colorist")])
    assert ids(index.search(Filters(q="colorist"))) == ["beta:3"]


def test_api(index):
    from storage.index import default_index

    app.dependency_overrides[default_index] = lambda: index
    try:
        client = TestClient(app)
        r = client.get("/api/jobs", params={"q": "editor", "type": "fulltime,unknown", "page_size": 1})
        body = r.json()
        assert r.status_code == 200 and body["total"] == 2 and len(body["items"]) == 1
        assert body["sort"] == "relevance" and "duplicates" not in body["items"][0]
        assert client.get("/api/jobs", params={"sort": "bogus"}).status_code == 422
        assert client.get("/api/jobs/alpha:2").json()["description_text"].startswith("Wedding")
        assert client.get("/api/jobs/alpha:99").status_code == 404
        regions = client.get("/api/regions").json()
        sea = next(r for r in regions["regions"] if r["code"] == "SEA")
        assert sea["count"] == 4 and "ID" in sea["countries"]
        assert regions["countries"]["ID"] == {"name": "Indonesia", "count": 4}
        assert client.get("/api/facets", params={"region": "sea"}).json()["source"] == {"alpha": 2, "beta": 2}
        sources = client.get("/api/sources").json()
        assert sources["total"] == 5 and sources["last_fetched"]
    finally:
        app.dependency_overrides.clear()
