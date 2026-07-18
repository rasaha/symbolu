# Token / Context Compression — Logic Evaluation

**Status:** Internal evaluation. Not a VC brief, not a claim of results.
**Question evaluated:** Is the "Ugence ContextGuard / Protected Context Compression"
logic (as outlined by ChatGPT and pasted into the task) sound, and do Symbolu's
existing components actually support it?
**Verdict in one line:** The *direction* is defensible and one metric is genuinely
novel-for-us; the *reuse claims* are partly category errors; nothing here proves an
advantage yet, and it must not be presented as if it does.

---

## 0 · What was actually checked in this repo

The ChatGPT outputs assert that existing formulas (SCC/coherence, USE, BCVF,
ActionGate, KVPro/INT4) "could contribute." Before evaluating the compression
logic, each reuse claim was grounded against the code, not the description.

| Component referenced | Exists in repo? | What it actually is | Reuse claim status |
|---|---|---|---|
| **ActionGate** | **Yes, as running code** — `cyber_security/action_gateway/` | Deterministic enforcement gate over a canonical **24-field action envelope**; JCS-canonicalized, hashed, evaluated by a frozen `gate.evaluate` (`gateway.py`, `mapping.py`) | **Strongest claim. Grounded.** The "decision-invariance" idea is real *because the decision is a real deterministic function.* |
| **KVPro / INT4** | Yes, as **VC briefs** (`KVPro_VC_brief.md`, `INT4_PROTECTED_VC_BRIEF.md`) | Quality-safe **KV-cache** compression *after* tokenization; "protected" values + WarmTier snapshot/restore | **Analogy is fair, complementarity is correct.** KVPro cannot reduce input tokens; it is orthogonal, not a substitute. |
| **BCVF** | Yes, as code — `cyber_security/behavioral_biometrics/study/bcvf.py` | Uncertainty-normalized disagreement between **two structurally distinct estimators of the same latent identity**, with a hard eligibility guard and a preregistered kill criterion | **Overstated.** BCVF is identity-biometric-specific and deliberately narrow. Reusing the *pattern* (two independent estimators must agree) is fine; invoking *BCVF itself* is a name-transplant, not a reuse. |
| **SCC / coherence** | **Not found as an implemented formula** (only prose) | — | **Unsupported.** Do not cite as an existing asset. |
| **USE / cross-source coupling** | **Not found as an implemented formula** (only prose) | — | **Unsupported.** Do not cite as an existing asset. |

Bottom line on reuse: **one grounded strong asset (ActionGate), one fair analogy
(KVPro), one narrow-but-adaptable pattern (BCVF), and two components that are
currently just names.** Any external framing that lists all five as "our existing
math applied to compression" would be inaccurate.

---

## 1 · Is the compression logic itself sound?

### 1.1 What ChatGPT got right

- **Separating a hard-constraint set from a weighted score is the correct core
  insight.** A pure `max Σ Iᵢ s.t. Σ tokens ≤ B` knapsack is dangerous: a high
  relevance score can "pay for" deleting a single `not`, an amount, or an
  authorization condition. Making a protected set `P0 ⊆ K` a *hard* constraint of
  the optimization — not a term in the objective — is the right formulation. This
  is the one non-obvious modeling decision and it is correct.

- **The three-layer decomposition is the right build order.** Deterministic
  structural compression (dedup, boilerplate, schema collapse, reference
  substitution) first, because it is transparent and testable; query-aware
  semantic selection second; preservation validation last with **fail-closed /
  reduce-ratio** behavior. Ordering the *provably safe* layer first is correct and
  is also the only layer worth shipping early.

- **The KVPro complementarity is arithmetically correct.** Fewer input tokens ×
  fewer KV bytes per retained token compound. They are orthogonal savings. The
  claim "process 12k instead of 20k, then store those 12k in INT4" is valid.

- **The caution against deriving importance from KV magnitude / attention is
  correct and important.** Activation magnitude ≠ semantic criticality; a 6-token
  negation can outweigh 2,000 tokens of history. ChatGPT explicitly warned against
  this shortcut. Keep that warning.

### 1.2 Where the logic is weak, hand-wavy, or unproven

1. **The scoring terms (R, N, C, D, U, S, X) are undefined operators.** Each is a
   research problem, not a coefficient. "Constraint importance C" and "consequence
   significance S" in particular presuppose a working constraint/entity/negation
   extractor. **The extractor is the product.** The weighted sum is the easy part;
   the paper's hard 90% is building extractors whose *recall of protected units is
   provably ≈ 1.* ChatGPT's formula hides this behind Greek letters.

2. **"Retain all hard constraints, entities, quantities, negations, exceptions,
   approvals, citations, dependency anchors" is stated as if detection were free.**
   It is not. If the detector misses one negation, the whole safety story
   collapses — and a missed-negation failure is exactly the failure mode that a
   weighted-average benchmark (EM/F1) will *not* surface, because it is rare and
   catastrophic rather than frequent and small. **The preservation metric must be
   worst-case recall of protected units, not average task quality.**

3. **"Meaning-protected (P1) may be shortened but propositions must remain
   unchanged" is not yet an operationalizable predicate.** "Propositions
   unchanged" requires an entailment/NLI check that is itself an LLM call —
   which reintroduces cost, latency, and its own error rate into the compressor.
   This is where the "compressor overhead erases the gains outside the right
   operating region" risk (which ChatGPT correctly flagged) actually bites.

