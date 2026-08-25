from fastapi import APIRouter, BackgroundTasks

from app.indexing import corpus_manifest, ingestion_state, run_ingestion
from app.schemas import IngestStatus

router = APIRouter()


@router.get("/api/ingest/status", response_model=IngestStatus)
def ingest_status():
    return ingestion_state.snapshot()


@router.get("/api/ingest/manifest")
def ingest_manifest():
    return corpus_manifest()


@router.post("/api/ingest", response_model=IngestStatus, status_code=202)
def ingest(background_tasks: BackgroundTasks, force: bool = False, limit: int | None = None):
    if ingestion_state.snapshot()["state"] == "running":
        return ingestion_state.snapshot()
    background_tasks.add_task(run_ingestion, limit, force)
    return {"state": "queued", "episodes_total": 0, "episodes_processed": 0, "evidence_units": 0}
