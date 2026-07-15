"""Differential conformance test (deliverable 12/16).

Asserts the reference and clean-room agree on validation, normalized payload,
canonical bytes, and digest across every V0.1 and V0.2 CER, with zero
identity-affecting differences and full V0.1 identity reproduction.
"""
from __future__ import annotations

from cer_v0_3.conformance import differential


def test_differential_full_agreement():
    r = differential.run()
    m = r["metrics"]
    assert r["all_identity_agree"] is True
    assert r["identity_affecting_differences"] == 0
    # explicit payload+bytes+digest agreement (not hash-only)
    assert m["payload_agree"] == m["valid_items"] > 0
    assert m["bytes_agree"] == m["valid_items"]
    assert m["digest_agree"] == m["valid_items"]
    assert m["validation_agree"] == m["items"]
    # every invalid vector rejected by both, same coarse error class
    assert m["error_category_agree"] == m["invalid_items"] > 0
    # every frozen V0.1 vector digest reproduced by the clean-room
    assert m["v0_1_identity_reproduced"] == m["v0_1_items"] > 0


def test_no_specification_ambiguity_affecting_identity():
    r = differential.run()
    ambiguous = [d for d in r["differences"] if d["class"] == "specification_ambiguity"]
    assert ambiguous == [], f"identity-affecting spec ambiguity found: {ambiguous}"
