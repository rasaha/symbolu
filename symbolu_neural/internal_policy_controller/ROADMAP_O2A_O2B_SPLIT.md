# Roadmap refinement: split O2 into O2A (Semantic Reading) and O2B (Policy Translation)

> **Type:** architecture roadmap. **No code. No v5.** Forward-looking only.
> **Lineage:** follows the v3 gate-valid null, the v4 high-fidelity null, the root-cause
> audit (first bottleneck = state extraction), the theory-vs-implementation audit (the
> controller used the self-declared *non-semantic* `vritti_mapper` as the primary signal
> and discarded the `varna_lens` semantic reading), and the omission roadmap.

## Why split

The previous **O2 — "wire the full varṇa chain into the policy"** conflated two
*independent* hypotheses, each of which can fail on its own:

- **H-reading:** Symbol-U produces a *meaningful semantic representation* of a sentence.
- **H-policy:** that representation can be *translated into instructions that improve an LLM's answer.*

H-reading is testable **fully offline** (deterministic, no API, no judge), which removes
every confound that contaminated v3/v4: judge position-bias, 512-token truncation, the
LLM's "just reformat the draft" behavior, and length effects. H-policy is only worth
testing **after** H-reading earns it.

---

## O2A — Semantic Reading ρ (offline; no policy, no LLM)

`sentence → varṇa decomposition → varṇa chain → essence/pole interactions → semantic reading → STOP`

**What the reading contains (description, not prescription):** dominant tendencies
(pole/essence profile), internal tension (binding↔liberating conflict), continuous
valence (graded + signed), coherence/confidence (concentrated vs conflicted), and
competing interpretations when present. It contains **no** tone/pace/caution
instructions — those are policy (O2B).

**Components (essential vs optional):**

| Component | Status in O2A |
|---|---|
| Full varṇa essence/pole chain | **essential** |
| Continuous emergent valence | **essential** |
| Tension / coherence summary | **essential** (new) |
| Positional composition (O3) | optional enrichment |
| CSR (O5) | conceptually in-scope, **deferred** (neural-infra-blocked; must not gate O2A) |
| Hierarchical emergence (O7) | optional/research |

**Design rule:** CSR belongs in the *intended* reading but must **not** block O2A, or
O2A inherits O5's neural dependency and stops being offline. Build the varṇa-chain
reading first; add CSR later as a measurable enrichment.

## O2B — Policy Translation (only if O2A passes)

`reading ρ → policy → prompt → LLM → answer`

- **Influences policy:** dominant tendency, tension, valence, confidence → behavioral
  axes (tone, caution, speculation, hedging). Confidence may *gate strength*.
- **Never injected at the LLM:** raw varṇa keys, IAST, essence glosses, CSR internals
  (the v4 trace showed dense ontology jargon → the LLM reformats and even fabricates).
- **Preserve vs summarize:** two-sided trap — too collapsed (v3) → constant generic
  policy; too raw (v4) → reformatting + fabrication. Target = natural behavioral
  instructions that still change substantially under relabel.
- **Translator fidelity check (pre-API):** relabel field/token divergence,
  divergence-from-generic, and mutual information(reading→policy) > 0.

---

## A. Revised dependency graph

```
O2A  Semantic Reading ρ  (offline, no LLM)                     [Easy–Moderate]
  ├── needs: varṇa chain (O2 data, already computed by analyze()), continuous valence (O1),
  │          tension/coherence summary
  ├── optional enrichments, each separately testable: O3 positional · O5 CSR · O7 hierarchy
  └── GATE (offline, pre-registered): discrimination > sentiment baseline · paraphrase
            stability · non-redundancy · human recoverability · generalization
         │   FAIL → STOP (policy program unsupported; no API spent)
         ▼
O2B  Policy Translation  (reading → policy → prompt → LLM → judge)   [Moderate]
  ├── needs: O2A PASSED + the existing gate-valid pairwise harness (v3/v4)
  └── GATE (pre-API): translator fidelity (relabel divergence, MI) → then quality test
```

## B. Implementation priorities
1. **O2A** (new milestone #1; absorbs old O1/O4 as components)
2. O2B (only after O2A passes its offline gate)
3. O3 / O5 / O7 as enrichments to O2A, each justified by marginal offline gain

## C. Scientific priorities
1. **O2A** — the more fundamental question and precondition for all else (raised above
   its prior rank).
2. CSR (O5) — deepest causal layer, still infra-blocked; reframed as an O2A enrichment.
3. O2B — important but downstream and LLM/judge-confounded.

## D. Offline evaluation criteria for O2A
See `O2A_OFFLINE_EVALUATION_PROTOCOL.md` (pre-registered). Pass requires **all** of:
discrimination above a sentiment baseline, paraphrase stability with meaning-separation,
non-redundant (orthogonal) variance, human recoverability, and generalization to
out-of-lexicon inputs. Any single failure → O2A fails and **O2B is not built**.

## E. Offline evaluation criteria for O2B
Before any API: relabel field/token divergence materially above v3/v4,
divergence-from-generic high, mutual-information(reading→policy) > 0. Only then spend
credits on the already-validated gate-valid pairwise test.

## F. Recommendation

**O2A replaces O2 as milestone #1 — unambiguously.** It isolates the real question,
costs no API, runs in minutes, and is a hard falsification gate: if the reading cannot
separate joy from grief above a sentiment dictionary or flips under paraphrase, the
entire Symbol-U-as-policy program is unsupported and we stop *before* O2B.

**Adversarial prior (not optimistic):** my genuine expectation is that the reading shows
*some* real discrimination but is **largely redundant with ordinary sentiment** and
**partly circular** (the glosses are hand-authored "gauge choices," not empirically
validated), so its non-redundant, generalizing signal may be small. The offline metrics
are designed to expose exactly that. O2A earns milestone #1 precisely because it can kill
the program cheaply if the program deserves to die.
