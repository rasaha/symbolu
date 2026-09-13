"""The identifier derivations, against the rule's own published test vectors.

Rule section 6a publishes eight vectors. They are reproduced here from this
implementation rather than copied from the model that generated them, so the table in
the PDF and the code in this package are checked against each other rather than
against a shared source of error.
"""

from __future__ import annotations

import pytest

from ugence_change_effect_records import (
    ContractViolation,
    IntroducingRole,
    assign_ordinals,
    chain_id,
    obligation_id,
)

BASE = dict(
    tenant="tenant-1", candidate_digest="cand-abc", anomaly_family="family-7",
    family_seed_digest="seed-9", chain_instance_id="inst-1",
)
BASE_CHAIN = "ed9c1339aaec9ab87341a9ba956a5de5e85d4ed8ee0e9c3bd684a30aeeebc2ea"


def test_the_published_chain_vectors():
    assert chain_id(**BASE) == BASE_CHAIN
    assert chain_id(**BASE) == chain_id(**BASE), "identical inputs, identical identifier"
    assert chain_id(**{**BASE, "tenant": "tenant-2"}) == (
        "d7b1d674575f0b5c534075ce860a1ad208548bb0f10a2647240c6e0b5dbe8aa9")
    assert chain_id(**{**BASE, "chain_instance_id": "inst-2"}) == (
        "8fae24182dc8e3611866d11d22c7026a3235a550746bf2b359912e4fa51633fc")


def test_the_published_obligation_vectors():
    common = dict(
        chain=BASE_CHAIN, introducing_role="CLASSIFICATION",
        obligation_kind="UNDERSIZED_CELL", coordinate="subject_classes/cell.1",
    )
    assert obligation_id(**common, ordinal=0) == (
        "205ee9fdb64b79eebc2eff3b2814a5ec678210e739506a7fcefb6d4df9322b81")
    assert obligation_id(**common, ordinal=1) == (
        "2f940f604811c262beb308c5b210553f93f0d1de8a15db0df616d86cca921ebb")


def test_the_concatenation_ambiguity_the_vectors_exist_to_demonstrate():
    """``"a|b"+"c"`` and ``"a"+"b|c"`` are one byte string; these are two identifiers."""

    a = chain_id(tenant="a|b", candidate_digest="c", anomaly_family="f",
                 family_seed_digest="s", chain_instance_id="i")
    b = chain_id(tenant="a", candidate_digest="b|c", anomaly_family="f",
                 family_seed_digest="s", chain_instance_id="i")
    assert a == "d3b0a0ea7e7ba5fc80e5ce155f79897806f3dfcad118f3e75602fb7cb38bd169"
    assert b == "dfa54a2c24a00d2a45e76fad23df2ee57dd11de01990e713e7f855593d822738"
    assert a != b


def test_identifiers_are_full_untruncated_digests():
    assert len(chain_id(**BASE)) == 64
    assert all(c in "0123456789abcdef" for c in chain_id(**BASE))


def test_tenant_is_normalised_before_hashing():
    assert chain_id(**{**BASE, "tenant": "  TENANT-1 "}) == BASE_CHAIN


def test_a_returning_candidate_receives_a_disjoint_obligation_set():
    """Same tenant, digest, family and reused seed; a fresh chain instance."""

    first = chain_id(**BASE)
    second = chain_id(**{**BASE, "chain_instance_id": "inst-2"})
    assert first != second
    common = dict(introducing_role="CLASSIFICATION", obligation_kind="NO_ANCHOR",
                  coordinate="context_predicates", ordinal=0)
    assert obligation_id(chain=first, **common) != obligation_id(chain=second, **common)


def test_the_introducing_role_is_a_constant_not_a_digest():
    common = dict(chain=BASE_CHAIN, obligation_kind="K", coordinate="c", ordinal=0)
    assert obligation_id(introducing_role=IntroducingRole.CLASSIFICATION, **common) != (
        obligation_id(introducing_role=IntroducingRole.CONFIRMATION_AMENDMENT, **common))
    with pytest.raises(ContractViolation):
        obligation_id(introducing_role="SOMETHING_ELSE", **common)


def test_an_ordinal_is_an_integer_and_never_a_boolean():
    with pytest.raises(ContractViolation):
        obligation_id(chain=BASE_CHAIN, introducing_role="CLASSIFICATION",
                      obligation_kind="K", coordinate="c", ordinal=True)


def test_ordinals_are_assigned_canonically_and_reproducibly():
    specs = [("B", "y"), ("A", "x"), ("A", "x"), ("A", "w")]
    assert assign_ordinals(specs) == (
        ("A", "w", 0), ("A", "x", 0), ("A", "x", 1), ("B", "y", 0))
    assert assign_ordinals(specs) == assign_ordinals(list(reversed(specs)))
