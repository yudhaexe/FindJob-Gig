"""Filesystem locations. Override the data dir with FJG_DATA_DIR."""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = Path(os.environ.get("FJG_DATA_DIR", ROOT_DIR / "data"))
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

RAW_DIR = DATA_DIR / "raw"
JOBS_DIR = DATA_DIR / "jobs"
RUNS_DIR = DATA_DIR / "runs"
STATE_DIR = DATA_DIR / "state"
ARCHIVE_DIR = DATA_DIR / "archive"


def ensure_data_dirs() -> None:
    for d in (RAW_DIR, JOBS_DIR, RUNS_DIR, STATE_DIR, ARCHIVE_DIR):
        d.mkdir(parents=True, exist_ok=True)
