"""
Public (leakage-controlled) loader.

Exposes only the executable projection of the synthetic corpus and the public
evidence records produced by the layer. Gold status, difficulty, family, and
authoring rationale are never exposed here.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Tuple

from relationship_claim_validation import corpus
from relationship_claim_validation.model import Document, RelationshipClaim
from relationship_claim_validation.validator import (
    ABLATIONS, AblationConfig, ClaimValidationLayer,
)

_BANNED_PUBLIC_KEYS = ("gold", "gold_status", "difficulty", "family", "rationale")


def public_claims() -> Tuple[dict, ...]:
    claims = corpus.public_claims()
    for c in claims:
        for k in _BANNED_PUBLIC_KEYS:
            assert k not in c, f"leakage: {k} in public claim"
    return claims


def full_config(name: str = "V4") -> AblationConfig:
    for cfg in ABLATIONS:
        if cfg.name == name:
            return cfg
    raise KeyError(name)


def validate_public(config_name: str = "V4") -> Tuple[dict, ...]:
    """Run the layer and return public evidence dicts (no gold)."""
    docs: Mapping[str, Document] = corpus.documents()
    claims: Tuple[RelationshipClaim, ...] = corpus.claims()
    layer = ClaimValidationLayer(full_config(config_name), docs)
    recs = layer.validate_corpus(claims)
    return tuple(r.to_public_dict() for r in recs)
