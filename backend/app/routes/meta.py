from fastapi import APIRouter

from core.paths import DATA_DIR

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "0.1.0", "data_dir": str(DATA_DIR)}
