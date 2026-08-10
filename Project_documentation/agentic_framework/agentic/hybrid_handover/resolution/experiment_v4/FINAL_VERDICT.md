# FINAL_VERDICT — Governance Semantics Experiment v0.1

**Resolver under test:** HybridRelationshipResolver Experimental v0.4
**Corpus:** Hidden Relationship Corpus Pilot v0.2 (60 cases)
**Lock:** `a14c3ba00b819278ee5b295a80662e4c998b6ebe73e1f22d487770607a582273`

---

## Verdict: **NO CLEAR SIGNAL** (full layer) — operative-source selection is a clean, causally isolated mechanism worth further research

The full Governance Semantics Layer (G4) does not earn PROMISING: its headline selective
gain (+0.2312) is coverage-driven (coverage 0.95 → 0.28; false-abstention 0 → 0.5) and it
violates three non-inferiority constraints. Under the preregistered rule — a gain driven
mainly by abstention/coverage reduction is NO CLEAR SIGNAL — that is the verdict for the
primary G4-vs-G0 endpoint. It is not FALSIFIED (no protected-stage identity broke, unsafe
did not increase, and the isolated mechanism helps). And the experiment is not null: the
ablation ladder cleanly isolates **operative-source selection (G3)** as a +0.088 selective
improvement with all non-inferiority satisfied and coverage held fixed — 5 fixes, 0 breaks
on exactly the competing-authority cases the v0.3 diagnostic predicted.

### One-paragraph story
Holding discovery, classification, validation, and packet Mode P bit-identical, and pinning
the governing set to the frozen set, the layer changed only which governing node the frozen
packet reads (the operative source) and when to abstain. Operative-source selection alone
(G3) fixed five competing-authority cases — including the `parallel_overrides` case Edge
Prioritization v0.3 broke — by reading the termination term from the prohibition-bearing
clause instead of the highest-authority clause. The full layer (G4) then added a
governance-abstention rule that over-fires on any prohibition/permission co-occurrence,
collapsing coverage and inflating selective accuracy artificially. The mechanism works; the
abstention rule as specified does not.

---

## The ten final questions

**1. Did explicit governance semantics improve selective accuracy?**
**Partially.** Operative-source selection (G3) improved it cleanly by +0.088 (0.298 →
0.386) with coverage held fixed. The full layer's larger jump (G4, +0.231) is a coverage
artifact and does not count.

**2. Did the layer correctly distinguish supersession from parallel applicability?**
**In the cases that changed, yes.** The five G3 fixes span both supersession/migration
(`policy_migration`) and parallel authority (`parallel_overrides`); reading the operative
term from the answer-bearing clause resolved both families correctly, with no breaks.

**3. Did separating the authority source from the operative source improve decisions?**
**Yes — this is the experiment's clean positive result.** G3 is exactly that separation:
5 fixes, 0 breaks, every other metric unchanged. It directly confirms the v0.3 diagnostic.

**4. How many decisions were fixed, broken, and unchanged?**
G3 vs G0: **5 fixed, 0 broken**, 17 unchanged-correct, 35 unchanged-incorrect. G4 vs G0 on
the answered set: 5 fixed, 0 broken, 4 unchanged-correct, 8 unchanged-incorrect (the rest
became abstentions).

**5. Were gains caused by semantic applicability rather than discovery, validation,
prioritization, packet changes, or increased abstention?**
**For G3, yes** — discovery/classification/validation/Mode P are bit-identical and coverage
is unchanged, so its +0.088 is pure operative-source semantics. **For G4's extra gain, no**
— it is driven by increased abstention (coverage reduction), which is precisely why the
full-layer verdict is NO CLEAR SIGNAL.

**6. Did all protected-stage and safety constraints pass?**
**Protected-stage identity: yes** (discovery, classification, validation, Mode P identical
across G0–G4; unsafe answers unchanged at 2). **Non-inferiority: G3 yes, G4 no** (G4
violates Mode G, coverage, and false-abstention).

**7. Is frozen governance now demonstrated to be the active architectural bottleneck?**
**Yes.** Changing only a governance sub-decision (operative-source selection), with every
other stage frozen, fixed five cases and broke none. That isolates frozen governance's
operative-source heuristic as the binding constraint on those cases — the first direct
demonstration in the series.

**8. Is the experimental Governance Semantics Layer justified for further research?**
**Yes — specifically the operative-source component.** It is a clean, non-inferior, causally
supported mechanism. The governance-abstention component is not justified as specified and
needs redesign (it over-abstains).

**9. Should it be promoted into the frozen resolver architecture?**
**No.** The frozen architecture is not changed regardless of outcome, and independently the
evidence does not warrant promotion: the clean effect is modest (+0.088, 5 cases, p bounded
by n=60), and the full layer regresses coverage.

**10. Is there sufficient evidence to claim broad relationship-governance generalization?**
**No.** Sixty synthetic cases are a pilot; the clean effect rests on five cases. No
generalization claim is supported.

---

## Series arc
- **v0.1** richer discovery — recall/F1/classification up; precision + selective violations.
- **v0.2** proposal validation — precision recovered at zero recall cost; selective flat.
- **v0.3** edge prioritization — decisions changed but net-zero; diagnosis: the bottleneck
  is governance *semantics* / operative-term location.
- **v0.4** governance semantics — **confirms that diagnosis**: operative-source selection
  cleanly fixes the competing-authority cases (G3), while the full layer's abstention rule
  over-fires (G4). The active bottleneck is now demonstrated, and the next lever is
  identified: a precise (non-over-firing) governance representation for competing operatives.

## Interpretation boundary
Even the clean G3 result supports only: *a deterministic operative-source-selection rule
improved selective accuracy on five competing-authority cases of the 60-case Hidden
Relationship Corpus Pilot v0.2.* It does not establish enterprise readiness, broad
generalization, production safety, real-document correctness, certification, or RRB v1.0.

## Status
HybridRelationshipResolver **Experimental v0.4** — NO CLEAR SIGNAL (full layer); operative
selection worth further research. Frozen architecture unchanged. Not promoted.
