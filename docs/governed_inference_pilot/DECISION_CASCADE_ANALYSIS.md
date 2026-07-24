# Decision-Cascade Analysis (Phase 19)

*`governed_inference_pilot/cascade_analysis.py` → `eval_results/cascade_latency_cost.json`. How
stage-local decisions compound into the final outcome, and which stages are load-bearing.*

## Which stage drives the final outcome

| Stage | Final outcomes it drove | Safety withholds it drove |
|---|--:|--:|
| EvidenceAssurance | 160 | **128** |
| ExecutionGate | 96 | 32 |
| ActionGate | 64 | 64 |
| ModelPolicy | 32 | 32 |
| orchestrator (contract/budget) | 32 | 32 |

**EvidenceAssurance is the dominant safety driver** — it produces the withhold that becomes the final
outcome on 128 cases, more than all other governance stages combined. This matches the baseline
ablation (removing EvidenceAssurance leaks 0.167 unsafe assertion escape) and identifies it as the
mandatory core for assertion safety. ActionGate is the sole driver of the 64 action-policy withholds —
it is mandatory whenever actions are present.

## Contradictory and redundant decisions

- **256 cases (67%) carry a contradictory decision** — one stage allows while another withholds.
  This is **expected and correctly handled**: in a typical failure case, execution and claim
  decomposition legitimately succeed (allow) while evidence or action governance withholds. Precedence
  reconciliation resolves every one so the final surfaces the withhold — the runtime never averages an
  allow against a withhold. Contradiction is the normal shape of a layered control plane, not a bug.
- **48 cases carry a redundant withhold** — two or more stages independently reach the same withhold
  (e.g. evidence rejects and the assertion gate also rejects). Redundancy is safe but is a candidate
  for the minimum-viable study (Phase 23): where two stages always agree, one may be droppable at a
  given risk tier.

## Load-bearing sequences

- **ExecutionGate → ModelPolicy** is load-bearing for the *availability* outcomes (64 cases resolve to
  EXECUTION_UNAVAILABLE before any content governance runs).
- **EvidenceAssurance → AssertionGate** is the load-bearing sequence for assertion safety; EA drives
  most withholds, and AssertionGate catches the residual signal-level failures.
- **action extraction → ActionGate** is load-bearing and independent — no other stage catches an
  action-policy failure (ActionGate is the only driver of those 64 withholds).

## Avoidable cascade effects

No case shows an avoidable over-block cascade (false-block rate is 0.000 across the corpus): conservative
stages do **not** compound into unusable over-blocking here. The one accumulation to watch is the
unresolved rate (0.125) — driven by AMBIGUOUS scope + evidence-indeterminate cases where two stages both
abstain; this is safe (a flag, not a wrong delivery) but is the availability cost of the composition.
