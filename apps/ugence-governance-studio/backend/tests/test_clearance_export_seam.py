"""Clearance export (CE-1 to CE-7) — the studio side of the seam.

Four claims are tested here that no other suite can make, because they are about
the studio's boundary rather than the export package's contracts:

* the SD-1 allowlist gained **exactly one** entry, and it is the ruled one (CE-6);
* the studio's own source still may not import a clearance evaluator or a receipt
  store, so CE-6's narrower reading is structural rather than a convention;
* the one v2 operation is a read, and no write appeared beside it (CE-5, §13.3);
* the three honesty labels reach the caller, in the artifact and in the envelope.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient

from ugence_action_clearance import ClearanceReceiptBody, ClearanceResult, ClearanceStatus
from ugence_governance_studio_api.app_v2 import build_studio_context, create_v2_app
from ugence_governance_studio_api.services.studio_v2 import ClearanceExportService

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP = os.path.dirname(_BACKEND)

T0 = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
TENANT = "tenant-alpha"

THE_THREE = {
    "identity_assurance": "PRESENTED_UNPROVEN",
    "authenticity": "UNSIGNED",
    "data_classification": "SYNTHETIC_DEMONSTRATION_ONLY",
}


def _body(tenant_id: str = TENANT, request_id: str = "req-1") -> ClearanceReceiptBody:
    return ClearanceReceiptBody.from_result(ClearanceResult(
        request_id=request_id,
        authorization_ref="authz-1",
        authorized_action_fingerprint="actfp-1",
        status=ClearanceStatus.CLEAR,
        reason_codes=("OPERATIONALLY_SAFE",),
        effective_constraints=("window:15m",),
        obligations=("record-outcome",),
        evaluated_at=T0,
        valid_until=T0 + timedelta(minutes=15),
        policy_refs=("policy:clearance:v1",),
        signal_refs=("sig-1",),
        request_fingerprint="reqfp-1",
        tenant_id=tenant_id,
        signal_bundle_fingerprint="bundlefp-1",
    ))


class _Source:
    """A received-clearance source with two reads and no write, like the port."""

    def __init__(self, bodies=(), tenant_id: str = TENANT) -> None:
        self.tenant_id = tenant_id
        self._by_id = {b.receipt_id: b for b in bodies}

    def read_receipt(self, *, tenant_id: str, receipt_id: str):
        found = self._by_id.get(receipt_id)
        if found is None or found.tenant_id != tenant_id:
            return None
        return found

    def list_receipt_ids(self, *, tenant_id: str):
        return [i for i, b in self._by_id.items() if b.tenant_id == tenant_id]


def _client(source=None) -> TestClient:
    return TestClient(create_v2_app(
        studio=build_studio_context(received_clearances=source)))


# -- CE-6: exactly one SD-1 entry ------------------------------------------- #

def test_the_allowlist_gained_exactly_one_entry_and_it_is_the_ruled_one():
    """CE-6 authorized one line. This asserts the count, not just the presence:
    a second entry added later fails here even if it looks harmless."""
    from tests.test_architecture import _PUBLIC_ENTRY_ALLOWLIST

    assert "ugence_clearance_export" in _PUBLIC_ENTRY_ALLOWLIST
    # Eleven at CE-6. Twelve since owner ruling BW-3A (authority-plane ADR §24, Bring
    # Your Workflow phase 3A) admitted ugence_workflow_drafts; the count moves only
    # with a ruling, which is the point of asserting it.
    assert len(_PUBLIC_ENTRY_ALLOWLIST) == 12
    assert "ugence_workflow_drafts" in _PUBLIC_ENTRY_ALLOWLIST
    assert _PUBLIC_ENTRY_ALLOWLIST["ugence_clearance_export"] == (
        "from ugence_clearance_export import ",
        "import ugence_clearance_export",
    )


def test_neither_the_evaluator_nor_the_receipt_store_is_allowlisted():
    """§13.3: admitting either later is a new owner decision, not a follow-on."""
    from tests.test_architecture import _PUBLIC_ENTRY_ALLOWLIST

    assert "ugence_action_clearance" not in _PUBLIC_ENTRY_ALLOWLIST
    assert "ugence_execution_reservation" not in _PUBLIC_ENTRY_ALLOWLIST


def test_the_studio_source_imports_neither_of_them():
    """Both are importable in this environment — the package needs action-clearance
    on the path. The point is that the studio's own source still does not reach
    them, which is what CE-6 actually rules."""
    from tests.test_architecture import _import_lines

    for filename, line in _import_lines():
        assert "ugence_action_clearance" not in line, f"{filename}: {line}"
        assert "ugence_execution_reservation" not in line, f"{filename}: {line}"


# -- CE-5: one operation, and it is a read ---------------------------------- #

def test_the_contract_gained_one_operation_and_it_is_a_get():
    from ugence_governance_studio_api.openapi_v2 import canonical_v2_openapi_bytes

    schema = json.loads(canonical_v2_openapi_bytes())
    exports = {
        (method.upper(), path)
        for path, methods in schema["paths"].items()
        for method, op in methods.items()
        if isinstance(op, dict) and op.get("operationId", "").startswith("v2_export")
    }
    assert exports == {("GET", "/api/v2/exports/{receipt_id}")}


def test_the_amendment_records_exactly_that_operation():
    record = json.load(open(
        os.path.join(_APP, "contracts", "openapi_v2.amendments.json"), encoding="utf-8"))
    (mine,) = [a for a in record["amendments"] if a["amendment_id"] == "v2-A6"]
    assert mine["operations_added"] == ["v2_export_read"]
    assert mine["operations_removed"] == []
    assert mine["paths_added"] == ["/api/v2/exports/{receipt_id}"]
    # The chain is unbroken from the original through every amendment.
    previous = record["original_sha256"]
    for amendment in record["amendments"]:
        assert amendment["previous_sha256"] == previous
        previous = amendment["sha256"]


def test_the_service_exposes_no_write():
    surface = {n for n in dir(ClearanceExportService) if not n.startswith("_")}
    assert surface == {"CAPABILITY", "read"}


def test_no_route_accepts_a_receipt():
    """§13.3: no operation may accept a receipt. The export prefix serves GET only."""
    client = _client(_Source([_body()]))
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        response = client.request(method, "/api/v2/exports/acr_whatever")
        assert response.status_code == 405, method


# -- the answer -------------------------------------------------------------- #

def test_a_held_clearance_exports_with_all_three_labels():
    body = _body()
    response = _client(_Source([body])).get(f"/api/v2/exports/{body.receipt_id}")
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["available"] is True
    assert result["integrity_verified"] is True
    assert result["receipt_id"] == body.receipt_id
    assert result["artifact_id"].startswith("cxp_")
    for label, value in THE_THREE.items():
        assert result[label] == value, label
        assert result["artifact"][label] == value, label


def test_the_answer_says_what_it_could_not_check_and_what_it_confers():
    body = _body()
    result = _client(_Source([body])).get(
        f"/api/v2/exports/{body.receipt_id}").json()["result"]
    assert len(result["uncheckable"]) == 4
    assert result["confers"].startswith("NOTHING")
    assert "EXPORT_IS_A_READ" in result["export_is_not_clearing"]
    assert "no signing key or trust root is configured" in result["authenticity_prerequisite"]


def test_an_unheld_clearance_is_refused_typed_not_answered_empty():
    """"no such clearance" and "no clearances" must not look alike to a runtime."""
    result = _client(_Source([])).get("/api/v2/exports/acr_absent").json()["result"]
    assert result["refused"] is True
    assert result["code"] == "clearance_not_held"
    assert result["result"] is None


def test_another_tenants_clearance_is_not_reachable():
    theirs = _body(tenant_id="tenant-beta", request_id="req-2")
    source = _Source([theirs], tenant_id=TENANT)
    result = _client(source).get(f"/api/v2/exports/{theirs.receipt_id}").json()["result"]
    assert result["refused"] is True
    assert result["code"] == "clearance_not_held"


def test_an_absent_source_reports_the_gap_rather_than_an_empty_answer():
    result = _client(None).get("/api/v2/exports/acr_anything").json()["result"]
    assert result["available"] is False
    assert "no received-clearance source is configured" in json.dumps(result)


def test_the_export_is_stable_across_calls():
    body = _body()
    client = _client(_Source([body]))
    first = client.get(f"/api/v2/exports/{body.receipt_id}").json()["result"]["artifact"]
    second = client.get(f"/api/v2/exports/{body.receipt_id}").json()["result"]["artifact"]
    assert first == second


@pytest.mark.parametrize("label", sorted(THE_THREE))
def test_the_service_cannot_be_asked_for_a_softer_label(label):
    """The labels are not parameters of the operation: there is no argument, query
    parameter or payload through which a caller could ask for a different one."""
    import inspect

    signature = inspect.signature(ClearanceExportService.read)
    assert label not in signature.parameters
    assert set(signature.parameters) == {"self", "receipt_id"}
