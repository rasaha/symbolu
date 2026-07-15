"""CER V0.3 profile registry (original side).

Adds ``database.mutation.v1`` (the new non-Kubernetes domain). The two Kubernetes
profiles remain frozen in ``cer_v0_2`` and are dispatched there — they are NOT
re-implemented here, so their digests are guaranteed unchanged.
"""
from __future__ import annotations

from . import database

REGISTRY = {
    database.PROFILE_ID: database,
}


def get_profile(profile_id: str):
    return REGISTRY.get(profile_id)
