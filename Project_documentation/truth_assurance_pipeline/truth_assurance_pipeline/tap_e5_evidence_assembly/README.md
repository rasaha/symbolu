# TAP-E5 — Evidence Assembly

The fifth TAP research layer. Given the four frozen upstream records — `IntentRecord`
(TAP-E1), `RetrievalRecord` (TAP-E2), `RelationshipRecord` (TAP-E3), `GovernanceRecord`
(TAP-E4), all consumed through their **frozen public interfaces** — it assembles exactly one
deterministic `EvidencePacket`: the **smallest complete, dependency-preserving,
provenance-preserving** object required by downstream claim validation.

> **E5 is a linker, not a reasoner.** The previous stages *discover* information; E5
> *packages* it into one object. It does **not** determine truth, validate claims, generate
> responses, retrieve evidence, perform governance reasoning, resolve conflicts, or fill
> gaps. It never invents, summarizes, rewrites, or merges evidence.

## Honesty (read first)

- New, independently authored synthetic corpus (not reused from any prior layer).
- Upstream records are **authored fixtures** — this phase evaluates the assembly/
  minimization mechanism, not upstream extraction. The packet gold (minimal complete set) is
  computed **independently** of the assembler.
- The eval split is content-hash locked and preregistered, but was inspected during
  iterative engineering — a **locked development evaluation, not an untouched/blind holdout**.
- Mechanism/construction validation only.

## Layout

```
tap_e5_evidence_assembly/
├── schema.py           # EvidencePacket + all sub-structures (frozen downstream interface)
├── dependency_graph.py # adjacency / reachability / orphans / cycle detection
├── assembler.py        # assembly engine + A–F baselines + 14-stage trace
├── packet_validator.py # structural packet validation
├── validator.py        # upstream-input validation (never repairs)
├── metrics.py          # packet metrics + 12 independent critical failures
├── harness.py          # E1→E2→E3→E4→E5 driver, dev-only selection, gates, verdict
├── loader.py           # gold-free public loader
├── corpus/             # 32 cases / 13 families (eval locked)
├── experiments/        # runner, preregistration, locks, results
└── tests/
```

## Run

```bash
python -m truth_assurance_pipeline.tap_e5_evidence_assembly.experiments.run_experiment
python -m pytest truth_assurance_pipeline/tap_e5_evidence_assembly/tests/ -q
```

## Result

Selected baseline **F** (the simplest satisfying all preregistered gates — minimization,
provenance, and validation require it). All fourteen gates pass on the locked eval split;
verdict **`PASS_WITH_LIMITED_CLAIM`**.

The `EvidencePacket` schema is the frozen downstream interface; the **next layer is TAP-E6 —
Claim Validation**, the first layer that evaluates whether a proposed claim is actually
supported by the assembled packet. See
[`EXPERIMENT_REPORT.md`](../../docs/truth_assurance_pipeline/experiments/tap_e5_evidence_assembly/EXPERIMENT_REPORT.md).
