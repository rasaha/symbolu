"""Action-hash projection: inclusion/exclusion rules (spec §10)."""

from __future__ import annotations

import copy

from action_gate_ref import hashing, jcs, projection
from action_gate_ref.conformance import ref_envelope


def _mut(e, **kw):
    e = copy.deepcopy(e)
    e.update(kw)
    return e


def test_excluded_fields_do_not_change_hash():
    e = ref_envelope()
    h = projection.action_hash(e)
    # action_id, timestamp, agent_identity.sig, approvals, attestation excluded
    e2 = _mut(e, action_id="00000000-0000-4000-8000-000000000000",
              timestamp="2026-07-12T23:59:59.000Z",
              approvals=[{"x": "y"}], attestation={"type": "z", "evidence": "q", "exp": "t"})
    e2["agent_identity"] = dict(e2["agent_identity"], sig="ffffffff")
    assert projection.action_hash(e2) == h


def test_included_fields_change_hash():
    e = ref_envelope()
    h = projection.action_hash(e)
    for field, val in [
        ("runtime", "other/9"),
        ("objective", "different"),
        ("operation", "DEPLOY"),
        ("target_resource", ["arn:x"]),
        ("arguments", {"grantee": "arn:changed"}),
        ("reversibility", "IRREVERSIBLE"),
        ("policy_version", "9.9.9+sha256:zz"),
        ("correlation_id", "other"),
        ("sequence_id", "other:0001"),
    ]:
        assert projection.action_hash(_mut(e, **{field: val})) != h, field


def test_agent_identity_id_and_keyid_included():
    e = ref_envelope()
    h = projection.action_hash(e)
    e2 = copy.deepcopy(e)
    e2["agent_identity"] = dict(e["agent_identity"], id="agent://other")
    assert projection.action_hash(e2) != h
    e3 = copy.deepcopy(e)
    e3["agent_identity"] = dict(e["agent_identity"], key_id="k9")
    assert projection.action_hash(e3) != h


def test_optional_fields_present_vs_absent_differ():
    e = ref_envelope()
    h = projection.action_hash(e)
    assert projection.action_hash(_mut(e, rollback_plan={"steps": ["a"]})) != h
    assert projection.action_hash(_mut(e, linked_ticket="JIRA-1")) != h


def test_expected_effects_included_by_digest_not_raw():
    e = ref_envelope()
    eff = {"changes": ["c1", "c2"]}
    payload = projection.project_action_payload(_mut(e, expected_effects=eff))
    assert "expected_effects" not in payload
    assert payload["expected_effects_digest"] == hashing.domain_digest(
        "SIMULATION", jcs.canonicalize(eff))
    # different effects -> different action_hash
    assert projection.action_hash(_mut(e, expected_effects=eff)) != \
        projection.action_hash(_mut(e, expected_effects={"changes": ["c3"]}))


def test_credential_scope_permissions_is_set_path():
    e = ref_envelope()
    cs1 = dict(e["credential_scope"], permissions=["iam:A", "iam:B"])
    cs2 = dict(e["credential_scope"], permissions=["iam:B", "iam:A"])
    assert projection.action_hash(_mut(e, credential_scope=cs1)) == \
        projection.action_hash(_mut(e, credential_scope=cs2))


def test_canonical_bytes_are_action_domain_input():
    e = ref_envelope()
    canon = projection.action_canonical_bytes(e)
    assert projection.action_hash(e) == hashing.domain_digest("ACTION", canon)


def test_projection_manifest_documents_exclusions():
    m = projection.PROJECTION_MANIFEST
    for k in ("action_id", "timestamp", "agent_identity.sig", "approvals", "attestation"):
        assert k in m["excluded"]
    assert "expected_effects" in m["included_by_digest"]
