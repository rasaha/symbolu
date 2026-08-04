"""Cloud Scaling Operations — MONOREPO-ONLY execution/operations code.

This namespace holds the execution, approval, orchestration, live-telemetry and
live-shadow modules that were separated OUT of the advisory distribution
``ugence-cloud-scaling-controller`` (v0.1.1) to keep that wheel advisory-only.

IMPORTANT:
  * This code is NOT part of the ``ugence-cloud-scaling-controller`` distribution.
  * It is NOT a stable, published, or supported API.
  * It depends on the advisory package (``ugence_cloud_scaling_controller``);
    the advisory package MUST NOT depend on this namespace.

A future independent, separately-governed distribution
(e.g. ``ugence-cloud-scaling-operations``) may package this — but not in this phase.
"""
