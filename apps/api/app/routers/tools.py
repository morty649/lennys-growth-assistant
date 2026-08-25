from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from app.dependencies import verify_internal
from app.retrieval import (
    clarification_for_resolution,
    corpus_catalog,
    get_source_context,
    resolve_guest_reference,
    search_transcripts,
)
from app.schemas import CatalogRequest, EntityResolveRequest, SearchRequest

router = APIRouter()


@router.post("/internal/tools/search")
def internal_search(
    payload: SearchRequest,
    x_internal_token: Annotated[str | None, Header()] = None,
):
    verify_internal(x_internal_token)
    started = perf_counter()
    result = search_transcripts(
        payload.query, guest=payload.guest, topic=payload.topic, limit=payload.limit
    )
    result["duration_ms"] = (perf_counter() - started) * 1000
    return result


@router.post("/internal/tools/catalog")
def internal_catalog(
    payload: CatalogRequest,
    x_internal_token: Annotated[str | None, Header()] = None,
):
    verify_internal(x_internal_token)
    return corpus_catalog(payload.query, payload.limit)


@router.post("/internal/tools/resolve-entity")
def internal_resolve_entity(
    payload: EntityResolveRequest,
    x_internal_token: Annotated[str | None, Header()] = None,
):
    verify_internal(x_internal_token)
    resolution = resolve_guest_reference(payload.reference)
    return {
        **resolution,
        "clarification": (
            clarification_for_resolution(resolution)
            if resolution["status"] != "resolved"
            else None
        ),
    }


@router.get("/internal/tools/source/{source_id:path}")
def internal_source(
    source_id: str,
    x_internal_token: Annotated[str | None, Header()] = None,
):
    verify_internal(x_internal_token)
    source = get_source_context(source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return source
