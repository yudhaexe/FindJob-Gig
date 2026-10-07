from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from core.models import Job, JobSummary, Salary

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_jobs_empty_page():
    r = client.get("/api/jobs", params={"q": "react", "region": "SEA"})
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_job_roundtrip_and_summary():
    job = Job(
        id="remotive:1",
        source="remotive",
        source_name="Remotive",
        source_url="https://remotive.com/x",
        title="Senior React Developer",
        salary=Salary(min=60000, max=80000, currency="USD", period="year"),
        duplicates=["remoteok:9"],
        fetched_at=datetime.now(timezone.utc),
        raw={"id": 1},
    )
    again = Job.model_validate_json(job.model_dump_json())
    assert again == job
    summary = JobSummary.from_job(job)
    assert summary.duplicate_count == 1
    assert summary.salary.currency == "USD"
