"""Version + maturity metadata must be present and conservatively honest."""

from __future__ import annotations

import ugence_procurement
from ugence_procurement.version import version_info
from ugence_procurement.product.version import product_maturity


def test_version_info_core_fields():
    info = version_info().to_dict()
    assert info["distribution"] == "ugence-procurement"
    assert info["distribution_version"] == "0.1.0"
    assert info["product"] == "Ugence Procurement"
    assert info["product_version"] == "0.1.0"
    assert info["canonical_namespace"] == "ugence_procurement"
    assert info["reference_workflow_verified"] is True


def test_pilot_and_production_are_false():
    info = version_info().to_dict()
    assert info["pilot_validated"] is False
    assert info["production_certified"] is False
    maturity = product_maturity().to_dict()
    assert maturity["pilot_validated"] is False
    assert maturity["production_certified"] is False


def test_evidence_maturity_is_conservative():
    info = version_info().to_dict()
    assert info["evidence_maturity"] == "REFERENCE_WORKFLOW_OFFLINE_VERIFIED"
    # No forbidden over-claim anywhere in the metadata.
    blob = str(info) + str(product_maturity().to_dict())
    for forbidden in ("PILOT_VALIDATED_TRUE", "PRODUCTION_VALIDATED", "PRODUCTION_READY",
                      "ERP_READY", "AUTONOMOUS_PROCUREMENT_READY"):
        assert forbidden not in blob


def test_distribution_version_matches_dunder_version():
    assert ugence_procurement.__version__ == "0.1.0"


def test_optional_integration_probe_present():
    info = version_info().to_dict()
    assert "api" in info["optional_integrations"]
