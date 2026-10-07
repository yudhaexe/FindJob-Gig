"""POST /api/scrape runs in the background; /api/runs reports progress (fake source, no network)."""

import time

from fastapi.testclient import TestClient

from app.main import app
from app.routes.scrape import get_sources, get_store
from storage.filestore import FileStore
from tests.test_storage_runner import FakeSource


def _client(tmp_path, sources):
    store = FileStore(tmp_path)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_sources] = lambda: sources
    return store


def test_scrape_then_poll_run(tmp_path):
    fake = FakeSource({"editor": [{"id": 1, "title": "Video Editor"}, {"id": 2, "title": "Photo Editor"}]})
    store = _client(tmp_path, {"fake": fake})
    try:
        with TestClient(app) as client:
            r = client.post("/api/scrape", json={"keywords": [" editor ", "editor", ""], "region": "sea"})
            assert r.status_code == 202
            run_id = r.json()["run_id"]
            for _ in range(100):
                run = client.get(f"/api/runs/{run_id}").json()
                if run["status"] not in ("queued", "running"):
                    break
                time.sleep(0.05)
            assert run["status"] == "done"
            assert run["query"]["keywords"] == ["editor"] and run["query"]["region"] == "SEA"
            assert run["sources"]["fake"]["new"] == 2
            assert [x["id"] for x in client.get("/api/runs").json()] == [run_id]
        assert set(store.read_jobs("fake")) == {"fake:1", "fake:2"}
    finally:
        app.dependency_overrides.clear()


def test_scrape_rejects_empty_or_unknown_sources(tmp_path):
    fake = FakeSource({})
    fake.markets = ["ID"]
    _client(tmp_path, {"fake": fake})
    try:
        client = TestClient(app)
        assert client.post("/api/scrape", json={"region": "EU"}).status_code == 422
        assert client.post("/api/scrape", json={"sources": ["nope"]}).status_code == 422
        assert client.get("/api/runs/missing").status_code == 404
        assert client.get("/api/runs/..%5C..%5Cx").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_scrape_sources_marks_region(tmp_path):
    fake = FakeSource({})
    fake.markets = ["ID", "SEA"]
    _client(tmp_path, {"fake": fake})
    try:
        client = TestClient(app)
        body = client.get("/api/scrape/sources", params={"region": "SG"}).json()
        [s] = body["sources"]
        assert any(p["name"] == "creative" and p["query"]["keywords"] for p in body["presets"])
        assert s["in_region"] and s["selected"]
        [s] = client.get("/api/scrape/sources", params={"region": "EU"}).json()["sources"]
        assert not s["in_region"] and not s["selected"]
        [s] = client.get("/api/scrape/sources", params={"region": "ID", "category": "job"}).json()["sources"]
        assert s["in_region"] and not s["selected"]  # fake is a gig source
    finally:
        app.dependency_overrides.clear()
