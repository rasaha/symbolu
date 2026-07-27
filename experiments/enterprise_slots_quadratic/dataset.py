"""
dataset.py — procurement & approval-governance workflows with STRUCTURAL labels (no LLM).

Primary decision: the required approval ROLE for a PurchaseRequest is a deterministic function of
(budget tier, active-policy version):  role = POLICY_TABLE[version][tier].  The two answer-
determining records — the BUDGET (keyed to the request) and the ACTIVE POLICY (keyed to the
CONTRACT, reachable only via request→vendor→contract→policy) — are placed at DISTANT workflow
steps. Superseded policy versions (T3 decoys), conflicting active policies (T2), irrelevant-pressure
records (T6) and unauthorized records (T7) fill the stream.

Retrieval-breadth asymmetry (the reason slots may help):
  * one-shot   — every authorized candidate is available at query time (fresh retrieval sees all).
  * streaming / multi-step — fresh retrieval only sees a bounded RECENT window, so distant required
    records (budget, policy) fall out of view; binding slots that admitted them earlier retain them.

Labels come straight from the generator. ABSTAIN is correct when a required record is absent from
what was observed, or when two active policies materially conflict (unresolved).
"""
from __future__ import annotations

import torch
from typing import Dict, List

from .schema import (Evidence, DomainCfg, ACTIVE, SUPERSEDED, EXPIRED, PENDING, REVOKED,
                     N_ROLE, ROLES)

N_TIERS = 4
ABSTAIN = N_ROLE                         # extra class for "cannot decide"
MODES = ("one_shot", "streaming", "multi_step")


def _policy_table(cfg: DomainCfg) -> List[List[int]]:
    """Fixed global rule (version, tier) -> approval role. Deterministic; learnable; stable."""
    g = torch.Generator().manual_seed(20260727)
    return [[int(torch.randint(0, N_ROLE, (1,), generator=g)) for _ in range(N_TIERS)]
            for _ in range(cfg.n_versions)]


def _ri(n, g):
    return int(torch.randint(0, n, (1,), generator=g).item())


def _all_roles_mask():
    return sum(1 << i for i in range(N_ROLE))


