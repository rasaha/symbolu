#!/usr/bin/env python3
"""Canonical Symbolic Profile — the single deterministic runtime contract for PSE symbolic state.

    concern / canonical concept
            ↓
    existing parser + conjunct normalization   (varna_lens tokenizer, unchanged)
            ↓
    authoritative B1.12 mapping                 (active lexicon; the only drive source)
            ↓
    CANONICAL SYMBOLIC PROFILE                  (this module)
            ├── reflection renderer
            ├── Arm D / symbolic conditioning
            ├── future coherence evaluation
            └── serialization / audit

The profile carries ONLY deterministic symbolic state derived from the resolved concept, the parser,
the authoritative B1.12 varṇa mappings, the existing deterministic trajectory logic, and provenance.
It contains NO renderer wording, NO scores, NO relationship/evaluator judgments, NO advice, NO
LLM-generated fields, NO old Sanskrit-label bridge output, and NO claim that a varṇa "means/reveals/
proves" anything about a person.

Identity is separated from display text: every pole carries an opaque, mechanically-derived
`source_mapping_id` (e.g. `varna.ka.binding`) that is IDENTITY ONLY; the `text` is the verbatim B1.12
source string. No new semantic categories are introduced.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import varna_lens as V
import pse_renderer as _R          # deterministic trajectory logic (reused, not duplicated)

SCHEMA_VERSION = "1.0"
PROFILE_BUILDER_VERSION = "1.0.0"
PARSER_VERSION = "varna_lens.tokenizer+conjunct_normalization.v1"

# Fields that must never appear in a runtime profile (evaluator/scoring/interpretation leakage).
FORBIDDEN_KEYS = (
    "score", "resonance", "bsr", "relationship", "verdict", "agreement", "evaluator", "confidence_score",
    "diagnosis", "personality", "advice", "coaching", "response", "summary_llm", "means", "reveals",
    "proves", "bridge_phrase",
)


# ---------------------------------------------------------------------------------------------------
def _mapping_provenance() -> Dict[str, str]:
    """Provenance for the ACTIVE B1.12 mapping, read from the active lexicon's own record."""
    src = (V.LEX.get("_mapping_source") or {}) if isinstance(V.LEX, dict) else {}
    return {
        "mapping_source": src.get("drives_from", "experiments/primitive_sequence_recovery/frozen/"
                                                 "varna_native_stage1_merged_v3.json"),
        "mapping_sha256": src.get("drives_sha256", ""),
        "active_lexicon": V.active_mapping_path().name,
        "parser_version": PARSER_VERSION,
        "profile_builder_version": PROFILE_BUILDER_VERSION,
    }


def _iast_deva(key: str, is_vowel: bool) -> Tuple[str, str]:
    table = V.LEX["vowels"] if is_vowel else V.LEX["consonants"]
    e = table.get(key) or {}
    return e.get("iast", key), e.get("deva", "")


def _mapping_id(key: str, pole: str) -> str:
    """Opaque, stable identity for a (varṇa, pole). Identity only — no semantics smuggled in."""
    return f"varna.{key}.{pole}"


@dataclass(frozen=True)
class SymbolicProfile:
    """Immutable, serializable, versioned canonical symbolic state. Build via build_symbolic_profile()."""
    schema_version: str
    profile_id: str
    input: Dict[str, Any]
    decomposition: Dict[str, Any]
    poles: Dict[str, List[Dict[str, str]]]
    trajectory: Dict[str, Any]
    provenance: Dict[str, str]
    status: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        # Deterministic ordering; deep structures are already plain JSON types.
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "input": self.input,
            "decomposition": self.decomposition,
            "poles": self.poles,
            "trajectory": self.trajectory,
            "provenance": self.provenance,
            "status": self.status,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=False)


