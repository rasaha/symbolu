"""Clearance export in the deployment (CE-6, CE-7).

The studio suite asserts the boundary and the answer. This one asserts the two
things only the deployment can: that the seeded receipts live **inside** the pinned
synthetic manifest rather than beside it, and that seeding is composition with no
runtime path that could add a receipt.
"""
from __future__ import annotations

import json
import os

import pytest

from governance_studio_deployment import DEPLOYMENT_VERSION
from governance_studio_deployment.clearances import (
    RECEIPT_FIXTURE_FILENAME,
    SEEDED_CLEARANCE_CLASSIFICATION,
    SeededClearanceSource,
    open_received_clearances,
)
from governance_studio_deployment.synthetic import SyntheticManifest, verify_bundle

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(HERE))
SCENARIOS_ROOT = os.path.join(REPO, "apps", "ugence-governance-studio", "demo_data")
MANIFEST = os.path.join(HERE, "synthetic-scenarios-manifest.json")
FIXTURE = os.path.join(SCENARIOS_ROOT, "procurement", RECEIPT_FIXTURE_FILENAME)
TENANT = "acme-demo"


def _cfg() -> dict:
    with open(os.path.join(HERE, "approved-runtime-config.json"), encoding="utf-8") as fh:
        return json.load(fh)


# -- CE-7: inside the existing discipline, not beside it -------------------- #

def test_the_fixture_lives_inside_a_scenario_the_manifest_hashes():
    assert os.path.isfile(FIXTURE)
    assert verify_bundle(SyntheticManifest.load(MANIFEST), SCENARIOS_ROOT) == []


def test_editing_a_seeded_receipt_fails_the_existing_bundle_check(tmp_path):
    """No second manifest and no second fail-closed path: a receipt edited after the
    manifest was pinned fails ``verify_bundle`` exactly as an edited scenario does."""
    import shutil

    root = tmp_path / "demo_data"
    shutil.copytree(SCENARIOS_ROOT, root)
    tampered = root / "procurement" / RECEIPT_FIXTURE_FILENAME
    payload = json.loads(tampered.read_text())
    payload["receipts"][0]["obligations"] = []
    tampered.write_text(json.dumps(payload, indent=2) + "\n")

    violations = verify_bundle(SyntheticManifest.load(MANIFEST), str(root))
    assert any("procurement" in v for v in violations), violations


def test_the_fixture_declares_itself_demonstration_data():
    payload = json.loads(open(FIXTURE, encoding="utf-8").read())
    assert payload["data_classification"] == SEEDED_CLEARANCE_CLASSIFICATION
    assert payload["tenant_id"] == TENANT
    assert payload["receipts"], "a fixture that seeds nothing proves nothing"


def test_a_fixture_without_the_classification_is_refused(tmp_path):
    from governance_studio_deployment.config import DeploymentConfigError

    scenario = tmp_path / "demo" / "scenario-a"
    scenario.mkdir(parents=True)
    (scenario / RECEIPT_FIXTURE_FILENAME).write_text(json.dumps({"receipts": []}))
    with pytest.raises(DeploymentConfigError) as excinfo:
        open_received_clearances(str(tmp_path / "demo"), tenant_id=TENANT)
    assert SEEDED_CLEARANCE_CLASSIFICATION in str(excinfo.value)


# -- seeding is composition, not a route ------------------------------------ #

def test_the_seeded_source_reads_and_cannot_write():
    source = open_received_clearances(SCENARIOS_ROOT, tenant_id=TENANT)
    assert isinstance(source, SeededClearanceSource)
    surface = {n for n in dir(source) if not n.startswith("_")}
    assert surface == {"read_receipt", "list_receipt_ids", "tenant_id"}


def test_the_seeded_source_satisfies_the_export_port():
    from ugence_clearance_export import ReceivedClearanceSource

    source = open_received_clearances(SCENARIOS_ROOT, tenant_id=TENANT)
    assert isinstance(source, ReceivedClearanceSource)


