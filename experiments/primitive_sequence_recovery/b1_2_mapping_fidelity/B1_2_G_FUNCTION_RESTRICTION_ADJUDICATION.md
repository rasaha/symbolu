# B1.2 G(word) Restriction Adjudication (R1–R5)

## 1. Scope and non-rescue rule

Resolves the five restrictions R1–R5 from `B1_2_G_FUNCTION_IMPLEMENTATION_PLAN_OR_STOP_NOW.md`
(decision: `GO_WITH_RESTRICTIONS`) so the G builder can either proceed to implementation or default to
STOP_NOW. **Adjudication / specification only** — no implementation, no models, no G outputs, no judging, no
scoring. Does **not** change or rescue B1.1, claim generation utility / ontology / Sanskrit privilege /
semantic truth, or unblock Track B. B1.1 stays `RANDOM_OR_SCRAMBLED_MATCHES`; Track B stays BLOCKED.
**Structure, not validated meaning.**

## 2. R1 — minimize LLM footprint

**Deterministic-first pipeline is required.** WordNet/dictionary rules are attempted **first** for every
stage (retrieval, synonym selection, shared-feature extraction, tiering). The LLM is allowed **only** for the
**target-specific residual extraction** step, and **only if** deterministic rules are demonstrably too
brittle on real definitions (documented per-stage brittleness finding required before any LLM use).

If used, the LLM is limited to **structured extraction from dictionary definitions**: it receives **no
varṇa, no V, no B1/B1.1 outputs, no arm labels**; emits **JSON schema only**; runs at **temperature 0 /
deterministic**; and its **model id + revision are pinned** where the environment allows. Its footprint is
one bounded call per word for one field (the residual), never free generation.

```
R1: R1_RESOLVED_DETERMINISTIC_FIRST
```

## 3. R2 — frozen G outputs authoritative

Once created and **audited**, the G outputs become **authoritative frozen artifacts** (hash-bound in the G
manifest). The builder **method and prompts are provenance**, not the source of truth. **Re-running the
builder is validation, not replacement**: a rerun checks reproducibility (R4) but the frozen audited G
outputs stand. If LLM output is not byte-reproducible across environments, the **frozen audited outputs
remain authoritative**. If, for any reason, G outputs **cannot be frozen by hash**, → STOP_NOW.

```
R2: R2_RESOLVED_FREEZE_OUTPUTS
```

## 4. R3 — V↔G comparability and style-tell audit (the fragile point)

**Both V and G are projected into one shared judge-facing schema** so the judge scores *fit*, not *source
style*. No long prose essay; compact, feature-first, matched length band, same register, no source-revealing
phrasing.

**Joint normalized judge-facing schema (identical for V and G, and for every distractor key):**

```json
{
  "signature_id": "opaque-id",
  "features": ["3–7 short noun-phrase features"],
  "summary": "one concise sentence (<= N words, frozen N)",
  "constraints": ["1–3 short distinguishing constraints"]
}
```

Rules: `features`/`constraints` are short noun phrases of matched count and length; `summary` is a single
frozen-length sentence; **no varṇa/Sanskrit labels; no dictionary-source phrasing that reveals G; no
bridge-source phrasing that reveals V; no arm/source labels**. Both pipelines render **through the same
normalizer**, pinned at freeze.

**Style-tell audit (mandatory, before freeze):** a **blinded classifier/judge** is given only the normalized
signatures (V-origin vs G-origin, labels hidden) and must guess the source type. **Pass** = source-type
detection at/near chance (pre-registered threshold, e.g. balanced accuracy ≤ 0.55 with its CI touching 0.5).
If detection is **above threshold**, the rendering is revised (shorten/normalize the giveaway field) and
re-audited **before** freeze. If comparability **cannot** be achieved after revision → STOP_NOW.

```
R3: R3_RESOLVED_SHARED_RENDER_FORMAT
```

## 5. R4 — reproducibility acceptance test

- **Deterministic stages:** re-running the builder in the same pinned environment on frozen inputs must
  **reproduce those outputs byte-for-byte (identical hash)**. Any mismatch on a deterministic stage → fail.
- **LLM residual stage (if used):** byte reproduction is **not** guaranteed. Accepted policy: **frozen
  audited outputs are authoritative** (R2); a rerun must reproduce **(a) schema validity** and **(b)
  feature-level similarity above a pre-registered threshold** (e.g. ≥ 0.8 Jaccard on the `features` set); if
  it cannot, the stage must fall back to **deterministic/rule extraction** or the word is dropped by rule.
- **Pass/fail is defined before implementation:** deterministic-stage hash-identity + LLM-stage
  schema-validity + feature-similarity ≥ threshold = pass; otherwise fail → rule fallback or STOP_NOW.

```
R4: R4_RESOLVED_REPRO_POLICY
```

## 6. R5 — fixed versioned dictionary source

- **Primary source: WordNet**, offline, **version-pinned** (e.g. WordNet 3.1 via nltk), the corpus itself
  **cached and hash-bound**.
- **Availability note (honest):** nltk is present in-repo (already used for cmudict), but the WordNet corpus
  is **not yet provisioned** in this environment. Implementation must **download once, pin the version, and
  hash the cached corpus**; thereafter no live calls.
