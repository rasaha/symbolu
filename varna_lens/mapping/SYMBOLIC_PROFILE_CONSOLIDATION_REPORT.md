# PSE Symbolic Runtime Consolidation — Canonical Symbolic Profile

Final consolidation after: B1.12 mapping migration · canonical ksha = k + ṣ · Layer-2 bridge retirement ·
confirmation that direct B1.12 payloads suffice. This task defines, implements, and **freezes** one
canonical Symbolic Profile as the sole interface between concern/concept resolution → varṇa parsing +
B1.12 mapping → downstream reflection / Arm D / evaluators.

---

## Phase 1 — Inventory of pre-consolidation symbolic objects

| Object | File | Producer | Consumers | Fields (symbolic) | Status |
|---|---|---|---|---|---|
| `read_op` engine output | `varna_lens.py` | engine | trajectory, reflect, profile | sequence, essence_short, emergent_valence, whole_word_essence | **canonical candidate** (folded into profile) |
| `trajectory()` dict | `pse_renderer.py` | renderer | render() | roles, stages, controlling_element, tone, valence | **canonical candidate** (reused by builder) |
| `render()` output | `pse_renderer.py` | renderer | CLI/tests | layer1_engine, layer2_trajectory, layer3_reflection | **renderer-only** (now consumes profile) |
| `scaffold()` dict | `reflect.py` | reflect CLI | reflect/name prompts | chain, glossary, emergent_valence | **adapter** (reflection CLI; reads active mapping) |
| `bridge()` result | `symbol_u_bridge/bridge_core.py` | concern bridge | concern lineage | concern_id, sanskrit_word, varnas, mapping_glosses, confidence_hint | **adapter** (concern→concept resolver; feeds profile `input`) |
| `profile()` units | `sample_text_rule_harness.py` | Layer-2 harness | Layer-3/4, conditioning | units{role,pole,term} | **research-only / retired** |
| `synthesize`/`_bridge`/`BRIDGE` | `sample_text_rule_harness.py` + `layer2_bridge_vocab.json` | Layer-2 harness | Layer-3/4, conditioning | bridge phrases | **obsolete** (0/66; retired) |
| `layer3 relate` / `layer4 attrs` | `layer3/4_*.py` | inspection | — | relation/attribute labels | **research-only / retired** |

**Overlap resolved:** the engine output + trajectory dict were the two "canonical candidates" carrying
the deterministic symbolic state; they are now unified in one immutable `SymbolicProfile` (builder reuses
both, no duplication). `reflect.scaffold` and `bridge_core.bridge` are lineage **adapters** (reflection
CLI and concern resolution); the Layer-2/3/4 objects are **retired**.

---

## Phase 2–4 — Contract & builder

Full schema and rules: `varna_lens/SYMBOLIC_PROFILE_CONTRACT.md`. Implemented as a frozen dataclass
`SymbolicProfile` + `build_symbolic_profile(...)` (`varna_lens/symbolic_profile.py`). Identity is
separated from display text via opaque `source_mapping_id = "varna.<key>.<pole>"`; `text` is verbatim
B1.12. `assert_no_evaluator_fields` guards against score/relationship/evaluator leakage.

## Phase 5–6 — Consumer migration

| Consumer | Migration | Reconstructs symbolic state? |
|---|---|---|
| `pse_renderer.render()` | Routes through `build_symbolic_profile` → `render_from_profile`; byte-identical output | **No** — consumes the profile |
| `pse_renderer.trajectory()` | Kept as the single structural computation; reused by the builder (optional `_analysis` reuse) | n/a (the source) |
| `reflect.py` | Reads the active B1.12 mapping via `V.active_mapping_path()` (already B1.12); reflection CLI, not migrated to profile shape (adapter, documented) | No (reads active mapping) |
| Arm D / conditioning | New path: `symbolic_profile` poles (+ optional deterministic compression); legacy conditioning demo retired | No |
| Concern→profile | `bridge_core.bridge()` resolves concern→concept→varṇas; feeds the profile's `input` (concern_id/canonical_concept) | No (upstream resolver) |
| Serialization/export | `SymbolicProfile.to_dict/to_json` + frozen fixture | n/a |

**Renderer separation (Phase 6):** `render_from_profile` copies fields out of the profile and writes
nothing back — verified by `test_renderer_does_not_mutate_profile` (serialization identical before/after
rendering across all modes).

## Phase 7 — Layer-2 bridge retirement

Executed: `layer2_bridge_vocab.json` archived to `experiments/retired/layer2_bridge/` (+ full README:
purpose, old-schema dependency, measured 0/66, no production dependency, replacement, reproducibility).
The 4 harness modules are marked `RETIRED (research-only)` in place and load the archived vocab (inline
fallback keeps them runnable). The 6 legacy tests are **historical regressions**: they skip under the
active B1.12 mapping (rc=0) and run their original assertions under the old-lexicon fixture
(`VARNA_LENS_MAPPING=…/lexicon_authoritative.json` → all pass). No historical evidence deleted.

## Phase 8 — Test migration

