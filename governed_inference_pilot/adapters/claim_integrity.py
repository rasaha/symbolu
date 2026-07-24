"""ClaimIntegrity + ScopeIntegrity adapters (read-only)."""
from __future__ import annotations

from typing import Any, Dict, List

from claim_integrity.claims import decompose
from scope_integrity.variants import variant_h_integrated
from .base import AdapterResult

_CI = "claim_integrity"
_SCOPE = "scope_integrity"


def run_claim_integrity(model_output: str) -> AdapterResult:
    res = decompose(model_output)
    claims = [c.text for c in res.claims]
    return AdapterResult(
        stage=_CI, component_version="ci_claim_v1", local_disposition=res.disposition,
        reason_codes=res.reason_codes or ["CI.VALID"],
        source_repr={"model_output": model_output},
        transformed_repr={"claims": claims, "disposition": res.disposition},
        extra={"claims": claims})


def run_scope_integrity(model_output: str, claims: List[str]) -> AdapterResult:
    produced = variant_h_integrated({"original_text": model_output})
    # INDETERMINATE_SCOPE iff the gated extension preserved a whole scope-conjunction span
    kept_whole = any(" unless " in p or " except " in p for p in produced) and \
        len(produced) < len([c for c in claims]) + 1 and any(
            (" and " in p or " but " in p) for p in produced)
    disp = "INDETERMINATE_SCOPE" if kept_whole else "resolved"
    return AdapterResult(
        stage=_SCOPE, component_version="scope_hybrid_v1", local_disposition=disp,
        reason_codes=["SCOPE.INDETERMINATE" if disp == "INDETERMINATE_SCOPE" else "SCOPE.RESOLVED"],
        source_repr={"claims_in": claims},
        transformed_repr={"claims_out": produced},
        extra={"claims": produced})
