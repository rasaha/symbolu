#!/usr/bin/env python3
"""Deterministic behavioral capture for the AI Hiring provider-dependency normalization.

Captures the AI Hiring product's deterministic, offline behavior so that a
pre-change snapshot can be compared, field for field, against post-change snapshots
taken through the canonical adapter modules and through the retained legacy adapter
module paths.

The capture is split into two parts:

* ``product_semantics`` — namespace-independent product behavior: version-info
  semantic fields, the full governed demo cohort (evidence → assessment →
  advisory recommendation → human binding decision → governed action-request
  preparation → authorization → reconciliation → audit, exercised through the
  framework's deterministic reference providers), a redacted accountability sample,
  and the reference-provider assertion/authorization integration outcomes.
* ``adapter_semantics`` — the optional adapter behavior exercised through the
  selected adapter module path (``--adapter canonical`` or ``--adapter legacy``)
  with deterministic in-process provider clients (the "deterministic fake
  clients").

Fields that are *permitted* to differ across the migration — the distribution
version, dependency distribution names, the provider import namespace, and the
adapter module label — are recorded under ``metadata`` and are EXCLUDED from the
semantic hashes. The semantic hashes cover only the forbidden-difference surface
(assessment/recommendation/decision/action-request/authorization/constraints/
obligations/evidence/audit/exception behavior/execution boundary).

Usage:
    python scripts/ai_hiring_provider_normalization_capture.py --out OUT.json \
        [--adapter {canonical,legacy}]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any


def _stable_hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode()
    ).hexdigest()


def _version_semantics() -> dict:
    """Namespace/version-independent version-info fields."""
    from ugence_ai_hiring import version_info

    info = info_dict = version_info().to_dict()
    return {
        "product_version": info["product_version"],
        "platform_baseline": info["platform_baseline"],
        "stability": info["stability"],
        "release_classification": info["release_classification"],
        "production_certified": info["production_certified"],
        # Schema key names (not the env-dependent boolean values or dep versions).
        "contract_version_keys": sorted(info["contract_versions"].keys()),
        "optional_integration_keys": sorted(info["optional_integrations"].keys()),
        "version_info_keys": sorted(info_dict.keys()),
    }


def _demo_semantics() -> dict:
    """The governed demo cohort — deterministic full-lifecycle outcomes."""
    from ugence_ai_hiring.product.demo import run_demo

    result = run_demo()
    summary = result.summary()

    accountability = None
    if result.sample_report is not None:
        d = result.sample_report.to_dict()
        # Keep semantic outcome/count/boolean fields; drop volatile identifiers and
        # pseudonymous refs that are provenance, not product semantics.
        def _strip(section: dict) -> dict:
            return {
                k: v
                for k, v in section.items()
                if not k.endswith("_id")
                and k not in ("tenant_id", "action_proposal_id", "recommendation_id",
                              "decision_id", "authorization_id", "attempt_id",
                              "decided_by", "provider_trace_id", "fingerprint")
            }

        accountability = {
            "recommendation": _strip(d.get("recommendation", {})),
            "human_decision": _strip(d.get("human_decision", {})),
            "authorization": _strip(d.get("authorization", {})),
            "execution": _strip(d.get("execution", {})),
            "reconciliation": _strip(d.get("reconciliation", {})),
            "compensation": _strip(d.get("compensation", {})),
            "integrity": d.get("integrity", {}),
            "audit": d.get("audit", {}),
            "claim_count": len(d.get("claims", [])),
            "claim_outcomes": [c.get("assertion_outcome") for c in d.get("claims", [])],
        }

    return {"cohort_summary": summary, "accountability_sample": accountability}


def _reference_integration_semantics() -> dict:
    """Direct neutral-integration outcomes through the framework reference providers.

    Exercises the core's own TAP claim-assertion and ActionGate authorization
    integration classes with the framework's deterministic reference providers —
    no concrete TAP/ActionGate provider involved.
    """
    from ugence_governance_provider_framework.api import (
        AssertionAssessmentIntegration,
        AssertionGovernanceRequest,
    )
    from ugence_governance_provider_framework.reference.assertion import (
        DeterministicAssertionProvider,
    )

    prov = DeterministicAssertionProvider()
    integ = AssertionAssessmentIntegration(prov)
    req = AssertionGovernanceRequest(
        assertion="Candidate has 5 years Python experience.",
        assertion_type="skill",
        evidence_refs=("ev-1", "ev-2"),
        source_identity="ai-generator",
        policy_refs=(),
        context={"application_id": "app-1", "criterion_id": "crit-1"},
        correlation_id="corr-1",
    )
    res = integ.assess(req)
    assertion = {
        "coverage": res.coverage.value,
        "evidence_coverage": res.evidence_coverage,
        "covered_evidence_refs": list(res.covered_evidence_refs),
        "unsupported_elements": list(res.unsupported_elements),
    }
    return {"reference_assertion": assertion}


def _adapter_semantics(adapter: str) -> dict:
    """Optional adapter behavior via deterministic in-process provider clients.

    ``adapter`` selects the module path under test:
      * ``canonical`` → ugence_ai_hiring.integrations.{tap,actiongate}_adapter
      * ``legacy``    → ugence_ai_hiring.integrations.{tap,actiongate}_legacy_adapter
    """
    if adapter == "canonical":
        from ugence_ai_hiring.integrations import actiongate_adapter as ag_mod
        from ugence_ai_hiring.integrations import tap_adapter as tap_mod
    elif adapter == "legacy":
        from ugence_ai_hiring.integrations import actiongate_legacy_adapter as ag_mod
        from ugence_ai_hiring.integrations import tap_legacy_adapter as tap_mod
    else:  # pragma: no cover
        raise ValueError(adapter)

    from ugence_governance_provider_framework.api import (
        ActionGovernanceRequest,
        AssertionGovernanceRequest,
    )

    # Deterministic in-process clients (the "fake clients").
    from ugence_tap_provider.client import InProcessTapClient
    from ugence_tap_provider.core import TapEngine
    from ugence_actiongate_provider.client import InProcessActionGateClient
    from ugence_actiongate_provider.core import ActionGateEngine

    # --- TAP through the adapter ---
    tap_prov = tap_mod.build_tap_provider(InProcessTapClient(TapEngine()))
    tap_prov.initialize()
    tap_desc = tap_prov.descriptor()
    tap_res = tap_prov.evaluate(
        AssertionGovernanceRequest(
            assertion="Holds a PMP certification.",
            assertion_type="credential",
            evidence_refs=("ev-a",),
            source_identity="ai-generator",
            policy_refs=(),
            context={},
            correlation_id="c-tap",
        )
    )
    tap_capture = {
        "descriptor_kind": tap_desc.kind.value,
        "descriptor_provider_id": tap_desc.provider_id,
        "coverage": tap_res.coverage.value,
        "evidence_coverage": tap_res.evidence_coverage,
        "has_authorize": hasattr(tap_prov, "authorize"),
    }

    # --- ActionGate through the adapter ---
    ag_prov = ag_mod.build_actiongate_provider(InProcessActionGateClient(ActionGateEngine()))
    ag_prov.initialize()
    ag_desc = ag_prov.descriptor()
    ag_res = ag_prov.authorize(ActionGovernanceRequest(action_type="ADVANCE_STAGE"))
    ag_capture = {
        "descriptor_kind": ag_desc.kind.value,
        "descriptor_provider_id": ag_desc.provider_id,
        "outcome": ag_res.outcome.value,
        "constraints": list(ag_res.constraints),
        "obligations": list(ag_res.obligations),
        # Execution boundary: an authorization provider exposes no dispatch/execute.
        "no_execution_surface": not any(
            hasattr(ag_prov, m) for m in ("dispatch", "execute", "reconcile", "compensate")
        ),
    }

    return {"tap": tap_capture, "actiongate": ag_capture}


def _adapter_metadata(adapter: str) -> dict:
    """Permitted-difference labels (namespace / module), excluded from semantics."""
    if adapter == "canonical":
        tap_module = "ugence_ai_hiring.integrations.tap_adapter"
        ag_module = "ugence_ai_hiring.integrations.actiongate_adapter"
    else:
        tap_module = "ugence_ai_hiring.integrations.tap_legacy_adapter"
        ag_module = "ugence_ai_hiring.integrations.actiongate_legacy_adapter"
    return {"adapter": adapter, "tap_module": tap_module, "actiongate_module": ag_module}


def capture(adapter: str) -> dict:
    import ugence_ai_hiring

    product = {
        "version": _version_semantics(),
        "demo": _demo_semantics(),
        "reference_integration": _reference_integration_semantics(),
    }
    adapter_sem = _adapter_semantics(adapter)

    report = {
        "metadata": {
            # Permitted differences — EXCLUDED from semantic hashes.
            "distribution": ugence_ai_hiring.version_info().distribution,
            "distribution_version": ugence_ai_hiring.__version__,
            **_adapter_metadata(adapter),
        },
        "product_semantics": product,
        "adapter_semantics": adapter_sem,
        "product_semantics_hash": _stable_hash(product),
        "adapter_semantics_hash": _stable_hash(adapter_sem),
    }
    report["combined_semantics_hash"] = _stable_hash(
        {"product": product, "adapter": adapter_sem}
    )
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--adapter", choices=("canonical", "legacy"), default="canonical")
    args = ap.parse_args()

    report = capture(args.adapter)
    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=2, sort_keys=True, default=str)
        fh.write("\n")
    print(f"wrote {args.out}")
    print(f"  product_semantics_hash = {report['product_semantics_hash']}")
    print(f"  adapter_semantics_hash = {report['adapter_semantics_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