def _forbidden_scan(obj, path="") -> List[str]:
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            # `trajectory.valence` is a legitimate structural field; guard on exact forbidden tokens only.
            if any(tok == kl or (tok in kl and tok not in ("means",)) for tok in FORBIDDEN_KEYS):
                hits.append(f"{path}/{k}")
            hits += _forbidden_scan(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += _forbidden_scan(v, f"{path}[{i}]")
    return hits


def assert_no_evaluator_fields(profile: SymbolicProfile) -> None:
    """Reject any profile carrying score/relationship/evaluator/verdict field NAMES. Text VALUES that
    happen to contain an English word like 'means' are allowed (they are verbatim B1.12 source prose)."""
    hits = _forbidden_scan({k: v for k, v in profile.to_dict().items() if k != "poles" and k != "decomposition"})
    # poles/decomposition text values are verbatim source; scan their KEYS only.
    for section in ("poles", "decomposition"):
        for k in _keys_only(profile.to_dict()[section]):
            if k.lower() in FORBIDDEN_KEYS:
                hits.append(f"/{section} key {k}")
    if hits:
        raise ValueError(f"profile carries forbidden evaluator/scoring/interpretation fields: {hits}")


def _keys_only(obj) -> List[str]:
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append(str(k)); out += _keys_only(v)
    elif isinstance(obj, list):
        for v in obj:
            out += _keys_only(v)
    return out


# ---------------------------------------------------------------------------------------------------
def build_symbolic_profile(*, source_text: str, concern_id: Optional[str] = None,
                           canonical_concept: Optional[str] = None, by: str = "hybrid") -> SymbolicProfile:
    """Deterministically build the canonical Symbolic Profile for a resolved concept / normalized input.

    Reuses the existing parser + conjunct normalization + active B1.12 mapping + deterministic trajectory
    logic. Never duplicates parser/mapping logic, never reads the old lexicon, never invents a mapping,
    and surfaces abstentions explicitly.
    """
    word = canonical_concept or source_text
    kw = {"hybrid": {"hybrid": True}, "sound": {}, "spelling": {"roman": True}}.get(by, {"hybrid": True})
    d, src, warn = V.analyze(word, model="op", **kw)

    tokens: List[Dict[str, Any]] = []
    varna_keys: List[str] = []
    binding: List[Dict[str, str]] = []
    liberating: List[Dict[str, str]] = []
    abstentions: List[Dict[str, Any]] = []

    if d is not None:
        for i, unit in enumerate(d["sequence"]):
            typ, key, surf = unit["type"], unit["key"], unit.get("surface", "")
            is_vowel = typ == "V"
            table = V.LEX["vowels"] if is_vowel else V.LEX["consonants"]
            mapped = key in table
            iast, deva = _iast_deva(key, is_vowel)
            status = "vowel" if (is_vowel and mapped) else ("mapped" if mapped else "unmapped")
            tokens.append({"index": i, "source_span": surf, "type": typ, "varna_key": key,
                           "iast": iast if mapped else key, "devanagari": deva,
                           "mapping_status": status})
            varna_keys.append(key)
            if not mapped:
                abstentions.append({"code": "UNMAPPED_VARNA", "index": i, "varna_key": key,
                                    "note": "no active B1.12 mapping for this varṇa; contributes nothing"})
            elif not is_vowel:
                ent = table[key]
                binding.append({"varna_key": key, "text": ent["binding_state"],
                                "source_mapping_id": _mapping_id(key, "binding")})
                liberating.append({"varna_key": key, "text": ent["liberating_state"],
                                   "source_mapping_id": _mapping_id(key, "liberating")})

    # Reuse the single deterministic trajectory computation (no duplication; no re-analyze).
    traj = _R.trajectory(word, by, _analysis=(d, src)) if d is not None else None
    if traj is not None:
        trajectory = {
            "roles": list(traj["trajectory"]),
            "valence": traj["layer1"]["valence"],
            "controlling_element": traj["controlling_element"],
            "tone": traj["tone"],
            "tone_parts": traj["tone_parts"],
            # deterministic engine essence (verbatim symbolic representation; NOT renderer wording).
            "chain": traj["layer1"]["chain"],
            "interaction": traj["layer1"]["interaction"],
            "whole_word_essence": traj["layer1"]["essence"],
            # per-beat STRUCTURAL state (role/sign/transform/element + verbatim source gloss). No wording.
            "stages": [{"varna_key": s["key"], "role": s["role"], "sign": s["sign"],
                        "transform": s["transform"], "element": s["element"], "text": s["gloss"]}
                       for s in traj["stages"]],
        }
    else:
        trajectory = {"roles": [], "valence": "mixed", "controlling_element": None, "tone": None,
                      "tone_parts": {}, "chain": "", "interaction": "(none)", "whole_word_essence": None,
                      "stages": []}

    n_mapped_cons = len(binding)
    complete = n_mapped_cons > 0
    if not complete:
        abstentions.append({"code": "NO_MAPPED_VARNA", "note": "no mapped consonant varṇa; the symbolic "
                            "layer abstains rather than fabricating"})

    provenance = _mapping_provenance()
    decomposition = {"normalized_input": word, "varna_keys": varna_keys, "tokens": tokens}
    input_section = {"concern_id": concern_id, "canonical_concept": canonical_concept,
                     "source_text": source_text, "reading_mode": by}
    status = {"complete": complete, "abstentions": abstentions, "warnings": list(warn or [])}

    profile_id = _profile_id(SCHEMA_VERSION, word, varna_keys, provenance["mapping_sha256"])
    profile = SymbolicProfile(
        schema_version=SCHEMA_VERSION, profile_id=profile_id, input=input_section,
        decomposition=decomposition,
        poles={"binding": binding, "liberating": liberating},
        trajectory=trajectory, provenance=provenance, status=status)
    assert_no_evaluator_fields(profile)
    return profile


def _profile_id(schema_version, word, varna_keys, mapping_sha) -> str:
    payload = json.dumps([schema_version, word, varna_keys, mapping_sha], ensure_ascii=False,
                         sort_keys=True)
    return "sp_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


if __name__ == "__main__":
    import sys
    for w in (sys.argv[1:] or ["compassion", "kṣamā", "śānti"]):
        p = build_symbolic_profile(source_text=w)
        print(f"\n=== {w} → {p.profile_id} ===")
        print(f"  varṇa_keys: {p.decomposition['varna_keys']}")
        print(f"  binding[0]: {p.poles['binding'][0]['source_mapping_id']} = {p.poles['binding'][0]['text'][:60]}")
        print(f"  trajectory: {p.trajectory['roles']} · elem={p.trajectory['controlling_element']} · tone={p.trajectory['tone']}")
        print(f"  status: complete={p.status['complete']} abstentions={len(p.status['abstentions'])}")
        print(f"  provenance: {p.provenance['active_lexicon']} sha={p.provenance['mapping_sha256'][:12]}…")