- **Fallback dictionary/thesaurus** (if a second source is needed) must be **versioned, cached, and
  hash-bound** — **no live web dictionary calls in the final run**.
- Source **edition / date / hash recorded**; **definitions frozen before G extraction**.
- If a **fixed, offline, version-pinnable source cannot be obtained** in the run environment → STOP_NOW.

```
R5: R5_RESOLVED_FIXED_SOURCE  (conditional on provisioning + hash-pinning WordNet at build)
```

## 7. Updated G builder constraints (to pass into implementation)

- **Retrieval policy:** WordNet (version-pinned, cached, hashed) as primary; any fallback source versioned +
  cached + hashed; no live web calls in the final run.
- **Synonym selection:** deterministic rule (synset members + hypernym siblings, POS-matched, top-k by a
  frozen metric), ≥10 per word, frozen before G, no post-hoc replacement.
- **Extraction:** deterministic shared-feature + residual extraction first; frozen-prompt, temp-0,
  JSON-only, revision-pinned LLM **only** for the residual step where rules are too brittle; no varṇa/V/B1.1
  input.
- **Rendering:** the single shared normalized schema (§4) for V, G, and all distractors; matched length/
  register; no source-revealing phrasing.
- **Audit:** lexical/format/leakage audit + the mandatory style-tell audit (source-type detection ≤ threshold)
  before freeze.
- **Freeze:** target set, sources+versions, synonym sets, definitions, extraction method/prompt, G outputs,
  tiers, distractor assignments, all hashes — bound under the joint B1.2 manifest; `INVALID_POSTHOC` on edit.

## 8. Updated STOP_NOW conditions

- any unresolved R1–R5 restriction → STOP_NOW;
- **style-tell failure** unresolved after revision → STOP_NOW;
- **no fixed dictionary source** obtainable offline → STOP_NOW;
- G output **requires hand-polishing** → STOP_NOW;
- G **leaks V/varṇa** → STOP_NOW;
- V/G **cannot be normalized** into the comparable schema → STOP_NOW.

## 9. Decision

```
DECISION: RESTRICTIONS_RESOLVED_WITH_LIMITED_LLM_GO_IMPLEMENTATION
```

All five restrictions are resolved **in specification**: deterministic-first (R1), frozen authoritative
outputs (R2), a shared render format with a mandatory style-tell gate (R3), an explicit reproducibility
policy (R4), and a fixed version-pinned dictionary source (R5, conditional on provisioning WordNet at build).
The **"with limited LLM"** qualifier is chosen honestly: the plan permits a **restricted, deterministic-first,
frozen-prompt LLM fallback** for the residual step, not a pure-rule guarantee. Full pure-deterministic GO is
not claimed because residual extraction may need the bounded LLM step; STOP_NOW is not triggered because every
restriction has a resolved path and a deterministic fallback.

This decision is **conditional at build time**: if WordNet cannot be version-pinned offline (R5), or the
style-tell audit cannot reach threshold (R3), implementation must **halt to STOP_NOW** rather than proceed.

## 10. Implementation constraints if GO

- **No live web calls** in the final run (all sources cached + hashed).
- **No B1.1 outputs** used anywhere in G.
- **No V / varṇa input** to G (independence enforced + scanned).
- **No manual residual editing** (frozen procedure output only).
- **Write full provenance** (sources, versions, dates, model+revision if LLM used).
- **Write hashes** for all inputs and outputs.
- **Produce an audit report** (lexical/format/leakage).
- **Produce a style-tell audit** (source-type detection ≤ threshold, with CI).
- **Produce a frozen G manifest** (folded into the joint B1.2 freeze).

## 11. Final status block

```
document:                   B1.2 G-function RESTRICTION ADJUDICATION (spec only; nothing built/run)
R1 (LLM footprint):         R1_RESOLVED_DETERMINISTIC_FIRST
R2 (frozen outputs):        R2_RESOLVED_FREEZE_OUTPUTS
R3 (V↔G comparability):     R3_RESOLVED_SHARED_RENDER_FORMAT (style-tell gate mandatory)
R4 (reproducibility):       R4_RESOLVED_REPRO_POLICY
R5 (fixed source):          R5_RESOLVED_FIXED_SOURCE (provision + hash-pin WordNet at build; else STOP_NOW)
decision:                   RESTRICTIONS_RESOLVED_WITH_LIMITED_LLM_GO_IMPLEMENTATION
B1.1 verdict:               UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
LIMITED_GENERATION_UTILITY: NOT earned
Track B:                    BLOCKED
Track G / Track F:          RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
authorized to run:          NO — implement G, audit, then joint V+G B1.2 freeze + prereg review
next gate:                  B1_2_G_FUNCTION_IMPLEMENTATION
```

**Structure, not validated meaning.** The restrictions are resolved in specification with a limited,
deterministic-first LLM fallback and hard STOP_NOW guards (style-tell, fixed source); the B1.1 verdict stands,
Track B remains BLOCKED, and B1.2 cannot run until G is built, audited, and a new joint freeze is created.
