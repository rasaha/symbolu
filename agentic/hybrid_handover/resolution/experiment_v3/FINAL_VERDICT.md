# FINAL_VERDICT — Edge Prioritization Experiment v0.1

**Resolver under test:** HybridRelationshipResolver Experimental v0.3
**Corpus:** Hidden Relationship Corpus Pilot v0.2 (60 cases)
**Lock:** `a36cadd8070d6880b6fe2b30a8a76370fb143f1d7eafbcb80049f3f713fc8db8`

---

## Verdict: **NO CLEAR SIGNAL**

A deterministic Edge Prioritization layer re-ranked competing governance sources and
changed real governance decisions, but the changes cancelled and selective accuracy
did not move. No protected metric degraded, so the layer is not falsified — it is
simply inert, on this pilot, as a net contributor to decision quality.

### One-paragraph story
Holding proposal generation and validation bit-identical to v0.2, and touching only the
ordering of the graph handed to the frozen governance in the full pipeline, the
prioritizer fired on the 3 hidden cases that contain competing governance sources. In
each, the **authority** component (later / higher instrument) decided the winner. Two
of those reorderings changed the final answer: one fixed a policy-migration case
(`unknown` → correct `prohibited`) and one broke a parallel-overrides case (correct
`prohibited` → `unknown`). Net selective accuracy change: 0.0 (McNemar 1 fix / 1 break,
p=1.0). Discovery, classification, governance Mode G, packet Mode P, and unsafe answers
are all identical to v0.2 — guaranteed by construction and confirmed empirically. P0–P4
are indistinguishable because authority alone is decisive in every competition.

---

## The six final questions

**1. How many competing edges were reprioritized?**
**3** — one per hidden case that contains ≥2 competing governance sources
(`HX59d7a3eb1c`, `HXb3def36e76`, `HPb167985bd5`). All three were decided by the
authority component. Everywhere else the layer is a strict no-op.

**2. How many governance decisions changed?**
**2** full-pipeline decisions changed (P4 vs P0). The third reprioritization did not
alter the final governance outcome.

**3. Did selective accuracy improve?**
**No.** 0.2982 → 0.2982. The two changed decisions cancel exactly — one fix
(policy migration), one break (parallel overrides) — for a net of zero (McNemar
p=1.0).

**4. Was any discovery performance lost?**
**No.** Discovery precision (0.8974), recall (0.4167), and classification (0.9143) are
unchanged, as are governance Mode G (0.60), packet Mode P (0.5167), and unsafe answers
(2). The layer cannot touch these by construction: it never alters the discovery graph
and never runs in Mode G / Mode P.

**5. Is prioritization now the dominant remaining bottleneck?**
**No.** The wash is the evidence: reordering competing governance sources is *not* what
stands between the resolver and better decisions. The remaining bottleneck is
**semantic** — deciding which competing instrument carries the operative term
(supersession vs parallel authority) — and that lives in the frozen governance and
packet builder, which this experiment is forbidden to change. Edge ordering is too
coarse an instrument to separate the fix case from the break case.

**6. Should Edge Prioritization become part of the frozen resolver architecture?**
**No.** Per the experiment's constraint the frozen architecture is not changed
regardless of outcome. Independently, the evidence does not justify promotion: zero net
benefit on the primary endpoint, a real regression on one case, and an effect confined
to 3 of 60 cases. Promotion would add machinery and a new failure mode (the parallel-
authority break) for no measured gain.

---

## Where the series stands
- **v0.1** — richer discovery: large recall/F1/classification gain, but precision and
  selective non-inferiority violations.
- **v0.2** — proposal validation: recovered precision (+0.083) at zero recall cost;
  selective flat.
- **v0.3** — edge prioritization: no selective gain; net-zero decision change; no
  protected-metric loss.

Two successive layers (validation, prioritization) have now improved or preserved every
*structural* metric without moving *selective accuracy*. The consistent signal across
v0.2 and v0.3 is that the remaining ceiling is in the **frozen governance/packet
semantics** for competing authorities — not in proposal, validation, or ordering. That
is the honest pointer for any future work, and it is out of scope here.

## Status
HybridRelationshipResolver **Experimental v0.3** — no clear signal, not promoted.
Frozen architecture unchanged. Not production-ready. Not RRB v1.0.
