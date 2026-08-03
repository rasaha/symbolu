"""Deterministic fingerprinting (domain-separated, canonical, stdlib-only).

Two digests, each with its own versioned domain separator so they can never
collide with each other or any other Ugence fingerprint, and both over canonical
JSON (sorted keys, no whitespace):

* :func:`result_fingerprint` — the **outcome** digest. A stable digest of the
  selected outcome only. Byte-identical to the v0.1.0 field. It deliberately does
  NOT include the opaque oracle equivalence-key value, the request contents, or the
  context contents — only what survived/was removed/restored/protected, the token
  counts, the equivalence status, the fallback flag, the policy version, and the
  oracle identity.
* :func:`run_fingerprint` — the **complete run identity** digest. Binds request
  identity (context contract version, id, correlation, ordered unit content digests
  + resolved token counts, requested reduction, requested token budget, mode,
  evaluation time), policy identity (version + actual policy fingerprint +
  token-counter mode), oracle identity (id, contract version, evaluation ref,
  validity horizon, correlation binding), and the outcome (including reason codes).
  It never includes credentials, secrets, or the opaque private equivalence key.
"""

from __future__ import annotations

import hashlib
import json

_DOMAIN = b"ugence-context-minimization/result/1\x00"
_RUN_DOMAIN = b"ugence-context-minimization/run/1\x00"


def _unit_content_digest(text: str) -> str:
    """Compact, canonical digest of a unit's extractive payload."""
    return hashlib.sha256(("t\x00" + (text or "")).encode("utf-8")).hexdigest()[:32]


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


def run_fingerprint(
    context,
    *,
    mode: str,
    requested_reduction: float,
    requested_token_budget,
    evaluation_time,
    policy,
    token_counter,
    base_eval,
    surviving_ids,
    removed_structural,
    removed_extractive,
    restored_ids,
    protected_ids,
    original_tokens: int,
    resulting_tokens: int,
    equivalence_status: str,
    fell_back: bool,
    reason_codes,
) -> str:
    """Return ``sha256:<hex>`` over the complete auditable run identity.

    ``context``/``policy``/``base_eval`` are the neutral package objects; only
    non-sensitive identity is read. ``base_eval`` may be ``None`` (e.g. structural
    mode or a pre-baseline failure), in which case the oracle block is null.
    """
    units = [
        {
            "id": u.id,
            "source_type": u.source_type,
            "content": _unit_content_digest(u.text),
            "tokens": u.counted_tokens(token_counter),
            "protected": bool(u.protected),
            "redundancy_set": u.redundancy_set,
        }
        for u in context.units
    ]
    oracle = None
    if base_eval is not None:
        oracle = {
            "oracle_id": base_eval.oracle_id,
            "contract_version": base_eval.contract_version,
            "evaluation_ref": base_eval.evaluation_ref,
            "valid_until": base_eval.valid_until,
            "correlation_id": base_eval.correlation_id,
        }
    payload = {
        "request": {
            "context_contract_version": context.context_contract_version,
            "context_id": context.id,
            "correlation_id": context.correlation_id,
            "mode": mode,
            "requested_reduction": requested_reduction,
            "requested_token_budget": requested_token_budget,
            "evaluation_time": evaluation_time,
            "units": units,
        },
        "policy": {
            "version": policy.version,
            "fingerprint": policy.fingerprint(),
            "token_counter": "default" if token_counter is None else type(token_counter).__name__,
        },
        "oracle": oracle,
        "outcome": {
            "surviving_ids": list(surviving_ids),
            "removed_structural": sorted(removed_structural),
            "removed_extractive": sorted(removed_extractive),
            "restored_ids": sorted(restored_ids),
            "protected_ids": sorted(protected_ids),
            "original_tokens": original_tokens,
            "resulting_tokens": resulting_tokens,
            "equivalence_status": equivalence_status,
            "fell_back": bool(fell_back),
            "reason_codes": list(reason_codes),
        },
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(_RUN_DOMAIN + blob).hexdigest()
