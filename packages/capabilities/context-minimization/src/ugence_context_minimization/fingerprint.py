"""Deterministic fingerprinting (domain-separated, canonical, stdlib-only).

Two digests, each with its own versioned domain separator so they can never
collide with each other or any other Ugence fingerprint, and both over canonical
JSON (sorted keys, no whitespace):

* :func:`result_fingerprint` — the **outcome** digest. A stable digest of the
  selected outcome only. Byte-identical to the v0.1.0 field. It binds ONLY: context
  id, mode, surviving ids (ordered), structurally-removed / extractively-removed /
  restored / protected id sets, equivalence status, fallback flag, policy **version**,
  oracle id, and oracle contract version. It deliberately does NOT include token
  counts, unit text/content, requested reduction/budget, evaluation time, reason
  codes, the policy fingerprint, the oracle validity/correlation, or the opaque
  equivalence-key value. (Token counts are bound by ``run_fingerprint``, not here.)
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
# run/2 (v0.1.2): the token-counter identity became module-qualified (was the bare
# class name), so the run-fingerprint domain is bumped honestly. run_fingerprint is a
# v0.1.1 addition with no external consumer; the outcome digest (result/1) is
# unchanged and remains byte-compatible.
_RUN_DOMAIN = b"ugence-context-minimization/run/2\x00"


def _unit_content_digest(text: str) -> str:
    """Compact, canonical digest of a unit's extractive payload."""
    return hashlib.sha256(("t\x00" + (text or "")).encode("utf-8")).hexdigest()[:32]


def _canonical_json(payload) -> bytes:
    """Canonical JSON for fingerprinting: sorted keys, no whitespace, and NON-FINITE
    numbers REJECTED (``allow_nan=False``). Default ``json.dumps`` would emit the
    non-standard ``NaN`` / ``Infinity`` tokens; a digest must never contain them.
    A non-finite value raises ``ValueError`` deterministically rather than producing
    an unstable or invalid digest.
    """
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _counter_identity(counter) -> str:
    """Stable identity for a token counter used in the run fingerprint.

    Prefers a neutral, explicit ``counter_id`` (optionally ``counter_version``) the
    counter may expose; otherwise falls back to the fully-qualified type name
    (module + qualname), which is stable across counters that merely share a bare
    class name. ``None`` means the default word/punct counter.
    """
    if counter is None:
        return "default"
    cid = getattr(counter, "counter_id", None)
    if isinstance(cid, str) and cid:
        cver = getattr(counter, "counter_version", None)
        return f"{cid}@{cver}" if isinstance(cver, str) and cver else cid
    t = type(counter)
    return f"{t.__module__}.{t.__qualname__}"


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
    blob = _canonical_json(payload)
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
            "token_counter": _counter_identity(token_counter),
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
    blob = _canonical_json(payload)
    return "sha256:" + hashlib.sha256(_RUN_DOMAIN + blob).hexdigest()