4. **BCVF-style dual-estimator validation is being invoked at the wrong layer.**
   In its real form BCVF compares two *independent estimators of one latent*, with
   an eligibility guard that both must independently show signal, and a kill
   criterion measured as incremental AUC. Transplanting it to "extractor A vs
   extractor B agree on retained propositions" is *plausible as a pattern* but
   inherits none of BCVF's validation — it would need its own preregistration and
   its own kill criterion. Calling it "BCVF" imports credibility it hasn't earned
   in this domain.

### 1.3 The one genuinely differentiated, testable idea

Everything above is shared with LLMLingua-2 / Selective Context / Bear-2. The
single thing Symbolu can state that they structurally cannot is:

> **ActionGate decision invariance:** `D(envelope(C_original)) == D(envelope(C_compressed))`

This is not hand-waving *here specifically*, because `D` is a real deterministic
function in this repo: a request is mapped to a canonical 24-field envelope
(`mapping.build_envelope`), canonicalized, hashed, and evaluated by a frozen gate
(`gateway.py`). That means decision invariance is **exactly measurable, offline,
with zero LLM in the loop** — you can compute both dispositions and check
equality. No competitor that lacks an admissibility oracle can even define this
metric. **This is the defensible wedge, and it is the part worth building a
benchmark around first** — precisely because it is the cheapest to measure and the
hardest for others to copy.

Caveat: it is only as meaningful as the envelope's coverage. If a compressed fact
never influences any of the 24 envelope fields, invariance is trivially true and
proves nothing. So the honest metric is: *decision invariance on a task
distribution deliberately seeded with context that changes envelope fields
(amounts, approvals, reversibility, policy version, state freshness).*

---

## 2 · Does any of this prove an advantage? No.

Consistent with the repo's own culture (preregistration, falsification, kill
criteria), the correct current claim is:

- **Buildable:** yes.
- **Formulas already prove an edge:** no. Zero measurements exist.
- **Differentiated *if* focused on action/policy-preserving compression:** yes,
  via decision invariance — but that is a hypothesis, not a result.
- **Risk of being a worse LLMLingua-2:** high, if built as generic
  "delete low-signal tokens."

The failure mode to avoid is shipping a VC brief that lists SCC/USE/BCVF/ActionGate/
KVPro as "applied math" before a single benchmark row exists. That would be
inconsistent with how `ACTIONGATE_VC_BRIEF.md` and the KVPro brief already
discipline themselves ("measured" vs "modeled" vs "projected").

---

## 3 · Minimal falsifiable experiment (before any brief)

Preregister this, in the style of the repo's `MILESTONE_A_PRIME_PREREGISTRATION`:

**H1 (safe layer).** Deterministic structural compression (dedup + boilerplate +
schema collapse + reference substitution) achieves ≥ X% token reduction with
**exact** preservation of protected units (recall = 1.0 by construction, since it
only removes provable duplicates/boilerplate). — *This is the shippable core and
should be validated on its own first.*

**H2 (decision invariance).** On a task set seeded so context influences envelope
fields, semantic compression at ratio ρ holds
`D(C_orig) == D(C_comp)` at rate ≥ 1 − ε, and **strictly beats LLMLingua-2 at the
same ρ** on this metric. — *This is the differentiation claim.*

**Kill criterion (mirror BCVF's discipline).** The action-aware compressor is
unsupported unless, at matched token reduction, it (a) does **not** worsen
decision-invariance vs generic compression, and (b) achieves worst-case
protected-unit recall ≥ generic + a preregistered margin, **without** compressor
overhead erasing end-to-end latency/cost gains in the target operating region.

**Required baselines** (all named by ChatGPT, keep them): no-compression, naive
truncation, extractive summarization, LLMLingua-2, Selective Context, top-k RAG
rerank; Bear-2 only if API access exists.

**Required metrics** (the non-negotiable additions over generic benchmarks):
worst-case protected-unit recall, numeric fidelity (exact), entity-binding
fidelity, **ActionGate decision-invariance rate**, plus the standard
token-reduction / task-quality / latency / cost / break-even columns.

---

## 4 · Recommendation

1. **Build the P0/P1/P2 tiering and the deterministic structural layer only,
   first.** It is the sole layer that can claim recall = 1.0 by construction and is
   the cheapest to test. Ship nothing semantic until it passes.
2. **Adopt "ActionGate decision invariance" as the headline metric, not average
   task quality.** It is the one thing this codebase can measure that competitors
   cannot define.
3. **Drop SCC and USE from any asset list** until an implemented formula exists;
   present BCVF-reuse only as an *analogous validation pattern requiring its own
   preregistration*, never as BCVF itself.
4. **Keep KVPro strictly as a complementary downstream layer**, described as
   orthogonal savings, never as part of the input-token reduction claim.
5. **Do not write a VC brief for this yet.** Write the preregistration and run H1.

---

*Scope note: this document evaluates logic and reuse claims only. It reports no
benchmark results because none have been run. Any figure needed for an external
brief must come from the H1/H2 experiment above, marked measured/modeled/projected
per repo convention.*
