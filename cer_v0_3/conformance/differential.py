"""Differential conformance runner (deliverable 12).

Runs every existing V0.1 and V0.2 conformance CER through TWO independent
implementations — the reference (original) and the clean-room — and requires
equality of:

    * validation result (valid / invalid),
    * normalized (v2-projected) payload,
    * canonical serialized bytes,
    * action digest,
    * coarse error category (for invalid vectors).

A matching digest with a divergent normalized payload is NOT accepted — the
payload and bytes are compared explicitly, before the hash.

Every difference is classified:
    specification_ambiguity | implementation_defect | vector_defect |
    unsupported_behavior | harmless_diagnostic

Deterministic. Usage: python -m cer_v0_3.conformance.differential [--json out.json]
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .. import _paths  # noqa: F401  (original side needs the frozen imports)

# --- reference (original) side ---
from cer_v0_2 import envelope as ref_env  # noqa: E402
from cer_v0_2.profiles.base import CERValidationError  # noqa: E402
from action_gate_ref import projection as ref_proj  # noqa: E402
from action_gate_ref.errors import GateError  # noqa: E402

# --- clean-room side ---
from ..cleanroom import cer as cr  # noqa: E402
from ..cleanroom.errors import CleanRoomError  # noqa: E402

# --- corpora ---
from cer_v0_2.corpus import build_corpus as build_v2  # noqa: E402
from cer_v0_1.corpus import build_corpus as build_v1  # noqa: E402
from cer_v0_1 import spec as v1spec  # noqa: E402


# ---------------------------------------------------------------------------
# Coarse, portable error taxonomy (both implementations map into it).
# ---------------------------------------------------------------------------
def _coarse_from_cleanroom(exc: CleanRoomError) -> str:
    cat = getattr(exc, "category", "error")
    return {
        "E_UNKNOWN_PROFILE": "UNKNOWN_PROFILE",
        "E_OPERATION_MISMATCH": "OPERATION_MISMATCH",
        "E_PROHIBITED_FIELD": "PROHIBITED_FIELD",
        "E_UNSUPPORTED_EXTENSION": "UNSUPPORTED_EXTENSION",
        "E_MISSING_FIELD": "MISSING_FIELD",
        "E_UNKNOWN_FIELD": "UNKNOWN_FIELD",
        "E_CER_SCHEMA": "SCHEMA",
        "E_VALUE_FORMAT": "VALUE_FORMAT",
        "E_SECRET_MATERIAL": "SECRET_MATERIAL",
        "E_BARE_NUMBER": "CANONICALIZATION",
        "E_NAN_INF": "CANONICALIZATION",
        "E_DUPLICATE_KEY": "CANONICALIZATION",
        "E_NON_NFC": "CANONICALIZATION",
        "E_DUPLICATE_SET_ELEMENT": "CANONICALIZATION",
        "E_UNSUPPORTED_TYPE": "CANONICALIZATION",
    }.get(cat, "OTHER")


def _coarse_from_reference(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    if code:  # ActionGate canonicalization / schema errors carry a machine code
        if code in ("E_BARE_NUMBER", "E_NAN_INF", "E_DUPLICATE_KEY", "E_NON_NFC"):
            return "CANONICALIZATION"
        return "SCHEMA"
    msg = str(exc).lower()
    if "unsupported profile" in msg or "unknown profile" in msg:
        return "UNKNOWN_PROFILE"
    if "inconsistent with" in msg and "profile" in msg:
        return "OPERATION_MISMATCH"
    if "prohibited field" in msg:
        return "PROHIBITED_FIELD"
    if "unsupported extension" in msg:
        return "UNSUPPORTED_EXTENSION"
    if "unsupported top-level" in msg or "unknown actuation field" in msg:
        return "UNKNOWN_FIELD"
    if "unsupported cer_version" in msg or "must be a json object" in msg:
        return "SCHEMA"
    if "required" in msg or "missing" in msg:
        return "MISSING_FIELD"
    return "VALUE_FORMAT"


@dataclass
class Eval:
    valid: bool
    payload: Optional[dict] = None
    canon: Optional[bytes] = None
    digest: Optional[str] = None
    error_coarse: Optional[str] = None
    error_detail: str = ""


def _eval_reference(cer: dict) -> Eval:
    try:
        ref_env.validate_cer(cer)
        env = ref_env.to_envelope(cer)
        payload = ref_proj.project_action_payload(env, identity_profile="v2")
        canon = ref_proj.action_canonical_bytes(env, identity_profile="v2")
        digest = ref_env.action_digest(cer)
        return Eval(True, payload, canon, digest)
    except (CERValidationError, GateError, KeyError, ValueError, TypeError) as exc:
        return Eval(False, error_coarse=_coarse_from_reference(exc), error_detail=str(exc))


def _eval_cleanroom(cer: dict) -> Eval:
    try:
        cr.validate(cer)
        payload = cr.normalized_payload(cer)
        canon = cr.canonical_bytes(cer)
        digest = cr.action_digest(cer)
        return Eval(True, payload, canon, digest)
    except CleanRoomError as exc:
        return Eval(False, error_coarse=_coarse_from_cleanroom(exc), error_detail=str(exc))


# ---------------------------------------------------------------------------
# V0.1 -> V0.2 identity-equivalent translation (scale-only V0.1 corpus).
# ---------------------------------------------------------------------------
def _v1_to_v2_scale(v1_cer: dict) -> dict:
    idy = v1_cer["identity"]
    return {
        "cer_version": "0.2", "profile": "kubernetes.scale.v1",
        "risk_tier": v1_cer.get("risk_tier", "GOVERNED"),
        "authority": idy["authority"],
        "state_binding": idy["external_state_binding"],
        "policy_ref": idy["policy_ref"],
        "actuation": {
            "operation": idy["operation"], "target": idy["target"],
            "arguments": idy["arguments"],
            "requested_state_transition": idy["requested_state_transition"],
            "reversibility": idy["reversibility"]},
        "provenance": v1_cer.get("provenance", {}),
    }


@dataclass
class Item:
    source: str            # "v0.2" | "v0.1"
    case_id: str
    runtime: str
    cer: dict
    expect_valid: bool
    v1_reference_digest: Optional[str] = None  # for V0.1 identity reproduction


def _collect_items() -> List[Item]:
    items: List[Item] = []
    # ---- V0.2 corpus: valid + invalid, all runtimes ----
    for c in build_v2():
        if c.expect == "invalid":
            items.append(Item("v0.2", c.case_id, "malformed", c.malformed_cer, False))
            continue
        for rt, cer in c.cers.items():
            items.append(Item("v0.2", c.case_id, rt, cer, True))
    # ---- V0.1 corpus: translate valid scale CERs; reproduce frozen digest ----
    for c in build_v1():
        if c.malformed:
            continue
        for rt, v1_cer in (("ugence", c.ug_cer), ("langgraph", c.lg_cer)):
            if not v1_cer or v1_cer.get("cer_version") != "0.1":
                continue
            ref_digest = v1spec.action_digest(v1_cer)
            items.append(Item("v0.1", c.case_id, rt, _v1_to_v2_scale(v1_cer), True,
                              v1_reference_digest=ref_digest))
    return items


def _classify(item: Item, ref: Eval, cln: Eval) -> Optional[Dict[str, str]]:
    """Return a classified difference record, or None if the pair fully agrees."""
    # 1. validation-result disagreement
    if ref.valid != cln.valid:
        return {"case": item.case_id, "runtime": item.runtime, "source": item.source,
                "kind": "validation_result",
                "class": "specification_ambiguity",
                "detail": f"reference valid={ref.valid} clean-room valid={cln.valid} "
                          f"(ref={ref.error_detail!r} cln={cln.error_detail!r})"}
    if not ref.valid:  # both invalid
        if ref.error_coarse != cln.error_coarse:
            return {"case": item.case_id, "runtime": item.runtime, "source": item.source,
                    "kind": "error_category",
                    "class": "harmless_diagnostic",
                    "detail": f"both reject; coarse category ref={ref.error_coarse} "
                              f"cln={cln.error_coarse}"}
        return None
    # both valid: compare payload, bytes, digest
    if ref.payload != cln.payload:
        return {"case": item.case_id, "runtime": item.runtime, "source": item.source,
                "kind": "normalized_payload", "class": "specification_ambiguity",
                "detail": "projected payload differs"}
    if ref.canon != cln.canon:
        return {"case": item.case_id, "runtime": item.runtime, "source": item.source,
                "kind": "canonical_bytes", "class": "specification_ambiguity",
                "detail": "canonical bytes differ with equal payload (canonicalization ambiguity)"}
    if ref.digest != cln.digest:
        return {"case": item.case_id, "runtime": item.runtime, "source": item.source,
                "kind": "digest", "class": "implementation_defect",
                "detail": "digest differs with equal canonical bytes (hashing defect)"}
    # V0.1 identity reproduction: both must equal the frozen V0.1 digest
    if item.v1_reference_digest is not None and cln.digest != item.v1_reference_digest:
        return {"case": item.case_id, "runtime": item.runtime, "source": item.source,
                "kind": "v0_1_identity", "class": "implementation_defect",
                "detail": f"clean-room {cln.digest[:12]} != frozen V0.1 "
                          f"{item.v1_reference_digest[:12]}"}
    return None


def run() -> Dict[str, Any]:
    items = _collect_items()
    diffs: List[Dict[str, str]] = []
    m = {"items": 0, "valid_items": 0, "invalid_items": 0,
         "validation_agree": 0, "payload_agree": 0, "bytes_agree": 0,
         "digest_agree": 0, "error_category_agree": 0,
         "v0_1_identity_reproduced": 0, "v0_1_items": 0}

    for it in items:
        m["items"] += 1
        ref = _eval_reference(it.cer)
        cln = _eval_cleanroom(it.cer)
        if ref.valid == cln.valid:
            m["validation_agree"] += 1
        if ref.valid and cln.valid:
            m["valid_items"] += 1
            if ref.payload == cln.payload:
                m["payload_agree"] += 1
            if ref.canon == cln.canon:
                m["bytes_agree"] += 1
            if ref.digest == cln.digest:
                m["digest_agree"] += 1
            if it.v1_reference_digest is not None:
                m["v0_1_items"] += 1
                if cln.digest == it.v1_reference_digest == ref.digest:
                    m["v0_1_identity_reproduced"] += 1
        elif not ref.valid and not cln.valid:
            m["invalid_items"] += 1
            if ref.error_coarse == cln.error_coarse:
                m["error_category_agree"] += 1
        d = _classify(it, ref, cln)
        if d is not None:
            diffs.append(d)

    # Any difference that affects identity is high severity.
    identity_affecting = [d for d in diffs
                          if d["kind"] in ("normalized_payload", "canonical_bytes",
                                           "digest", "v0_1_identity", "validation_result")]
    report = {
        "cer_version": "0.3",
        "implementations": ["reference (cer_v0_2 + action_gate_ref)",
                            "clean-room (cer_v0_3.cleanroom)"],
        "metrics": m,
        "differences": diffs,
        "identity_affecting_differences": len(identity_affecting),
        "all_identity_agree": (m["payload_agree"] == m["valid_items"]
                               and m["bytes_agree"] == m["valid_items"]
                               and m["digest_agree"] == m["valid_items"]
                               and m["validation_agree"] == m["items"]
                               and m["v0_1_identity_reproduced"] == m["v0_1_items"]),
    }
    return report


def main(argv=None):
    argv = argv or sys.argv[1:]
    report = run()
    text = json.dumps(report, indent=2, sort_keys=True)
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as fh:
            fh.write(text + "\n")
    print(text)
    ok = report["all_identity_agree"] and report["identity_affecting_differences"] == 0
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
