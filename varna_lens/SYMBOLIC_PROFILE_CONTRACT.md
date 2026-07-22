# Canonical Symbolic Profile — Runtime Contract (v1.0)

The **Symbolic Profile** is the single deterministic interface between varṇa parsing + the authoritative
B1.12 mapping and every downstream symbolic consumer. It is produced once by
`varna_lens/symbolic_profile.py::build_symbolic_profile` and consumed read-only by the reflection
renderer, Arm D / symbolic conditioning, future coherence evaluators, and serialization/audit.

```
concern / canonical concept
        ↓
existing parser + conjunct normalization   (varna_lens tokenizer, unchanged)
        ↓
authoritative B1.12 mapping                 (varna_lens/lexicon_b1_12.json; sole drive source)
        ↓
CANONICAL SYMBOLIC PROFILE   ── build_symbolic_profile(...)
        ├── reflection renderer   (pse_renderer.render_from_profile)
        ├── Arm D / conditioning  (poles[].text, optionally compressed)
        ├── future coherence eval
        └── serialization / audit (to_dict / to_json)
```

## Schema

```jsonc
{
  "schema_version": "1.0",
  "profile_id": "sp_<sha256[:16]>",              // deterministic: hash(schema, input word, varṇa keys, mapping sha)
  "input": {
    "concern_id": null,                          // optional (concern lineage)
    "canonical_concept": null,                   // optional (resolved Sanskrit concept)
    "source_text": "compassion",
    "reading_mode": "hybrid"                     // hybrid | sound | spelling
  },
  "decomposition": {
    "normalized_input": "compassion",
    "varna_keys": ["ka","o","ma","pa","a","sha","i","nna"],
    "tokens": [
      { "index": 0, "source_span": "K", "type": "C", "varna_key": "ka",
        "iast": "Ka", "devanagari": "क", "mapping_status": "mapped" }   // mapped | vowel | unmapped
    ]
  },
  "poles": {                                      // ordered; the authoritative B1.12 drive payload
    "binding":    [ { "varna_key": "ka", "text": "<verbatim B1.12 binding vṛtti>",   "source_mapping_id": "varna.ka.binding" } ],
    "liberating": [ { "varna_key": "ka", "text": "<verbatim B1.12 liberating vṛtti>","source_mapping_id": "varna.ka.liberating" } ]
  },
  "trajectory": {                                 // deterministic structural state (no wording)
    "roles": ["SOURCE","INTEGRATION","…","RESOLUTION"],
    "valence": "liberating",                      // binding | liberating | mixed (derived from the chain)
    "controlling_element": "water",
    "tone": "expansive·open",
    "tone_parts": { "weight": "…", "flow": "…", "resolution": "…" },
    "chain": "<essence_short>",                   // verbatim engine essence
    "interaction": "<essence long>",
    "whole_word_essence": { "iast": "…", "sign": "+|−", "essence": "…" },
    "stages": [ { "varna_key": "ka", "role": "SOURCE", "sign": "−", "transform": false,
                  "element": "water", "text": "<verbatim B1.12 gloss>" } ]
  },
  "provenance": {
    "mapping_source": "experiments/primitive_sequence_recovery/frozen/varna_native_stage1_merged_v3.json",
    "mapping_sha256": "65116f371aca9f24…",
    "active_lexicon": "lexicon_b1_12.json",
    "parser_version": "varna_lens.tokenizer+conjunct_normalization.v1",
    "profile_builder_version": "1.0.0"
  },
  "status": {
    "complete": true,
    "abstentions": [],                            // e.g. {code:"UNMAPPED_VARNA"|"NO_MAPPED_VARNA", …}
    "warnings": []
  }
}
```

## Contract rules (all enforced)

- **Deterministic** — same input → byte-identical `to_json()` (no time/random; `profile_id` is a content hash).
- **Serializable / versioned** — `to_dict()` / `to_json()`; `schema_version` = `1.0`.
- **Immutable** — `@dataclass(frozen=True)`; the renderer copies fields out and never writes back.
- **Renderer-wording-independent** — carries structural state + verbatim source text only; no prose/imagery.
- **No experiment/score fields** — `assert_no_evaluator_fields` rejects score/relationship/evaluator/verdict field names.
- **No old Layer-2 bridge** — poles are verbatim B1.12 text, never bridge paraphrases.
- **Sole B1.12 source** — poles read only from the active lexicon (`lexicon_b1_12.json` → v3 mapping).
- **Explicit abstention** — unmapped varṇa → `UNMAPPED_VARNA`; no mapped consonant → `NO_MAPPED_VARNA`; never silently back-filled, never reads the old lexicon.
- **Transliteration-stable** — kṣ / ksh / x / kSh converge to the same canonical varṇa sequence (`[ka, ssa]`).
- **Auditable** — provenance carries the mapping sha256 + parser/builder versions.

## Identity vs display text (Phase 3)

Prose is **never** a join key. Every pole carries an opaque, mechanically-derived
`source_mapping_id = "varna.<key>.<pole>"` (identity only — no semantics smuggled in). The `text` is the
**verbatim B1.12 source string**; a shorter *deterministic* presentation derivative is available via
`varna_lens/tools/layer2_ablation/ablation.py::compress` (marked as a derivative, never authored).

## Forbidden fields (never present)

resonance/BSR score · relationship classification · evaluator confidence · psychological diagnosis ·
personality interpretation · advice / coaching · response wording · LLM summaries · old Sanskrit-label
bridge output · dynamically authored semantic IDs · any "this varṇa means/reveals/proves X about a
person" claim.

## Builder & consumers

- **Builder:** `build_symbolic_profile(*, source_text, concern_id=None, canonical_concept=None, by="hybrid")`
  — invokes the existing parser, applies conjunct normalization, resolves every varṇa through the active
  B1.12 mapping, builds ordered poles, reuses the single deterministic trajectory computation
  (`pse_renderer.trajectory`, no duplication), attaches provenance, surfaces abstentions.
- **Renderer:** `pse_renderer.render_from_profile(profile, mode)` (and `render(word, …)` which builds a
  profile then consumes it) — derives imagery/phrasing/tone/order; writes nothing back.
