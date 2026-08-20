"""This package reads no clock. Asserted over source imports and AST call expressions.

Every instant Phase 5B-0A handles is one a caller injected. That matters twice over: a
verification determination must be reproducible by an auditor holding the same inputs, and
an anchor's lifecycle answer is meaningless without saying *as of when*. A package that
reached for the wall clock would produce a determination nobody else could reproduce.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from _producer_fixtures import (
    AS_OF,
    WINDOW_FROM,
    WINDOW_TO,
    build_anchor,
    build_attestation,
    build_directory,
    build_signer,
    build_verifier,
)

import ugence_cloud_scaling_producer_attestation as pkg
from ugence_cloud_scaling_producer_attestation import (
    KeyRevocation,
    ProducerAttestationCanonicalFieldError,
    ProducerAttestationVerifier,
    ProducerAuthenticityOutcome,
    anchor_lifecycle_outcome,
    mint_producer_attestation,
)

#: Property category: this module's default is declared in ``tests/conftest.py``
#: (``MODULE_PROPERTY_CATEGORY``), and a test that departs from it carries its own
#: ``@pytest.mark.<category>``, which wins. ``tests/test_property_ledger.py`` counts
#: the resolved categories, so the adversarial-to-happy ratio is machine-checked
#: rather than claimed.

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
SOURCES = sorted(PKG_DIR.rglob("*.py"))
O = ProducerAuthenticityOutcome

#: Every way this package could read a wall clock.
CLOCK_CALLS = {"now", "utcnow", "today", "time", "monotonic", "perf_counter", "fromtimestamp"}
CLOCK_MODULES = {"time", "calendar"}


def test_no_module_imports_a_clock_source():
    """T-1: ``time`` and ``calendar`` are absent from every module in the package."""

    offenders = []
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in CLOCK_MODULES:
                        offenders.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in CLOCK_MODULES:
                    offenders.append(f"{path.name}: from {node.module}")
    assert offenders == [], offenders


def test_no_ast_call_expression_reads_a_wall_clock():
    """T-2: no ``.now()``, ``.utcnow()``, ``.today()`` or monotonic read anywhere."""

    offenders = []
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in CLOCK_CALLS:
                    offenders.append(f"{path.name}: .{node.func.attr}()")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in CLOCK_CALLS:
                    offenders.append(f"{path.name}: {node.func.id}()")
    assert offenders == [], offenders


@pytest.mark.invariant
def test_the_verification_entry_point_requires_an_injected_instant():
    """T-3: ``as_of`` is a required keyword parameter with no default."""

    parameter = inspect.signature(ProducerAttestationVerifier.verify).parameters["as_of"]
    assert parameter.default is inspect.Parameter.empty
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY


@pytest.mark.invariant
def test_the_minting_entry_point_requires_an_injected_instant():
    """T-4: minting takes ``issued_at`` from the caller too, and stamps no timestamp."""

    parameter = inspect.signature(mint_producer_attestation).parameters["issued_at"]
    assert parameter.default is inspect.Parameter.empty


@pytest.mark.parametrize(
    "naive", [datetime(2026, 1, 1), datetime(2026, 6, 30, 12, 0, 0)]
)
def test_a_naive_instant_is_refused_at_every_entry_point(candidate, naive):
    """T-5: refused, never assumed UTC — at verification and at minting alike."""

    verifier = build_verifier()
    result = verifier.verify(
        candidate=candidate, attestation=build_attestation(candidate), as_of=naive
    )
    assert result.refusal.outcome is O.UNSUPPORTED_EXACT_TYPE

    with pytest.raises(ProducerAttestationCanonicalFieldError):
        mint_producer_attestation(
            signer=build_signer(),
            tenant_id=candidate.tenant_id,
            subject_id=candidate.subject_id,
            recommendation_id=candidate.recommendation_id,
            recommendation_digest=candidate.recommendation_digest,
            issued_at=naive,
        )


def test_the_same_inputs_at_different_instants_can_differ_only_through_the_anchor(
    candidate,
):

    """T-6: time enters exactly one decision — the anchor's lifecycle — and no other."""

    attestation = build_attestation(candidate)
    anchor = build_anchor(
        effective_from=WINDOW_FROM, effective_to=WINDOW_FROM + timedelta(minutes=10)
    )
    verifier = build_verifier(directory=build_directory(anchor))

    inside = verifier.verify(
        candidate=candidate, attestation=attestation, as_of=WINDOW_FROM
    )
    outside = verifier.verify(
        candidate=candidate,
        attestation=attestation,
        as_of=WINDOW_FROM + timedelta(minutes=11),
    )

    assert inside.refusal is None
    assert outside.refusal.outcome is O.ANCHOR_EXPIRED


@pytest.mark.happy
def test_an_offset_aware_non_utc_instant_is_normalized_not_refused(candidate):
    """T-7: any stated offset is acceptable and is normalized; only silence is refused."""

    plus_two = timezone(timedelta(hours=2))
    result = build_verifier().verify(
        candidate=candidate,
        attestation=build_attestation(candidate),
        as_of=AS_OF.astimezone(plus_two),
    )
    assert result.refusal is None
    assert result.verified_attestation.verified_as_of_fact == AS_OF.astimezone(
        timezone.utc
    )


def test_the_lifecycle_helper_requires_an_aware_instant():
    """T-8: even the internal lifecycle helper refuses a naive instant."""

    with pytest.raises(ProducerAttestationCanonicalFieldError):
        anchor_lifecycle_outcome(build_anchor(), datetime(2026, 1, 1, 0, 5, 0))


def test_revocation_is_dated_rather_than_a_bare_flag(candidate):
    """T-9: 'revoked' is always 'revoked as of when', decided against the injected instant."""

    revoked_at = AS_OF
    anchor = build_anchor(revocation=KeyRevocation(effective_at=revoked_at))
    verifier = build_verifier(directory=build_directory(anchor))
    attestation = build_attestation(candidate)

    before = verifier.verify(
        candidate=candidate, attestation=attestation, as_of=revoked_at - timedelta(seconds=1)
    )
    at_and_after = verifier.verify(
        candidate=candidate, attestation=attestation, as_of=revoked_at
    )

    assert before.refusal is None
    assert at_and_after.refusal.outcome is O.ANCHOR_REVOKED


@pytest.mark.happy
def test_no_freshness_check_is_performed_on_the_attestation(candidate):
    """T-10: ``issued_at`` is a carried fact, never compared to ``as_of``.

    Attestation freshness — a maximum age, a TTL, a skew allowance — is a later phase's,
    under its own trusted clock and its own ratified bounds. Phase 5B-0A deliberately does
    not invent one: an unratified freshness window would be an unratified authority
    decision. A very old attestation verifies here, and the artifact carries the issuance
    instant so a later phase can judge it.
    """

    ancient = build_attestation(
        candidate, issued_at=datetime(2020, 1, 1, tzinfo=timezone.utc)
    )
    result = build_verifier().verify(
        candidate=candidate, attestation=ancient, as_of=AS_OF
    )
    assert result.refusal is None
    assert result.verified_attestation.attestation_issued_at_fact.year == 2020
