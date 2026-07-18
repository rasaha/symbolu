# B1.x — Claims-and-Measurability Ladder (docs-only)

## 1. Status

**Docs-only claims-and-measurability ladder.** No experiment run. No embeddings computed. No result label
emitted. No B1.8 results changed; B1.9 unchanged. **Readiness label: `B1_X_CLAIMS_MEASURABILITY_LADDER_READY`.**

**B1.4b′ remains `NULL_RETURN_BOTTOM`.** Original B1.4b blocked; Track B blocked. Structure, not validated meaning.

## 2. Why this document exists

Across B1.4b′ → B1.6 → B1.8 → B1.9, a recurring failure mode of interpretation is **inflation**: letting a
narrow, low-level, or exploratory result be read as a stronger claim (truth, ontology, privilege, utility). This
index fixes, in advance, **what each claim would actually require empirically, whether it is measurable at all,
and what the current evidence status is** — so no positive result at a low rung is silently promoted to a higher
rung. In particular, **B1.9 is a narrow generation-free content-level test**: it can test only whether authentic
varṇa facet aggregates are closer to word/context representations than controls. It **cannot** by itself
establish semantic truth, ontology, Sanskrit privilege, generation utility, causal meaning recovery, or
human-recognizable semantics.

## 3. Claim ladder table