New contract suite `varna_lens/test_symbolic_profile.py` (**11/11**): determinism · transliteration
convergence (kṣ/ksh/x/kSh → `[ka,ssa]`) · sibilant correctness (ś→artha, ṣ→kāma, dental s distinct) ·
mapping authority (every pole from the active B1.12 artifact) · no-fallback (abstains explicitly) ·
no-evaluator-leakage (rejects a `resonance_score` field) · renderer invariance · renderer non-mutation ·
consumer compatibility (render byte-identical to legacy path) · serialization stability (frozen fixture).

## Phase 9 — Regression (old distributed vs canonical builder)

12-word corpus (`mapping/SYMBOLIC_PROFILE_REGRESSION_REPORT.md`): **varṇa-sequence diffs 0 · trajectory
diffs 0 · pole diffs 0 · renderer-output diffs 0 · abstention diffs 0**. The profile ADDS explicit
provenance not previously emitted. Outcome exactly as targeted: **one canonical profile + no semantic
change + less duplicate logic** (render no longer rebuilds symbolic state).

## Phase 10 — Freeze assessment

| Freeze criterion | Status |
|---|---|
| All production consumers use the profile or a documented adapter | ✅ renderer consumes it; reflect/bridge are documented adapters |
| No production path reconstructs varṇa poles independently | ✅ render routes through the builder |
| No production path reads `lexicon_authoritative.json` | ✅ verified (grep: none) |
| No production path reads `layer2_bridge_vocab.json` | ✅ archived; only the retired harness reads it |
| B1.12 is the sole mapping authority | ✅ builder reads only the active lexicon; provenance sha pinned |
| All required tests pass | ✅ symbolic_profile 11/11, ksha 9/9, guard 11/11, ablation 7/7, renderer/ontology/crs pass; legacy skip-green |
| Schema + provenance documented | ✅ `SYMBOLIC_PROFILE_CONTRACT.md` + `SYMBOLIC_PROFILE_PROVENANCE.json` + frozen fixture |
| Remaining adapters explicitly listed | ✅ see below |

**Verdict: SAFE TO FREEZE at schema_version 1.0.**

---

## Final report

1. **Final canonical profile schema** — see `SYMBOLIC_PROFILE_CONTRACT.md` (schema_version 1.0):
   `input · decomposition{tokens} · poles{binding,liberating with opaque source_mapping_id} ·
   trajectory{roles,valence,controlling_element,tone,stages} · provenance · status{abstentions}`.
2. **Runtime source of truth** — `SymbolicProfile` from `varna_lens/symbolic_profile.py`.
3. **Consumers migrated** — `pse_renderer.render()` (now consumes the profile, byte-identical). Reflect
   CLI and the concern bridge remain documented adapters on the active B1.12 mapping.
4. **Duplicate symbolic reconstruction remaining** — none in the renderer path. Remaining adapters
   (`reflect.scaffold`, `bridge_core.bridge`) resolve/present rather than reconstruct poles; both read
   the active B1.12 mapping, neither reads the old lexicon or the bridge.
5. **Does the renderer mutate the profile?** — No (verified before/after serialization identity).
6. **Old lexicon / Layer-2 bridge reachable in runtime?** — No. `lexicon_authoritative.json` is a
   comparison artifact (loadable only via explicit `VARNA_LENS_MAPPING` override for regressions);
   `layer2_bridge_vocab.json` is archived and read only by the retired research harness.
7. **Semantic outputs changed?** — No. Phase-9 regression: 0 diffs in varṇa sequence, poles, trajectory,
   and renderer output; abstentions 0. Only additive: explicit provenance.
8. **All tests pass?** — Yes (active suites green; legacy tests skip under B1.12 and pass under the
   old-lexicon fixture).
9. **Safe to freeze?** — Yes, at schema_version 1.0 (all freeze criteria met).
10. **Remaining technical debt (explicit):**
    - `reflect.scaffold` and `bridge_core.bridge` are **temporary adapters** — they still emit their own
      lineage-shaped dicts rather than a `SymbolicProfile`. Low priority; both read the active B1.12
      mapping and reconstruct no poles. Future work: have them emit/consume `SymbolicProfile` directly.
    - The 4 Layer-2/3/4 harness modules remain physically in `varna_lens/` (marked RETIRED) rather than
      moved into `experiments/retired/layer2_bridge/`, because their `HERE`-relative imports/data-refs are
      tightly coupled to the directory; only the obsolete **data** artifact was physically relocated. No
      functional impact (research-only, skip under B1.12).
    - `build_symbolic_profile` calls `V.analyze` once and reuses it for `trajectory` via `_analysis`; the
      `by="hybrid"` path still reloads cmudict per call inside the parser (pre-existing engine trait, not
      introduced here).

### Evidence discipline
Runtime import/data-flow paths were verified (grep + byte-identity + non-mutation tests), not inferred
from test existence. No duplicate object was preserved without documentation. Missing mappings abstain
explicitly (never coerced). No new semantics were derived from B1.12 prose (opaque IDs only). No
presentation fields were mixed into symbolic state (renderer wording stays in the renderer).
