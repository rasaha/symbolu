"""MVP 1E acceptance tests — static read-only security inspection + credential isolation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from cg_clearance_helpers import EVAL
from cg_operator_helpers import FAKE_CREDENTIAL, adapters_for, build_operator

from ugence_code_governance.pilot_operator import scan_for_credential, scan_source
from ugence_code_governance.pilot_operator.security import SecurityFinding, scan_paths

_SRC = Path(__file__).resolve().parents[1] / "src" / "ugence_code_governance"


# --- 31-40. static read-only security inspection ---------------------------
def test_direct_http_client_detected():
    res = scan_source("import requests\nrequests.get('x')")
    assert res.of(SecurityFinding.DIRECT_HTTP_CLIENT)


def test_post_path_detected():
    res = scan_source("import requests\nrequests.post('u', json={})")
    assert res.of(SecurityFinding.PROHIBITED_HTTP_VERB)


def test_patch_path_detected():
    res = scan_source("s.patch('u')")
    assert res.of(SecurityFinding.PROHIBITED_HTTP_VERB)


def test_graphql_mutation_detected():
    res = scan_source('q = "mutation { addComment(x:1) }"')
    assert res.of(SecurityFinding.GRAPHQL_MUTATION)


def test_merge_endpoint_detected():
    res = scan_source('url = "/repos/o/r/pulls/1/merge"')
    assert res.of(SecurityFinding.GITHUB_MUTATION_ENDPOINT)


def test_write_scope_detected():
    res = scan_source('scopes = ["contents:write"]')
    assert res.of(SecurityFinding.WRITE_SCOPE)


def test_execution_provider_import_detected():
    res = scan_source("from x.execution_provider import Provider")
    assert res.of(SecurityFinding.EXECUTION_PROVIDER_IMPORT)


def test_reserve_once_detected():
    res = scan_source("def f():\n    reserve_once()")
    assert res.of(SecurityFinding.RESERVE_ONCE)


def test_valid_get_only_adapter_passes():
    res = scan_source("def collect(t):\n    return t.get('https://api.github.com/repos/o/r', source_id='s')")
    assert res.clean


def test_ast_ignores_documentation_only_forbidden_words():
    src = '"""This adapter adds no reserve_once and never POSTs or merges."""\nX = 1'
    assert scan_source(src).clean


def test_real_adapter_and_operator_boundary_scans_clean():
    paths = list((_SRC / "adapters").glob("*.py")) + list((_SRC / "pilot_operator").glob("*.py"))
    assert scan_paths(paths).clean


# --- 41-48. credential isolation -------------------------------------------
def _run_with_credential():
    svc, rid, ctx, op, cfg = build_operator()
    rec = op.run_once(rid, adapters_for(ctx), collection_time=EVAL, evaluation_time=EVAL,
                      actor_ref="user:approver")
    return svc, rid, ctx, op, cfg, rec


def _all_store_payloads(svc, pilot="pilot-1"):
    payloads = []
    for wf in (f"op:{pilot}", f"pilot:{pilot}"):
        for env in svc.durable_store.list_for_workflow("acme", wf):
            payloads.append(env.canonical_payload)
    return payloads


def test_credential_absent_from_durable_store():
    svc, *_ = _run_with_credential()
    hits = [h for p in _all_store_payloads(svc) for h in scan_for_credential(FAKE_CREDENTIAL, p)]
    assert not hits
    svc.close()


def test_credential_absent_from_logs():
    svc, rid, ctx, op, cfg, rec = _run_with_credential()
    hits = [h for e in op.logger.events for h in scan_for_credential(FAKE_CREDENTIAL, e)]
    assert not hits
    svc.close()


def test_credential_absent_from_metrics():
    svc, rid, ctx, op, cfg, rec = _run_with_credential()
    assert not scan_for_credential(FAKE_CREDENTIAL, op.metrics().snapshot())
    svc.close()


def test_credential_absent_from_pilot_report():
    svc, rid, ctx, op, cfg, rec = _run_with_credential()
    summary = op.closeout(EVAL)
    assert not scan_for_credential(FAKE_CREDENTIAL, summary)
    svc.close()


def test_credential_absent_from_audit_bundle():
    svc, rid, ctx, op, cfg, rec = _run_with_credential()
    bundle = svc.export_governance_audit_bundle("acme", rid)
    assert not scan_for_credential(FAKE_CREDENTIAL, bundle)
    svc.close()


def test_credential_absent_from_request_and_result_fingerprints():
    svc, rid, ctx, op, cfg, rec = _run_with_credential()
    assert not scan_for_credential(FAKE_CREDENTIAL, rec.adapter_request_ref)
    assert not scan_for_credential(FAKE_CREDENTIAL, list(rec.adapter_result_refs))
    svc.close()


def test_credential_absent_from_exception_message():
    from ugence_code_governance.pilot_operator import CredentialReference, ResolverKind
    from ugence_code_governance.pilot_operator.errors import CredentialBoundaryError
    # A credential reference that tries to inline a value-looking token fails, and the
    # error message must not echo the value.
    with pytest.raises(CredentialBoundaryError) as exc:
        CredentialReference("r", ResolverKind.ENVIRONMENT, "api.github.com",
                            environment_variable_name="ghp_" + "A" * 30)
    assert "ghp_" + "A" * 30 not in str(exc.value)
