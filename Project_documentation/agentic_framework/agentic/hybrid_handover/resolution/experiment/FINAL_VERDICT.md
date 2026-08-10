# FINAL_VERDICT — Exploratory Resolver Study v0.1

**Resolver under test:** HybridRelationshipResolver Experimental v0.1
**Corpus:** Hidden Relationship Corpus Pilot v0.2 (22 seed + 38 pilot = 60 cases)
**Primary endpoint:** hidden owner-clean macro
**Lock:** `d31c20580cda4beddc665a86e49db75fe61052552d29f5f2d4b36adfd8d797ec`

---

## Verdict: **PROMISING SIGNAL** (not non-inferior in current form)

The architecture produces a **measurable, statistically and practically significant
capability signal** on unseen wording, cleanly attributable to relationship
discovery — so it *is* worth further research. It is **not** a clean win: in its
current form it violates two preregistered non-inferiority constraints (discovery
precision and selective accuracy), because the broad proposal lexicon over-proposes
edges. The signal is real; the resolver is not yet safe to promote.

This is neither **NO CLEAR SIGNAL** (the macro gain is +0.0788 with a 95% CI of
[0.035, 0.131] excluding zero, and discovery-completeness McNemar p = 7.6e-05) nor
**FALSIFIED IN CURRENT FORM** (the improvement is large, broad, and reproducible).
It sits precisely at the study's stated purpose: *worth further research, not yet
proven.*

### The one-paragraph story
Holding the frozen governance and packet builder fixed and swapping in a richer
relationship-proposal layer raises the hidden owner-clean macro from 0.4973 to
0.5761. The gain comes entirely from discovery (recall 0.18 → 0.42, F1 0.30 → 0.55)
and the classification that rides on it (0.73 → 0.91); governance and packet are
byte-for-byte unchanged (McNemar n=0 discordant). The gain holds in both
independently authored wording families, at every difficulty level, on most
capabilities and edge types, and on the negative controls (where the hybrid is
*better*, 0.70 vs 0.47 — it does not hallucinate governance). The cost is precision:
the broad lexicon over-fires on varied wording, dropping discovery precision to 0.81
and nudging selective accuracy down 0.035. Crucially, unsafe/overconfident answers do
**not** increase (2 vs 2) and determinism holds. Ablation A1 shows the semantic
proposal layer is the sole driver; the confidence gate (A4) and provenance filter
(A5) are inert on this corpus.

---

## The six required questions

**Q1 — Is there a measurable capability signal beyond the deterministic baselines?**
**YES.** Hidden macro +0.0788 over GraphTraversal (0.5761 vs 0.4973), above the
preregistered 0.03 practical threshold; discovery F1 +0.248; classification +0.181.

**Q2 — Is the signal statistically distinguishable from noise under paired,
multiple-comparison-corrected testing?**
**YES.** Paired bootstrap 95% CI on the macro [0.035, 0.131] excludes zero. Exact
McNemar on discovery completeness: 18 fixes vs 1 break, p = 7.6e-05, and it is the
one endpoint that survives Holm correction across the stage family.

**Q3 — Is the signal attributable specifically to relationship reasoning (not
governance, packet, parser, or SafetyGate)?**
**YES.** Governance (Mode G) and packet (Mode P) are identical to GraphTraversal by
construction (frozen reuse; McNemar n=0 discordant), and parser/SafetyGate metrics are
excluded from the owner-clean macro. Ablation A1 removes the proposal layer and the
gain vanishes entirely. The signal is isolated to relationship discovery/classification.

**Q4 — Does it improve without sacrificing precision, abstention quality, safety, or
determinism (i.e. does it pass non-inferiority)?**
**NO.** Two frozen non-inferiority constraints are violated: discovery precision
−0.186 (margin 0.05) and selective accuracy −0.0351 (margin 0.03). The resolver
over-proposes edges. It does *not* regress on safety (unsafe answers 2 = 2,
false-abstention 0.0, missed-abstention actually improves 0.267 → 0.217) and
determinism holds — but the precision failure means the gain does not count as a clean
success under the preregistered rule.

**Q5 — Does the signal generalize across more than one wording/structural family and
across difficulty within the pilot?**
**YES (within this pilot only).** The gain is present in both the seed family
(+0.086) and the independently authored pilot family (+0.074), at all five difficulty
levels, and on the majority of capabilities and gold edge-types. A few capabilities
regress (`table_vs_text`, `hierarchical_governance`), left unfixed to avoid post-hoc
tuning.

**Q6 — Does the study demonstrate broad generalization / readiness for certification
or production?**
**NO — a priori and after the fact.** Sixty synthetic cases are a *pilot*, not a
certification corpus. Slice sizes are 2–13 cases and are descriptive only; no
per-slice hypothesis test is claimed. This result licenses *further research*, not a
production claim, an RRB v1.0, or any statement of broad generalization.

---

## What a follow-up should do
1. **Fix the precision leak first** — a precision-oriented proposal gate (e.g.
   requiring corroborating structural signal before emitting broad-lexicon edges),
   re-validated on the visible corpus, then re-locked and re-run on the hidden pilot.
2. Investigate the `table_vs_text` over-proposal specifically (a spurious table/text
   conflict edge) and the `hierarchical_governance` regression.
3. Only after non-inferiority is met, consider a larger, adversarially curated hidden
   corpus before any generalization claim.

**Status:** HybridRelationshipResolver Experimental v0.1 — promising, not promoted.
Not production-ready. Not RRB v1.0.
