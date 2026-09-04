"""Ugence Cloud Scaling Bounded Execution — Phase 5D.

**The only path from a credential grant to the executor.** This package consumes a 5X
``CredentialGrant`` for a ``RESERVED`` execution reservation and dispatches exactly one
bounded capacity change through Cloud Scaling Operations' ``ControlledScalingExecutor``,
per ADR 5D decisions D-1 … D-5:

* :class:`BoundedExecutionSeam` mints the operations-local ``ExecutionAuthorization`` itself,
  with itself as issuer, from the grant, the reservation and the target scope, so the
  executor's own gates run unchanged against ladder-derived values (D-1);
* :class:`BoundedDispatch` binds the grant, the reservation, the authorization and the
  target scope; the seam proves, at one clock read, that the grant re-derives from exactly
  those artifacts through the 5X minter before any client is touched, and the execution
  key's serialized form is the executor's idempotency key (D-2);
* ``LIVE`` survives only under a fully proven production posture; any absence resolves to
  ``DRY_RUN`` and never to ``SIMULATION`` (D-3);
* the executor's ``TargetPolicy`` is narrowed to the grant's role and never widened beyond
  config; exactly one ``set_replicas`` per dispatch; rollback is a second bounded action and
  a bare-policy rollback is refused (D-4);
* a :class:`BoundedExecutionRecord` with aware instants and the RA-8 correlation fields is
  minted from the receipt, the reservation is advanced at dispatch and at observation, and an
  ``EffectObservation`` is emitted for RA-8; reconciliation stays RA-8's (D-5).

What it does **not** do: read a clock; build a backend or hold a credential; load a
kubeconfig or call a cloud SDK; reconcile an effect. The executor's own ``time`` import and
HMAC verifier are Cloud Scaling Operations' and are carried, not adopted.
"""

from __future__ import annotations

from .errors import (
    BarePolicyRollbackRefused,
    BoundedExecutionConfigurationError,
    BoundedExecutionContractError,
    BoundedExecutionExactTypeError,
    CloudScalingBoundedExecutionError,
)
from .identifiers import (
    DEFAULT_DISPATCH_DEADLINE,
    DISPATCHABLE_ACTION_TYPES,
    ISSUER_ID,
    PROVIDER_ID,
    RECORD_SCHEMA_VERSION,
    SIGNATURE_ALGORITHM,
)
from .mapping import OpsTarget, business_outcome_for, finality_for, ops_action_for, ops_target_for, to_epoch
from .posture import LivePosture, narrow_target_policy, resolve_effective_mode
from .record import (
    BoundedExecutionRecord,
    BoundedExecutionRecordStore,
    InMemoryBoundedExecutionRecordStore,
    RecordDisposition,
    derive_record_id,
    effect_observation_for,
)
from .refusals import DispatchRefusal
from .seam import BoundedDispatch, BoundedDispatchOutcome, BoundedExecutionSeam, ExecutorParts
from .version import __version__

__all__ = [
    "__version__",
    # --- the seam and its request/outcome ---
    "BoundedExecutionSeam",
    "BoundedDispatch",
    "BoundedDispatchOutcome",
    "ExecutorParts",
    "DispatchRefusal",
    # --- posture and blast radius ---
    "LivePosture",
    "resolve_effective_mode",
    "narrow_target_policy",
    # --- the record and its observation ---
    "BoundedExecutionRecord",
    "RecordDisposition",
    "BoundedExecutionRecordStore",
    "InMemoryBoundedExecutionRecordStore",
    "derive_record_id",
    "effect_observation_for",
    # --- projections ---
    "OpsTarget",
    "ops_target_for",
    "ops_action_for",
    "to_epoch",
    "business_outcome_for",
    "finality_for",
    # --- identifiers ---
    "ISSUER_ID",
    "PROVIDER_ID",
    "SIGNATURE_ALGORITHM",
    "RECORD_SCHEMA_VERSION",
    "DEFAULT_DISPATCH_DEADLINE",
    "DISPATCHABLE_ACTION_TYPES",
    # --- typed errors ---
    "CloudScalingBoundedExecutionError",
    "BoundedExecutionConfigurationError",
    "BoundedExecutionContractError",
    "BoundedExecutionExactTypeError",
    "BarePolicyRollbackRefused",
]
