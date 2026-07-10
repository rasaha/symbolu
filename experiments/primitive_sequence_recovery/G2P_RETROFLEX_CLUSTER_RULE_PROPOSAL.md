# G2P Retroflex-Cluster Rule — SCOPING PROPOSAL (not implemented)

**Status: PROPOSAL / scoping only. No code changed. No representation re-pointed. No test re-run.**
Resonance refinement only — no ontology/semantic-truth/Sanskrit-privilege claim, no `GENUTILITY_*`, no
`ONTOLOGICAL_SIGNAL`. **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

---

## 1. Problem (the gap this closes)

English `t/d` before `r` (*drum, train, tree, dry, dragon, truck*) is phonetically **retroflex-flavored**
(post-alveolar [ɖ]/[ʈ]). Classically that is **ḍa (ड)** / **ṭa (ट)**, not dental **da (द)** / **ta (त)**.
The bridge author knew this — `frozen/b1_6_phoneme_to_varna_bridge_manifest.json` already maps the phonemes
`dr → dda` and `tr → tta`. **But those mappings are dead code:** the G2P (`stage_a_prime_coverage`, `A_PRIME_EN`)
**pre-splits** the cluster into `d + r` / `t + r` before the bridge runs, so:

| word | G2P now | varṇas now | phonetically-faithful |
|---|---|---|---|
| drum | `d, r, u, m` | `da, ra, ma` (dental) | `ḍa, ra, ma` |
| train | `t, r, e, n` | `ta, ra, na` (dental) | `ṭa, ra, na` |

So every retroflex-flavoured English cluster is flattened to its **dental cousin, landing on a different vṛtti**
(`da` = krodha/karkaśatā irritability, `ta` = jāḍya inertia) instead of the retroflex one (`ḍa` = lajjā shyness,
`ṭa` = vitarka overstatement). This is a **systematic under-representation of the retroflex series**, not mere
unreachability.

## 2. The rule (Phase 1 — high confidence)

> **Context-sensitive retroflexion:** a `/t/` or `/d/` phoneme immediately followed by `/r/` maps to the
> **retroflex** varṇa (`tta` / `dda`) instead of the dental (`ta` / `da`). The `/r/` is unaffected.

- `[d, r] → ḍa (dda) + ra`  → *drum* = `ḍa, ra, ma`
- `[t, r] → ṭa (tta) + ra`  → *train* = `ṭa, ra, na`

### 2a. DECISION FORK — does the `/r/` survive?
Two defensible readings; the operator must choose before implementation:
- **(chosen default) `/r/` SURVIVES** → `ḍa + ra` (drum = ḍa, ra, ma). The `r` phoneme is genuinely present; the
  retroflexion colours the stop, it doesn't delete the `r`. Conservative and faithful to the sequence.
- **`/r/` SUBSUMED** → `ḍa` alone (drum = ḍa, ma). Treats `dr` as a single retroflex affricate [ɖʐ]; matches the
  *literal* existing bridge key `dr → dda` (which, as a 1:1 phoneme→varṇa entry, drops the `r`). More aggressive.

The two give different varṇa sequences for every `tr/dr` word, so this must be fixed first.

## 3. Placement — two implementation routes

- **Route A — G2P emits the cluster:** change `A_PRIME_EN` to keep `dr`/`tr` as single phonemes; the existing
  bridge `dr→dda`/`tr→tta` then fire. Minimal bridge change, but **subsumes the `r`** (route 2a-subsumed) unless
  the bridge is also changed to emit `ra`.
- **Route B (recommended) — context-aware bridge rule:** keep the G2P as-is; make the bridge do a **bigram
  lookahead** so `/t|d/` + `/r/` → retroflex-stop **plus** `ra`. Keeps the `r` (route 2a-survives), leaves the G2P
  untouched, and is the smaller conceptual change. Requires the bridge to stop being a pure 1:1 dict.

## 4. Scope boundaries

**In scope (Phase 1):** `dr → ḍa`, `tr → ṭa` only. Phonetically solid in General American.

**Candidates (Phase 2, need separate justification):**
- `nr → ṇa (nna)` — marginal in English (*Henry*); weak trigger.
- `shr → ṣa (ssa)` — English `/ʃr/`; `/ʃ/` is not truly retroflex, so this is the **weakest** claim; likely reject.
- **post-`r` retroflexion** (`rt`, `rd` → ṭ/ḍ, as in Indian-English *cart/hard*) — accent-dependent (rhotic);
  **out of scope** for a General-American G2P.

**Does NOT reach even with the rule:** the retroflex **aspirates** `ṭha (ttha)` / `ḍha (ddha)` — English has no
trigger (no `thr → retroflex`; `thr` is the dental fricative `/θr/`). They stay reference-only. So Phase 1 recovers
**2 of the 5** practically-unreachable retroflex/palatal targets (`tta`, `dda`); `nna`, `nya`, `ssa` stay dead.

## 5. Impact analysis (measured)

- **Frozen experiment sets barely move:** only **`dread`** contains `t/d + r` — 1 of 24 pole-DiD items, 1 of 12
  B1.9 targets. Effect: `dread` = `da, ra, da` → `ḍa, ra, da` (shifts its first varṇa krodha→lajjā). Nothing else
  in the frozen sets changes.
- **General English is pervasively affected:** 22/22 of a common `tr/dr` sample (*drum, train, tree, dry, drive,
  dragon, truck, try, country, hundred, children, address, dream, drop, trust, true, street, strong, district,
  industry, introduce, three*→no). So for any NEW/arbitrary English word set, the rule changes a large fraction of
  sequences — high leverage there, near-zero on the current frozen corpus.

## 6. Cost to adopt (if approved)

1. Pick the §2a fork (r survives vs subsumed) and the §3 route (A vs B).
2. New **representation version** — a `A_PRIME_EN` v2 (Route A) or a `bridge v2` with lookahead (Route B); new
   file, new sha256 hashes.
3. **Re-derive** every affected varṇa sequence (only `dread` among frozen items; plus anything new).
4. **Re-freeze** the evidence declarations that hash the decomposer/bridge (pole-DiD, pole-sanity, B1.8/B1.9).
5. **New prereg** + operator sign-off; **freeze before** authoring/re-running (anti-circularity).

## 7. What it does and does NOT buy

- **Buys:** phonetic fidelity of the *resonance* mapping — `tr/dr` words get their classically-correct retroflex
  root (`ṭa/ḍa`); the retroflex series goes from 0→2 reachable.
- **Does NOT buy:** any change to validity. It's a **resonance refinement** — it swaps which resonance a word
  receives, and does not touch the content-level nulls (B1.4b′ `NULL_RETURN_BOTTOM`, B1.9 embedding, B1.8/B1.9
  generation). A word mapping to a "better" root is not evidence the root *carries* meaning.

## 8. Recommendation

Worth doing **as a scoped, versioned, pre-registered change** if the goal is a phonetically faithful resonance
map — but **low urgency**: it changes exactly one frozen item (`dread`). Suggested defaults: **Route B**
(context-aware bridge, G2P untouched) with **`/r/` surviving** (`drum → ḍa, ra, ma`), **Phase 1 only** (`dr`, `tr`),
explicitly deferring `nr`/`shr`/post-`r`. Implement only on operator approval; nothing here is applied.

---

**Guardrails:** proposal only; no code, no re-derivation, no re-run. Resonance refinement, not validated meaning.
No `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`. **B1.4b′ remains `NULL_RETURN_BOTTOM`.** Structure, not validated meaning.
