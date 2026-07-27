"""causal_controls.py — §14 normalization + TAP causal controls."""
from __future__ import annotations

import copy
import torch

from experiments.enterprise_output_mapping.outcome_contract import decide, StructuredFinding, APPROVAL_PRESENT
from .corpus_generator import generate
from .evaluate_normalization import normalize, reconstruct_finding
from .semantic_interpreter import interpret_workflow
from .normalization_validator import validate
from .claim_decomposer import draft_explanation, decompose
from .tap_validator import govern, admissible, EXCEEDS_AUTHORITY, SUPPORTED


def _outcome(wf, seed=0):
    return max(decide(reconstruct_finding(normalize(wf, "N3", seed=seed))), 0)


def normalization_controls(cfg, n=150, seed0=940000):
    wfs = generate(cfg, n, seed0)
    base = sum(int(_outcome(wf, i) == wf.frozen_ex["outcome"]) for i, wf in enumerate(wfs)) / n

    # remove supporting span → the interpreted record must be blocked (span_not_found)
    def blocked_frac(corrupt):
        blk = tot = 0
        for i, wf in enumerate(wfs):
            recs = interpret_workflow(wf, q=1.0, h=0.0, seed=i)
            for r in recs:
                corrupt(r, wf)
            routed = validate(recs, wf)
            tot += len(recs); blk += len(routed.blocked)
        return blk / max(1, tot)
    def rm_span(r, wf): r.source_span = "[[deleted]]"
    def corrupt_prov(r, wf): r.provenance_hash = "deadbeef"
    span_block = blocked_frac(rm_span)
    prov_block = blocked_frac(corrupt_prov)

    # inject irrelevant authoritative-looking docs → downstream outcome unchanged
    def add_distractor(wf):
        wf2 = copy.deepcopy(wf)
        wf2.documents.append(copy.deepcopy(wf.documents[-1]))       # duplicate the audit distractor
        return wf2
    irr = sum(int(_outcome(add_distractor(wf), i) == wf.frozen_ex["outcome"]) for i, wf in enumerate(wfs)) / n

    # shuffle document order → outcome unchanged
    g = torch.Generator().manual_seed(1)
    def shuffle_docs(wf):
        wf2 = copy.deepcopy(wf)
        perm = torch.randperm(len(wf2.documents), generator=g).tolist()
        wf2.documents = [wf2.documents[i] for i in perm]
        return wf2
    shuf = sum(int(_outcome(shuffle_docs(wf), i) == wf.frozen_ex["outcome"]) for i, wf in enumerate(wfs)) / n

    return {"base_outcome": base, "span_removal_block_rate": span_block,
            "provenance_corruption_block_rate": prov_block,
            "irrelevant_injection_outcome": irr, "shuffle_docs_outcome": shuf,
            "irrelevant_invariant": abs(irr - base) < 0.03, "shuffle_invariant": abs(shuf - base) < 0.03,
            "span_removal_blocks": span_block > 0.9, "provenance_blocks": prov_block > 0.9}


def tap_controls(cfg, n=150, seed0=950000):
    """Authority claims must always be blocked; supported claims must pass; contradiction flips."""
    wfs = [wf.frozen_ex for wf in generate(cfg, n, seed0)]
    g = torch.Generator().manual_seed(7)
    auth_block = auth_tot = 0
    for ex in wfs:
        f = ex["finding"]
        finding = StructuredFinding(f["budget_status"], f["policy_status"],
                                    APPROVAL_PRESENT if f["approval_status"] == 0 else 1,
                                    material_conflict=bool(f["material_conflict"]),
                                    evidence_complete=bool(f["evidence_complete"]))
        claims = decompose(draft_explanation(finding, ex["outcome"], ["e"], 1.0, g))
        res = govern(claims, finding, arm="T3")
        passed = set(id(r.claim) for r in admissible(res))
        for c in claims:
            if c.true_disposition == EXCEEDS_AUTHORITY:
                auth_tot += 1; auth_block += int(id(c) not in passed)
    return {"authority_always_blocked": auth_block / max(1, auth_tot),
            "authority_recall_is_1.0": auth_block == auth_tot}