def test_the_seeded_receipts_are_readable_and_intact():
    from ugence_clearance_export import (
        ExportAuthenticity,
        ExportDataClassification,
        IdentityAssurance,
        build_export,
        verify_export,
    )

    source = open_received_clearances(SCENARIOS_ROOT, tenant_id=TENANT)
    ids = source.list_receipt_ids(tenant_id=TENANT)
    assert len(ids) == 2
    for receipt_id in ids:
        body = source.read_receipt(tenant_id=TENANT, receipt_id=receipt_id)
        assert body is not None and body.receipt_id == receipt_id
        report = verify_export(build_export(
            body,
            identity_assurance=IdentityAssurance.PRESENTED_UNPROVEN,
            authenticity=ExportAuthenticity.UNSIGNED,
            data_classification=ExportDataClassification.SYNTHETIC_DEMONSTRATION_ONLY))
        assert report.integrity_verified is True
        assert report.data_classification == SEEDED_CLEARANCE_CLASSIFICATION


def test_a_foreign_tenants_receipt_is_skipped_never_rebound():
    """The tenant is part of what the receipt says and part of its fingerprint.
    Rewriting it would forge a clearance for a tenant nobody evaluated one for."""
    assert open_received_clearances(SCENARIOS_ROOT, tenant_id="someone-else") is None


def test_no_fixture_means_no_source_rather_than_an_empty_one(tmp_path):
    """The studio has to tell "holds no such clearance" from "holds none at all"."""
    (tmp_path / "scenario-a").mkdir()
    assert open_received_clearances(str(tmp_path), tenant_id=TENANT) is None


# -- the recorded composition ------------------------------------------------ #

def test_the_runtime_config_records_the_seam_and_the_sixth_amendment():
    cfg = _cfg()
    seam = cfg["clearance_export"]
    assert seam["operations"] == ["v2_export_read"]
    assert seam["sd1_entries_added"] == ["ugence_clearance_export"]
    assert set(seam["sd1_entries_refused"]) == {
        "ugence_action_clearance", "ugence_execution_reservation"}
    assert seam["honesty_labels"] == {
        "identity_assurance": "PRESENTED_UNPROVEN",
        "authenticity": "UNSIGNED",
        "data_classification": "SYNTHETIC_DEMONSTRATION_ONLY",
    }
    assert seam["confers"].startswith("nothing")
    assert "No store, no server, no driver, no DSN" in seam["source"]
    # v2-A6 stays recorded; the freeze now leads with the amendment that followed it
    assert "v2-A6 (CE-5" in cfg["frozen"]["openapi_v2_amendment"]
    assert cfg["deployment_version"] == DEPLOYMENT_VERSION


def test_the_ceiling_and_the_prohibitions_are_untouched():
    cfg = _cfg()
    assert cfg["data_classification"] == "SYNTHETIC_DEMONSTRATION_ONLY"
    egress = cfg["external_network_egress"]
    assert egress["default"] == "none"
    assert len(egress["permitted"]) == 1, "FD-8.4: no second destination"
    assert "review" in egress["permitted"][0]["purpose"].lower()
    for prohibition in ("agent_execution", "persistent_database"):
        assert prohibition in cfg["prohibited"]
    assert cfg["frozen"]["openapi_sha256"] == (
        "dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656")


def test_the_composition_record_names_the_new_seam():
    # The seam-10 record, kept byte-for-byte since the deployment-status seam superseded it.
    record = json.load(open(os.path.join(HERE, "composition-record.seam-10.json"), encoding="utf-8"))
    assert record["seams_handed_to_build_studio_context"][-1] == "received_clearances"
    assert record["supersedes_record"] == "composition-record.seam-9.json"
    assert record["binding"]["binding_id"].endswith("front-door/seam-10")
    notes = record["registration"]["notes"]
    assert "CE-1 to CE-7" in notes
    assert "composition, not a route" in notes
