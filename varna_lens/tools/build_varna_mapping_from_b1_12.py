#!/usr/bin/env python3
"""Deterministic adapter: B1.12 frozen varṇa mapping  →  PSE Varṇa-Tool runtime mapping.

WHAT THIS DOES (mapping-source replacement only)
------------------------------------------------
The PSE Varṇa Tool (varna_lens/) historically read its varṇa→drive payload from
`lexicon_authoritative.json`. The Symbol-U concern bridge already reads the B1.12 frozen
mapping `frozen/varna_native_stage1_merged_v3.json`. This adapter makes that SAME B1.12
frozen artifact the single authoritative varṇa→drive source for the renderer/reflection
lineage too, so both PSE lineages share one mapping substrate.

It swaps ONLY the drive payload (the binding/liberating vṛtti glosses). It does NOT change
the parser, the acoustic rules, the trajectory/renderer, abstention, honesty, or confidence
logic. Display/imagery scaffolding that is NOT a varṇa→drive mapping and is NOT present in
B1.12 (the IAST display label, devanāgarī glyph, varga, and the renderer's `expanded_properties`
elemental-imagery bank) is PRESERVED unchanged from the prior presentation config — it is
renderer presentation data, not a drive mapping, and altering or dropping it would either
break the renderer or invent fields B1.12 does not supply.

INCLUDED FROM B1.12  : frozen varṇa keys, binding_vritti, liberating_vritti, pole polarity
                       provenance, activation_scope, category, aliases, devanāgarī, iast,
                       source version + sha256.
EXCLUDED FROM B1.12  : (none of these exist in the mapping file, and the adapter asserts it)
                       BSR/0–100 resonance scores, relationship-type labels, opposition/
                       implication/consequence/no_relationship evaluator judgments, evaluator
                       prose, cross-model agreement, per-word verdicts, evaluator-derived
                       confidence, any LLM-generated interpretation.

DISCIPLINE
----------
* Deterministic (sorted keys, stable formatting). Two runs → byte-identical output.
* No LLM call, no network, no randomness, no authored semantic interpretation.
* Preserves all source drive values EXACTLY (verbatim strings from the frozen file).
* FAILS EXPLICITLY on: missing/duplicate/conflicting join, null pole, malformed row, or any
  evaluator/scoring field detected in the source.
* Logs provenance (source path + sha256) into every emitted artifact.

Usage:
    python varna_lens/tools/build_varna_mapping_from_b1_12.py            # write artifacts
    python varna_lens/tools/build_varna_mapping_from_b1_12.py --check    # build in-memory, do not write
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent                 # varna_lens/tools
_VL = _HERE.parent                                      # varna_lens
_REPO = _VL.parent                                      # repo root
_MAP_DIR = _VL / "mapping"

B1_12_SOURCE = (_REPO / "experiments" / "primitive_sequence_recovery" / "frozen"
                / "varna_native_stage1_merged_v3.json")
PSE_PRESENTATION = _VL / "lexicon_authoritative.json"   # scaffolding source (iast/deva/varga/expanded_properties)

OUT_CANONICAL = _MAP_DIR / "varna_mapping_b1_12_canonical.json"   # task's canonical contract
OUT_LEXICON = _VL / "lexicon_b1_12.json"                          # engine-shaped runtime file
OUT_PROVENANCE = _MAP_DIR / "PROVENANCE_B1_12_MAPPING.json"

GENERATOR_VERSION = "1.0.0"

# Fields that must NEVER enter the runtime mapping (evaluator/scoring material). The adapter refuses
# to run if any source field name matches — a hard guard even though the frozen mapping has none.
FORBIDDEN_FIELD_TOKENS = (
    "bsr", "resonance", "score", "verdict", "agreement", "evaluator", "relationship_type",
    "no_relationship", "implication", "opposition", "consequence", "eval_", "judge", "per_word",
)
# These evaluator tokens may legitimately appear inside prose provenance notes, so we only scan KEYS.


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scan_forbidden_keys(obj, path=""):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if any(tok in kl for tok in FORBIDDEN_FIELD_TOKENS):
                hits.append(f"{path}/{k}")
            hits += _scan_forbidden_keys(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += _scan_forbidden_keys(v, f"{path}[{i}]")
    return hits


def _build_v3_indices(v3_rows):
    """Return lookup indices + duplicate detection for robust, deterministic joining."""
    by_deva, by_srckey, by_alias, by_canon = {}, {}, {}, {}
    for r in v3_rows:
        canon = r["canonical_parser_unit"]
        by_canon.setdefault(canon, []).append(r)
        deva = r.get("devanagari")
        if deva:
            by_deva.setdefault(deva, []).append(r)
        sk = r.get("source_key")
        if sk:
            by_srckey.setdefault(sk, []).append(r)
        for a in (r.get("aliases") or []):
            by_alias.setdefault(a, []).append(r)
    return {"deva": by_deva, "srckey": by_srckey, "alias": by_alias, "canon": by_canon}


def _resolve(pse_key, pse_entry, idx):
    """Resolve one PSE varṇa key to exactly one B1.12 row, deterministically.

    Priority: devanāgarī glyph → source_key → PSE key as v3 canonical/alias. Every method that
    yields a row must agree on the same canonical_parser_unit, or we FAIL (conflict surfaced).
    Returns (row, join_via) or (None, None) when the source has no mapping for this key.
    """
    candidates = []  # (method, row)
    pse_deva = pse_entry.get("deva")
    if pse_deva and pse_deva in idx["deva"]:
        for r in idx["deva"][pse_deva]:
            candidates.append(("devanagari", r))
    if pse_key in idx["srckey"]:
        for r in idx["srckey"][pse_key]:
            candidates.append(("source_key", r))
    if pse_key in idx["canon"]:
        for r in idx["canon"][pse_key]:
            candidates.append(("canonical_parser_unit", r))
    if pse_key in idx["alias"]:
        for r in idx["alias"][pse_key]:
            candidates.append(("alias", r))

    if not candidates:
        return None, None
    canon_set = {r["canonical_parser_unit"] for _, r in candidates}
    if len(canon_set) != 1:
        raise SystemExit(
            f"[FATAL] conflicting B1.12 join for PSE key {pse_key!r}: resolves to multiple rows "
            f"{sorted(canon_set)} via {[m for m, _ in candidates]}. Refusing to guess.")
    # Deterministic pick: first method in fixed priority order.
    order = {"devanagari": 0, "source_key": 1, "canonical_parser_unit": 2, "alias": 3}
    method, row = sorted(candidates, key=lambda mr: order[mr[0]])[0]
    return row, method


def _mechanical_metadata(row, join_via):
    """Only mechanical fields required to interpret the mapping + provenance. NO evaluator material."""
    return {
        "v3_canonical_parser_unit": row["canonical_parser_unit"],
        "v3_source_key": row.get("source_key"),
        "v3_iast": row.get("iast"),
        "devanagari": row.get("devanagari"),
        "category": row.get("category"),
        "activation_scope": row.get("activation_scope"),
        "binding_pole_provenance": row.get("binding_pole_provenance"),
        "liberating_pole_provenance": row.get("liberating_pole_provenance"),
        "parser_reachable": row.get("parser_reachable"),
        "aliases": row.get("aliases"),
        "source_artifact": row.get("source_artifact"),
        "join_via": join_via,
    }


def build():
    if not B1_12_SOURCE.exists():
        raise SystemExit(f"[FATAL] B1.12 source not found: {B1_12_SOURCE}")
    if not PSE_PRESENTATION.exists():
        raise SystemExit(f"[FATAL] PSE presentation scaffolding not found: {PSE_PRESENTATION}")

    v3 = json.loads(B1_12_SOURCE.read_text(encoding="utf-8"))
    pres = json.loads(PSE_PRESENTATION.read_text(encoding="utf-8"))

    # Guard: refuse to proceed if the source carries any evaluator/scoring field.
    forbidden = _scan_forbidden_keys(v3)
    if forbidden:
        raise SystemExit(f"[FATAL] B1.12 source carries evaluator/scoring fields; refusing to import: {forbidden}")

    idx = _build_v3_indices(v3["rows"])
    src_sha = sha256_of(B1_12_SOURCE)

    canonical_mappings = {}
    lexicon_cons, lexicon_vow = {}, {}
    coverage = {"consonants": {}, "vowels": {}}
    unmapped = {}

    def handle(kind, pse_key, pse_entry):
        row, join_via = _resolve(pse_key, pse_entry, idx)
        cov = coverage["consonants" if kind == "C" else "vowels"]
        if row is None:
            unmapped[pse_key] = {
                "kind": "consonant" if kind == "C" else "vowel",
                "disposition": "EXPLICIT_ABSTENTION",
                "reason": v3.get("ksha_note") if pse_key == "ksha"
                else "no varṇa→drive mapping exists in the B1.12 frozen source for this key",
                "runtime_effect": "engine emits '(no lexicon entry)'; varṇa contributes nothing "
                                  "to the essence — surfaced, never silently back-filled",
            }
            cov[pse_key] = "UNMAPPED"
            return
        b = row.get("binding_vritti")
        l = row.get("liberating_vritti")
        if not b or not l:
            raise SystemExit(f"[FATAL] null pole for PSE key {pse_key!r} (v3 {row['canonical_parser_unit']!r}): "
                             f"binding={bool(b)} liberating={bool(l)}. Refusing to emit a malformed mapping.")
        # --- canonical contract entry (drives + mechanical metadata + provenance only) ---
        canonical_mappings[pse_key] = {
            "binding_drive": b,           # verbatim from B1.12
            "liberating_drive": l,        # verbatim from B1.12
            "mechanical_metadata": _mechanical_metadata(row, join_via),
        }
        cov[pse_key] = f"MAPPED (via {join_via} → {row['canonical_parser_unit']})"
        # --- engine-shaped entry: drives from v3, presentation scaffolding preserved verbatim ---
        entry = dict(pse_entry)             # preserve iast/deva/varga/expanded_properties EXACTLY
        entry["binding_state"] = b          # REPLACED drive payload (string pole; engine handles strings)
        entry["liberating_state"] = l       # REPLACED drive payload
        entry["_drive_source"] = "b1_12:varna_native_stage1_merged_v3"
        entry["_drive_v3_unit"] = row["canonical_parser_unit"]
        if kind == "C":
            lexicon_cons[pse_key] = entry
        else:
            lexicon_vow[pse_key] = entry

    for k in sorted(pres["consonants"]):
        handle("C", k, pres["consonants"][k])
    for k in sorted(pres["vowels"]):
        handle("V", k, pres["vowels"][k])

    n_cons_mapped = sum(1 for v in coverage["consonants"].values() if v != "UNMAPPED")
    n_vow_mapped = sum(1 for v in coverage["vowels"].values() if v != "UNMAPPED")

    canonical = {
        "schema_version": "1.0",
        "_purpose": "Single authoritative varṇa→drive mapping for the PSE Varṇa Tool, generated "
                    "deterministically from the B1.12 frozen mapping. Contains ONLY drive payload + "
                    "mechanical metadata + provenance. NO evaluator/scoring material.",
        "source": {
            "artifact": str(B1_12_SOURCE.relative_to(_REPO)),
            "artifact_type": v3.get("artifact_type"),
            "schema_version": v3.get("schema_version"),
            "sha256": src_sha,
            "operator_ruling": v3.get("operator_ruling"),
        },
        "generator": {
            "script": str(Path(__file__).relative_to(_REPO)),
            "version": GENERATOR_VERSION,
            "deterministic": True,
            "llm_used": False,
            "join_priority": ["devanagari", "source_key", "canonical_parser_unit", "alias"],
        },
        "excluded_from_source": [
            "BSR/0-100 resonance scores", "relationship-type labels",
            "opposition/implication/consequence/no_relationship evaluator judgments",
            "evaluator prose", "cross-model agreement", "per-word verdicts",
            "evaluator-derived confidence", "any LLM-generated interpretation",
        ],
        "coverage_summary": {
            "consonants_mapped": n_cons_mapped, "consonants_total": len(pres["consonants"]),
            "vowels_mapped": n_vow_mapped, "vowels_total": len(pres["vowels"]),
            "unmapped_keys": sorted(unmapped),
        },
        "mappings": dict(sorted(canonical_mappings.items())),
        "unmapped": dict(sorted(unmapped.items())),
    }

    lexicon = {
        "_source": "GENERATED — do not hand-edit. Rebuild via varna_lens/tools/build_varna_mapping_from_b1_12.py",
        "_mapping_source": {
            "drives_from": str(B1_12_SOURCE.relative_to(_REPO)),
            "drives_sha256": src_sha,
            "note": "binding_state/liberating_state are the B1.12 binding_vritti/liberating_vritti "
                    "(verbatim). This is the authoritative varṇa→drive mapping.",
        },
        "_scaffolding_source": {
            "presentation_from": str(PSE_PRESENTATION.relative_to(_REPO)),
            "fields": ["iast", "deva", "varga", "expanded_properties", "contextual_usage"],
            "note": "Display label, devanāgarī, varga, and elemental-imagery bank are PRESERVED "
                    "presentation scaffolding — NOT a varṇa→drive mapping and NOT present in B1.12. "
                    "No old drive payload is retained.",
        },
        "_legend": pres.get("_legend"),
        "_romanization": pres.get("_romanization"),
        "_romanization_note": pres.get("_romanization_note"),
        "_expanded_properties_note": pres.get("_expanded_properties_note"),
        "consonants": dict(sorted(lexicon_cons.items())),
        "vowels": dict(sorted(lexicon_vow.items())),
        "contextual_usage": pres.get("contextual_usage"),
    }

    return canonical, lexicon, {
        "schema_version": "1.0",
        "generator_version": GENERATOR_VERSION,
        "source": {"artifact": str(B1_12_SOURCE.relative_to(_REPO)), "sha256": src_sha,
                   "schema_version": v3.get("schema_version")},
        "presentation_scaffolding": {"artifact": str(PSE_PRESENTATION.relative_to(_REPO)),
                                     "sha256": sha256_of(PSE_PRESENTATION)},
        "coverage": coverage,
        "unmapped": dict(sorted(unmapped.items())),
        "counts": {"consonants_mapped": n_cons_mapped, "consonants_total": len(pres["consonants"]),
                   "vowels_mapped": n_vow_mapped, "vowels_total": len(pres["vowels"])},
    }


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="build in-memory and validate; do not write files")
    args = ap.parse_args(argv)

    canonical, lexicon, provenance = build()

    # Post-build guard: emitted artifacts must contain no evaluator/scoring field either.
    for name, art in (("canonical", canonical), ("lexicon", lexicon)):
        bad = _scan_forbidden_keys(art)
        if bad:
            raise SystemExit(f"[FATAL] emitted {name} artifact carries forbidden fields: {bad}")

    cov = provenance["counts"]
    print(f"B1.12 → PSE mapping adapter (v{GENERATOR_VERSION})")
    print(f"  source: {B1_12_SOURCE.relative_to(_REPO)}  sha256={provenance['source']['sha256'][:16]}…")
    print(f"  consonants mapped: {cov['consonants_mapped']}/{cov['consonants_total']}")
    print(f"  vowels mapped:     {cov['vowels_mapped']}/{cov['vowels_total']}")
    print(f"  unmapped (explicit abstention): {sorted(provenance['unmapped']) or 'none'}")

    if args.check:
        print("  --check: not writing files.")
        return 0

    _MAP_DIR.mkdir(parents=True, exist_ok=True)
    OUT_CANONICAL.write_text(_dump(canonical), encoding="utf-8")
    OUT_LEXICON.write_text(_dump(lexicon), encoding="utf-8")
    # provenance records hashes of the two generated files too (computed after writing).
    provenance["generated"] = {
        "canonical": {"path": str(OUT_CANONICAL.relative_to(_REPO)), "sha256": sha256_of(OUT_CANONICAL)},
        "lexicon": {"path": str(OUT_LEXICON.relative_to(_REPO)), "sha256": sha256_of(OUT_LEXICON)},
    }
    OUT_PROVENANCE.write_text(_dump(provenance), encoding="utf-8")
    print(f"  wrote: {OUT_CANONICAL.relative_to(_REPO)}")
    print(f"  wrote: {OUT_LEXICON.relative_to(_REPO)}")
    print(f"  wrote: {OUT_PROVENANCE.relative_to(_REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
