# B1.12 — Gate G1 Instrument Design v1 — Report

**Verdict: `G1_PASS_WITH_LIMITED_CLAIM`.** A leakage-safe evaluator-facing representation exists that preserves
exact order and repetition and supports a coherent **within-word order-discrimination** task — but, with the
opaque encoding required for leakage safety, it supports only a **structural** order claim, **not** direct
semantic word recovery.

`DIAGNOSTIC_ONLY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`. No contexts authored, no generators/judges run,
no evidence freeze, no confirmatory run. No change to the selected six, G0 thresholds, the pool, the parser, or
the opaque-ID map. B1.4b′ `NULL_RETURN_BOTTOM`; B1.10 `G0_NOT_TESTABLE_WITH_CURRENT_PROSE_PACKETS`; B1.11
unchanged.

---

## 0. Controlling artifacts

prereg `2c613f4` · V1.1 `6f197fd` · V1.2 `7935f48` · pool-curator `d50fbb9` · **G0 audit `1713311` (G0_PASS)**.
Selected six: **W03 asthi, W15 grīvā, W20 jñāna, W23 keśa, W30 nadī, W35 sūrya**.

## 1. Selected-set structural audit (Step 1) — classification `MIXED_ORDER_AND_INVENTORY`

Opaque sequences (frozen G0 map), `s(x)` = per-word self-order:

| id | IAST | len | ordered opaque sequence | s(x) | first | last |
|---|---|---|---|---|---|---|
| W03 | asthi | 4 | U25 U17 U19 U27 | 0.50 | U25 | U27 |
| W15 | grīvā | 5 | U06 U16 U30 U20 U29 | 0.40 | U06 | U29 |
| W20 | jñāna | 5 | U09 U22 U29 U14 U25 | 0.80 | U09 | U25 |
| W23 | keśa | 4 | U10 U26 U23 U25 | 0.50 | U10 | U25 |
| W30 | nadī | 4 | U14 U25 U05 U30 | 0.50 | U14 | U30 |
| W35 | sūrya | 5 | U17 U31 U16 U21 U25 | 0.80 | U17 | U25 |

- **All six inventories are distinct** (no pair shares a multiset); **no repeated units** in any word.
- Pairwise `d_ord|inv`: **8/15 pairs positive** (0.2–0.4), **7/15 zero**; multiset-Jaccard 0.0–0.29.
- **Consequence:** cross-word discrimination is **inventory-separable** — every word is identifiable by its bag
  (and by a **unique first opaque unit**) — so a cross-word candidate task would test **inventory recognition,
  not order**. Classification `MIXED_ORDER_AND_INVENTORY` (order signal present but not the basis of cross-word
  separability). This is **diagnostic and does not override G0_PASS**.

## 2. Encoding options (Steps 2) & task models (Step 3)

See `encoding_options_comparison.md`. Primary = **Option A content in Option D formatting**: position-tagged
opaque IDs, e.g. `p1:U09 p2:U22 p3:U29 p4:U14 p5:U25`. Primary task = **Model 3 (same-word order
discrimination)**. Models 2/4 rejected (inventory/first-unit leakage; B1.10 gloss confound); Model 1 (learned
key) deferred; Option C (semantic glosses) is secondary-only.

## 3. Order-vs-inventory feasibility (Step 4) — PASS

For every selected word, the three arms under the primary encoding satisfy (deterministic checks, all ✔):
A/B identical multiset **and** length, order differs, and B ≠ canonical-sorted; A/D same units, D is the
canonical unordered representative, A ≠ D; content-masked A = B = D. Worked example (`W20 jñāna`):

```
A (true order):          p1:U09 p2:U22 p3:U29 p4:U14 p5:U25
B (order-scramble):      p1:U29 p2:U14 p3:U09 p4:U25 p5:U22   (seed 20260101, feasibility only)
D (unordered inventory): p1:U09 p2:U14 p3:U22 p4:U25 p5:U29
content-masked (A=B=D):  p1:• p2:• p3:• p4:• p5:•
```

Within a trial, inventory and length carry **zero** discriminative information; only **order** distinguishes the
arms. (The confirmatory Arm-B scramble seed is **not** frozen here — this seed is a feasibility instantiation.)

## 4. Leakage audit (Step 5) — all checks pass; no `CONTROL_LEAKAGE`

| check | result |
|---|---|
| no IAST / Devanāgarī characters in any render | ✔ |
| no word-transliteration substring in any render | ✔ |
| content-masked arms identical within word (A=B=D) → no template/length artifact | ✔ |
| within-trial length constant across arms | ✔ |
| content-masked arm unclassifiable | ✔ |
| content-masked word ambiguous (len groups of 3: {asthi,keśa,nadī}=4, {grīvā,jñāna,sūrya}=5) | ✔ |

