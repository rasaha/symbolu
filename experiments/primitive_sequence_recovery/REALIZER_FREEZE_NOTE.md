# Realizer / Run-Params Freeze Note — Primitive-Sequence Recovery (Step C.5)

**Status:** Freeze/configuration only. Records `frozen/realizer.json` and
`frozen/run_params.json`. **No** manifest was created; readiness remains **NOT_READY** and
the runner remains **NOT_RUN**. No code, no model, no concept resolver, no embeddings, no
similarity, no scores, no downloads, no network/LLM, no Stage A change, no pre-registration
change. This commit freezes the **execution interface only** — after it, the repository is
still incapable of producing any experimental result.

## What was frozen

- **`realizer.json`** — the future realizer's *interface and safety flags*, deliberately
  **unimplemented**: `status = NOT_IMPLEMENTED`, `implementation_present = false`,
  `execution_allowed = false`, `deterministic = true`, `offline_only = true`,
  `model_asset = null`, `model_sha256 = null`, `concept_resolver = null`,
  `concept_resolver_status = NOT_IMPLEMENTED`, empty `robustness_realizers`. No product/model
  name appears anywhere (no Sentence-Transformers / OpenAI / Gemini / Claude / HuggingFace /
  etc.); `primary_realizer_type` is a *capability* description, not a model.
- **`run_params.json`** — the frozen statistical plan: `scoring_metric = MRR`,
  `secondary_metric = Top1`, `K = 8`, `scramble_seeds = 1000`, `bootstrap_iterations = 10000`,
  `paired_test = wilcoxon_signed_rank`, `confidence_interval = 0.95`, `alpha = 0.05`,
  `order_scramble_enabled = true`, `assignment_scramble_enabled = true`,
  `family_bootstrap = true`, `run_enabled = false`, `execution_status = NOT_RUN`. No scores,
  results, timestamps, hardware, or runtime configuration.

Both validate against their JSON schemas (`schemas/realizer.schema.json` — rewritten for the
unimplemented-interface field set — and the new `schemas/run_params.schema.json`).

## Why the realizer is frozen but unimplemented

Freezing the *interface* now — expected input/output, similarity metric, normalization, the
determinism/offline invariants, and the safety flags — pins the contract the eventual
implementation must satisfy, **before** any model exists to bias the choice. Because there is
no executable code and no asset, this commit cannot compute anything: it records *what the
realizer will be required to be*, not *how it works*. The gate was extended so that an
unimplemented realizer is a hard `NOT_READY` block (`status != IMPLEMENTED`,
`execution_allowed != true`, `implementation_present != true`, or a null `model_asset` all
force NOT_READY), and the runner stays `NOT_RUN`.

## Why model choice is postponed

Naming or pinning an embedding/similarity model now would (a) inject a model-specific bias
into a pre-registered test before the interface is even fixed, and (b) invite post-hoc model
shopping — trying models until one "works" — which is a researcher degree of freedom that
inflates false positives. `model_asset`/`model_sha256` stay `null` until a specific
**offline, deterministic** asset is selected and pinned by hash in a later, separate step, so
the choice is on the record and cannot be quietly swapped. No model was downloaded.

## Why concept resolution is deferred

`realization_concept_id` references opaque concept-node IDs (`svc:*`, `wmc:*`) whose semantic
*similarity structure* must come from a concept resolver/graph that does not yet exist.
Implementing it now would mean inventing that structure — exactly the kind of unfrozen
degree of freedom this pipeline is built to prevent. `concept_resolver = null` /
`concept_resolver_status = NOT_IMPLEMENTED` records the deferral honestly; until it exists,
the concept realization cannot contribute independent signal (consistent with the caveats in
`REALIZATIONS_NOTE.md`).

## Why READY must never depend on an implicit model

If the gate treated "no model specified" as acceptable, a run could silently fall back to
some default embedding, and the result would depend on an unpinned, unaudited artifact —
irreproducible and unfalsifiable. The gate therefore requires an **explicit, pinned,
hash-verified** `model_asset` and an `IMPLEMENTED` / `execution_allowed` realizer before
READY. "Absent model" and "implicit default model" are both rejected; only a named, frozen,
offline, deterministic asset qualifies.

## Freezing an interface vs freezing an implementation

- **Freezing an interface** (this step) pins the *contract*: input/output shape, metric,
  normalization, determinism/offline requirements, and the safety flags — with **no code and
  no model**. It is inert: it cannot run.
- **Freezing an implementation** (a later step) pins a *specific realizer*: the actual
  offline asset, its `sha256`, and the deterministic procedure — flipping `status` to
  `IMPLEMENTED`, `execution_allowed`/`implementation_present` to `true`, and filling
  `model_asset`/`model_sha256`. Only then can the gate reach READY and the runner execute.

Keeping these two steps separate is what lets us commit a frozen, reviewable execution
contract while guaranteeing the repository still produces no result.

> structure, not validated meaning.
