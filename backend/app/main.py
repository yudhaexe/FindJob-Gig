"""FastAPI entry point. Run: uvicorn app.main:app --reload (from backend/)."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import jobs, meta
from core.paths import FRONTEND_DIST, ensure_data_dirs

ensure_data_dirs()

app = FastAPI(title="FindJob&Gig", version="0.1.0")
app.include_router(meta.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")

# Production: serve the built React app. In dev, Vite serves it and proxies /api.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
