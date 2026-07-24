# Deployment Packaging & Rollback/Recovery (M8)

*`customer_shadow_readiness/deployment.py`. A reproducible, pinned, **non-enforcing** pilot package
manifest and a rollback/recovery procedure to the frozen baseline. No real deployment infrastructure is
built — packaging *specification* and safety gates only.*

## Pilot manifest (`csr_pilot_manifest_v1`)

`build_manifest()` produces a manifest that pins:

- **the frozen baseline commit** `ab237af` (governed_inference_pilot);
- **13 component versions** — including `action_gate_real: action_gate_ref_v1` (the M2/M3 **real** gate,
  read-only, never the shadow mapping);
- **21 frozen artifact hashes** — the exact bytes the pilot runs against;
- **the pilot configuration**, whose safety-critical fields are fixed:
  `enforcement: OFF`, `external_actions: DISABLED`, `live_provider_calls: DISABLED`,
  `execution_mode: fixture`, `action_gate: real_read_only`, `tenant_isolation: ENABLED`,
  `kill_switches: [pilot, tenant]`, `data_egress: minimized_redacted_only`.

The manifest is the single artifact that describes exactly what a pilot deployment *is* — pinned,
reproducible, and provably non-enforcing.

## Deployment preflight (fail-closed gate)

`preflight()` refuses to declare the pilot deployable unless **both**:

1. **enforcement is off** (`enforcement == OFF` and `external_actions == DISABLED`), and
2. **all 21 frozen artifacts are byte-identical** (the guard passes).

`deployable` is `True` only when both hold. A pilot that has drifted from the frozen baseline, or that
has enforcement enabled, is not deployable — the packaging step cannot ship an enforcing or drifted
build.

## Rollback & recovery

`rollback_check()` confirms rollback to the frozen baseline is **safe iff the baseline artifacts are
byte-identical** (`rollback_safe = baseline_intact`). The recovery procedure:

1. **engage the pilot-wide kill** (stop accepting work);
2. **verify the frozen guard** (confirm the baseline is intact);
3. **redeploy the frozen manifest** (the pinned components + config);
4. **restore the kill switch** only after validation.

No data migration is needed on rollback: the pilot stores only minimized, redacted, tenant-scoped
records (M5), so recovery is a redeploy, not a data-restore.

## Scope honesty

This is a packaging **specification** and a set of safety gates, not a deployment system. There is no
container image, orchestration (k8s/helm), CI/CD, or infrastructure-as-code — those are NOT-EVALUATED
production dimensions. What this establishes for a bounded pilot: the deployment is pinned and
reproducible, provably non-enforcing at preflight, and rollback to the frozen, safe baseline is a
verified one-step procedure.
