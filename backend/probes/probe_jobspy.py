"""Validate JobSpy against real boards for creative freelance roles."""
import json, time, traceback
from pathlib import Path
from jobspy import scrape_jobs

OUT = Path(__file__).resolve().parents[2] / "data" / "probes"
OUT.mkdir(parents=True, exist_ok=True)

CASES = [
    # (label, kwargs)
    ("indeed_us_videographer_contract", dict(site_name=["indeed"], search_term="videographer", location="USA", country_indeed="USA", job_type="contract", results_wanted=20, hours_old=168)),
    ("indeed_id_videografer", dict(site_name=["indeed"], search_term="videografer", location="Indonesia", country_indeed="Indonesia", results_wanted=20)),
    ("indeed_id_video_editor", dict(site_name=["indeed"], search_term="video editor", location="Jakarta", country_indeed="Indonesia", results_wanted=20)),
    ("linkedin_photographer_freelance", dict(site_name=["linkedin"], search_term="freelance photographer", location="Indonesia", results_wanted=20, hours_old=336)),
    ("linkedin_video_editor_remote", dict(site_name=["linkedin"], search_term="video editor", is_remote=True, job_type="contract", results_wanted=20)),
    ("google_photo_editor", dict(site_name=["google"], google_search_term="freelance photo editor jobs remote since last week", results_wanted=20)),
    ("glassdoor_videographer", dict(site_name=["glassdoor"], search_term="videographer", location="New York, NY", country_indeed="USA", results_wanted=15)),
    ("ziprecruiter_videographer", dict(site_name=["zip_recruiter"], search_term="videographer", location="Los Angeles, CA", results_wanted=15)),
]

summary = []
for label, kw in CASES:
    t = time.time()
    try:
        df = scrape_jobs(verbose=0, description_format="markdown", **kw)
        rows = df.to_dict("records") if df is not None else []
        status, err = "ok", None
    except Exception as e:  # noqa
        rows, status, err = [], "error", f"{type(e).__name__}: {e}"[:300]
    ms = int((time.time() - t) * 1000)
    cols = ["site", "title", "company", "location", "job_type", "is_remote", "min_amount", "max_amount", "currency", "interval", "date_posted", "job_url"]
    sample = [{k: (str(r.get(k)) if r.get(k) is not None else None) for k in cols} for r in rows[:5]]
    (OUT / f"jobspy_{label}.json").write_text(json.dumps([{k: str(v) for k, v in r.items()} for r in rows], ensure_ascii=False, indent=1), encoding="utf8")
    with_salary = sum(1 for r in rows if str(r.get("min_amount")) not in ("None", "nan"))
    summary.append({"case": label, "status": status, "ms": ms, "rows": len(rows), "with_salary": with_salary, "error": err, "sample": sample})
    print(f"{label:36} {status:5} {ms:6}ms rows={len(rows):3} salary={with_salary:3} {err or ''}", flush=True)
    time.sleep(3)

(OUT / "_summary_jobspy.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf8")
