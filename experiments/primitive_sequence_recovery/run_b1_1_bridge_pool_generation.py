#!/usr/bin/env python3
"""B1.1 bridge-pool generation (DRAFT, FALLBACK_QUALIFIED) — deterministic transform of the resolved
binding/liberating lexicon into 68 bridge phrases (binding_bridge + liberating_bridge per varṇa).

No model, no network, no generation/scoring/judge. Generated from the B1.1 experimental JSON ONLY; never
reads or modifies source lexicons in varna_lens/. Bridge phrases are uniform template derivations of the
source fields (no per-entry hand editing). FALLBACK_QUALIFIED because the real embedding gate is BLOCKED.

    python3 experiments/primitive_sequence_recovery/run_b1_1_bridge_pool_generation.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
LEX = HERE / "b1_1_experimental_contrastive_lexicon_draft.json"
POOL = HERE / "b1_1_bridge_pool_draft.json"
REPORT_JSON = HERE / "B1_1_BRIDGE_POOL_GENERATION_REPORT.json"
REPORT_MD = HERE / "B1_1_BRIDGE_POOL_GENERATION_REPORT.md"

FORBIDDEN = ("good", "bad", "positive", "negative", "vice", "virtue")


def norm(t):
    return re.sub(r"\s+", " ", (t or "").strip())


def normlow(t):
    return norm(t).lower()


def build():
    lex = json.loads(LEX.read_text(encoding="utf-8"))
    entries = lex["entries"]
    pool = []
    for e in entries:
        binding_bridge = norm(e["binding_expression"])
        liberating_bridge = norm(f"{e['liberating_expression']} — {e['functional_operation']}")
        pool.append({
            "varna": e["varna"], "lexicon_key": e["lexicon_key"],
            "source_attested_pole": e["source_attested_pole"], "source_note": e["source_note"],
            "binding_expression": e["binding_expression"], "liberating_expression": e["liberating_expression"],
            "functional_operation": e["functional_operation"], "contrast_boundary": e["contrast_boundary"],
            "rewrite_status": e["rewrite_status"], "b1_1_use_status": e["b1_1_use_status"],
            "binding_bridge": binding_bridge, "liberating_bridge": liberating_bridge,
            "binding_bridge_source": "binding_expression",
            "liberating_bridge_source": "liberating_expression + functional_operation"})
    return lex, entries, pool


def validate(entries, pool):
    by = {p["varna"]: p for p in pool}
    all_phrases = [p["binding_bridge"] for p in pool] + [p["liberating_bridge"] for p in pool]
    norm_phrases = [normlow(x) for x in all_phrases]
    dup = sorted({x for x in norm_phrases if norm_phrases.count(x) > 1})

    def has(v, key, *needles):
        s = normlow(by[v][key])
        return all(n.lower() in s for n in needles)

    forbidden_hits = []
    for x in all_phrases:
        for w in FORBIDDEN:
            if re.search(rf"\b{re.escape(w)}\b", x.lower()):
                forbidden_hits.append((w, x))
    moksha_hits = [x for x in all_phrases if "mokṣa" in x.lower() or "moksha" in x.lower()
                   or "final endpoint" in x.lower()]

    checks = {}
    checks["1_34_entries"] = (len(entries) == 34, len(entries))
    checks["2_68_phrases"] = (len(all_phrases) == 68, len(all_phrases))
    checks["3_no_missing_varnas"] = (len({p["varna"] for p in pool}) == 34, len({p["varna"] for p in pool}))
    checks["4_no_duplicate_bridge"] = (not dup, dup)
    checks["5_no_empty_phrase"] = (all(all_phrases), sum(1 for x in all_phrases if not x))
    checks["6_no_forbidden_framing"] = (not forbidden_hits, forbidden_hits)
    checks["7_no_moksha_endpoint"] = (not moksha_hits, moksha_hits)
    checks["8_ca_va_distinct"] = (
        has("Ca", "liberating_bridge", "falsehood") and has("Va", "liberating_bridge", "accepts-as-true")
        and by["Ca"]["liberating_bridge"] != by["Va"]["liberating_bridge"],
        {"Ca": by["Ca"]["liberating_bridge"][:70], "Va": by["Va"]["liberating_bridge"][:70]})
    checks["9_ha_ksa_distinct"] = (
        has("Ha", "liberating_bridge", "realized") and has("Kṣa", "liberating_bridge", "instrumental")
        and by["Ha"]["liberating_bridge"] != by["Kṣa"]["liberating_bridge"],
        {"Ha": by["Ha"]["liberating_bridge"][:70], "Kṣa": by["Kṣa"]["liberating_bridge"][:70]})
    checks["10_sa_guna_binding_aware"] = (
        has("Sa", "binding_bridge", "owned"), by["Sa"]["binding_bridge"][:90])
    checks["11_ra_dual_source"] = (
        ("prāṇaśakti" in by["Ra"]["source_note"].lower() and "sarvanāśa" in by["Ra"]["source_note"].lower()
         and "destructive collapse" in by["Ra"]["binding_bridge"].lower()),
        by["Ra"]["binding_bridge"][:90])
    checks["12_ddha_la_distinct"] = (
        has("Ḍha", "binding_bridge", "malice") and has("La", "binding_bridge", "physical")
        and by["Ḍha"]["liberating_bridge"] != by["La"]["liberating_bridge"],
        {"Ḍha": by["Ḍha"]["binding_bridge"][:60], "La": by["La"]["binding_bridge"][:60]})
    checks["13_ka_sa_not_identical"] = (
        by["Ka"]["liberating_bridge"] != by["Sa"]["liberating_bridge"],
        {"Ka": by["Ka"]["liberating_bridge"][:70], "Sa": by["Sa"]["liberating_bridge"][:70]})
    checks["14_each_phrase_one_source"] = (
        all(p.get("binding_bridge_source") and p.get("liberating_bridge_source") for p in pool), True)

    distinction = {"Ca_Va": checks["8_ca_va_distinct"][0], "Ha_Ksa": checks["9_ha_ksa_distinct"][0],
                   "Sa_guna": checks["10_sa_guna_binding_aware"][0], "Ra_dual": checks["11_ra_dual_source"][0],
                   "Ddha_La": checks["12_ddha_la_distinct"][0], "Ka_Sa": checks["13_ka_sa_not_identical"][0]}
    all_pass = all(v[0] for v in checks.values())
    status = ("FAIL_DUPLICATE_BRIDGE" if dup else
              "PASS_BRIDGE_DRAFT" if all_pass else "REVIEW_REQUIRED")
    return checks, distinction, status, dup, forbidden_hits


def main():
    lex, entries, pool = build()
    POOL.write_text(json.dumps({
        "artifact": "b1_1_bridge_pool_draft", "status": "draft_not_frozen",
        "qualification": "FALLBACK_QUALIFIED",
        "qualification_note": "Generated under weaker LOCAL lexical fallback; the real embedding gate remains "
                              "BLOCKED_DEPENDENCY_UNAVAILABLE (huggingface.co egress-denied) and is still owed. "
                              "NOT a B1.1 freeze, NOT generation authorization.",
        "b1_verdict_unchanged": "RANDOM_OR_SCRAMBLED_MATCHES", "track_b_status": "BLOCKED",
        "source_lexicon": "b1_1_experimental_contrastive_lexicon_draft.json",
        "source_lexicon_sha256": hashlib.sha256(LEX.read_bytes()).hexdigest(),
        "n_varnas": len(pool), "n_bridge_phrases": 2 * len(pool),
        "bridge_derivation": {"binding_bridge": "binding_expression (normalized)",
                              "liberating_bridge": "liberating_expression + ' — ' + functional_operation"},
        "manual_heuristic_alteration": False,
        "non_claims": ["binding/liberating language only", "no good/bad framing",
                       "experimentally testable, not spiritual truth", "no ontology/Sanskrit/semantic claim"],
        "entries": pool}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    checks, distinction, status, dup, forbidden = validate(entries, pool)
    lex_sha = hashlib.sha256(LEX.read_bytes()).hexdigest()
    rep = {"artifact": "b1_1_bridge_pool_generation_report",
           "qualification": "FALLBACK_QUALIFIED",
           "b1_verdict_unchanged": "RANDOM_OR_SCRAMBLED_MATCHES", "track_b_status": "BLOCKED",
           "input_lexicon_sha256": lex_sha, "n_entries": len(entries), "n_bridge_phrases": 2 * len(pool),
           "duplicate_bridge": dup, "forbidden_language": forbidden,
           "distinction_checks": distinction, "manual_heuristic_alteration": False,
           "checks": {k: {"pass": v[0], "detail": v[1]} for k, v in checks.items()},
           "gate_status": status,
           "caveat": "Bridge pool generated under FALLBACK_QUALIFIED status (embedding gate BLOCKED). "
                     "Not final B1.1 freeze; not generation authorization.",
           "non_claims": ["no ontology validation", "no Sanskrit privilege", "no semantic truth"]}
    REPORT_JSON.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def row(k, v):
        return f"| {k} | {'PASS' if v[0] else 'FAIL'} | {str(v[1])[:80]} |\n"
    md = f"""# B1.1 Bridge-Pool Generation — REPORT (DRAFT, FALLBACK_QUALIFIED)