def make_workflow(cfg: DomainCfg, N: int, mode: str, g: torch.Generator,
                  subj_pool=None, tmpl_pool=None, table=None,
                  min_required=2, force_abstain=None) -> Dict:
    from .schema import SUBJECT_TYPES, RELATION_TYPES, OBJECT_TYPES
    ST = {n: i for i, n in enumerate(SUBJECT_TYPES)}
    RT = {n: i for i, n in enumerate(RELATION_TYPES)}
    OT = {n: i for i, n in enumerate(OBJECT_TYPES)}
    table = table if table is not None else _policy_table(cfg)
    subj_pool = subj_pool if subj_pool is not None else list(range(cfg.n_subject_ids))
    tmpl_pool = tmpl_pool if tmpl_pool is not None else list(range(cfg.n_templates))
    tenant = _ri(cfg.n_tenants, g)
    role_idx = 1                                   # the querying role (role:finance) — fixed for pilot
    tpl = lambda: tmpl_pool[_ri(len(tmpl_pool), g)]

    req = subj_pool[_ri(len(subj_pool), g)]        # PurchaseRequest id
    vendor = subj_pool[_ri(len(subj_pool), g)]
    contract = subj_pool[_ri(len(subj_pool), g)]
    policy = subj_pool[_ri(len(subj_pool), g)]
    tier = _ri(N_TIERS, g)
    version = _ri(cfg.n_versions, g)
    all_roles = _all_roles_mask()

    events: List[Evidence] = []
    eid = [0]

    def add(sec, s_type, s_id, rel, o_type, o_val, status=ACTIVE, ver=1, auth=1.0,
            roles=None, tag="", tmpl=None):
        e = Evidence(tenant_id=tenant, evidence_id=eid[0], document_id=_ri(cfg.n_documents, g),
                     section_id=sec, subject_type=ST[s_type], subject_id=s_id,
                     relation_type=RT[rel], object_type=OT[o_type], object_id_or_value=o_val,
                     timestamp=len(events), valid_from=0, valid_to=10 ** 9, version=ver,
                     status=status, source_authority=auth,
                     source_span=_ri(64, g), access_roles=(all_roles if roles is None else roles),
                     template=(tmpl if tmpl is not None else tpl()), tag=tag, arrival_section=sec)
        eid[0] += 1
        events.append(e)
        return e

    # ---- distant section layout ----
    last = cfg.n_sections - 1
    early = 1 + _ri(max(1, cfg.n_sections // 4), g)
    mid = cfg.n_sections // 2 + _ri(max(1, cfg.n_sections // 8), g)

    # decide abstention scenario
    scenario = force_abstain
    if scenario is None:
        r = _ri(10, g)
        scenario = "missing" if r < 2 else "conflict" if r < 4 else "normal"

    # ---- required chain (distant) ----
    add(early, "PurchaseRequest", req, "has_budget", "Amount", tier, tag="budget")          # BUDGET (tier)
    add(early + 1, "PurchaseRequest", req, "awarded_to", "Vendor", vendor, tag="vendor_link")
    add(mid, "Vendor", vendor, "governed_by", "Contract", contract, tag="contract_link")
    active_policy = add(mid + 1, "Contract", contract, "governed_by", "Policy", policy,
                        status=ACTIVE, ver=version, tag="policy_active")                     # ACTIVE POLICY (version)
    required_ids = [e.evidence_id for e in events if e.tag in ("budget", "policy_active")]

    # superseded earlier policy versions (T3 decoys), distinct versions
    for j in range(2):
        sv = (version + 1 + j) % cfg.n_versions
        add(early + 2 + j, "Contract", contract, "governed_by", "Policy", policy,
            status=SUPERSEDED, ver=sv, tag="policy_superseded")

    conflict = 0
    if scenario == "conflict":
        # a second ACTIVE policy with a DIFFERENT version → unresolved material conflict
        cv = (version + 3) % cfg.n_versions
        add(mid + 2, "Contract", contract, "governed_by", "Policy", policy, status=ACTIVE,
            ver=cv, tag="policy_conflict")
        conflict = 1

    # unauthorized-but-relevant record (T7): correct chain link the querying role may NOT read
    add(mid, "Contract", contract, "governed_by", "Policy", policy, status=ACTIVE, ver=version,
        roles=(1 << 4), tag="unauthorized_policy")                    # readable only by role:admin

    # ---- fill with irrelevant-pressure records (T6) across all sections ----
    while len(events) < N - 1:
        s_id = subj_pool[_ri(len(subj_pool), g)]
        sec = _ri(cfg.n_sections, g)
        add(sec, "Invoice", s_id, "bills", "Value", _ri(cfg.n_object_ids, g),
            status=ACTIVE, ver=_ri(cfg.n_versions, g), auth=round(0.5 + 0.5 * torch.rand(1, generator=g).item(), 2),
            tag="irrelevant")

    # ---- final authorization query (last section) ----
    query = add(last, "PurchaseRequest", req, "requires_approval", "Role", 0, tag="query")
    query_pos = len(events) - 1

    # if scenario == missing, REMOVE the active policy record from the observed stream
    if scenario == "missing":
        events = [e for e in events if e.tag != "policy_active"]
        required_present = False
    else:
        required_present = True

    # ---- label ----
    if scenario == "missing" or (scenario == "conflict"):
        answer_role = ABSTAIN
    else:
        answer_role = table[version][tier]
    abstain = int(answer_role == ABSTAIN)

    # keep the query last, then order the rest by arrival section (stable, resolvable)
    non_q = [e for e in events if e.tag != "query"]
    qev = [e for e in events if e.tag == "query"][0]
    non_q.sort(key=lambda e: (e.arrival_section, e.timestamp))
    events = non_q + [qev]
    for i, e in enumerate(events):
        e.timestamp = i
    query_pos = len(events) - 1
    active_policy_id = next((e.evidence_id for e in events if e.tag == "policy_active"), -1)
    budget_id = next((e.evidence_id for e in events if e.tag == "budget"), -1)

    return {"events": events, "tenant": tenant, "role_idx": role_idx, "mode": mode,
            "req": req, "contract": contract, "policy": policy, "tier": tier, "version": version,
            "answer_role": answer_role, "abstain": abstain, "conflict": conflict,
            "active_version": version, "scenario": scenario, "required_present": required_present,
            "required_ids": [budget_id, active_policy_id], "budget_id": budget_id,
            "active_policy_id": active_policy_id, "query_pos": query_pos, "N": len(events),
            "n_sections": cfg.n_sections}


def generate(cfg: DomainCfg, N: int, mode: str, n: int, seed: int,
             subj_pool=None, tmpl_pool=None, table=None):
    g = torch.Generator().manual_seed(seed)
    return [make_workflow(cfg, N, mode, g, subj_pool, tmpl_pool, table) for _ in range(n)]
