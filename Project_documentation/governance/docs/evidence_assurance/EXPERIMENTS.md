# Correlated-Failure & Missing-Metadata Experiments (Phases 15–16)

*`evidence_assurance/experiments.py` → `eval_results/experiments_v1.json`. Deterministic. Two studies:
how the reference component behaves across correlated-failure mechanisms (15), and how it degrades as
observed metadata disappears (16). The endpoint that matters is **escape** — delivering a
gold-unsupported claim as supported. Abstention (`INDETERMINATE`) is a *safe* outcome, not a failure.*

## Phase 15 — correlated-failure scenarios

23 scenarios: the 11 failure types embedded in the corpus + a clean control, 8 adversarial variants
that fabricate observed diversity over the trap cases, an all-out fabrication including the upstream
signal, and one **constructed no-tell case** that the corpus cannot contain.

| Scenario | n | escape | indeterminate |
|---|--:|--:|--:|
| clean control | 52 | 0.000 | 0.000 |
| T1 shared-bad-retrieval … T29 official-superseded (11 types) | 52 ea | 0.000 | 0.000–0.250 |
| S13–S20 fake publisher / retrieval / provconf / hashes / years / authority / all (no upstream) | 156 ea | 0.000 | 0.083 |
| S21 fake upstream roots + high provenance confidence | 156 | 0.000 | 0.083 |
| S22 fake everything **including** upstream | 156 | 0.000 | 0.083 |
| **S23 no-tell correlated failure (constructed)** | 80 | **1.000** | 0.000 |

### What the corpus scenarios show (0 escape) — and the honest caveat

Every corpus and fabrication scenario yields **zero escape**, including S21/S22 where the load-bearing
`observed_upstream_ids` signal and `observed_provenance_confidence` are fabricated to look fully
independent. That is because **every trap case in `ea_corpus_v1_1` carries at least one observable
tell**: either the 10% NLI-proxy noise flips its passage-alignment signal, or it has discoverable
counterevidence. We verified this directly — the count of trap cases that pass alignment *and* have no
counterevidence is **0**. So the component never needs the independence layer to be un-fooled; a
second tell always catches the case.

This means the corpus's clean 0-escape **overstates** what independence-checking alone buys. The
component is robust *on this corpus* because the corpus's correlated failures are all detectable by
*some* layer — not because fabricated provenance is defeated by the independence layer (S21/S22 show
the independence layer *is* fooled; alignment/counterevidence carry those cases).

### S23 — the honest ceiling (100% escape)

S23 constructs the case the corpus omits: a claim that is **false**, but whose every observable signal
says supported — passage aligned (no NLI tell), **no** discoverable counterevidence, and fabricated
independent provenance. The component escapes **100%**. This is taxonomy types 23/30 (model consensus
on a false premise, shared training-data contamination): the dependence and the error live entirely
*outside* the evidence record. **No metadata-based method can catch a failure that leaves no metadata
trace** — and this component is a metadata-based method. Its value is real but bounded: it catches
correlated failures that leave *a* tell (alignment, counterevidence, or provenance dependence), and it
cannot catch those that leave none. Those require independent human or external verification (Phase 23),
not more metadata analysis.

## Phase 16 — missing-metadata degradation

Observed provenance metadata (publishers, domains, retrieval paths, upstream ids, content hashes,
provenance confidence) is dropped for a ρ fraction of cases; a dropped case has those fields emptied
and `metadata_complete=False`.

| missingness ρ | escape | false block | indeterminate |
|--:|--:|--:|--:|
| 0.00 | 0.000 | 0.114 | 0.021 |
| 0.10 | 0.000 | 0.220 | 0.074 |
| 0.20 | 0.000 | 0.303 | 0.112 |
| 0.30 | 0.000 | 0.417 | 0.162 |
| 0.40 | 0.000 | 0.492 | 0.199 |
| 0.50 | 0.000 | 0.591 | 0.250 |
| 0.60 | 0.000 | 0.651 | 0.287 |
| 0.70 | 0.000 | 0.758 | 0.335 |

**The degradation is safe, not silent.** As metadata disappears, **escape stays at 0.000** while
`INDETERMINATE` (abstention) and false-block both climb. The component responds to missing provenance
by refusing to certify (`missing_provenance → INDETERMINATE`), never by guessing "supported." The cost
is availability — at 70% missingness, 76% of genuinely-supported claims are withheld and a third of all
cases are abstained — but the safety endpoint holds. This is the intended failure mode: under
uncertainty, withhold. A production deployment would treat rising abstention as a data-quality alarm,
not silently ship unsupported claims.

## Reading both phases together

- **Where the component works:** correlated failures that leave an observable tell — a misaligned
  passage, discoverable counterevidence, or detectable provenance dependence. On the corpus, that is
  100% of them, so escape is 0.
- **Where it cannot work:** no-tell correlated failure (S23) and, equivalently, metadata that is
  simply absent (Phase 16, where it abstains rather than escapes). The first is unsafe if trusted; the
  second is safe because the component knows it doesn't know.
- **The design line that matters:** the component never converts *absence of evidence of dependence*
  into *evidence of independence*. Missing or untrusted provenance → `INDETERMINATE`, not `VERIFIED`.
  That single rule is what keeps escape at 0 everywhere except the case where the failure is, by
  construction, unobservable.
