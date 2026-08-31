# Unseen-identifier copy/selection — fresh smoke/development re-authorization (post-#1379, docs-only)

**Documentation-only record. Nothing is executed, generated, trained, or seeded by this file.**
This record re-establishes smoke/development execution authorization **bound to the merged corrected
shortcut gate** (PR #1379), because the shortcut-precheck decision rule changed and the prior
smoke/development authorization/evidence is therefore superseded and must not be reused as current
evidence.

## Why a fresh authorization is required
PR #1379 changed the **shortcut-precheck decision rule** (`experiments/unseen_identifier_copy_selection/shortcuts.py`)
from a flat point-estimate `p̂ > chance + 0.05` line to a sampling-aware dual condition
(practical leg `p̂ > chance + 0.05` **and** statistical leg: exact one-sided binomial upper tail under
Holm–Bonferroni FWER control across all (split × baseline) comparisons). The development gate therefore
changed; the earlier `DEVELOPMENT_SHORTCUT_BLOCKED` evidence (commit `d22bd5cf`) is **superseded**.

## Binding to the merged corrected implementation
This authorization binds to the authoritative default branch after the #1379 merge:

| Item | Value |
|------|-------|
| Authoritative default-branch commit | `ed95bff68c1d867cec5fdadc97f7bbc3ad9501d4` |
| PR #1379 merge commit | `ed95bff68c1d867cec5fdadc97f7bbc3ad9501d4` (parents `b73a9f1e` + `23b90c02`) |
| Audited corrective PR head | `23b90c0256658014cd5f9f5a2943279c99e2aad8` |
| Corrected `shortcuts.py` sha256 | `d189bb9e1922ec92ab5cd2fdd095518a237afdac5cd4399c3cccc98175e52c55` |
| Independent audit status | `CORRECTIVE_GATE_AUDIT_PASS` |

The corrected `shortcuts.py` on default is byte-identical to the audited head `23b90c02`.

## Authorization statement
> Under the phase-protocol control model (authorization = the reviewed, independently-audited, **merged**
> change plus the operator's explicit **phase-named invocation**), and with the operator's explicit
> direction in this session, this record authorizes **only**:
> * **smoke** seed **9070** (`--phase smoke --seed 9070`);
> * **development** seeds **9071, 9072, 9073** (each `--phase development` with a single seed).
>
> Every reserved run uses the frozen implementation via explicit phase-named invocation of the merged
> CLI/driver, one seed per invocation.

## Explicitly preserved prohibitions (unchanged)
* **Final seeds 90760–90764 remain PROHIBITED.** They may not be opened, generated, inspected, or
  consumed under this or any smoke/development authorization.
* **`--phase final` is NOT authorized** here and additionally requires a separate, independently-audited
  final authorization plus a passing shortcut precheck out of scope here.
* **No capability verdict** is authorized. Development emits only the frozen smoke/development namespace
  verdicts (`SMOKE_*`, `DEVELOPMENT_*`); no `UNSEEN_IDENTIFIER_*` capability verdict is computed.
* The **prior development verdict is superseded** (gate changed).

## Not modified by this authorization
Model architecture · task construction · training recipe · optimizer · seed allocations · evaluation
semantics · capability thresholds · final verdict logic. This record touches none of them.

## Resulting state
Bound to the merged corrected gate on default `ed95bff6` with operator direction:
**smoke (9070) and development (9071–9073) execution is AUTHORIZED** under the frozen implementation and
the phase-protocol control model; **final (90760–90764) remains PROHIBITED.** Running the authorized
phases is the separate, operator-directed execution step performed in this same session.

Standing invariants preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` ·
`E1_TEMPORAL_TRANSFER_PARTIAL` · `KDA_VALIDATION_BLOCKED`.
