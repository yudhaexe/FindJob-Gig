"""FastAPI entry point. Run: uvicorn app.main:app --reload (from backend/)."""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import jobs, meta, schedules, scrape
from core.paths import FRONTEND_DIST, ensure_data_dirs
from scraper import scheduler

ensure_data_dirs()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # FJG_NO_SCHEDULER=1 disables the in-app loop (tests; Task Scheduler-only setups).
    task = None if os.environ.get("FJG_NO_SCHEDULER") else asyncio.create_task(scheduler.loop())
    yield
    if task:
        task.cancel()


app = FastAPI(title="FindJob&Gig", version="0.1.0", lifespan=lifespan)
app.include_router(meta.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(scrape.router, prefix="/api")
app.include_router(schedules.router, prefix="/api")

# Production: serve the built React app. In dev, Vite serves it and proxies /api.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
