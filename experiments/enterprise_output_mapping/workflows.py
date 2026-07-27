"""
workflows.py — outcome-labeled procurement workflows built ON TOP of the FROZEN slot/quadratic
dataset (the frozen `make_workflow` is imported unchanged; nothing in enterprise_slots_quadratic is
modified). This module adds: an approval-evidence record, a budget-sufficiency constraint, the true
StructuredFinding + bounded outcome label, and optional duplicate-noise injection (§9/§10).
"""
from __future__ import annotations

import torch
from typing import Dict, List

from experiments.enterprise_slots_quadratic.schema import (Evidence, DomainCfg, ACTIVE, SUPERSEDED)
from experiments.enterprise_slots_quadratic.dataset import make_workflow, _policy_table, N_TIERS
from experiments.enterprise_slots_quadratic.schema import (SUBJECT_TYPES, RELATION_TYPES, OBJECT_TYPES,
                                                           N_ROLE)
from .outcome_contract import (StructuredFinding, decide, BUDGET_SUFFICIENT, BUDGET_INSUFFICIENT,
                               BUDGET_MISSING, POLICY_IDENTIFIED, POLICY_MISSING, POLICY_CONFLICTED,
                               APPROVAL_PRESENT, APPROVAL_MISSING)

ST = {n: i for i, n in enumerate(SUBJECT_TYPES)}
RT = {n: i for i, n in enumerate(RELATION_TYPES)}
OT = {n: i for i, n in enumerate(OBJECT_TYPES)}
BUDGET_THRESHOLD = 1                      # tier < threshold ⇒ INSUFFICIENT ⇒ REJECT
DUP_KINDS = ("EXACT_DUPLICATE", "SOURCE_REDUNDANT", "SEMANTICALLY_SIMILAR_BUT_DISTINCT",
             "CONFLICT_PAIR", "VERSION_PAIR", "NON_DUPLICATE")


def _ri(n, g):
    return int(torch.randint(0, n, (1,), generator=g).item())


def _next_id(ex):
    return max(e.evidence_id for e in ex["events"]) + 1


def _add(ex, e: Evidence):
    ex["events"].append(e)


def _all_roles():
    return sum(1 << i for i in range(N_ROLE))


def _mk(ex, cfg, g, sec, s_type, s_id, rel, o_type, o_val, status=ACTIVE, ver=1, auth=1.0,
        roles=None, tag=""):
    return Evidence(tenant_id=ex["tenant"], evidence_id=_next_id(ex), document_id=_ri(cfg.n_documents, g),
                    section_id=sec, subject_type=ST[s_type], subject_id=s_id, relation_type=RT[rel],
                    object_type=OT[o_type], object_id_or_value=o_val, timestamp=0, valid_from=0,
                    valid_to=10 ** 9, version=ver, status=status, source_authority=auth,
                    source_span=_ri(64, g), access_roles=(_all_roles() if roles is None else roles),
                    template=_ri(cfg.n_templates, g), tag=tag, arrival_section=sec)


