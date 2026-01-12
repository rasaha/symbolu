"""
Master Chat API Endpoints
=========================

FastAPI endpoints for the master chat system.

Provides REST API access to:
- Master chat with context retrieval
- Bucket browsing and search
- Session statistics

Usage:
    Include this router in your FastAPI app:

    from symbolu.service.master_chat.api import router as master_chat_router
    app.include_router(master_chat_router, prefix="/master-chat")

Version: 1.0
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .bucket_models import MessageSignals, BucketCategory
from .master_session import get_master_session_store, MasterSessionStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Master Chat"])


# =============================================================================
# Request/Response Models
# =============================================================================

class SignalsInput(BaseModel):
    """Input model for ontological signals."""
    ontology_layers: Dict[int, float] = Field(default_factory=dict)
    lower_mass: float = 0.5
    upper_mass: float = 0.5
    kosha_activations: Dict[str, float] = Field(default_factory=dict)
    kosha_resonance: float = 0.5
    vritti_distribution: Dict[str, float] = Field(default_factory=dict)
    dominant_vritti: str = "inertia"
    guna_distribution: Dict[str, float] = Field(default_factory=dict)
    guna_resonance: float = 0.5
    entropy_H_D: float = 0.5
    entropy_H_G: float = 0.5
    entropy_H_K: float = 0.5
    normalized_entropy: float = 0.5


class GetContextRequest(BaseModel):
    """Request for getting context."""
    user_id: str = Field(..., description="User identifier")
    message: str = Field(..., description="User's message")
    signals: Optional[SignalsInput] = Field(
        None,
        description="Ontological signals (optional)"
    )


class GetContextResponse(BaseModel):
    """Response with context for LLM."""
    turn_id: str
    context_text: str
    buckets_activated: int
    activated_buckets: List[Dict[str, Any]]
    routing_metadata: Dict[str, Any]


class HarvestTurnRequest(BaseModel):
    """Request to harvest knowledge from a turn."""
    user_id: str
    user_message: str
    assistant_response: str
    signals: Optional[SignalsInput] = None
    turn_id: Optional[str] = None


class HarvestTurnResponse(BaseModel):
    """Response from harvesting."""
    facts_harvested: int
    turn_id: str


class BucketEntryResponse(BaseModel):
    """Response model for a bucket entry."""
    entry_id: str
    content: str
    summary: Optional[str]
    importance_score: float
    timestamp: str
    entities: List[str]


class BucketResponse(BaseModel):
    """Response model for a bucket."""
    bucket_id: str
    display_name: str
    description: str
    total_entries: int
    access_count: int
    last_accessed: Optional[str]


class SessionStatsResponse(BaseModel):
    """Response model for session statistics."""
    user_id: str
    turn_count: int
    total_entries: int
    buckets_with_entries: int
    most_active_bucket: Optional[str]
    entries_by_bucket: Dict[str, int]
    session_age_hours: float


# =============================================================================
# Helper Functions
# =============================================================================

def get_store() -> MasterSessionStore:
    """Get the global master session store."""
    return get_master_session_store()


def signals_input_to_message_signals(
    signals_input: Optional[SignalsInput]
) -> Optional[MessageSignals]:
    """Convert Pydantic model to dataclass."""
    if signals_input is None:
        return None

    return MessageSignals(
        ontology_layers=signals_input.ontology_layers,
        lower_mass=signals_input.lower_mass,
        upper_mass=signals_input.upper_mass,
        kosha_activations=signals_input.kosha_activations,
        kosha_resonance=signals_input.kosha_resonance,
        vritti_distribution=signals_input.vritti_distribution,
        dominant_vritti=signals_input.dominant_vritti,
        guna_distribution=signals_input.guna_distribution,
        guna_resonance=signals_input.guna_resonance,
        entropy_H_D=signals_input.entropy_H_D,
        entropy_H_G=signals_input.entropy_H_G,
        entropy_H_K=signals_input.entropy_H_K,
        normalized_entropy=signals_input.normalized_entropy,
    )


# =============================================================================
# Context Endpoints
# =============================================================================

@router.post("/context", response_model=GetContextResponse)
async def get_context(request: GetContextRequest) -> GetContextResponse:
    """
    Get context for a user message.

    Activates relevant buckets based on the message and signals,
    returns formatted context for LLM injection.
    """
    store = get_store()
    signals = signals_input_to_message_signals(request.signals)

    turn_context = store.get_context(
        user_id=request.user_id,
        message=request.message,
        signals=signals,
    )

    # Format activated buckets for response
    activated_info = []
    for ab in turn_context.activated_buckets:
        activated_info.append({
            "bucket_id": ab.bucket.bucket_id,
            "display_name": ab.bucket.display_name,
            "activation_score": ab.activation_score,
            "activation_reason": ab.activation_reason,
            "entries_count": len(ab.retrieved_entries),
        })

    return GetContextResponse(
        turn_id=turn_context.turn_id,
        context_text=turn_context.context_text,
        buckets_activated=len(turn_context.activated_buckets),
        activated_buckets=activated_info,
        routing_metadata=turn_context.routing_metadata,
    )


@router.post("/harvest", response_model=HarvestTurnResponse)
async def harvest_turn(request: HarvestTurnRequest) -> HarvestTurnResponse:
    """
    Harvest knowledge from a completed conversation turn.

    Extracts facts from the user message and assistant response,
    classifies them into appropriate buckets.
    """
    store = get_store()
    signals = signals_input_to_message_signals(request.signals)

    facts_count = await store.harvest_turn(
        user_id=request.user_id,
        user_message=request.user_message,
        assistant_response=request.assistant_response,
        signals=signals,
        turn_id=request.turn_id,
    )

    return HarvestTurnResponse(
        facts_harvested=facts_count,
        turn_id=request.turn_id or "generated",
    )


# =============================================================================
# Bucket Browsing Endpoints
# =============================================================================

@router.get("/users/{user_id}/buckets", response_model=List[BucketResponse])
async def list_buckets(user_id: str) -> List[BucketResponse]:
    """List all buckets for a user."""
    store = get_store()
    session = store.get(user_id)

    if not session:
        raise HTTPException(status_code=404, detail="User session not found")

    buckets = []
    for bucket in session.buckets.values():
        buckets.append(BucketResponse(
            bucket_id=bucket.bucket_id,
            display_name=bucket.display_name,
            description=bucket.description,
            total_entries=bucket.total_entries,
            access_count=bucket.access_count,
            last_accessed=bucket.last_accessed.isoformat() if bucket.last_accessed else None,
        ))

    return buckets


@router.get(
    "/users/{user_id}/buckets/{bucket_id}/entries",
    response_model=List[BucketEntryResponse]
)
async def get_bucket_entries(
    user_id: str,
    bucket_id: str,
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("recency", regex="^(recency|importance)$"),
) -> List[BucketEntryResponse]:
    """Get entries from a specific bucket."""
    store = get_store()

    entries = store.get_bucket_entries(
        user_id=user_id,
        bucket_id=bucket_id,
        limit=limit,
        sort_by=sort_by,
    )

    if not entries:
        # Check if user or bucket exists
        session = store.get(user_id)
        if not session:
            raise HTTPException(status_code=404, detail="User session not found")
        if bucket_id not in session.buckets:
            raise HTTPException(status_code=404, detail="Bucket not found")
        # Empty bucket is valid
        return []

    return [
        BucketEntryResponse(
            entry_id=e.entry_id,
            content=e.content,
            summary=e.summary,
            importance_score=e.importance_score,
            timestamp=e.timestamp.isoformat(),
            entities=e.entities,
        )
        for e in entries
    ]


@router.get("/users/{user_id}/search", response_model=List[BucketEntryResponse])
async def search_entries(
    user_id: str,
    query: str = Query(..., min_length=2),
    bucket_ids: Optional[str] = Query(None, description="Comma-separated bucket IDs"),
    limit: int = Query(10, ge=1, le=50),
) -> List[BucketEntryResponse]:
    """Search for entries across buckets."""
    store = get_store()

    bucket_id_list = None
    if bucket_ids:
        bucket_id_list = [b.strip() for b in bucket_ids.split(",")]

    entries = store.search_buckets(
        user_id=user_id,
        query=query,
        bucket_ids=bucket_id_list,
        limit=limit,
    )

    return [
        BucketEntryResponse(
            entry_id=e.entry_id,
            content=e.content,
            summary=e.summary,
            importance_score=e.importance_score,
            timestamp=e.timestamp.isoformat(),
            entities=e.entities,
        )
        for e in entries
    ]


# =============================================================================
# Session Management Endpoints
# =============================================================================

@router.get("/users/{user_id}/stats", response_model=SessionStatsResponse)
async def get_session_stats(user_id: str) -> SessionStatsResponse:
    """Get statistics for a user's session."""
    store = get_store()
    stats = store.get_stats(user_id)

    if not stats:
        raise HTTPException(status_code=404, detail="User session not found")

    return SessionStatsResponse(**stats)


@router.post("/users/{user_id}/init")
async def init_session(user_id: str) -> Dict[str, Any]:
    """Initialize a new master session for a user."""
    store = get_store()
    session = store.get_or_create(user_id)

    return {
        "status": "initialized",
        "user_id": user_id,
        "session_id": session.session_id,
        "bucket_count": len(session.buckets),
    }


@router.delete("/users/{user_id}")
async def delete_session(user_id: str) -> Dict[str, Any]:
    """
    Delete a user's session.

    WARNING: This permanently deletes all harvested knowledge.
    """
    store = get_store()

    if store.delete(user_id):
        return {"status": "deleted", "user_id": user_id}
    else:
        raise HTTPException(status_code=404, detail="User session not found")


@router.get("/users", response_model=List[str])
async def list_users() -> List[str]:
    """List all users with active sessions."""
    store = get_store()
    return store.list_users()


# =============================================================================
# Bucket Categories Info
# =============================================================================

@router.get("/bucket-categories")
async def list_bucket_categories() -> List[Dict[str, str]]:
    """List all available bucket categories with descriptions."""
    return [
        {"category": cat.value, "name": cat.name}
        for cat in BucketCategory
    ]
