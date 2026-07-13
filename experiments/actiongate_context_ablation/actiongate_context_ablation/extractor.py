"""F: context -> canonical envelope, in two modes.

STRUCTURED_ORACLE_EXTRACTOR
    Merges each surviving unit's explicit ``contrib`` fragment. Zero NLP error:
    establishes TRUE semantic causality on deterministic fixtures.

REALISTIC_EXTRACTOR (narrow transparent reference)
    Recovers a contrib fragment from each unit's natural-language ``text`` via a
    small, fully-readable keyword/regex ruleset. It is deliberately imperfect —
    phrasing it does not recognize is silently dropped. Its purpose is to measure
    deployable behaviour and, by disagreeing with the oracle, to expose
    EXTRACTOR_SENSITIVE cases. It is NOT production quality; limits are documented
    in EXTRACTOR_SPEC.md.

Neither mode changes ActionGate semantics; both feed the real ``adapter.build_env``.
"""

from __future__ import annotations

import re

from . import adapter
from .units import Context

ORACLE = "STRUCTURED_ORACLE_EXTRACTOR"
REALISTIC = "REALISTIC_EXTRACTOR"


# --------------------------------------------------------------------------- #
# merge: base + list of contrib fragments -> adapter.RequestSpec
# --------------------------------------------------------------------------- #
def _merge(base: dict, fragments: list) -> adapter.RequestSpec:
    tool = base["tool"]
    verb = base["verb"]
    target = list(base.get("target", []))
    args: dict = dict(base.get("args", {}))
    permissions = list(base["permissions"]) if base.get("permissions") else None
    reversibility = base.get("reversibility")
    state_as_of = base.get("state_as_of")
    state_hash = base.get("state_hash", adapter.DEFAULT_STATE_HASH)
    evidence: list = list(base.get("evidence", []))
    approvals: list = list(base.get("approvals", []))
    attestation = base.get("attestation")

    for frag in fragments:
        if not frag:
            continue
        if "attestation" in frag:
            attestation = frag["attestation"]
        if "args" in frag:
            args.update(frag["args"])
        if "target_add" in frag:
            target.extend(frag["target_add"])
        if "reversibility" in frag:
            reversibility = frag["reversibility"]
        if "permissions_add" in frag:
            permissions = (permissions or []) + list(frag["permissions_add"])
        if "state_as_of" in frag:
            state_as_of = frag["state_as_of"]
        if "state_hash" in frag:
            state_hash = frag["state_hash"]
        if "evidence" in frag:
            evidence.extend(frag["evidence"])
        if "approvals" in frag:
            approvals.extend(frag["approvals"])

    return adapter.RequestSpec(
        tool=tool, verb=verb, target=tuple(target), args=args,
        reversibility=reversibility,
        permissions=tuple(permissions) if permissions else None,
        state_as_of=state_as_of, state_hash=state_hash,
        evidence=tuple(evidence), approvals=tuple(approvals),
        attestation=attestation)


def oracle_spec(ctx: Context, surviving_ids) -> adapter.RequestSpec:
    keep = set(surviving_ids)
    frags = [u.contrib for u in ctx.units if u.id in keep]
    return _merge(ctx.base, frags)


# --------------------------------------------------------------------------- #
# realistic reference extractor: text -> contrib fragment (narrow, transparent)
# --------------------------------------------------------------------------- #
_NUM_ROWS = re.compile(r"(\d[\d,]*)\s*(?:rows|records|objects|resources)", re.I)


def reference_fragment(text: str) -> dict:
    """Recover a contrib fragment from natural language via readable keyword rules.

    KNOWN LIMITS (see EXTRACTOR_SPEC.md): recognizes only the phrasings enumerated
    below; paraphrases, negation scope beyond these keywords, and implicit facts
    are dropped. This under-recovery is intentional and is what the instability
    metric measures.
    """
    t = text.lower()
    frag: dict = {}
    args: dict = {}

    # evidence phrases
    if "signed artifact" in t or "signed build" in t:
        frag.setdefault("evidence", []).append({"kind": "signed_artifact", "producer": "registry"})
    if "simulation" in t or "dry run" in t or "dry-run" in t or "simulated" in t:
        fidelity = "HIGH" if "high" in t or "full" in t else ("MEDIUM" if "medium" in t or "partial" in t else "HIGH")
        frag.setdefault("evidence", []).append({"kind": "simulation", "fidelity": fidelity, "producer": "planner"})
    if "verified backup" in t or "restorable backup" in t or "backup verified" in t:
        frag.setdefault("evidence", []).append({"kind": "verified_restorable_backup", "producer": "restore-checker"})

    # attestation phrases
    if "workload identity" in t or "workload-identity" in t or "attestation" in t:
        frag["attestation"] = {"type": "workload-identity", "evidence": "deadbeef",
                               "exp": "2026-07-12T15:00:00.000Z"}

    # approval phrases
    if "dual control" in t or "two approvers" in t or "dual-control" in t:
        frag.setdefault("approvals", []).append({"approver_policy": "dual_control", "approvers": "dual"})
    elif "approved by" in t or "single approver" in t or "manager approval" in t:
        frag.setdefault("approvals", []).append({"approver_policy": "single", "approvers": "single"})

    # boolean facts via keywords
    if "unbounded" in t or "no limit" in t or "without a where" in t:
        args["unbounded"] = True
    if "bulk" in t:
        args["bulk"] = True
    if ("public" in t) and ("sensitive" in t):
        args["public"] = True
        args["target_sensitive"] = True
    if "0.0.0.0/0" in t or "open to the internet" in t:
        args["cidr"] = "0.0.0.0/0"
        if "admin" in t:
            args["admin_port"] = True
    if "widen" in t:
        args["widening"] = True
    if "last replica" in t or "only replica" in t:
        args["last_replica"] = True
    if "self-grant" in t or "grant to itself" in t or "grant themselves" in t:
        args["grantee"] = "agent://sre/1"
    if "export" in t:
        args["export"] = True
        if "approved sink" in t or "sink approved" in t or "approved destination" in t:
            args["sink_approved"] = True

    # numeric affected count
    m = _NUM_ROWS.search(text)
    if m:
        args["affected_count"] = m.group(1).replace(",", "")

    if args:
        frag["args"] = args
    return frag


def realistic_spec(ctx: Context, surviving_ids) -> adapter.RequestSpec:
    keep = set(surviving_ids)
    frags = [reference_fragment(u.text) for u in ctx.units if u.id in keep]
    return _merge(ctx.base, frags)


def extract_and_eval(ctx: Context, surviving_ids, signed_policy, *, mode=ORACLE) -> dict:
    spec = oracle_spec(ctx, surviving_ids) if mode == ORACLE else realistic_spec(ctx, surviving_ids)
    return adapter.evaluate(spec, signed_policy)
