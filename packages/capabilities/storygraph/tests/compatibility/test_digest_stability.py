"""S3 — frozen digest stability across the migration.

Pins the exact digest/version anchors recorded in the pre-migration baseline
(Project_documentation/repository/docs/migrations/storygraph/BASELINE.md §4–§5). Any drift in graph, policy,
replay, pre-registration, or schema digests fails here — the guard that the
physical move introduced no semantic change.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

from ugence_storygraph import storygraph as sg
from ugence_storygraph import storyverdict as sv
from ugence_storygraph.policypack import compiler, reference, replay, replay_gates
import ugence_storygraph.evaluation.freeze as freeze

_PP = pathlib.Path(reference.__file__).resolve().parent

# --- baseline anchors (recorded before movement) ---------------------------
ATO_DIGEST = "sha-256:6a77b8997263c40f2b6d791c9391ae562dfb51ba6e7ae04ce5da5f775cc081a8"
EXFIL_DIGEST = "sha-256:a8bce84705439cc449fb36ce15ce2a9b54cdea23fb5cc4a6a7b715134668d9e1"
REF_BUNDLE_DIGEST = "sha-256:f6323c9275e125be0766fbc3986683aae3ece8009cad80df08278f8114896a1e"
REPLAY_REPORT_DIGEST = "sha-256:0dcf2bc4730bf12a89e5e5e6b54b8a9442b59b105dc068659d8035033977923b"
PREREG_DIGEST = "sha-256:1f026c7a95ee64bb9d2d8398941f84d75ff38f6414b7429b42eba76a736422d4"
SCHEMA_SHA = "sha-256:24bc416ee4d54967264e5f86d7f959bd458bd2d5f6a3d0696c8af074d8070779"


def test_frozen_graph_digests_unchanged():
    graphs = freeze.current_config()["story_graphs"]
    assert graphs["ACCOUNT_TAKEOVER_TRANSFER@1.0.0"] == ATO_DIGEST
    assert graphs["DIGITAL_EXFILTRATION_STORY@1.0.0"] == EXFIL_DIGEST


def test_reference_pack_digests_unchanged():
    b = compiler.compile_pack(reference.ACCOUNT_TAKEOVER_PACK)
    # the compiled reference graph reproduces the frozen ATO graph exactly
    assert compiler.graph_freeze_digest(b) == ATO_DIGEST
    assert b.bundle_digest == REF_BUNDLE_DIGEST


def test_deterministic_replay_report_digest_unchanged():
    fx = json.loads((_PP / "fixtures" / "account_takeover_replay.json").read_text())
    res = replay.run_replay(reference.account_takeover_pack(), fx["records"])
    assert res["report_digest"] == REPLAY_REPORT_DIGEST


def test_preregistration_digest_unchanged():
    assert replay_gates.preregistration_digest() == PREREG_DIGEST


def test_policypack_schema_bytes_unchanged():
    p = _PP / "schemas" / "storypolicypack.schema.json"
    assert "sha-256:" + hashlib.sha256(p.read_bytes()).hexdigest() == SCHEMA_SHA


def test_version_identifiers_unchanged():
    assert sg.STORYGRAPH_SCHEMA_VERSION == "ctd.storygraph/1.1.0"
    assert sg.MATCHER_SEMANTICS_VERSION == "ctd.storygraph.matcher/2.0.0"
    assert sg.PARTIAL_ESCALATION_POLICY_VERSION == "ctd.partial_escalation/1.0.0"
    assert sv.TIE_BREAK_RULE_VERSION == "ctd.witness.tiebreak/2.0.0"
    assert sv.MINIMALITY_BASIS == "SEMANTIC_EQUIVALENCE_CLASS"
    assert compiler.COMPILER_VERSION == "ctd.policypack.compiler/1.0.0"
