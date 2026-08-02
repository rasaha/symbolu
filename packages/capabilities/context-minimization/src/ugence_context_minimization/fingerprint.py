"""Deterministic result fingerprinting (domain-separated, canonical, stdlib-only).

The fingerprint is a stable digest of the *outcome* of a minimization run. It uses
canonical JSON (sorted keys, no whitespace) and a domain-separation prefix so it
can never collide with any other Ugence fingerprint. It deliberately does NOT
include the opaque oracle equivalence key value (that is the oracle's private
contract) — only whether equivalence was verified, and the oracle identity.
"""

from __future__ import annotations

import hashlib
import json

_DOMAIN = b"ugence-context-minimization/result/1\x00"


def result_fingerprint(
    *,
    context_id: str,
    mode: str,
    surviving_ids,
    removed_structural,
    removed_extractive,
    restored_ids,
    protected_ids,
    equivalence_status: str,
    fell_back: bool,
    policy_version: str,
    oracle_id,
    oracle_contract_version,
) -> str:
    """Return ``sha256:<hex>`` over a canonical view of the outcome.

    Surviving ids preserve order (order is part of the outcome); the id *sets* for
    removed/restored/protected are sorted so the digest is independent of discovery
    order but sensitive to membership.
    """
    payload = {
        "context_id": context_id,
        "mode": mode,
        "surviving_ids": list(surviving_ids),
        "removed_structural": sorted(removed_structural),
        "removed_extractive": sorted(removed_extractive),
        "restored_ids": sorted(restored_ids),
        "protected_ids": sorted(protected_ids),
        "equivalence_status": equivalence_status,
        "fell_back": bool(fell_back),
        "policy_version": policy_version,
        "oracle_id": oracle_id,
        "oracle_contract_version": oracle_contract_version,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(_DOMAIN + blob).hexdigest()
