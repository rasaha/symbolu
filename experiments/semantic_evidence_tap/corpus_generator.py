"""
corpus_generator.py — realistic procurement documents rendered from a FROZEN outcome workflow.

Each workflow reuses the frozen `build_outcome` example (the underlying truth) and renders it as free
text with §4 semantic challenges — explicit amounts/versions (deterministically parseable) plus
semantic spans (approval requested-vs-granted, active-vs-superseded, negated exceptions, conditional
language, distractors, retrospective corrections). Normalization is then the inverse problem; the
downstream pipeline stays the frozen deterministic one. `truth` carries ground-truth facts + spans.
"""
from __future__ import annotations

import torch
from typing import List

from experiments.enterprise_slots_quadratic.schema import DomainCfg
from experiments.enterprise_slots_quadratic.dataset import _policy_table, N_TIERS
from experiments.enterprise_output_mapping.workflows import build_outcome
from experiments.enterprise_output_mapping.outcome_contract import OUTCOMES
from .document_schema import Document, Workflow, Fact
from .evidence_schema import EXACT, INFERRED, AMBIGUOUS

TIER_DOLLARS = {0: 4000, 1: 12000, 2: 45000, 3: 120000}
GRANTED_PHRASES = ["approval has been granted", "the request is hereby approved",
                   "sign-off is complete", "we approve this purchase"]
REQUESTED_PHRASES = ["approval is requested", "seeking approval from finance",
                     "please review for approval", "pending sign-off"]


def _ri(n, g):
    return int(torch.randint(0, n, (1,), generator=g).item())


def _fact(field, value, status, challenge, span):
    return Fact(field=field, value=value, interpretation_status=status, challenge=challenge, span=span)


def generate_workflow(cfg: DomainCfg, seed: int, table=None) -> Workflow:
    g = torch.Generator().manual_seed(seed)
    table = table if table is not None else _policy_table(cfg)
    ex = build_outcome(cfg, 64, "streaming", g, dup_noise=False, table=table)
    tid = ex["tenant"]; req = ex["req"]; tier = ex["tier"]; version = ex["version"]
    scenario = ex["scenario"]; approval_present = ex["approval_id"] >= 0
    docs: List[Document] = []
    wid = f"WF-{seed:05d}"

    # 1 purchase request — explicit amount (deterministic)
    amt = TIER_DOLLARS[tier]
    docs.append(Document(f"{wid}-PR", tid, "purchase_request", subject_id=req,
        body=f"Purchase Request request:{req}. Requested amount: ${amt:,}. Vendor engagement pending.",
        truth=[_fact("amount", amt, EXACT, "explicit", f"${amt:,}"),
               _fact("budget_tier", tier, EXACT, "explicit", f"${amt:,}")]))

    # 2 policy document — active policy version + status (active vs superseded challenge).
    # In the 'missing' scenario the ACTIVE policy is genuinely absent from the corpus (only the
    # superseded draft remains) → normalization must recover no active policy → downstream abstains.
    if scenario != "missing":
        docs.append(Document(f"{wid}-POL", tid, "policy_document", subject_id=req,
            body=(f"Governance Policy for contract {ex['contract']}. Version {version}.0 is currently in "
                  f"effect. Prior versions are superseded and must not be applied."),
            truth=[_fact("policy_version", version, EXACT, "active_vs_superseded", f"Version {version}.0"),
                   _fact("explicit_status", "active", EXACT, "active_vs_superseded", "currently in effect")]))
    # a superseded distractor policy
    sv = (version + 1) % cfg.n_versions
    docs.append(Document(f"{wid}-POLD", tid, "policy_document", subject_id=req,
        body=f"Earlier draft: Version {sv}.0 was circulated but has since been superseded.",
        truth=[_fact("policy_version", sv, EXACT, "active_vs_superseded", f"Version {sv}.0"),
               _fact("explicit_status", "superseded", EXACT, "active_vs_superseded", "superseded")]))

    # 3 approval email — requested vs granted (INTERPRETED)
    if approval_present:
        phrase = GRANTED_PHRASES[_ri(len(GRANTED_PHRASES), g)]; granted = True
    else:
        phrase = REQUESTED_PHRASES[_ri(len(REQUESTED_PHRASES), g)]; granted = False
    docs.append(Document(f"{wid}-APR", tid, "approval_email", subject_id=req,
        body=f"Re: request:{req}. Note: {phrase}. Regards, Finance.",
        truth=[_fact("approval_record_exists", True, EXACT, "explicit", "Re: request"),
               _fact("approval_granted", granted, INFERRED, "requested_vs_granted", phrase)]))

    # 4 conflict scenario — two active policies (conflicting_authority, INTERPRETED conflict)
    if scenario == "conflict":
        cv = (version + 3) % cfg.n_versions
        docs.append(Document(f"{wid}-POLC", tid, "policy_document", subject_id=req,
            body=(f"Separate authority asserts Version {cv}.0 is the operative policy, in force now. "
                  f"This has not been reconciled with the governance office."),
            truth=[_fact("policy_version", cv, EXACT, "conflicting_authority", f"Version {cv}.0"),
                   _fact("explicit_status", "active", EXACT, "conflicting_authority", "in force now"),
                   _fact("clauses_conflict", True, INFERRED, "conflicting_authority", "not been reconciled")]))

    # 5 exception request with negation (does NOT apply) — negation challenge
    neg = _ri(2, g) == 0
    docs.append(Document(f"{wid}-EXC", tid, "exception_request", subject_id=req,
        body=("An exception to the standard threshold does not apply to this request." if neg else
              "A temporary exception may apply if conditions are met."),
        truth=[_fact("exception_applies", (not neg), (INFERRED if not neg else EXACT),
                     ("conditional" if not neg else "negation"),
                     ("may apply if" if not neg else "does not apply"))]))

    # 6 distractor — plausible but irrelevant authoritative-looking doc
    docs.append(Document(f"{wid}-AUD", tid, "audit_event", subject_id=_ri(cfg.n_subject_ids, g),
        body=f"Audit: unrelated request:{_ri(cfg.n_subject_ids, g)} amount ${TIER_DOLLARS[_ri(N_TIERS, g)]:,} logged.",
        truth=[]))

    return Workflow(wid, docs, frozen_ex=ex)


def generate(cfg, n, seed0, table=None):
    return [generate_workflow(cfg, seed0 + i, table) for i in range(n)]
