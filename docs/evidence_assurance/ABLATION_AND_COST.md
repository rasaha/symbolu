# Ablation, Cost, and the Complexity Question (Phases 17–19)

*`evidence_assurance/eval_ablation.py` → `eval_results/ablation_v1.json`. Is the six-layer stack
justified, or is it complexity for its own sake? The honest answer: **on benign data one layer
suffices for the safety endpoint; the full stack earns its keep only against an adversary who
fabricates provenance.***

## Phase 17 — cost proxy

Wall-clock timing is non-deterministic, so cost is a **probe count**: metadata reads / search
strategies per layer. Comparable across configurations.

| Layer | probes | why |
|---|--:|---|
| counterevidence | 9 | runs the strategy set (the expensive layer) |
| provenance | 3 | upstream ids, content hashes, retrieval paths |
| independence | 2 | verdict over the provenance graph |
| alignment | 2 | passage + scope/temporal/jurisdiction |
| authority | 1 | authority class × risk |
| freshness | 1 | publication years |
| **full stack** | **18** | |

## Phase 18 — leave-one-out ablation (ea_corpus_v1_1)

| Config | cf-escape | overall escape | false block | accuracy | cost |
|---|--:|--:|--:|--:|--:|
| FULL | 0.000 | 0.000 | 0.114 | 0.768 | 18 |
| −alignment | 0.000 | 0.106 | 0.000 | 0.667 | 16 |
| −counterevidence | 0.000 | 0.085 | 0.114 | 0.635 | 9 |
| −provenance | 0.000 | 0.000 | 0.114 | 0.768 | 15 |
| −authority | 0.000 | 0.039 | 0.114 | 0.737 | 17 |
| −freshness | 0.000 | 0.106 | 0.114 | 0.601 | 17 |
| −independence | 0.000 | 0.106 | 0.114 | 0.684 | 16 |

**No single layer is individually necessary for zero correlated-failure escape.** Remove any one and
cf-escape stays 0 — because (Phase 15) every trap case in the corpus carries *more than one* tell, so a
second layer catches what the removed one would have. But each layer owns a distinct slice of the
*other* failure modes: dropping alignment lets misaligned claims through (overall escape 0 → 0.106) but
removes the NLI-noise false-blocks (0.114 → 0.000); dropping freshness collapses staleness accuracy
(0.768 → 0.601); dropping independence raises overall escape to 0.106. Ablation confirms the layers are
**complementary across evidence-failure types**, not redundant contributors to one number.

## Phase 19a — minimal sufficient subset on benign data

Greedy removal targeting zero cf-escape at lowest cost returns **`independence` alone** (2 probes vs
18): on the unattacked corpus, every trap case is `DUPLICATE`/`UNKNOWN`, so the independence verdict
alone refuses them all. **But that subset also lets overall escape rise to 0.366** — it misses stale,
conflicted, and misaligned claims that ride on genuinely independent sources. So "independence alone"
is sufficient for the *correlated-failure* endpoint on benign data and *insufficient* for evidence
verification in general.

## Phase 19b — defense in depth: why the full stack exists

Take the trap cases and let an adversary fabricate **all** provenance metadata — distinct upstream
ids, distinct content hashes, six publishers, high provenance confidence, reputable authority, fresh
dates — so the sources *look* fully independent and trustworthy.

| Subset | benign cf-escape | **fabricated** cf-escape | cost |
|---|--:|--:|--:|
| independence only | 0.000 | **0.500** | 2 |
| independence + alignment | 0.000 | 0.192 | 4 |
| independence + counterevidence | 0.000 | 0.250 | 11 |
| **FULL** | 0.000 | **0.000** | 18 |

Against a metadata-fabricating adversary, **independence alone leaks half the correlated failures** —
it believes the faked provenance. Alignment catches the ones whose passage doesn't actually support
the claim; counterevidence catches the ones with a discoverable contradiction; provenance-untrust
(→ INDETERMINATE) catches the rest. Only the full stack returns to zero. **This is the justification
for the complexity: it is not benign accuracy — it is adversarial robustness (defense in depth).**

## The honest complexity verdict

- If evidence metadata is **trustworthy**, a cheap independence check buys the correlated-failure
  safety endpoint; the rest of the stack is for covering other evidence-failure states.
- If evidence metadata can be **fabricated** — which is the exact threat model that motivates
  EvidenceAssurance — the redundant layers are load-bearing, and independence alone is unsafe (0.500
  escape).
- The greedy benign minimal-subset (`independence`, 2 probes) is therefore a **trap**: correct on the
  clean corpus, dangerous in deployment. We report it precisely so it cannot be quoted as "you only
  need one layer." You only need one layer *if you can trust the metadata* — and the reason this
  component exists is that you often cannot.
- **Ceiling reminder (Phase 15):** even the full stack escapes 100% on a no-tell correlated failure
  (a false claim with no observable trace). No amount of layering closes that; it needs external
  verification (Phase 23).
