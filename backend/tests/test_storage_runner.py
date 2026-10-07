"""FileStore upserts and the scrape runner, using a fake source (no network)."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import orjson
import pytest

from core.models import Job, ScrapeQuery
from scraper.base import Http, Source, SourceBlocked
from scraper.runner import pick_sources, run_scrape
from storage.filestore import FileLock, FileStore, LockTimeout

NOW = datetime.now(timezone.utc)


def _job(id_: str, title: str = "Video Editor", **kw) -> Job:
    return Job(id=id_, source="fake", source_name="Fake", source_url=f"https://x/{id_}", title=title,
               fetched_at=kw.pop("fetched_at", NOW), **kw)


def test_upsert_new_unchanged_updated(tmp_path):
    store = FileStore(tmp_path)
    first = store.upsert_jobs("fake", [_job("fake:1"), _job("fake:2")])
    assert (first.new, first.updated, first.unchanged) == (2, 0, 0)
    seen = store.read_jobs("fake")["fake:1"].first_seen_at

    later = NOW + timedelta(hours=1)
    second = store.upsert_jobs("fake", [
        _job("fake:1", fetched_at=later, raw={"noise": 1}),       # only volatile fields differ
        _job("fake:2", title="Senior Video Editor", fetched_at=later),
    ])
    assert (second.new, second.updated, second.unchanged) == (0, 1, 1)
    jobs = store.read_jobs("fake")
    assert jobs["fake:1"].first_seen_at == seen
    assert jobs["fake:1"].updated_at == NOW
    assert jobs["fake:2"].updated_at == later and jobs["fake:2"].title == "Senior Video Editor"
    assert store.get_job("fake:2").title == "Senior Video Editor"
    assert not list((tmp_path / "jobs").glob("*.tmp"))


def test_corrupt_line_is_skipped(tmp_path):
    store = FileStore(tmp_path)
    store.upsert_jobs("fake", [_job("fake:1")])
    with open(store.jobs_path("fake"), "ab") as f:
        f.write(b"{not json\n")
    assert list(store.read_jobs("fake")) == ["fake:1"]


def test_append_raw_returns_line_refs(tmp_path):
    store = FileStore(tmp_path)
    a = store.append_raw("fake", [{"n": 1}, {"n": 2}], NOW)
    b = store.append_raw("fake", [{"n": 3}], NOW)
    assert [r.line for r in a + b] == [1, 2, 3]
    lines = (tmp_path / b[0].file).read_bytes().splitlines()
    assert orjson.loads(lines[b[0].line - 1]) == {"n": 3}


def test_lock_blocks_second_holder(tmp_path):
    path = tmp_path / "x.lock"
    with FileLock(path):
        with pytest.raises(LockTimeout):
            with FileLock(path, timeout=0.2):
                pass
    with FileLock(path, timeout=0.2):
        pass


class FakeSource(Source):
    name = "fake"
    display_name = "Fake"
    category = "gig"

    def __init__(self, items: dict[str, list[dict]], blocked: bool = False) -> None:
        super().__init__({"enabled": True, "min_interval": 0})
        self.items = items
        self.blocked = blocked

    async def search(self, keyword, q, limit, http: Http) -> list[dict[str, Any]]:
        if self.blocked:
            raise SourceBlocked("403 Forbidden")
        return self.items.get(keyword, [])[:limit]

    def to_job(self, raw, fetched_at):
        if raw.get("broken"):
            raise KeyError("title")
        return Job(id=f"fake:{raw['id']}", source="fake", source_name="Fake", source_url=f"https://x/{raw['id']}",
                   title=raw["title"], category="gig", posted_at=raw.get("posted_at"), fetched_at=fetched_at, raw=raw)


class BlockedSource(FakeSource):
    name = "blocked"


def test_runner_end_to_end(tmp_path):
    old = (NOW - timedelta(days=30)).isoformat()
    fake = FakeSource({
        "video editor": [{"id": 1, "title": "Freelance Video Editor"}, {"id": 2, "title": "Video Editor", "posted_at": old}],
        "photographer": [{"id": 1, "title": "Freelance Video Editor"}, {"id": 3, "title": "Photographer"},
                         {"id": 4, "broken": True}],
    })
    blocked = BlockedSource({}, blocked=True)
    store = FileStore(tmp_path)
    q = ScrapeQuery(keywords=["video editor", "photographer"], since_hours=72)
    run = asyncio.run(run_scrape(q, store=store, available={"fake": fake, "blocked": blocked}))

    assert run.status == "partial"
    r = run.sources["fake"]
    assert (r.status, r.fetched, r.new, r.skipped) == ("done", 4, 2, 2)  # 1 too old + 1 unparseable
    assert "could not be parsed" in r.error
    assert run.sources["blocked"].status == "error" and "403" in run.sources["blocked"].error

    jobs = store.read_jobs("fake")
    assert set(jobs) == {"fake:1", "fake:3"}
    assert jobs["fake:1"].matched_queries == ["photographer", "video editor"]
    assert jobs["fake:1"].raw_ref.line >= 1
    assert jobs["fake:1"].scan_run_id == run.id
    assert "video" in jobs["fake:1"].topics
    assert store.load_run(run.id).status == "partial"
    assert len(r.logs) > 0
    assert any("Fetched" in log for log in r.logs)
    assert any("Failed parsing item" in log for log in r.logs)
    assert any("Completed" in log for log in r.logs)
    assert len(run.sources["blocked"].logs) > 0
    assert any("Failed with SourceError" in log for log in run.sources["blocked"].logs)


def test_pick_sources_by_region_and_category():
    jobstreet_like = FakeSource({})
    jobstreet_like.markets = ["ID", "SEA"]
    available = {"fake": jobstreet_like}
    assert pick_sources(ScrapeQuery(region="SG"), available) == [jobstreet_like]
    assert pick_sources(ScrapeQuery(region="EU"), available) == []
    assert pick_sources(ScrapeQuery(category="job"), available) == []
    with pytest.raises(ValueError):
        pick_sources(ScrapeQuery(sources=["nope"]), available)


def test_prune_archives_old_raw_and_runs_only(tmp_path):
    from datetime import datetime, timezone

    store = FileStore(tmp_path)
    old = datetime(2026, 1, 1, tzinfo=timezone.utc)
    new = datetime(2026, 9, 30, tzinfo=timezone.utc)
    store.append_raw("alpha", [{"a": 1}], old)
    store.append_raw("alpha", [{"a": 2}], new)
    (store.runs_dir / "2026-01-01T10-00-00_aaaa.json").write_text("{}")
    (store.runs_dir / "2026-09-30T10-00-00_bbbb.json").write_text("{}")
    (store.jobs_dir / "alpha.jsonl").write_text("{}\n")
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)

    dry = store.prune(30, dry_run=True, now=now)
    assert len(dry["raw"]) == 1 and len(dry["runs"]) == 1 and store.raw_path("alpha", old).exists()

    store.prune(30, now=now)
    assert not store.raw_path("alpha", old).exists() and store.raw_path("alpha", new).exists()
    assert (tmp_path / "archive/raw/alpha/2026-01-01.jsonl").exists()
    assert (tmp_path / "archive/runs/2026-01-01T10-00-00_aaaa.json").exists()
    assert (store.runs_dir / "2026-09-30T10-00-00_bbbb.json").exists()
    assert (store.jobs_dir / "alpha.jsonl").exists()


class SlowSource(FakeSource):
    """First keyword answers at once; the second one hangs until cancelled."""

    name = "slow"

    async def search(self, keyword, q, limit, http):
        if keyword == "hang":
            await asyncio.sleep(30)
        return await super().search(keyword, q, limit, http)

    def to_job(self, raw, fetched_at):
        job = super().to_job(raw, fetched_at)
        return job.model_copy(update={"id": f"slow:{raw['id']}", "source": "slow"})


def test_stop_saves_what_was_fetched_and_skips_the_rest(tmp_path):
    slow = SlowSource({"quick": [{"id": 1, "title": "Video Editor"}]})
    idle = SlowSource({})  # only "hang": nothing fetched before the stop
    idle.name = "idle"
    store = FileStore(tmp_path)
    q = ScrapeQuery(keywords=["quick", "hang"], sources=["slow", "idle"])

    async def go():
        stop = asyncio.Event()
        task = asyncio.create_task(run_scrape(q, store=store, available={"slow": slow, "idle": idle}, stop=stop))
        await asyncio.sleep(0.3)
        stop.set()
        return await asyncio.wait_for(task, 5)

    run = asyncio.run(go())
    assert run.stopped and run.finished_at
    assert run.sources["slow"].status == "done" and run.sources["slow"].new == 1
    assert any("Stopped by user" in line for line in run.sources["slow"].logs)
    assert set(store.read_jobs("slow")) == {"slow:1"}
    # "idle" had nothing yet for its first keyword, so it's skipped, not an error
    assert run.sources["idle"].status in ("skipped", "done")
    assert run.status == "done"
