"""Wiring for the last-mile authority recheck (RA-6 §8).

**This module implements no recheck.** Risk Authority's status runtime already ships
one — ``make_pre_effect_recheck`` — and it already returns exactly the
``(evaluation, proposal, now) -> (ok, reasons)`` shape Agent Runtime's
``authority_recheck`` seam expects. Re-implementing it here would duplicate
authority-critical logic outside the package that owns it, which is precisely what this
integration layer exists to avoid.

What is missing, and what this module supplies, is the *resolver*: the function that
maps a neutral ``(evaluation, proposal)`` pair to the signed envelope and risk tier the
recheck must re-verify. Only the hook knows that, because only the hook saw which
envelope a given CLEAR rested on. So the binding is: the hook records
``fingerprint -> (envelope, tier)`` when it clears, and this resolver reads it back.

ADR §8 row 6 established why this matters. With ``authority_recheck`` unset, a revocation
landing between CLEAR and the effect goes unnoticed and the provider *is* invoked — the
matrix asserts that negative case explicitly. Under a durable engine the gap between
clearance and effect is routine rather than exceptional, so configuring this is a
requirement, not a refinement.
"""
from __future__ import annotations

from typing import Any, Callable, Optional, Tuple

__all__ = ["hook_envelope_resolver", "build_authority_recheck", "ClearanceRecordMissing"]


class ClearanceRecordMissing(RuntimeError):
    """A CLEAR reached the last mile but the hook no longer holds its record.

    Raised, not returned as ``None``: ``make_pre_effect_recheck`` reads ``None`` as
    "not authority-bound" and passes through, which for a clearance whose record was
    consumed or aged out would let the provider call proceed with no re-verification.
    ``validate_clearance`` turns a raising recheck into a refusal
    (``GOVERNANCE_AUTHORITY_RECHECK_ERROR``), so raising here fails closed.
    """


def hook_envelope_resolver(hook: Any) -> Callable[[object, object], Optional[Any]]:
    """A ``resolve`` for ``make_pre_effect_recheck``, backed by the hook's own record.

    Returns ``None`` for a proposal the hook never cleared. ``make_pre_effect_recheck``
    reads that as "not authority-bound" and passes through — correct here, because a
    proposal with no recorded envelope never obtained a CLEAR from this hook and so has
    no provider call for the recheck to guard. The refusal already happened upstream.

    The one case that must NOT pass through is a CLEAR evaluation whose record the hook
    has since dropped (consumed, expired, or aged out of the bounded record). That is
    distinguishable from "never cleared" by the evaluation itself — it carries the CLEAR
    disposition and an authorization reference — and it raises
    :class:`ClearanceRecordMissing` so the runtime refuses rather than proceeds.

    Resolving consumes the record: it is dropped at the hook's next sweep.
    """
    from ugence_agent_runtime.governance.interfaces import GovernanceDisposition
    from ugence_risk_authority_status_runtime.enforcement import PreEffectContext

    def _resolve(evaluation: object, proposal: object) -> Optional[PreEffectContext]:
        record = hook.consume_envelope(proposal)
        if record is None:
            if (
                getattr(evaluation, "disposition", None) is GovernanceDisposition.CLEAR
                and getattr(evaluation, "authorization_reference", None)
            ):
                raise ClearanceRecordMissing(
                    "the hook holds no clearance record for a CLEAR evaluation; "
                    "refusing rather than re-verifying nothing"
                )
            return None
        envelope, tier = record
        if envelope is None:
            return None
        return PreEffectContext(
            envelope=envelope,
            tier=tier,
            expected_tenant=getattr(envelope, "tenant_id", None),
            expected_session=getattr(envelope, "session_id", None),
            expected_audience=getattr(envelope, "audience", None),
        )

    return _resolve


def build_authority_recheck(
    *,
    hook: Any,
    reader: Any,
    policy: Any,
    key_ring: Any,
    clock: Callable[[], Any],
    sync: Optional[Callable[[], None]] = None,
) -> Callable[[object, object, float], Tuple[bool, Tuple[str, ...]]]:
    """Build the ``authority_recheck`` callable for ``AgentRuntimeConfig``.

    A thin composition over Risk Authority's own ``make_pre_effect_recheck``: this
    supplies the resolver and passes everything else straight through. ``sync`` refreshes
    the status cache before the read, so a revocation or epoch advance that landed after
    the initial CLEAR is actually observed at the commit point — without it the recheck
    can re-verify against a snapshot as stale as the clearance it is checking, which
    would make the whole mechanism decorative.

    ``clock`` here returns a ``datetime`` (Risk Authority's status API), not the epoch
    float the runtime uses; the runtime's own ``now`` is passed through separately by
    ``validate_clearance``. Keeping both on the same real time base is the deployment's
    responsibility and is the skew condition ADR §8 row 11 tests.
    """
    from ugence_risk_authority_status_runtime.enforcement import make_pre_effect_recheck

    return make_pre_effect_recheck(
        reader=reader,
        policy=policy,
        key_ring=key_ring,
        clock=clock,
        resolve=hook_envelope_resolver(hook),
        sync=sync,
    )
