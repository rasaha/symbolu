# Human-Review Protocol (Phase 21) & Operator Trace Viewer (Phase 22)

*`governed_inference_pilot/human_review.py` + `governed_inference_pilot/viewer/`. Real reviewers were
unavailable, so this produces the protocol **and** a deterministic dual-rubric simulation, labeled
honestly as a simulation — not a claim about real human behavior.*

## Review bundle (per case)

`review_bundle(case)` assembles what a reviewer sees: the original request, the model output, the
extracted claims, every stage decision, the final shadow disposition, the reason codes, the
uncertainties (which stages abstained), and the component versions. This is the unit a real reviewer
would be shown.

## Measures (protocol)

- reviewer agreement with the final outcome; per-stage agreement; review time; reason-code usefulness;
  trace comprehensibility; missing context; override rate; override direction; reviewer confidence.

## Deterministic dual-rubric simulation (labeled)

Two deterministic rubrics stand in for reviewers:

- **Reviewer A (safety-first):** overrides a bare `WOULD_ALLOW` on a high/critical-risk request toward
  escalation; otherwise agrees.
- **Reviewer B (utility-first):** agrees unless the outcome is an over-block on a clean case.

Simulated results over the 384-case corpus:

| Measure | Value |
|---|--:|
| reviewer-A agreement with final | 0.917 |
| reviewer-B agreement | 1.000 |
| both agree | 0.917 |
| override rate | 0.083 |
| override direction | toward escalation (safety-first, on bare high-risk allow) |
| mean review units (proxy) | 9.54 |
| reason-code coverage | 1.000 |

**This is a simulation, not evidence about real reviewers.** It establishes that (a) the trace carries
enough structure for a rule-based reviewer to reach a decision on every case (100% reason-code
coverage), and (b) the only systematic override is the safety-first reviewer wanting escalation on
bare high-risk allows — a signal the runtime could adopt as a policy. Real human-subject review is a
product-readiness gap (Phase 28), not something this track claims to have done.

## Operator trace viewer (Phase 22)

`viewer/render.py` renders a trace to a **self-contained static HTML** fragment: request summary,
pipeline timeline, stage dispositions, reasons, latency, errors, final disposition, human-review state,
and replay signature. It has a redacted (operator) and an internal view.

**It is not a production dashboard.** No authentication, no deployment, no live data, no server — a
static renderer only. Building auth/deployment/observability infrastructure is explicitly out of scope
for this track and is listed as a product-readiness gap.
