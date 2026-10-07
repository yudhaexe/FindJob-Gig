"""Schedules: interval parsing, claim/no double run, pause after failures, API CRUD."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes.scrape import get_sources, get_store
from core.models import Schedule, ScrapeQuery
from scraper import scheduler
from scraper import runner
from storage.filestore import FileStore
from tests.test_storage_runner import FakeSource

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


def _sched(store, **kw):
    s = Schedule(id=kw.pop("id", "sched_a"), name="t", query=ScrapeQuery(keywords=["editor"], sources=["fake"]),
                 next_run_at=kw.pop("next_run_at", NOW - timedelta(minutes=1)), **kw)
    store.update_schedules(lambda items: items.append(s))
    return s


@pytest.fixture
def fake_runner(monkeypatch):
    fake = FakeSource({"editor": [{"id": 1, "title": "Video Editor"}]})
    real = runner.run_scrape

    async def patched(q, **kw):
        return await real(q, available={"fake": fake}, **kw)

    monkeypatch.setattr(scheduler, "run_scrape", patched)
    return fake


def test_parse_every():
    assert scheduler.parse_every("6h") == timedelta(hours=6)
    assert scheduler.parse_every("30m") == timedelta(minutes=30)
    for bad in ("5m", "x", "6", "0h"):
        with pytest.raises(ValueError):
            scheduler.parse_every(bad)


def test_run_due_runs_once_and_reschedules(tmp_path, fake_runner):
    store = FileStore(tmp_path)
    _sched(store)
    _sched(store, id="sched_future", next_run_at=NOW + timedelta(hours=1))
    _sched(store, id="sched_off", enabled=False)
    runs = asyncio.run(scheduler.run_due(store, NOW))
    assert [r.schedule_id for r in runs] == ["sched_a"] and runs[0].trigger == "schedule"
    s = {x.id: x for x in store.load_schedules()}["sched_a"]
    assert s.last_status == "done" and s.last_run_id == runs[0].id
    assert s.next_run_at == NOW + timedelta(hours=6)
    assert asyncio.run(scheduler.run_due(store, NOW)) == []  # already claimed: no double run


def test_pause_after_three_failures(tmp_path, fake_runner):
    store = FileStore(tmp_path)
    _sched(store)
    fake_runner.blocked = True
    for i in range(3):
        asyncio.run(scheduler.run_due(store, NOW + timedelta(days=i)))
    s = store.load_schedules()[0]
    assert not s.enabled and s.consecutive_failures == 3 and "Paused" in s.paused_reason


def test_api_crud(tmp_path):
    store = FileStore(tmp_path)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_sources] = lambda: {"fake": FakeSource({})}
    try:
        with TestClient(app) as c:
            body = {"name": "React", "every": "6H", "query": {"keywords": [" react ", "react"], "region": "sea", "sources": ["fake"]}}
            r = c.post("/api/schedules", json=body)
            assert r.status_code == 201
            s = r.json()
            assert s["every"] == "6h" and s["query"]["keywords"] == ["react"] and s["query"]["region"] == "SEA"
            assert c.post("/api/schedules", json={**body, "every": "1m"}).status_code == 422
            assert c.patch(f"/api/schedules/{s['id']}", json={"every": "12h", "enabled": False}).json()["enabled"] is False
            assert c.patch("/api/schedules/nope", json={"name": "x"}).status_code == 404
            assert [x["id"] for x in c.get("/api/schedules").json()] == [s["id"]]
            assert c.delete(f"/api/schedules/{s['id']}").status_code == 204
            assert c.get("/api/schedules").json() == []
    finally:
        app.dependency_overrides.clear()
