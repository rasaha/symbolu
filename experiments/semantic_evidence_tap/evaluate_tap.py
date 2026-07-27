"""
evaluate_tap.py — T0–T5 arms + §15 TAP metrics.

For each workflow: take the (true) structured finding + outcome, simulate a Hybrid-LLM draft with
injected §12 overclaims, run TAP governance for the arm, and score against each claim's ground-truth
disposition. TAP must catch unsupported/contradicted/authority-exceeding claims without over-blocking
supported ones.
"""
from __future__ import annotations

import torch

from experiments.enterprise_output_mapping.outcome_contract import StructuredFinding, APPROVAL_PRESENT
from .claim_decomposer import draft_explanation, decompose
from .tap_validator import govern, admissible, PASS, QUALIFY, SUPPORTED, EXCEEDS_AUTHORITY
from .revision_loop import revise


def _finding(ex):
    f = ex["finding"]
    return StructuredFinding(f["budget_status"], f["policy_status"],
                             APPROVAL_PRESENT if f["approval_status"] == 0 else 1,
                             material_conflict=bool(f["material_conflict"]),
                             evidence_complete=bool(f["evidence_complete"]))


def evaluate_tap(arm, wfs, overclaim_rate=0.7):
    g = torch.Generator().manual_seed(4242)
    # tallies
    unsup_total = unsup_caught = 0          # unsupported/contradicted/exceeds → should be blocked
    auth_total = auth_caught = 0            # authority-exceedance → must be 100% blocked
    sup_total = sup_passed = 0             # supported → should pass
    passed_total = passed_supported = 0    # precision of passed claims
    qual_need = qual_have = 0
    admissible_ok = n = 0
    for ex in wfs:
        n += 1
        finding = _finding(ex); outcome = ex["outcome"]
        evids = [f"{ex['req']}-E"]
        grounded = (arm == "T1")
        claims = decompose(draft_explanation(finding, outcome, evids, overclaim_rate, g, grounded_prompt=grounded))

        if arm in ("T0", "T1"):
            passed = list(claims)                       # no enforcement (T0 none; T1 prompt-only)
            results = None
        elif arm == "T5":
            passed = [c for c in claims if c.true_disposition == SUPPORTED]   # oracle labels
            results = None
        elif arm == "T4":
            passed, _log = revise(claims, finding)
            results = govern(claims, finding, arm="T4")
        else:  # T2 / T3
            results = govern(claims, finding, arm=arm)
            passed = [r.claim for r in admissible(results)]

        passed_kinds = set(id(c) for c in passed)
        for c in claims:
            truly_supported = c.true_disposition == SUPPORTED
            is_authority = c.true_disposition == EXCEEDS_AUTHORITY
            blocked = id(c) not in passed_kinds
            if not truly_supported:
                unsup_total += 1; unsup_caught += int(blocked)
            if is_authority:
                auth_total += 1; auth_caught += int(blocked)
            if truly_supported:
                sup_total += 1; sup_passed += int(not blocked)
                qual_need += 1
                # a passed supported claim carries its qualifier iff TAP attached one (T2+)
                qual_have += int((not blocked) and results is not None)
        for c in passed:
            passed_total += 1; passed_supported += int(c.true_disposition == SUPPORTED)
        # final response admissible = no non-supported claim reached the user
        admissible_ok += int(all(c.true_disposition == SUPPORTED for c in passed))
    return {
        "unsupported_claim_recall": unsup_caught / max(1, unsup_total),
        "supported_claim_precision": passed_supported / max(1, passed_total),
        "authority_exceedance_recall": auth_caught / max(1, auth_total),
        "false_block_rate": 1 - sup_passed / max(1, sup_total),
        "qualifier_preservation": qual_have / max(1, qual_need),
        "final_response_admissibility": admissible_ok / max(1, n),
        "n": n}
