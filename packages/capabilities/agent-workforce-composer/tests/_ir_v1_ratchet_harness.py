"""The comparison core of the Workflow IR v1 canonicalization ratchet.

Kept free of pytest and of both distributions so the negative controls in
``test_workflow_ir_v1_ratchet_controls.py`` can drive it with injected encoders
and prove it detects drift — without ever modifying production source.
"""
from __future__ import annotations

import hashlib
from typing import Any, Callable, Dict, List, Sequence, Tuple

#: ``sha256:``-prefixed lowercase hex, matching both implementations' digest shape.
DIGEST_PREFIX = "sha256:"


def digest_of(text: str) -> str:
    """The digest a golden entry pins: sha256 over the canonical UTF-8 bytes."""
    return DIGEST_PREFIX + hashlib.sha256(text.encode("utf-8")).hexdigest()


def compare_accepted(
    vectors: Sequence[Tuple[str, Any]],
    compiler_dumps: Callable[[Any], str],
    awc_dumps: Callable[[Any], str],
    goldens: Dict[str, Dict[str, str]],
) -> List[str]:
    """Return one failure line per vector that breaks compatibility.

    Three independent obligations, all required:

    1. **Pairwise** — the two implementations produce identical canonical bytes.
    2. **Golden (compiler)** — the compiler matches the committed expected bytes.
    3. **Golden (AWC)** — AWC matches the same committed expected bytes.

    Pairwise alone cannot see symmetric drift: both implementations could change
    together and still agree. The golden anchor is what catches that, so a vector
    with no committed golden is a failure, never a pass.
    """
    failures: List[str] = []
    for vector_id, value in vectors:
        golden = goldens.get(vector_id)
        if golden is None:
            failures.append(
                f"{vector_id}: no committed golden entry -- a new vector must be "
                "reviewed and pinned, not silently accepted")
            continue
        try:
            c_bytes = compiler_dumps(value)
        except Exception as exc:                       # noqa: BLE001 - reported, not raised
            failures.append(f"{vector_id}: compiler refused an accepted vector: {exc!r}")
            continue
        try:
            a_bytes = awc_dumps(value)
        except Exception as exc:                       # noqa: BLE001
            failures.append(f"{vector_id}: AWC refused an accepted vector: {exc!r}")
            continue

        if c_bytes != a_bytes:
            failures.append(
                f"{vector_id}: PAIRWISE drift\n     compiler: {c_bytes!r}\n     awc     : {a_bytes!r}")
        expected = golden["canonical_bytes"]
        if c_bytes != expected:
            failures.append(
                f"{vector_id}: compiler drifted from golden\n     expected: {expected!r}\n     actual  : {c_bytes!r}")
        if a_bytes != expected:
            failures.append(
                f"{vector_id}: AWC drifted from golden\n     expected: {expected!r}\n     actual  : {a_bytes!r}")
        if digest_of(c_bytes) != golden["digest"]:
            failures.append(
                f"{vector_id}: digest drifted from golden\n     expected: {golden['digest']}\n     actual  : {digest_of(c_bytes)}")
    return failures


def compare_rejected(
    vectors: Sequence[Tuple[str, Any]],
    compiler_dumps: Callable[[Any], str],
    awc_dumps: Callable[[Any], str],
) -> List[str]:
    """Return one failure line per vector where the two disagree on refusal.

    Exception *messages* are deliberately not compared: neither implementation
    publishes its message text as contract. A value one accepts and the other
    refuses is the failure this guards.
    """
    failures: List[str] = []
    for vector_id, value in vectors:
        c_ok = a_ok = True
        try:
            compiler_dumps(value)
        except Exception:                              # noqa: BLE001
            c_ok = False
        try:
            awc_dumps(value)
        except Exception:                              # noqa: BLE001
            a_ok = False
        if c_ok and a_ok:
            failures.append(f"{vector_id}: BOTH accepted a value the corpus pins as rejected")
        elif c_ok != a_ok:
            accepter, refuser = ("compiler", "AWC") if c_ok else ("AWC", "compiler")
            failures.append(
                f"{vector_id}: ACCEPTANCE DISAGREEMENT -- {accepter} accepted it, {refuser} refused it")
    return failures


def build_golden_payload(
    vectors: Sequence[Tuple[str, Any]],
    compiler_dumps: Callable[[Any], str],
    corpus_version: str,
    pinned_version: str,
) -> Dict[str, Any]:
    """Build a candidate golden payload. Deterministically ordered, no clock read."""
    return {
        "corpus_version": corpus_version,
        "pinned_digest_compiler_version": pinned_version,
        "vectors": {
            vid: {"canonical_bytes": (enc := compiler_dumps(value)), "digest": digest_of(enc)}
            for vid, value in vectors
        },
    }