Informational (motivates the within-word design, **not** a leak of the chosen instrument): the **first opaque
unit is unique per selected word**, so a *cross-word* candidate task would leak the answer via the first unit —
which is precisely why the primary task presents **no cross-word choice**. `control_leakage = false`.

## 5. Recommended primary design (Step 7)

- **Evaluator receives:** position-tagged opaque ID sequences for the arms of a **single hidden word**, in an
  identical template/length.
- **Evaluator does NOT receive:** the Sanskrit word, IAST/Devanāgarī, any semantic gloss, the opaque-ID legend,
  or a cross-word candidate list.
- **Target answer:** a **structural order judgment** (e.g. which arm is the reference's true order; whether two
  renders share the same order) — never a word or meaning.
- **Why true order could help:** A differs from B and D *only* in the order of an identical multiset; any
  above-chance discrimination must use order.
- **Why inventory alone is insufficient:** within a trial all arms share the exact multiset and length.
- **Controls matched:** identical multiset, length, template, position tags; content-masked renders byte-identical.
- **A positive result supports:** ordered opaque varṇa composition is a **recoverable, distinguishable
  structural signal** (order is preserved and usable, not collapsed).
- **A positive result does NOT support:** semantic/word-specific meaning of order, truth of varṇa mappings,
  Sanskrit encoding of referents, H2 (semantic), or any rescue of B1.10.
- Per the user's guidance and the sparse cross-word order signal, the design compares **each word's own** true
  order against its own scramble/unordered versions, rather than relying on cross-word structural distinctness.

## 6. Verdict & narrowed claim (Step 6)

**`G1_PASS_WITH_LIMITED_CLAIM`.** Narrowed claim: *the B1.12 instrument can support a within-word
order-discrimination task on leakage-safe opaque varṇa compositions — testing whether the true ordered
composition is distinguishable from its own order-scrambled and unordered-inventory versions. It cannot, with
this leakage-safe opaque encoding, support direct semantic word recovery (that needs a keyed/training phase
(Model 1) or semantic glosses (Model 4, which reintroduces B1.10 prose confounds).* **Evaluator real-model
usability is UNRESOLVED** — no judge panel is available in this environment (torch/transformers absent); the
verdict rests on deterministic structural + leakage feasibility, not on a model's demonstrated performance.

## 7. Diagnostic-only feasibility (Step 8)

No real model is available, so evaluator usability is **not** demonstrated and is marked unresolved. The
deterministic structural and leakage tests (below) validate that the *encoding* makes order available and the
controls matched; they do **not** show that an LLM/human *does* the task, and success on a trivial "which is
ordered?" check would not be semantic evidence. Plumbing only; no confirmatory claim.

## 8. Tests (Step 10) — 12 passed

`test_b1_12_g1_design_v1.py`: arm A/B inventory+length equality & order inequality; A/D inventory equality & D
canonical; raw-word/transliteration leakage; formatting & position-tag parity; repeated-unit preservation;
content-masked arm indistinguishability; length-only & endpoint-only elimination impossibility; cross-word
first-unit-unique rationale; classification & verdict; deterministic rendering (re-run byte-identical);
G0/pool/parser inputs untouched (hashes verified).

## 9. Artifacts (Step 9)

`results/b1_12_g1_design_v1/`: `selected_set_structural_audit.json`, `encoding_options_comparison.md`,
`proposed_primary_encoding.json`, `arm_render_examples.json`, `leakage_audit.json`, `g1_manifest.json`, this
report; engine `b1_12_g1_design_v1.py`; tests `test_b1_12_g1_design_v1.py`. (No final contexts, no evidence-run
prompts.)

## 10. Unresolved dependencies & exact next step

- **Unresolved:** real-model/human evaluator usability of opaque order-discrimination; the confirmatory Arm-B
  scramble-seed freeze; final control/context design; whether any keyed/semantic secondary arm is ever
  introduced (B1.10-confound risk).
- **Exact next step:** a separately-versioned G1 **usability probe** — run the within-word order-discrimination
  task on an *available* judge/human panel (or a GPU harness) as `DIAGNOSTIC_ONLY`, to resolve whether the
  opaque encoding is usable; only then design controls/contexts and, much later, a confirmatory freeze. This G1
  result is preserved; any alternative encoding is a new version, never an in-place edit.

## 11. Interpretation discipline

A G1 pass means only that a leakage-safe, order-preserving evaluator instrument with a meaningful
order-vs-inventory contrast can be built. It does **not** mean order carries semantic information, that varṇa
mappings are true, that Sanskrit words encode referents, that B1.12 is supported, or that B1.10 is rescued.
Structure, not validated meaning.
