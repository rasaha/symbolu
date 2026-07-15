"""CER V0.2 profile registry. Unknown profiles fail closed."""
from __future__ import annotations

from . import rollout, scale
from .base import CERValidationError

REGISTRY = {
    scale.PROFILE_ID: scale,
    rollout.PROFILE_ID: rollout,
}


def get_profile(profile_id: str):
    prof = REGISTRY.get(profile_id)
    if prof is None:
        raise CERValidationError(f"unsupported profile {profile_id!r} (fail closed)")
    return prof
