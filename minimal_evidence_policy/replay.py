"""Phase 8 - Deterministic replay verification for minimal-policy decisions."""
from __future__ import annotations
from typing import Any, Dict, List
from minimal_evidence_policy import classifier


def replay_stable(items: List[Dict[str, Any]]) -> bool:
    """Every item's decision signature must be identical across two runs."""
    a = [classifier.replay_signature(classifier.classify(it)) for it in items]
    b = [classifier.replay_signature(classifier.classify(it)) for it in items]
    return a == b
