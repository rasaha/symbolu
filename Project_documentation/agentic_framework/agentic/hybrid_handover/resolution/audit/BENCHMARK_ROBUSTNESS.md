# BENCHMARK_ROBUSTNESS — Governance on Out-of-Distribution Structures

Feed the reference governance graph structures that do not appear in the 16 gold
cases and record whether it behaves sensibly. Run via `run_audit.run_robustness`.

## Observations

| Structure | Result | Assessment |
|---|---|---|
| redundant duplicate edge (`A⊳B, A⊳B`) | governing `[A]`, discarded `[B]` | ✅ idempotent |
| irrelevant unconnected node `D` | governing `[A, D]` | ❌ **no relevance filter** — `D` pollutes the governing set |
| multiple paths to discard `C` (`A⊳C, B⊳C`) | governing `[A, B]`, discarded `[C]` | ✅ sensible |
| parallel overrides (`P1▸A, P2▸A`) | governing `[P1, P2]`, discarded `[A]` | ⚠️ **silent ambiguity** — two governors, no tie-break |
| nested exceptions (`E1→A, E2→E1`) | governing `[A]`, discarded `[]` | ⚠️ **nesting ignored** — only top-level exception modelled |
| multi-hop chain (`A⊳B, B⊳C`) | governing `[A]`, discarded `[B, C]` | ✅ works — but by "discard every supersede-dst", not by transitive reasoning |
| dangling reference (`A→GhostDoc`) | governing `[A]`, **no abstain** | ❌ **not detected** — dangling abstention is attribute-driven, not structural |

(⊳ = supersedes, ▸ = overrides, → = references/exception_to)

## Findings
1. **No relevance filter.** Any `Clause`/`Policy` node not discarded becomes
   governing, including unrelated nodes. A resolver that emits extra nodes inflates
   the governing set. Governance should require a relevance/connection criterion.
2. **Parallel overrides are silently ambiguous.** Two overriding policies both
   govern with no tie-break; packet construction then picks one arbitrarily.
   Behaviour must be specified (abstain, or authority ordering).
3. **Nested exceptions unmodelled.** `exception_to` chains beyond depth 1 are not
   handled. Either specify or explicitly exclude.
4. **Dangling detection is fragile.** It depends on a `dangling` attribute set by
   the baseline parser, not on the structural fact `dst ∉ nodes`. A different
   resolver producing the same edge without that attribute would NOT abstain.
   **Make dangling/unusable abstention structural.**
5. **Multi-hop "works" for the wrong reason.** Chains resolve because every
   supersede-`dst` is discarded, not via transitive traversal; a chain where the
   head is itself a `dst` (e.g. `C⊳A, A⊳B`) would discard `A` too and mis-resolve.
   Transitive precedence should be defined explicitly.

## Consequence for trust
Governance is correct on the 16 in-distribution cases but **underspecified** on
structures a future (e.g. neural) resolver may legitimately produce. Freezing now
would let two resolvers that emit equivalent graphs receive different scores due
to unspecified governance behaviour. These behaviours must be defined (and
dangling made structural) before freeze.
