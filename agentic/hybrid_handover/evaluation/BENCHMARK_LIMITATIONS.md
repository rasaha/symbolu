# Benchmark Limitations — SEEB v1.0.0

Honest audit of the benchmark itself (Phase A). These are properties of the
**evaluation artifact**, not of any extractor. They are documented, not fixed —
fixing them would change the benchmark and break comparability. Each carries a
proposed Version 2 mitigation.

> The benchmark is a **research instrument with known biases**. It is trustworthy
> for *relative* comparison of extractors under identical conditions. It is NOT a
> measure of real-world enterprise efficacy.

## A. Audit findings — potential bias toward the current baseline

| # | Finding | Type | Effect | V2 mitigation |
|---|---|---|---|---|
| A1 | Validators and metrics hard-code contract-termination vocabulary (`terminate for convenience`, `fee`, `month`, a fixed defeater-term list, OCR hints) | Domain / evaluator leakage | Benchmark favours extractors surfacing this domain's terms; a cross-domain extractor is judged by contract-specific validators | Parameterise domain lexicons; supply per-corpus term sets |
| A2 | Packet Sufficiency is computed with the **extractor's own `resolve()`** as the downstream reasoner | Evaluator leakage | Conflates extraction with the extractor's reasoning; a weak/absent `resolve()` lowers sufficiency for reasons unrelated to packet completeness | Use an independent reference reasoner (or a frozen frontier stub) as the oracle |
| A3 | `ContradictionSearchValidator` is itself a keyword system | Evaluator ceiling | It can only catch defeaters phrased with its term list; definitional conflicts are invisible to it (hence Definition Recall 0% is un-blocked) | Replace with a semantic contradiction detector; add a definition-conflict validator |
| A4 | Harness always routes with `task_type="interpretation"`, and baseline confidence is a constant 0.96 | Routing assumption | `SERVE_IN_HOUSE` is never produced; routing collapses to ESCALATE-vs-REFUSE; confidence-based routing is untested | Exercise all three routing outcomes; vary task types |
| A5 | Grounding requires exact `char_span → quote` equality | Packet-interface assumption | Extractors that paraphrase or return approximate offsets fail grounding even with correct content | Add a fuzzy-grounding tolerance mode, reported separately |
| A6 | Faithfulness gate reuses `extractor.resolve()` (packet-only vs full) | Evaluator coupling | The gate's strength scales with the extractor's own resolver; a trivial resolver makes it weak | Independent re-resolution reasoner |
| A7 | Span-retrieval matching is normalized **substring** containment | Overfitting vector | An extractor returning over-broad giant spans that contain the needle scores as "retrieved" | Add span-precision / span-length penalties |
| A8 | `approx_tokens` are declared, not real; corpora are 2–4 short docs | Scope limitation | **The architecture's actual long-context claim is NOT exercised.** The benchmark tests completeness on short synthetic contracts | Add genuinely long (10k–100k token) corpora |
| A9 | `gates_only` imports `ground_spans` / `packet_only_reresolve` / `decide_escalation` from the frozen package | Compatibility coupling | If the frozen package changes, `gates_only` numbers move | Pin the frozen package by version; treat its change as a benchmark MAJOR bump |
| A10 | Confidence values are synthetic and constant | Calibration gap | No confidence-calibration signal is measured; abstention is validator-driven, not extractor-driven | Require extractors to emit calibrated confidence; add calibration metrics |

## B. Scope limitations
- **All corpora are SYNTHETIC.** No real contracts. Results bound framework and baseline behaviour only.
- **Short-context only** (see A8) — the benchmark does not yet measure long-context retrieval, which is the HybridPhaseTransformer's central claim.
- **Single domain** (enterprise contracts / termination). Cross-domain generalisation is untested.
- **English only.**
- **The downstream frontier tier is a template mock**; generated-answer quality is deliberately out of scope.

## C. Metric-interpretation caveats
- **Packet Sufficiency** is bounded by the deterministic resolver (A2), not a frontier model — read it as a lower bound tied to the current oracle.
- **Unsafe Handover Rate** is `P(accept | decisive evidence missing)` where "missing" is defined by the benchmark's own ground truth; it does not capture *wrong-but-complete* packets (e.g. `hidden_negation`, `policy_override` produce complete packets with wrong verdicts — a reasoning failure the completeness metrics correctly do **not** flag as unsafe).
- **Coverage Completeness** keys on marker strings and reference patterns; a novel corruption mode it does not recognise would pass.

## D. What these limitations do NOT undermine
- Determinism and reproducibility (verified).
- Ground-truth integrity (verified: 0 errors).
- **Relative** comparison between extractors run under identical conditions.
- The core falsification result: the frozen gates alone accept ~65% of incomplete packets; independent validation cuts this to ~17% but not to zero.
