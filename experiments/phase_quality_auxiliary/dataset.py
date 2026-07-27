"""
dataset.py — bounded enterprise case-history evidence streams with STRUCTURAL quality labels.

Each example is one long ordered stream of records for many subjects, plus a focus subject whose
long-range information-health we label. Labels are produced directly by the generator (no LLM),
derivable from structure (not from memorized IDs). Four Phase-plausible targets:

    persistence            — the focus issue stays active across DISTANT evidence (early & late)
    unresolved_recurrence  — focus issue opens, is resolved locally, then RETURNS unresolved later
    context_shift          — later evidence explicitly supersedes/amends the earlier focus context
    sequence_anomaly       — a focus record violates its established temporal trajectory

Designed information asymmetry (the whole point): the causal evidence for these conditions is
placed at controlled (often large) distances from the query at the end. The bounded quadratic
packet is LOCAL (deterministic index around the query), so it structurally cannot see the distant
evidence; only an O(N) full-stream scanner (Phase, or a temporal baseline) can. Harmless-unusual
events are injected so a true `sequence_anomaly` must be distinguished from mere rarity.

Record schema (all ids are small ints; strings are template ids so renaming is structural):
    document_id, section_id, evidence_id, subject_id, relation_id, object_id,
    timestamp, version, status, source_authority, source_span
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict

import torch

# status codes
OPEN, RESOLVED, SUPERSEDED, AMENDED, EXCEPTION, NOTE = 0, 1, 2, 3, 4, 5
STATUS_NAMES = {OPEN: "open", RESOLVED: "resolved", SUPERSEDED: "superseded",
                AMENDED: "amended", EXCEPTION: "exception", NOTE: "note"}
N_STATUS = 6
TARGETS = ("persistence", "unresolved_recurrence", "context_shift", "sequence_anomaly")


@dataclass
class Schema:
    n_subjects: int = 64
    n_relations: int = 8
    n_objects: int = 32
    n_documents: int = 16
    n_sections: int = 8
    n_authorities: int = 4
    n_templates: int = 12          # wording/event templates (for held-out template splits)
    packet_K: int = 16             # bounded quadratic candidate packet size

    # numeric feature width per record (fed to the encoder)
    @property
    def n_status(self): return N_STATUS


def _ri(n, g):
    return int(torch.randint(0, n, (1,), generator=g).item())


def _rf(g):
    return float(torch.rand(1, generator=g).item())


def _rec(eid, doc, sec, subj, rel, obj, ts, ver, status, auth, span, template, tag=""):
    return {"evidence_id": eid, "document_id": doc, "section_id": sec, "subject_id": subj,
            "relation_id": rel, "object_id": obj, "timestamp": ts, "version": ver,
            "status": status, "source_authority": auth, "source_span": span,
            "template": template, "tag": tag}


def make_stream(schema: Schema, N: int, g: torch.Generator,
                subj_pool=None, template_pool=None) -> Dict:
    """Generate one stream + focus labels. subj_pool/template_pool restrict ids for held-out splits."""
    S = schema
    subj_pool = subj_pool if subj_pool is not None else list(range(S.n_subjects))
    template_pool = template_pool if template_pool is not None else list(range(S.n_templates))
    focus = subj_pool[_ri(len(subj_pool), g)]
    frel = _ri(S.n_relations, g)
    theme_obj = _ri(S.n_objects, g)

    # label booleans (balanced ~50%); anomaly slightly rarer, harmless-unusual always present
    has_persist = _rf(g) < 0.5
    has_recur = _rf(g) < 0.5
    has_shift = _rf(g) < 0.5
    has_anom = _rf(g) < 0.4

    events: List[Dict] = []
    tpl = lambda: template_pool[_ri(len(template_pool), g)]
    auth = lambda: _ri(S.n_authorities, g)

    def add(subj, rel, obj, status, ver, tag=""):
        ts = len(events)                                  # monotone base timestamp = arrival order
        events.append(_rec(-1, _ri(S.n_documents, g), _ri(S.n_sections, g), subj, rel, obj, ts,
                           ver, status, auth(), _ri(64, g), tpl(), tag))

    # ---- distant focus evidence (placed early; query is at the end) ----
    # reserve slots: we build a background of distractors and splice focus records at target
    # positions to control distance. First lay down N background records, then overwrite chosen
    # positions with focus records so the causal evidence sits far from the end.
    for _ in range(N):
        subj = subj_pool[_ri(len(subj_pool), g)]
        add(subj, _ri(S.n_relations, g), _ri(S.n_objects, g), NOTE, 1)

    def place(pos, rel, obj, status, ver, tag):
        events[pos] = _rec(-1, events[pos]["document_id"], events[pos]["section_id"], focus, rel,
                           obj, pos, ver, status, auth(), events[pos]["source_span"], tpl(), tag)

    early = 1 + _ri(max(1, N // 8), g)                    # distant region (near the front)
    mid = N // 2 + _ri(max(1, N // 8), g)
    late = N - 2 - _ri(max(1, N // 8), g)                 # near the query
    relevant_positions = []

    if has_persist:
        place(early, frel, theme_obj, OPEN, 1, "persist_early")
        place(late, frel, theme_obj, OPEN, 1, "persist_late")
        relevant_positions += [early, late]
    if has_recur:
        r0 = max(2, early - 1); r1 = mid; r2 = late - 1
        place(r0, frel, theme_obj, OPEN, 1, "recur_open")
        place(r1, frel, theme_obj, RESOLVED, 2, "recur_resolved")
        place(r2, frel, theme_obj, OPEN, 3, "recur_reopen")
        relevant_positions += [r0, r1, r2]
    if has_shift:
        s0 = early + 1 if early + 1 < mid else early
        place(s0, frel, theme_obj, OPEN, 1, "shift_orig")
        place(mid + 1 if mid + 1 < late else mid, frel, (theme_obj + 1) % S.n_objects,
              SUPERSEDED, 2, "shift_supersede")
        relevant_positions += [s0, mid + 1 if mid + 1 < late else mid]
    if has_anom:
        # true anomaly: a version/status regression inconsistent with the trajectory
        ap = mid - 2 if mid - 2 > early + 2 else mid
        place(ap, frel, theme_obj, RESOLVED, 5, "anom_reg")           # high version resolved…
        place(ap + 1 if ap + 1 < late else ap, frel, theme_obj, OPEN, 1, "anom_regress_ver")  # …then version drops to 1 (impossible)
        relevant_positions += [ap, ap + 1 if ap + 1 < late else ap]
    # harmless unusual event (rare-but-valid): a lone EXCEPTION status, never an anomaly label
    hp = N // 3 + _ri(max(1, N // 8), g)
    place(hp, frel, theme_obj, EXCEPTION, 1, "harmless_unusual")

    # ---- query record at the end (focus, asks about current health) ----
    place(N - 1, frel, theme_obj, NOTE, 1, "query")
    query_pos = N - 1

    # assign unique evidence ids in arrival order
    for i, e in enumerate(events):
        e["evidence_id"] = i

    labels = {"persistence": int(has_persist), "unresolved_recurrence": int(has_recur),
              "context_shift": int(has_shift), "sequence_anomaly": int(has_anom)}
    # distance of the nearest relevant distant evidence from the query
    dist = min([query_pos - p for p in relevant_positions], default=query_pos)
    return {"events": events, "focus": focus, "frel": frel, "theme_obj": theme_obj,
            "labels": labels, "query_pos": query_pos, "N": N,
            "relevant_positions": sorted(set(relevant_positions)),
            "min_relevant_distance": int(dist)}


# ---------- deterministic index: bounded candidate packet around the query ----------
def deterministic_packet(ex: Dict, schema: Schema) -> List[int]:
    """Deterministic subject/object index → bounded LOCAL candidate packet for the quadratic module.
    Includes: the query, temporally-adjacent records, and same-subject records within a LOCAL window
    near the query. Distant focus evidence is intentionally OUT of the packet (bounded, local)."""
    ev = ex["events"]; q = ex["query_pos"]; K = schema.packet_K
    W = 4 * K                                              # local window scanned deterministically
    lo = max(0, q - W)
    local = list(range(lo, q + 1))
    focus = ex["focus"]
    same_subj = [i for i in local if ev[i]["subject_id"] == focus]
    adj = [i for i in range(max(0, q - K // 2), q + 1)]
    conflicting = [i for i in same_subj
                   if ev[i]["relation_id"] == ex["frel"] and ev[i]["object_id"] != ex["theme_obj"]]
    superseding = [i for i in same_subj if ev[i]["status"] in (SUPERSEDED, AMENDED)]
    packet = []
    for group in (same_subj, superseding, conflicting, adj):
        for i in group:
            if i not in packet:
                packet.append(i)
    packet = sorted(packet)[-K:]                           # bounded
    if q not in packet:
        packet = (packet + [q])[-K:]
    return packet


# ---------- featurization ----------
CAT_FIELDS = ("document_id", "section_id", "subject_id", "relation_id", "object_id",
              "status", "source_authority", "template")


def field_dims(schema: Schema) -> Dict[str, int]:
    return {"document_id": schema.n_documents, "section_id": schema.n_sections,
            "subject_id": schema.n_subjects, "relation_id": schema.n_relations,
            "object_id": schema.n_objects, "status": N_STATUS,
            "source_authority": schema.n_authorities, "template": schema.n_templates}


def encode_categoricals(ex: Dict, schema: Schema, device="cpu"):
    """Return dict field -> LongTensor[N] plus numeric [N,3] (timestamp, version, span-normalized)."""
    ev = ex["events"]; N = len(ev)
    cats = {f: torch.tensor([e[f] for e in ev], dtype=torch.long, device=device) for f in CAT_FIELDS}
    num = torch.tensor([[e["timestamp"] / max(1, N), e["version"] / 8.0, e["source_span"] / 64.0]
                        for e in ev], dtype=torch.float32, device=device)
    return cats, num


def deterministic_quality_features(ex: Dict, schema: Schema, device="cpu") -> torch.Tensor:
    """Already-deterministic quality dims (provenance/authority/timestamp/schema/version) computed
    on the bounded packet — the metadata-only signal available WITHOUT temporal modeling."""
    ev = ex["events"]; packet = deterministic_packet(ex, schema)
    p = [ev[i] for i in packet]
    n = max(1, len(p))
    provenance_present = sum(1 for e in p if e["source_span"] >= 0) / n
    authority_mean = sum(e["source_authority"] for e in p) / n / schema.n_authorities
    ts_valid = sum(1 for e in p if 0 <= e["timestamp"] <= ex["N"]) / n
    max_ver = max((e["version"] for e in p), default=0) / 8.0
    n_superseded = sum(1 for e in p if e["status"] in (SUPERSEDED, AMENDED)) / n
    n_open = sum(1 for e in p if e["status"] == OPEN) / n
    n_resolved = sum(1 for e in p if e["status"] == RESOLVED) / n
    n_conflict = sum(1 for e in p if e["relation_id"] == ex["frel"]
                     and e["object_id"] != ex["theme_obj"]) / n
    packet_frac = len(packet) / ex["N"]
    return torch.tensor([provenance_present, authority_mean, ts_valid, max_ver, n_superseded,
                         n_open, n_resolved, n_conflict, packet_frac], dtype=torch.float32, device=device)


DET_FEAT_DIM = 9


def generate(schema: Schema, N: int, n: int, seed: int, subj_pool=None, template_pool=None):
    g = torch.Generator().manual_seed(seed)
    return [make_stream(schema, N, g, subj_pool, template_pool) for _ in range(n)]