## Scope and non-claims
Deterministic transform of the resolved binding/liberating lexicon into **{2*len(pool)} bridge phrases**
(binding + liberating per varṇa). No model / generation / scoring / judge. Generated from the B1.1 JSON only;
source lexicons untouched. **FALLBACK_QUALIFIED** — the real embedding gate is `BLOCKED_DEPENDENCY_UNAVAILABLE`
and still owed; this is **not** a B1.1 freeze and **not** generation authorization. Does not modify B1, change
the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**). **Structure, not validated meaning.**

## Inputs & derivation
- input: `b1_1_experimental_contrastive_lexicon_draft.json` (sha256 `{lex_sha}`)
- entries loaded: **{len(entries)}** · bridge phrases: **{2*len(pool)}**
- binding_bridge = binding_expression (normalized) · liberating_bridge = liberating_expression + " — " + functional_operation
- **manual/heuristic per-entry alteration: NONE** (uniform template; every phrase links to one source expression)

## Validator checks
| check | result | detail |
|---|---|---|
{''.join(row(k, v) for k, v in checks.items())}
## Distinction checks
Ca/Va {'✓' if distinction['Ca_Va'] else '✗'} · Ha/Kṣa {'✓' if distinction['Ha_Ksa'] else '✗'} ·
Sa guṇa-aware {'✓' if distinction['Sa_guna'] else '✗'} · Ra dual-source {'✓' if distinction['Ra_dual'] else '✗'} ·
Ḍha/La {'✓' if distinction['Ddha_La'] else '✗'} · Ka/Sa non-identical {'✓' if distinction['Ka_Sa'] else '✗'}

## Gate status
**`{status}`**

## Caveat
Bridge pool generated under **FALLBACK_QUALIFIED** because the embedding gate remains blocked. Not final
B1.1 freeze; not generation authorization. Before freeze: run the real embedding gate, OR the prereg must
explicitly record the weaker local fallback and the elevated R-risk.

## Manual process checks
- source lexicons in `varna_lens/`: NOT modified · B1 artifacts: NOT modified
- no embedding / model / generation / scoring / judging run · no bridge generation authorized

## Final status
```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
Bridge pool:           DRAFT (FALLBACK_QUALIFIED)
Embedding gate:        BLOCKED (still owed)
Gate status:           {status}
```
**Structure, not validated meaning.**
"""
    REPORT_MD.write_text(md, encoding="utf-8")
    print(f"[ok] entries={len(entries)} phrases={2*len(pool)} dup={dup or 'none'} "
          f"forbidden={forbidden or 'none'} status={status}")
    print(f"[ok] distinctions: {distinction}")
    print(f"[ok] wrote {POOL.name}, {REPORT_JSON.name}, {REPORT_MD.name}")


if __name__ == "__main__":
    main()