| # | claim | measurable status | required design | current status | honest prior | a positive result WOULD / WOULD NOT mean |
|---|---|---|---|---|---|---|
| 1 | **Semantic truth** | strong = **not measurable**; weak = **proxy measurable (already measured)** | proxy: predict independent human norms (valence/arousal/dominance, McRae features, word-association) | **proxy already measured → null (B1.4b′)** | low | WOULD: predictive alignment with norms. WOULD NOT: truth (no oracle for a word's "true meaning"). |
| 2 | **Ontology** | **not measurable (outside empirical scope)** | none — text/behavior/embeddings/generation cannot test correspondence to real layers of being | **unreachable** | n/a | WOULD (at most): internal structural coherence. WOULD NOT: correspondence to reality. No experiment may emit `ONTOLOGICAL_SIGNAL`. |
| 3 | **Sanskrit privilege** | **measurable with a different design** | cross-system content-distance bake-off (§ below) | **not yet tested** | low | WOULD: a *relative* mapping advantage over alternatives. WOULD NOT: ontology or semantic truth. |
| 4 | **Generation utility** | **already measured** | generation + blind judging (B1.6/B1.8) | **null/negative** | low | WOULD: better blind-rated outputs. WOULD NOT: truth/ontology. (Result: no benefit.) |
| 5 | **Causal meaning recovery** | **partially measurable** | confound-controlled / ablation / held-out designs (§ below) | **not cleanly established** | low | WOULD: signal survives specific confounds. WOULD NOT: deep causal truth (a fixed mapping can't be intervened on like a mechanism). |
| 6 | **Human-recognizable varṇa semantics** | **measurable with a different design** | blind human forced-choice / matching (§ below) | **not yet tested** | low | WOULD: human-recognizable semantic structure. WOULD NOT: ontology. |
| 7 | **Content-level semantic proximity (B1.9 gate)** | **preregistered, not run** | generation-free embedding distance; `delta_distance = d_control − d_auth` | **preregistered; not run** | low | WOULD: a low-level mapping-proximity signal only. WOULD NOT: truth / ontology / privilege / utility / recognizability. |

### Row detail

**1. Semantic truth.** Strong semantic truth is **not empirically measurable** — there is no oracle for the
"true meaning" of a word. A **weak proxy is measurable** via independent human norms (valence/arousal/dominance,
McRae semantic features, word-association norms). **B1.4b′ already tested a proxy and returned
`NULL_RETURN_BOTTOM`.** A positive proxy would show predictive alignment with norms, **not** truth. *Current
status: proxy already measured and null.*

**2. Ontology.** **Not empirically measurable** by text, behavior, embeddings, or generation. Experiments can
show coherence, prediction, or usefulness — never correspondence to real layers of being. *Current status:
unreachable / outside empirical scope.* **No future B-series experiment may emit `ONTOLOGICAL_SIGNAL`.**

**3. Sanskrit privilege.** Measurable **only by cross-system comparison.** Required design — a cross-system
content-distance **bake-off** comparing the Sanskrit-varṇa mapping against: random phoneme→concept mappings; an
English sound-symbolism / phonosemantic baseline; an IPA distinctive-feature mapping; Hebrew / Greek / Arabic
root-style mappings if available; an LLM-generated decomposition baseline; and a shuffled Sanskrit-varṇa mapping.
Endpoint: **effect-size ranking of authentic-vs-control semantic proximity across systems.** *Current status: not
yet tested. Honest prior: low.* A positive result would support a **relative** mapping advantage — **not**
ontology or semantic truth.

**4. Generation utility.** Measurable and **already tested** in B1.6/B1.8 (generation + blind judging). *Current
status: null/negative.* B1.8 showed: tied with the scrambled selected-pole control; no gain over the unresolved
both-poles scaffold; underperformed plain/generic/semantic baselines. **Further generation tests should not
proceed unless an upstream B1.9-style content signal is robust.**

**5. Causal meaning recovery.** A fully causal claim is **limited** — a fixed mapping cannot be physically
intervened on like a biological mechanism. **Partially measurable** through confound-controlled designs: hold
facet **wording** constant and swap only the phoneme→varṇa assignment; **vocabulary-matched** controls;
**varṇa-level ablation/permutation**; **held-out prospective words**; control for the **semantic genericness** of
the facet pool; preregistered **negative controls.** *Current status: not cleanly established. Honest prior:
low.* A positive result would mean the mapping **survives specific confounds** — **not** deep causal truth.

**6. Human-recognizable varṇa semantics.** Measurable via **blind human forced-choice matching**: show humans a
target/context and multiple facet sets (authentic + controls); ask whether they can identify the authentic /
best-fitting set **above chance.** No LLM generation, no LLM judging. *Current status: not yet tested. Honest
prior: low.* A positive result would support **human-recognizable semantic structure** — **not** ontology.

**7. Content-level semantic proximity / B1.9.** **Preregistered but not run.** Generation-free, judge-free.
Primary endpoint `delta_distance = d_control − d_auth`; positive means authentic facets are closer to
target/context than controls. A positive B1.9 would be **only a low-level mapping-proximity signal.** It would
**not** imply semantic truth, ontology, Sanskrit privilege, generation utility, or human-recognizable semantics.
A **robust** positive B1.9 could justify climbing to (a) the cross-system bake-off (privilege), (b) human
forced-choice (recognizability), (c) ablation/held-out designs (causal-ish robustness). A **null** B1.9 should
**stop or strongly deprioritize** further B-series utility testing.

## 4. Current evidence map

- **B1.4b′:** `NULL_RETURN_BOTTOM` (primitive attributions carry no recoverable meaning; the semantic-truth
  proxy is null).
- **B1.6:** 10-sample generation probe did **not** establish utility; the `specificity_to_target` lean was
  exploratory only.
- **B1.8:** context-resolved KCPR Layer-1 utility **null/negative** — tied with the scrambled selected-pole
  control, no gain over the unresolved both-poles scaffold, underperformed plain/generic/semantic baselines; the
  specificity thread is **confounded by a semantic-overlap control-design issue** (scramble not
  distance-controlled; the post-hoc clean-subset "flip" is a circular-selection artifact).
- **B1.9:** preregistered content-distance **gate**, runner mock-tested, **not run.**

## 5. Gating logic

- **If B1.9 is null:** stop or strongly deprioritize further B-series utility testing.
- **If B1.9 is weak:** do **not** climb to strong claims; improve controls first (distance-matched scramble,
  vocabulary matching).
- **If B1.9 is robust:** the next tests, in order, are —
  1. **cross-system bake-off** for Sanskrit privilege (claim 3);
  2. **human forced-choice** test for recognizability (claim 6);
  3. **confound-controlled ablation / held-out** tests for causal-ish robustness (claim 5).
- **Generation utility (claim 4) should NOT be re-run** unless the upstream content-level signal is robust.

## 6. Forbidden inferences

No B1.x result may infer **ontology**, **semantic truth**, **Sanskrit privilege**, **generation utility**,
**causal meaning recovery**, or **human-recognizable semantics** **unless the corresponding dedicated design
(above) has been run and passed.** In particular: no positive at a lower rung licenses a higher rung; `B1.9` ≠
privilege/utility/recognizability; and `ONTOLOGICAL_SIGNAL` / `GENUTILITY_*` are never emitted from any B1.x
result on the strength of a proxy or a lower-rung test.

## 7. Recommended next step

**B1.9 remains the next appropriate gate.** Do **not** run the B1.10 cross-system bake-off or the human
forced-choice test until B1.9 has a **robust positive** result. If B1.9 is null or weak, the honest action is to
stop or deprioritize, not to climb.

## 8. Guardrails

- No `ONTOLOGICAL_SIGNAL`; no `GENUTILITY_*`; no semantic-truth claim; no Sanskrit-privilege claim.
- No raw `run_out/` data committed. No experiment run; no embeddings computed.
- **B1.4b′ remains `NULL_RETURN_BOTTOM`**; original B1.4b blocked; Track B blocked. Structure, not validated meaning.

---

## Final report

- **File created:** `experiments/primitive_sequence_recovery/B1_X_CLAIMS_AND_MEASURABILITY_LADDER.md` (docs-only).
- **Commit hash:** recorded on the commit below.
- **Readiness label:** `B1_X_CLAIMS_MEASURABILITY_LADDER_READY`.
- **No experiment was run** (no embeddings, no generation, no judging).
- **No raw `run_out/` data committed.**
- **B1.9 remains preregistered and not run.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

B1.x claims-and-measurability ladder committed docs-only. No experiment run. B1.9 remains preregistered and not
run. No raw run_out data committed. No GENUTILITY terminal label. No ONTOLOGICAL_SIGNAL. B1.4b′ remains
NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track B remains blocked. Structure, not validated meaning.
