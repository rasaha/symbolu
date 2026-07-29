"""
datasets.py — synthetic enterprise procurement/approval corpus (§8).

Each `Instance` carries FOUR aligned views of the same underlying facts:

    oracle_records     ground-truth normalized EventRecords (the construction ceiling)
    predicted_records  what an extraction pipeline would emit — lossy/noisy (§9 Stage 2)
    raw_text           document text the token path (Mistral stand-in) reads
    retrieved_text      a retrieved packet (H1: ordinary text, no normalized events)

The gold answer is a DETERMINISTIC function of the oracle records — never of the text or of any
model — so the labels are ground truth, not LLM-derived.

Task families are split by the capability they stress:

    lookup / rule-solvable   exact_threshold, active_policy, active_vs_stale, multi_record_chain,
                             unresolved_conflict, evidence_incomplete   → deterministic rules suffice
    pairwise-relational      approval_req_vs_granted, authoritative_source, supporting_vs_opposing,
                             exception_interaction                      → need slot-to-slot interaction

Mean pooling (H2) destroys the pairwise structure the relational families depend on; full event
self-attention (H3) preserves it. That asymmetry is the whole point of the H3 − H2 comparison.

Held-out evaluation uses UNSEEN entity ids, templates, and wording (§8) — a disjoint high id range
and a separate phrasing lexicon — so memorization cannot pass.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from ._common import RNG
from .event_schema import (EventRecord, Query, Instance, REL, ACTIVE, SUPERSEDED, EXPIRED,
                           PENDING, REVOKED, INTERP_RESOLVED, INTERP_PROVISIONAL, INTERP_AMBIGUOUS,
                           INTERP_CONFLICTED, scope_mask, seal_all, SUBJECT_TYPES, OBJECT_TYPES)

_SUBJ_IDX = {n: i for i, n in enumerate(SUBJECT_TYPES)}
_OBJ_IDX = {n: i for i, n in enumerate(OBJECT_TYPES)}

# ---------------- answer vocabulary (shared head across all arms) ----------------
# 0..4 = the five ROLES ; 5 = ABSTAIN ; 6 = CONFLICT ; 7 = YES ; 8 = NO
ABSTAIN, CONFLICT, YES, NO = 5, 6, 7, 8
N_CLASS = 9
CLASS_NAMES = ["role:requester", "role:finance", "role:finance_director", "role:auditor",
               "role:admin", "ABSTAIN", "CONFLICT", "YES", "NO"]

# POLICY_TABLE[active_policy_version][budget_tier] -> required approval role (deterministic)
POLICY_TABLE = [
    [1, 2, 2, 3],
    [1, 1, 2, 3],
    [2, 2, 3, 3],
    [1, 2, 3, 4],
]
N_VERSION = len(POLICY_TABLE)
N_TIER = 4

FAMILIES = [
    "exact_threshold", "active_policy", "approval_req_vs_granted", "authoritative_source",
    "active_vs_stale", "supporting_vs_opposing", "exception_interaction", "multi_record_chain",
    "unresolved_conflict", "evidence_incomplete",
]
RELATIONAL_FAMILIES = {"approval_req_vs_granted", "authoritative_source",
                       "supporting_vs_opposing", "exception_interaction"}


@dataclass
class DataCfg:
    n_train: int = 900
    n_heldout: int = 320
    n_distractors: int = 3            # irrelevant records added per instance
    extract_drop_p: float = 0.10      # predicted pipeline drops a record
    extract_corrupt_p: float = 0.14   # predicted pipeline corrupts a field
    heldout_id_base: int = 500        # unseen entity id range for held-out
    seed: int = 0


# ---------------- token lexicon (for the raw text the token path reads) ----------------
STATUS_WORD = {ACTIVE: "active", SUPERSEDED: "superseded", EXPIRED: "expired",
               PENDING: "pending", REVOKED: "revoked"}
ROLE_WORD = ["requester", "finance", "finance_director", "auditor", "admin"]
# two phrasing lexicons: train vs held-out (unseen wording)
PHRASE = {
    "train": {"policy": "policy", "version": "version", "budget": "budget", "tier": "tier",
              "requires": "requires", "approval": "approval", "threshold": "threshold",
              "amount": "amount", "granted": "granted", "requested": "requested",
              "exception": "exception", "authority": "authority", "conflicts": "conflicts",
              "supports": "supports", "opposes": "opposes"},
    "heldout": {"policy": "directive", "version": "revision", "budget": "allocation", "tier": "band",
                "requires": "mandates", "approval": "signoff", "threshold": "ceiling",
                "amount": "sum", "granted": "issued", "requested": "sought",
                "exception": "waiver", "authority": "standing", "conflicts": "clashes",
                "supports": "backs", "opposes": "counters"},
}


class Vocab:
    def __init__(self):
        self.tok2id: Dict[str, int] = {"<pad>": 0, "<unk>": 1, "<bos>": 2, "<eos>": 3}
        self.frozen = False

    def add(self, tok: str) -> int:
        if tok not in self.tok2id and not self.frozen:
            self.tok2id[tok] = len(self.tok2id)
        return self.tok2id.get(tok, 1)

    def encode(self, text: str, max_len: int) -> List[int]:
        ids = [2] + [self.add(t) for t in text.split()][: max_len - 2] + [3]
        ids += [0] * (max_len - len(ids))
        return ids[:max_len]

    def __len__(self):
        return len(self.tok2id)


# ---------------- record factory ----------------
class _Ctx:
    def __init__(self, rng: RNG, tenant: int, id_base: int):
        self.rng = rng
        self.tenant = tenant
        self.next_id = id_base
        self.records: List[EventRecord] = []

    def mk(self, subject_type, subject_id, relation, object_type, obj, version=0,
           status=ACTIVE, authority=0.8, valid_from=0, valid_to=99, interp=INTERP_RESOLVED,
           norm=None, roles=None, doc=0, span=0, conf=0.95, arrival=0) -> EventRecord:
        eid = self.next_id
        self.next_id += 1
        if roles is None:
            roles = [0, 1, 2, 3, 4]          # readable by all roles by default
        if norm is None:
            norm = obj
        st_idx = _SUBJ_IDX[subject_type] if isinstance(subject_type, str) else subject_type
        ob_idx = _OBJ_IDX[object_type] if isinstance(object_type, str) else object_type
        r = EventRecord(
            evidence_id=eid, tenant_id=self.tenant, source_document_id=doc, source_span=span,
            subject_id=subject_id, relation_type=relation, object_id_or_value=obj,
            normalized_value=norm, version=version, status=status, valid_from=valid_from,
            valid_to=valid_to, authority=authority, access_scope=scope_mask(roles),
            interpretation_status=interp, confidence=conf, subject_type=st_idx,
            object_type=ob_idx, arrival_step=arrival).seal()
        self.records.append(r)
        return r


def _verbalize(rec: EventRecord, lex: Dict[str, str]) -> str:
    rel = None
    for k, v in REL.items():
        if v == rec.relation_type:
            rel = k
            break
    st = STATUS_WORD[rec.status]
    return (f"doc ent_{rec.subject_id} {rel} ent_{rec.object_id_or_value} "
            f"{lex['version']} v{rec.version} {st} {lex['authority']} "
            f"a{int(rec.authority * 10)} norm n{rec.normalized_value}")


# ---------------- per-family generators ----------------
def _distractors(ctx: _Ctx, subj: int, k: int) -> None:
    for _ in range(k):
        s = ctx.rng.randint(900, 999)
        ctx.mk("Vendor", s, REL["belongs_to"], "Value", ctx.rng.randint(0, 20),
               status=ctx.rng.choice([ACTIVE, EXPIRED]), authority=0.4,
               interp=INTERP_RESOLVED)


def _gen_instance(family: str, cfg: DataCfg, rng: RNG, lex: Dict[str, str],
                  id_base: int, reader_role: int, tenant: int) -> Instance:
    ctx = _Ctx(rng, tenant, id_base)
    subj = rng.randint(id_base, id_base + 40)
    required: List[int] = []
    labels: Dict = {"conflict": 0, "abstain": 0}
    ans = ABSTAIN

    if family == "exact_threshold":
        thr = rng.randint(2, 8)
        amt = rng.randint(0, 12)
        t = ctx.mk("Policy", subj, REL["threshold_at"], "Amount", thr, norm=thr, authority=0.9)
        a = ctx.mk("PurchaseRequest", subj, REL["has_budget"], "Amount", amt, norm=amt, authority=0.9)
        required = [t.evidence_id, a.evidence_id]
        ans = YES if amt > thr else NO

    elif family == "active_policy":
        ver = rng.randint(0, N_VERSION)
        tier = rng.randint(0, N_TIER)
        stale = (ver + 1) % N_VERSION
        p_active = ctx.mk("Policy", subj, REL["governed_by"], "Policy", ver, version=ver,
                          status=ACTIVE, authority=0.9)
        ctx.mk("Policy", subj, REL["governed_by"], "Policy", stale, version=stale,
               status=SUPERSEDED, authority=0.85)
        b = ctx.mk("PurchaseRequest", subj, REL["has_budget"], "Value", tier, norm=tier, authority=0.9)
        required = [p_active.evidence_id, b.evidence_id]
        ans = POLICY_TABLE[ver][tier]

    elif family == "approval_req_vs_granted":
        role = rng.randint(1, 5)
        req = ctx.mk("Approval", subj, REL["approval_requested"], "Role", role, norm=role, authority=0.9)
        granted_role = role if rng.random() < 0.5 else rng.randint(1, 5)
        g = ctx.mk("Approval", subj, REL["approval_granted"], "Role", granted_role,
                   norm=granted_role, authority=0.9)
        required = [req.evidence_id, g.evidence_id]
        ans = YES if granted_role == role else NO

    elif family == "authoritative_source":
        v1 = rng.randint(1, 5)
        v2 = rng.randint(1, 5)
        while v2 == v1:
            v2 = rng.randint(1, 5)
        a1 = rng.choice([0.6, 0.7, 0.9])
        a2 = rng.choice([0.6, 0.7, 0.9])
        r1 = ctx.mk("Policy", subj, REL["requires_approval"], "Role", v1, norm=v1, authority=a1)
        r2 = ctx.mk("Policy", subj, REL["requires_approval"], "Role", v2, norm=v2, authority=a2)
        required = [r1.evidence_id, r2.evidence_id]
        if a1 > a2:
            ans = v1
        elif a2 > a1:
            ans = v2
        else:
            ans = CONFLICT
            labels["conflict"] = 1

    elif family == "active_vs_stale":
        va = rng.randint(1, 5)
        vs = rng.randint(1, 5)
        active = ctx.mk("Policy", subj, REL["requires_approval"], "Role", va, norm=va,
                        version=3, status=ACTIVE, authority=0.85)
        ctx.mk("Policy", subj, REL["requires_approval"], "Role", vs, norm=vs,
               version=1, status=SUPERSEDED, authority=0.85)
        required = [active.evidence_id]
        ans = va

    elif family == "supporting_vs_opposing":
        claim_role = rng.randint(1, 5)
        n_sup = rng.randint(0, 4)
        n_opp = rng.randint(0, 4)
        for _ in range(n_sup):
            s = ctx.mk("Policy", subj, REL["authorized_by"], "Role", claim_role, norm=claim_role,
                       authority=0.8)
            required.append(s.evidence_id)
        for _ in range(n_opp):
            s = ctx.mk("Policy", subj, REL["conflicts_with"], "Role", claim_role, norm=claim_role,
                       authority=0.8)
            required.append(s.evidence_id)
        anchor = ctx.mk("Approval", subj, REL["approval_requested"], "Role", claim_role,
                        norm=claim_role, authority=0.9)
        required.append(anchor.evidence_id)
        if n_sup > n_opp:
            ans = YES
        elif n_opp > n_sup:
            ans = NO
        else:
            ans = CONFLICT
            labels["conflict"] = 1

    elif family == "exception_interaction":
        tier = rng.randint(0, N_TIER)
        ver = rng.randint(0, N_VERSION)
        base_role = POLICY_TABLE[ver][tier]
        p = ctx.mk("Policy", subj, REL["governed_by"], "Policy", ver, version=ver, status=ACTIVE,
                   authority=0.9)
        b = ctx.mk("PurchaseRequest", subj, REL["has_budget"], "Value", tier, norm=tier, authority=0.9)
        required = [p.evidence_id, b.evidence_id]
        # an exception may lower the requirement by one role level if ACTIVE
        exc_active = rng.random() < 0.5
        lowered = max(1, base_role - 1)
        e = ctx.mk("Exception", subj, REL["grants_exception"], "Role", lowered, norm=lowered,
                   status=ACTIVE if exc_active else EXPIRED, authority=0.8)
        required.append(e.evidence_id)
        ans = lowered if exc_active else base_role

    elif family == "multi_record_chain":
        vendor = subj + 100
        contract = subj + 200
        ver = rng.randint(0, N_VERSION)
        tier = rng.randint(0, N_TIER)
        r1 = ctx.mk("PurchaseRequest", subj, REL["awarded_to"], "Vendor", vendor, authority=0.9)
        r2 = ctx.mk("Vendor", vendor, REL["governed_by"], "Contract", contract, authority=0.9)
        r3 = ctx.mk("Contract", contract, REL["governed_by"], "Policy", ver, version=ver,
                    status=ACTIVE, authority=0.9)
        b = ctx.mk("PurchaseRequest", subj, REL["has_budget"], "Value", tier, norm=tier, authority=0.9)
        required = [r1.evidence_id, r2.evidence_id, r3.evidence_id, b.evidence_id]
        ans = POLICY_TABLE[ver][tier]

    elif family == "unresolved_conflict":
        v1 = rng.randint(1, 5)
        v2 = rng.randint(1, 5)
        while v2 == v1:
            v2 = rng.randint(1, 5)
        a = ctx.mk("Policy", subj, REL["requires_approval"], "Role", v1, norm=v1, version=2,
                   status=ACTIVE, authority=0.85, interp=INTERP_CONFLICTED)
        b = ctx.mk("Policy", subj, REL["requires_approval"], "Role", v2, norm=v2, version=2,
                   status=ACTIVE, authority=0.85, interp=INTERP_CONFLICTED)
        required = [a.evidence_id, b.evidence_id]
        ans = CONFLICT
        labels["conflict"] = 1

    elif family == "evidence_incomplete":
        # the required active policy is simply absent → must abstain
        tier = rng.randint(0, N_TIER)
        ctx.mk("PurchaseRequest", subj, REL["has_budget"], "Value", tier, norm=tier, authority=0.9)
        ans = ABSTAIN
        labels["abstain"] = 1
        required = []  # the answer-determining record is intentionally missing

    _distractors(ctx, subj, cfg.n_distractors)

    oracle = seal_all(ctx.records)
    labels["family"] = family
    q = Query(task_family=family, subject_id=subj, reader_role=reader_role, tenant_id=tenant)

    # raw text: verbalize every oracle record + a couple of noise lines
    lines = [_verbalize(r, lex) for r in oracle]
    rng.shuffle(lines)
    raw = " . ".join(lines)
    # retrieved packet (H1): the required lines (still ordinary text, no normalized events)
    req_set = set(required)
    ret_lines = [_verbalize(r, lex) for r in oracle if r.evidence_id in req_set] or lines[:2]
    retrieved = " . ".join(ret_lines)

    predicted = _extract(oracle, cfg, rng, req_set)
    return Instance(query=q, oracle_records=oracle, predicted_records=predicted, raw_text=raw,
                    retrieved_text=retrieved, gold_answer=ans, required_ids=required, labels=labels)


def _extract(oracle: List[EventRecord], cfg: DataCfg, rng: RNG, req: set) -> List[EventRecord]:
    """Simulate a lossy extraction pipeline → provisional records (§9 Stage 2).

    Corruptions change an EXACT field then RE-SEAL, so the record is provenance-valid but
    semantically wrong (the realistic failure mode). Occasional drops remove a record entirely.
    Distractors survive unchanged. This is the sole source of the H5 (oracle) − H6 (predicted) gap.
    """
    out: List[EventRecord] = []
    for r in oracle:
        if rng.random() < cfg.extract_drop_p:
            continue
        import dataclasses as _dc
        c = _dc.replace(r)
        if rng.random() < cfg.extract_corrupt_p:
            f = rng.randint(0, 3)
            if f == 0:
                c.normalized_value = max(0, c.normalized_value + rng.choice([-1, 1]))
                c.object_id_or_value = c.normalized_value
            elif f == 1:
                c.status = rng.choice([ACTIVE, SUPERSEDED, EXPIRED])
            elif f == 2:
                c.version = max(0, c.version + rng.choice([-1, 1]))
            else:
                c.authority = min(1.0, max(0.0, c.authority + rng.choice([-0.2, 0.2])))
            c.confidence = 0.7
            c.interpretation_status = INTERP_PROVISIONAL
        c.seal()  # re-seal: provenance valid, identity possibly changed
        out.append(c)
    return out


def build_dataset(cfg: DataCfg) -> Tuple[List[Instance], List[Instance], Vocab]:
    rng = RNG(cfg.seed)
    vocab = Vocab()
    train: List[Instance] = []
    for i in range(cfg.n_train):
        fam = FAMILIES[i % len(FAMILIES)]
        reader = 2  # finance_director issues most queries; scope grants it
        inst = _gen_instance(fam, cfg, rng, PHRASE["train"], id_base=0, reader_role=reader, tenant=0)
        vocab.encode(inst.raw_text, 999)  # grow vocab on train text
        vocab.encode(inst.retrieved_text, 999)
        train.append(inst)
    vocab.frozen = True  # held-out cannot grow the vocab (unseen wording → <unk>)
    heldout: List[Instance] = []
    rng2 = RNG(cfg.seed + 777)
    for i in range(cfg.n_heldout):
        fam = FAMILIES[i % len(FAMILIES)]
        inst = _gen_instance(fam, cfg, rng2, PHRASE["heldout"], id_base=cfg.heldout_id_base,
                             reader_role=2, tenant=0)
        heldout.append(inst)
    return train, heldout, vocab
