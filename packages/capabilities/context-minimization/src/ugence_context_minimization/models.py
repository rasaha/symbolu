"""Immutable, package-neutral data models for Context Minimization.

Nothing here imports a product, a capability, a provider, ActionGate, a model, or
a tokenizer. A :class:`Context` is an ordered list of :class:`ContextUnit`s that
*another component has already assembled or admitted*. Context Minimization never
decides whether information was permitted to enter the context — it only reduces
an already-assembled context by extractive omission.

All identity-bearing models are ``frozen`` dataclasses. Caller-supplied mapping
values are defensively copied into read-only mappings so a caller mutation can
never reach back into a stored model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional

from .errors import InvalidRequestError, InvalidUnitError
from .numeric import is_finite_number, is_timestamp, is_token_count

# --------------------------------------------------------------------------- #
# Neutral, approximate token counting (stdlib only).
# --------------------------------------------------------------------------- #
_TOKEN_RE = re.compile(r"\w+|[^\w\s]")


def default_token_count(text: str) -> int:
    """Transparent word/punctuation token count.

    This is a deliberately simple, model-neutral approximation — NOT a provider
    BPE tokenizer. It exists so budgets have a defined default when the caller
    supplies neither per-unit token counts nor a :class:`TokenCounter`. Reported
    reductions computed from it are approximate and MUST NOT be presented as exact
    provider billing savings.
    """
    return len(_TOKEN_RE.findall(text or ""))


def _freeze_mapping(m: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    """Return a read-only copy of ``m`` under the scalar metadata value contract.

    Metadata keys must be strings. Values must already be **scalar JSON-compatible**
    values — ``str``, a finite ``int``/``float``, ``bool``, or ``None``. Lists,
    dicts, sets, bytes, callables, dates/datetimes, non-finite numbers, and arbitrary
    objects are rejected with :class:`InvalidUnitError` rather than being coerced via
    ``str()`` (which, for arbitrary objects, would embed nondeterministic memory
    addresses). This keeps stored models deterministic and JSON-serializable without
    silently claiming determinism for un-canonicalizable values.
    """
    if not m:
        return MappingProxyType({})
    out: dict[str, Any] = {}
    for k, v in m.items():
        if not isinstance(k, str):
            raise InvalidUnitError(f"metadata keys must be str, got {type(k).__name__}")
        if v is None or isinstance(v, str) or isinstance(v, bool) or is_finite_number(v):
            out[k] = v
        else:
            raise InvalidUnitError(
                f"metadata value for {k!r} must be a scalar (str / finite number / "
                f"bool / None), got {type(v).__name__}"
            )
    return MappingProxyType(out)


# --------------------------------------------------------------------------- #
# Enumerations.
# --------------------------------------------------------------------------- #
class MinimizationMode(str, Enum):
    """Which minimization capability is being invoked."""

    #: Structural, structurally-lossless omission (exact duplicates / declared
    #: redundancy sets). Requires NO oracle.
    STRUCTURAL = "STRUCTURAL"
    #: Extractive removal verified against a neutral invariance oracle. Requires an
    #: oracle; fails closed to the full context when equivalence cannot be proven.
    ORACLE_VERIFIED = "ORACLE_VERIFIED"


class EquivalenceStatus(str, Enum):
    """The equivalence outcome of a minimization run."""

    #: Structural mode: no oracle equivalence was evaluated.
    NOT_EVALUATED = "NOT_EVALUATED"
    #: Reduced context proven equivalent to the full context by the oracle.
    VERIFIED = "VERIFIED"
    #: Equivalence achieved only after restoring necessary spans.
    RESTORED = "RESTORED"
    #: Equivalence could not be established; the full context was returned.
    FALLBACK = "FALLBACK"


# --------------------------------------------------------------------------- #
# Context models.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ContextUnit:
    """A single, independently removable span of an assembled context.

    ``text`` is the extractive payload — every surviving output span is this exact
    value, byte-for-byte. ``token_count`` is caller-supplied when known; when
    ``None`` the minimizer falls back to a :class:`TokenCounter` or the neutral
    :func:`default_token_count`.
    """

    id: str
    text: str
    source_type: str = "unspecified"
    token_count: Optional[int] = None
    redundancy_set: Optional[str] = None
    protected: bool = False
    provenance: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise InvalidUnitError("ContextUnit.id must be a non-empty str")
        # Token counts must be a non-negative int (never bool, float, NaN, inf, str).
        if self.token_count is not None and not is_token_count(self.token_count):
            raise InvalidUnitError(
                f"ContextUnit {self.id!r}: token_count must be a non-negative int, "
                f"got {self.token_count!r}"
            )
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    def counted_tokens(self, counter: "Optional[TokenCounter]" = None) -> int:
        """Resolve this unit's token count deterministically.

        Precedence: caller-supplied ``token_count`` → injected ``counter`` →
        :func:`default_token_count`. A zero-token span counts as zero. An injected
        counter that returns anything other than a non-negative ``int`` raises
        :class:`InvalidUnitError` deterministically, before any fingerprint uses the
        value.
        """
        if self.token_count is not None:
            return self.token_count
        if counter is not None:
            n = counter.count(self.text)
            if not is_token_count(n):
                raise InvalidUnitError(
                    f"TokenCounter returned a non-(non-negative-int) count {n!r} "
                    f"for {self.id!r}"
                )
            return n
        return default_token_count(self.text)


@dataclass(frozen=True)
class Context:
    """An ordered, already-assembled context to be minimized.

    The unit order is significant and preserved; ``correlation_id`` lets an oracle
    tie its evaluation to the caller's request.
    """

    id: str
    units: tuple[ContextUnit, ...]
    correlation_id: Optional[str] = None
    scope: Optional[str] = None
    context_contract_version: str = "1.0.0"
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "units", tuple(self.units))
        ids = [u.id for u in self.units]
        if len(ids) != len(set(ids)):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"Context {self.id!r}: duplicate unit ids {dupes}")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    def unit(self, uid: str) -> ContextUnit:
        for u in self.units:
            if u.id == uid:
                return u
        raise KeyError(uid)

    @property
    def unit_ids(self) -> tuple[str, ...]:
        return tuple(u.id for u in self.units)

    def total_tokens(self, counter: "Optional[TokenCounter]" = None) -> int:
        return sum(u.counted_tokens(counter) for u in self.units)

    def with_units(self, unit_ids) -> "Context":
        """Return a new Context keeping only ``unit_ids`` (order preserved)."""
        keep = set(unit_ids)
        return Context(
            id=self.id,
            units=tuple(u for u in self.units if u.id in keep),
            correlation_id=self.correlation_id,
            scope=self.scope,
            context_contract_version=self.context_contract_version,
            metadata=dict(self.metadata),
        )


# --------------------------------------------------------------------------- #
# Protection + oracle evaluation results (neutral).
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ProtectionResult:
    """The set of unit ids that must never be removed, plus provenance.

    ``uncertain_ids`` are units a provider was unsure about; the fail-closed rule
    is that uncertainty RETAINS the unit, so uncertain ids are treated as protected.
    """

    protected_ids: frozenset[str]
    uncertain_ids: frozenset[str] = frozenset()
    provider_id: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "protected_ids", frozenset(self.protected_ids))
        object.__setattr__(self, "uncertain_ids", frozenset(self.uncertain_ids))

    @property
    def effective_protected(self) -> frozenset[str]:
        """Protected ∪ uncertain — everything the minimizer must keep."""
        return self.protected_ids | self.uncertain_ids


@dataclass(frozen=True)
class OracleEvaluation:
    """A neutral, opaque equivalence result returned by an :class:`InvarianceOracle`.

    The minimizer treats ``equivalence_key`` as an OPAQUE value: two contexts are
    equivalent iff their keys are equal. The minimizer never parses the key nor
    constructs authorization semantics of its own. The oracle owns what the key
    means and how it is canonicalized.
    """

    equivalence_key: str
    oracle_id: str
    contract_version: str
    evaluation_ref: Optional[str] = None
    correlation_id: Optional[str] = None
    valid_until: Optional[float] = None
    reason_codes: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


# --------------------------------------------------------------------------- #
# Request + result.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class MinimizationRequest:
    """A single minimization invocation."""

    context: Context
    mode: MinimizationMode = MinimizationMode.STRUCTURAL
    #: Fraction of tokens to attempt to remove, in [0, 1]. Ignored for structural
    #: mode (structural removes exactly the provable duplicates).
    target_reduction: float = 0.0
    #: Absolute surviving-token ceiling; when set, extractive selection removes
    #: until total surviving tokens <= this value. Mutually complementary with
    #: ``target_reduction`` (the stricter of the two applies).
    token_budget: Optional[int] = None
    evaluation_time: Optional[float] = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.target_reduction <= 1.0:
            raise InvalidRequestError("target_reduction must be within [0, 1]")
        if self.token_budget is not None and not is_token_count(self.token_budget):
            raise InvalidRequestError("token_budget must be a non-negative int")
        if self.evaluation_time is not None and not is_timestamp(self.evaluation_time):
            raise InvalidRequestError(
                "evaluation_time must be a finite real number (not bool/NaN/inf/str)"
            )


@dataclass(frozen=True)
class MinimizationResult:
    """The audit-friendly outcome of a minimization run.

    Records exactly what happened and why: which ids survived / were removed
    (structurally vs extractively) / restored, whether the run fell back, and the
    oracle contract used.

    Two fingerprints (v0.1.1), so a single field is never overloaded with two
    meanings:

    * ``outcome_fingerprint`` — a deterministic digest of the *selected outcome*:
      context id, mode, surviving/structurally-removed/extractively-removed/restored/
      protected ids, equivalence status, fallback, policy **version**, and oracle
      identity (id + contract version). It does NOT bind token counts, unit text,
      requested reduction/budget, evaluation time, reason codes, the policy
      fingerprint, or the oracle validity/correlation — it is not a complete identity
      of the request, context contents, or oracle evaluation.
    * ``run_fingerprint`` — the *complete auditable run identity*: request identity
      (context contract version, id, correlation, ordered unit content digests,
      requested reduction, requested token budget, mode, evaluation time), policy
      identity (version + actual policy fingerprint + token-counter mode), oracle
      identity (id, contract version, evaluation ref, validity horizon, correlation),
      and the outcome (including reason codes).

    ``fingerprint`` is a DEPRECATED compatibility alias whose value equals
    ``outcome_fingerprint`` (byte-identical to the v0.1.0 field).
    """

    context_id: str
    mode: MinimizationMode
    original_ids: tuple[str, ...]
    surviving_ids: tuple[str, ...]
    removed_ids: tuple[str, ...]
    removed_structural: tuple[str, ...]
    removed_extractive: tuple[str, ...]
    restored_ids: tuple[str, ...]
    protected_ids: tuple[str, ...]
    original_tokens: int
    resulting_tokens: int
    #: The caller's requested fractional reduction in [0, 1], preserved verbatim on
    #: every result path (v0.1.1 fix — was previously hardcoded to 0.0).
    requested_reduction: float
    equivalence_status: EquivalenceStatus
    reduced: bool
    fell_back: bool
    reason_codes: tuple[str, ...]
    policy_version: str
    oracle_id: Optional[str] = None
    oracle_contract_version: Optional[str] = None
    #: The caller's requested absolute surviving-token ceiling, if any (v0.1.1).
    requested_token_budget: Optional[int] = None
    #: Digest of the selected outcome (see class docstring).
    outcome_fingerprint: str = ""
    #: Complete auditable run identity (see class docstring).
    run_fingerprint: str = ""
    #: DEPRECATED alias of ``outcome_fingerprint`` (byte-identical to v0.1.0).
    fingerprint: str = ""

    @property
    def achieved_reduction(self) -> float:
        if not self.original_tokens:
            return 0.0
        return (self.original_tokens - self.resulting_tokens) / self.original_tokens

    @property
    def equivalence_verified(self) -> bool:
        return self.equivalence_status in (
            EquivalenceStatus.VERIFIED,
            EquivalenceStatus.RESTORED,
        )


# Imported at end to avoid a circular import at module load; used only for typing
# in method signatures above.
from .protocols import TokenCounter  # noqa: E402,F401
