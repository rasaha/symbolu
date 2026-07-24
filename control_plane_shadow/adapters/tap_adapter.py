"""Real TAP assertion-governance adapter (Phase 5/6). Wraps the TAP-E4 GovernanceResolver
(tap_e4_governance_truth.GovernanceTruthLayer, config F) — TIER 3, deterministic, no network.

SEMANTIC GAP (documented, not hidden): E4 resolves *which documented authority governs a
situation*, not *whether a model's claim may be asserted*. This adapter maps GovStatus to the
canonical assertion vocabulary as an APPROXIMATION; it does NOT claim production TAP integration.

Valid upstream records are built read-only from the real E4 corpus (`corpus.cases`,
`build_retrieval_record`, `build_relationship_record`, `harness._intent`). The adapter does NOT
mutate the engine or its frozen inputs.
"""
from __future__ import annotations

from typing import Any, Optional

from truth_assurance_pipeline.tap_e4_governance_truth.applicability import GovernanceTruthLayer, config
from truth_assurance_pipeline.tap_e4_governance_truth.corpus import cases as e4corpus
from truth_assurance_pipeline.tap_e4_governance_truth.harness import _intent
from truth_assurance_pipeline.tap_e4_governance_truth.validator import require_valid

from control_plane_shadow.adapters.base import AdapterHealth, ShadowAdapter
from control_plane_shadow.vocabulary import AssertionDisposition, map_tap, provenance


def _cases_by_id():
    out = {}
    for split in ("dev", "eval"):
        for c in e4corpus.cases_for_split(split):
            out[c.case_id] = c
    return out


class TAPAssertionAdapter(ShadowAdapter):
    component = "TAP"
    source_version = "tap_e4_governance_F"

    def __init__(self):
        self.layer = GovernanceTruthLayer(config("F"))
        self._cases = _cases_by_id()

    def health(self) -> AdapterHealth:
        return AdapterHealth(self.component, available=True, determinism="deterministic",
                             live_call_risk=False, real_action_risk=False,
                             source_version=self.source_version, adapter_version=self.adapter_version,
                             capabilities=["authority_resolution", "confidence_band", "provenance",
                                           "SEMANTIC_GAP:authority_not_assertion"])

    def case_ids(self):
        return sorted(self._cases)

    @staticmethod
    def _record_disposition(rec) -> str:
        """Derive a record-level GovStatus (adapter-authored rule; recorded as derived)."""
        if rec.governing_authorities:
            return rec.governing_authorities[0].status.value
        if rec.governance_conflicts:
            return "CONFLICTED"
        if rec.governance_gaps:
            return "NO_GOVERNING_AUTHORITY"
        return "UNRESOLVED"

    def govern(self, case_id: str) -> Any:
        case = self._cases.get(case_id)
        if case is None:
            res = self._result(tier="TIER3", canonical={"assertion_disposition":
                               AssertionDisposition.INDETERMINATE.value, "state": "UNKNOWN_CASE"},
                               reason_codes=["ASSERT.INSUFFICIENT_BASIS"], health="DEGRADED",
                               error=f"unknown TAP case {case_id!r}")
            return res
        intent = _intent(case)
        retrieval = e4corpus.build_retrieval_record(case)
        relationship = e4corpus.build_relationship_record(case)
        require_valid(intent, retrieval, relationship)
        rec = self.layer.resolve(intent, retrieval, relationship, case.situation)   # REAL engine
        gov_status = self._record_disposition(rec)
        disp = map_tap(gov_status)
        reason = {"ALLOW": [], "QUALIFY": ["ASSERT.ASSERTION_QUALIFIED"],
                  "REJECT": ["ASSERT.ASSERTION_REJECTED"], "ESCALATE": ["ASSERT.ASSERTION_ESCALATED"],
                  "INDETERMINATE": ["ASSERT.INSUFFICIENT_BASIS"]}[disp.value]
        canonical = {
            "assertion_disposition": disp.value,
            "governed_output_ref": f"gov:{rec.governance_record_id}",
            "source_gov_status": gov_status,
            "confidence_band": rec.confidence_vector.band(),
            "n_conflicts": len(rec.governance_conflicts),
            "n_gaps": len(rec.governance_gaps),
            "state": disp.value,
        }
        loss = ["8-axis confidence_vector, conflict/gap detail, and provenance chain not "
                "represented by the disposition (kept in source_output)",
                "SEMANTIC GAP: authority-resolution used as assertion-permission proxy"]
        return self._result(tier="TIER3", canonical=canonical,
                            source_output={"governance_record_id": rec.governance_record_id,
                                           "gov_status": gov_status,
                                           "confidence_band": rec.confidence_vector.band(),
                                           "conflicts": len(rec.governance_conflicts),
                                           "gaps": len(rec.governance_gaps)},
                            reason_codes=reason, information_loss=loss,
                            derived_fields=["assertion_disposition (record-level derivation)"],
                            provenance=[provenance("TAP", gov_status, disp)])