def build_outcome(cfg: DomainCfg, N, mode, g, subj_pool=None, tmpl_pool=None,
                  dup_noise=True, table=None) -> Dict:
    table = table if table is not None else _policy_table(cfg)
    ex = make_workflow(cfg, N, mode, g, subj_pool, tmpl_pool, table)     # FROZEN generator, unchanged
    req = ex["req"]; tier = ex["tier"]; version = ex["version"]; scenario = ex["scenario"]
    required_role = table[version][tier]

    # budget sufficiency (deterministic constraint)
    budget_status = BUDGET_SUFFICIENT if tier >= BUDGET_THRESHOLD else BUDGET_INSUFFICIENT
    if scenario == "missing":
        budget_status = budget_status                                    # budget still present; policy missing
    policy_status = (POLICY_MISSING if scenario == "missing" else
                     POLICY_CONFLICTED if scenario == "conflict" else POLICY_IDENTIFIED)

    # inject approval evidence for the required role with ~50% probability (distant section)
    approval_present = (_ri(2, g) == 0) and scenario == "normal"
    if approval_present:
        sec = 2 + _ri(max(1, cfg.n_sections // 3), g)
        _add(ex, _mk(ex, cfg, g, sec, "Approval", req, "authorized_by", "Role", required_role,
                     status=ACTIVE, ver=1, tag="approval"))
    approval_status = APPROVAL_PRESENT if approval_present else APPROVAL_MISSING

    evidence_complete = policy_status != POLICY_MISSING and budget_status != BUDGET_MISSING

    # optional duplicate-noise injection (§10): controlled, labeled duplicate kinds
    dup_log = []
    if dup_noise:
        _inject_duplicates(ex, cfg, g, dup_log)

    finding = StructuredFinding(budget_status, policy_status, approval_status,
                                material_conflict=(scenario == "conflict"),
                                evidence_complete=evidence_complete, unauthorized_present=False)
    outcome = decide(finding)

    # keep query last, re-id
    non_q = [e for e in ex["events"] if e.tag != "query"]
    qev = [e for e in ex["events"] if e.tag == "query"][0]
    non_q.sort(key=lambda e: (e.arrival_section, e.evidence_id))
    ex["events"] = non_q + [qev]
    for i, e in enumerate(ex["events"]):
        e.timestamp = i
    ex["query_pos"] = len(ex["events"]) - 1
    ex["budget_id"] = next((e.evidence_id for e in ex["events"] if e.tag == "budget"), -1)
    ex["active_policy_id"] = next((e.evidence_id for e in ex["events"] if e.tag == "policy_active"), -1)
    ex["approval_id"] = next((e.evidence_id for e in ex["events"] if e.tag == "approval"), -1)
    ex["required_ids"] = [ex["budget_id"], ex["active_policy_id"]]

    ex["required_role"] = required_role
    ex["outcome"] = outcome
    ex["finding"] = {"budget_status": budget_status, "policy_status": policy_status,
                     "approval_status": approval_status, "material_conflict": int(scenario == "conflict"),
                     "evidence_complete": int(evidence_complete)}
    ex["dup_log"] = dup_log
    return ex


def _inject_duplicates(ex, cfg, g, dup_log):
    """Add controlled duplicate variants of the active-policy record (§10)."""
    active = next((e for e in ex["events"] if e.tag == "policy_active"), None)
    if active is None:
        return
    kind = DUP_KINDS[_ri(len(DUP_KINDS), g)]
    base = active
    if kind == "EXACT_DUPLICATE":
        _add(ex, _mk(ex, cfg, g, base.section_id + 1, "Contract", base.subject_id, "governed_by",
                     "Policy", base.object_id_or_value, status=base.status, ver=base.version,
                     auth=base.source_authority, tag="dup_exact"))
    elif kind == "SOURCE_REDUNDANT":
        _add(ex, _mk(ex, cfg, g, base.section_id + 1, "Contract", base.subject_id, "governed_by",
                     "Policy", base.object_id_or_value, status=base.status, ver=base.version,
                     auth=round(min(1.0, base.source_authority - 0.1), 2), tag="dup_source"))
    elif kind == "SEMANTICALLY_SIMILAR_BUT_DISTINCT":
        _add(ex, _mk(ex, cfg, g, base.section_id + 1, "Contract", base.subject_id, "governed_by",
                     "Policy", (base.object_id_or_value + 1) % cfg.n_object_ids, status=ACTIVE,
                     ver=base.version, tag="dup_similar"))
    elif kind == "VERSION_PAIR":
        _add(ex, _mk(ex, cfg, g, base.section_id + 1, "Contract", base.subject_id, "governed_by",
                     "Policy", base.object_id_or_value, status=SUPERSEDED,
                     ver=(base.version + 1) % cfg.n_versions, tag="dup_versionpair"))
    dup_log.append(kind)
