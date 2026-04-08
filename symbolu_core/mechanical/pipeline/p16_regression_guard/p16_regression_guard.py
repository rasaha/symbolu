"""
P16 Regression Guard — Core Guard Logic

Implements the P16RegressionGuard class with:
- snapshot(ctx) -> HashSnapshot: Capture upstream authority state
- assert_unchanged(ctx, snapshot) -> List[ContractViolation]: Verify no mutations
- enforce_allowlist(ctx, allowed_write_paths): Validate write operations

HARD INVARIANTS:
1. NO AUTHORITY DRIFT: Hashes of upstream authority objects unchanged post-P16
2. NO SLOT EXPANSION: P8 semantic slots unchanged (subset rule)
3. NO CERTAINTY AMPLIFICATION: P16 cannot introduce certainty flags
4. NO ACOUSTIC ESCALATION: P16 must not modify P10/P13/P14 frames

DESIGN PRINCIPLES:
- Deterministic: Same input → same violations
- No hidden state
- No LLM usage
- No heuristics
- No auto-correction
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from symbolu_core.mechanical.pipeline.p16_regression_guard.p16_contract_schema import (
    AuthorityScope,
    ContractViolation,
    HashSnapshot,
    P16InputContract,
    P16GuardResult,
    ScopeHash,
    ViolationType,
)
from symbolu_core.mechanical.pipeline.p16_regression_guard.p16_hashing import (
    stable_hash,
    stable_hash_combine,
)


class P16RegressionGuard:
    """
    Guard that enforces P16 contract and detects upstream authority mutations.

    This class provides three core operations:
    1. snapshot(ctx) - Capture immutable hash snapshot of upstream phases
    2. assert_unchanged(ctx, snapshot) - Verify no mutations occurred
    3. enforce_allowlist(ctx, allowed) - Validate P16 write boundaries

    The guard is STATELESS. It does not store snapshots internally.
    The snapshot should be stored on the PipelineContext.

    Usage:
        guard = P16RegressionGuard()
        contract = P16InputContract()

        # Pre-P16 work
        snapshot = guard.snapshot(ctx, contract)

        # ... P16 work happens ...

        # Post-P16 validation
        violations = guard.assert_unchanged(ctx, snapshot, contract)
        if violations:
            raise P16ContractViolationError(violations)
    """

    # Mapping of context attribute names to AuthorityScope
    SCOPE_ATTR_MAP: Dict[AuthorityScope, str] = {
        AuthorityScope.PO1: "phase_minus_one",
        AuthorityScope.PO2: "phase_zero",
        AuthorityScope.PO3: "allowed_actions",
        AuthorityScope.PO4: "po4_proposal",
        AuthorityScope.PO5: "po5_execution_eligibility",
        AuthorityScope.P6: "p6_regime",
        AuthorityScope.P7: "p7_discourse_envelope",
        AuthorityScope.P8: "semantic_frame",
        AuthorityScope.P9: "lexical_frame",
        AuthorityScope.P10: "p10_acoustic",
        AuthorityScope.P11: "p11_prosodic_evidence",
        AuthorityScope.P12: "p12_consistency",
        AuthorityScope.P13: "p13_safety_envelope",
        AuthorityScope.P14: "p14_surface",
        AuthorityScope.P15: "interaction_directive",
    }

    def __init__(self) -> None:
        """Initialize the guard (stateless)."""
        pass

    # =========================================================================
    # SNAPSHOT CAPTURE
    # =========================================================================

    def snapshot(
        self,
        ctx: Any,
        contract: Optional[P16InputContract] = None,
    ) -> HashSnapshot:
        """
        Capture a stable hash snapshot of all upstream authority objects.

        Args:
            ctx: The PipelineContext to snapshot
            contract: Optional contract (defaults to P16InputContract())

        Returns:
            HashSnapshot: Immutable snapshot of all authority hashes

        Raises:
            ValueError: If required context fields are missing
        """
        if contract is None:
            contract = P16InputContract()

        scope_hashes: List[ScopeHash] = []

        # Hash each readable scope
        for scope in contract.readable_scopes:
            attr_name = self.SCOPE_ATTR_MAP.get(scope)
            if attr_name is None:
                continue

            obj = getattr(ctx, attr_name, None)
            if obj is not None:
                try:
                    hash_value = stable_hash(obj)
                    field_count = self._count_fields(obj)
                    scope_hashes.append(ScopeHash(
                        scope=scope,
                        hash_value=hash_value,
                        field_count=field_count,
                        is_present=True,
                    ))
                except (TypeError, ValueError) as e:
                    # If object can't be hashed, use a placeholder
                    scope_hashes.append(ScopeHash(
                        scope=scope,
                        hash_value=f"unhashable:{type(obj).__name__}",
                        field_count=0,
                        is_present=True,
                    ))
            else:
                # Mark as not present
                scope_hashes.append(ScopeHash(
                    scope=scope,
                    hash_value="not_present",
                    field_count=0,
                    is_present=False,
                ))

        # Compute aggregate hash
        present_hashes = [sh.hash_value for sh in scope_hashes if sh.is_present]
        aggregate_hash = stable_hash_combine(*present_hashes) if present_hashes else "empty"

        # Extract slot set hash from P8
        slot_set_hash = self._extract_slot_set_hash(ctx)

        # Extract safety bounds hash from P13
        safety_bounds_hash = self._extract_safety_bounds_hash(ctx)

        # Extract blocked state
        blocked_state = self._extract_blocked_state(ctx)

        # Check for uncertainty markers
        uncertainty_present = self._check_uncertainty_present(ctx)

        return HashSnapshot(
            scope_hashes=frozenset(scope_hashes),
            aggregate_hash=aggregate_hash,
            slot_set_hash=slot_set_hash,
            safety_bounds_hash=safety_bounds_hash,
            blocked_state=blocked_state,
            uncertainty_present=uncertainty_present,
            captured_at_phase=15,
        )

    # =========================================================================
    # MUTATION DETECTION
    # =========================================================================

    def assert_unchanged(
        self,
        ctx: Any,
        snapshot: HashSnapshot,
        contract: Optional[P16InputContract] = None,
    ) -> List[ContractViolation]:
        """
        Assert that upstream authority objects have not been mutated.

        This method checks ALL authority-bearing fields and collects
        ALL violations. It does NOT stop at the first violation.

        Args:
            ctx: The current PipelineContext
            snapshot: The HashSnapshot captured before P16
            contract: Optional contract (defaults to P16InputContract())

        Returns:
            List[ContractViolation]: All detected violations (may be empty)
        """
        if contract is None:
            contract = P16InputContract()

        violations: List[ContractViolation] = []

        # Check authority scope hashes
        self._check_authority_drift(ctx, snapshot, contract, violations)

        # Check slot expansion
        self._check_slot_expansion(ctx, snapshot, violations)

        # Check certainty amplification
        self._check_certainty_amplification(ctx, snapshot, violations)

        # Check acoustic escalation
        self._check_acoustic_escalation(ctx, snapshot, contract, violations)

        # Check blocked state preservation
        self._check_blocked_preservation(ctx, snapshot, violations)

        return violations

    # =========================================================================
    # ALLOWLIST ENFORCEMENT
    # =========================================================================

    def enforce_allowlist(
        self,
        ctx: Any,
        written_paths: Set[str],
        contract: Optional[P16InputContract] = None,
        debug_before: Optional[Any] = None,
        metrics_before: Optional[Any] = None,
    ) -> List[ContractViolation]:
        """
        Enforce the P16 write allowlist.

        P16 may only write to:
        - ctx.p16 (full write)
        - ctx.debug (append-only)
        - ctx.metrics (append-only)

        Args:
            ctx: The current PipelineContext
            written_paths: Set of paths that were written to
            contract: Optional contract (defaults to P16InputContract())
            debug_before: Debug state before P16 (for append-only check)
            metrics_before: Metrics state before P16 (for append-only check)

        Returns:
            List[ContractViolation]: Violations for forbidden writes
        """
        if contract is None:
            contract = P16InputContract()

        violations: List[ContractViolation] = []

        # Check each written path
        for path in written_paths:
            if not contract.is_writable(path) and not contract.is_append_only(path):
                violations.append(ContractViolation(
                    scope=AuthorityScope.P16,
                    violation_type=ViolationType.FORBIDDEN_WRITE,
                    field_path=path,
                    expected="no write",
                    observed="write attempted",
                    reason=f"P16 attempted to write to forbidden path: {path}",
                ))

        # Check append-only semantics for debug
        if debug_before is not None:
            self._check_append_only(
                ctx, "debug", debug_before,
                getattr(ctx, "debug", None),
                violations
            )

        # Check append-only semantics for metrics
        if metrics_before is not None:
            self._check_append_only(
                ctx, "metrics", metrics_before,
                getattr(ctx, "metrics", None),
                violations
            )

        return violations

    # =========================================================================
    # INTERNAL VALIDATION METHODS
    # =========================================================================

    def _check_authority_drift(
        self,
        ctx: Any,
        snapshot: HashSnapshot,
        contract: P16InputContract,
        violations: List[ContractViolation],
    ) -> None:
        """Check that authority scope hashes have not drifted."""
        for scope in contract.authority_scopes:
            expected_hash = snapshot.get_scope_hash(scope)
            if expected_hash is None or expected_hash == "not_present":
                continue

            attr_name = self.SCOPE_ATTR_MAP.get(scope)
            if attr_name is None:
                continue

            current_obj = getattr(ctx, attr_name, None)
            if current_obj is None:
                # Object was removed - that's a violation
                violations.append(ContractViolation(
                    scope=scope,
                    violation_type=ViolationType.AUTHORITY_DRIFT,
                    field_path=attr_name,
                    expected=expected_hash,
                    observed="removed",
                    reason=f"Authority object {attr_name} was removed",
                ))
                continue

            try:
                current_hash = stable_hash(current_obj)
            except (TypeError, ValueError):
                current_hash = f"unhashable:{type(current_obj).__name__}"

            if current_hash != expected_hash:
                violations.append(ContractViolation(
                    scope=scope,
                    violation_type=ViolationType.AUTHORITY_DRIFT,
                    field_path=attr_name,
                    expected=expected_hash,
                    observed=current_hash,
                    reason=f"Authority hash drift detected for {scope.value}",
                ))

    def _check_slot_expansion(
        self,
        ctx: Any,
        snapshot: HashSnapshot,
        violations: List[ContractViolation],
    ) -> None:
        """Check that P8 semantic slots have not been expanded."""
        if not snapshot.slot_set_hash:
            return

        current_slot_hash = self._extract_slot_set_hash(ctx)

        if current_slot_hash != snapshot.slot_set_hash:
            # Get actual slot sets for comparison
            original_slots = self._extract_slot_names(ctx, from_snapshot=True)
            current_slots = self._extract_slot_names(ctx, from_snapshot=False)

            # Check for expansion (new slots added)
            if current_slots and original_slots:
                expanded = current_slots - original_slots
                if expanded:
                    violations.append(ContractViolation(
                        scope=AuthorityScope.P8,
                        violation_type=ViolationType.SLOT_EXPANSION,
                        field_path="semantic_frame.slots",
                        expected=snapshot.slot_set_hash,
                        observed=current_slot_hash,
                        reason=f"P8 slots expanded: {sorted(expanded)}",
                    ))

    def _check_certainty_amplification(
        self,
        ctx: Any,
        snapshot: HashSnapshot,
        violations: List[ContractViolation],
    ) -> None:
        """
        Check that P16 doesn't introduce certainty where uncertainty existed.

        If P8 had UNCERTAINTY markers, P16 cannot introduce certainty signals.
        """
        if not snapshot.uncertainty_present:
            return

        # Check for certainty flags that shouldn't exist
        certainty_signals = [
            "certainty",
            "confidence",
            "authority_certainty",
            "semantic_certainty",
        ]

        for signal in certainty_signals:
            value = getattr(ctx, signal, None)
            if value is not None:
                violations.append(ContractViolation(
                    scope=AuthorityScope.P16,
                    violation_type=ViolationType.CERTAINTY_AMPLIFICATION,
                    field_path=signal,
                    expected=None,
                    observed=value,
                    reason=f"Certainty signal '{signal}' introduced despite upstream uncertainty",
                ))

        # Also check p16 namespace for certainty
        p16_data = getattr(ctx, "p16", None)
        if p16_data is not None:
            if isinstance(p16_data, dict):
                for key in certainty_signals:
                    if key in p16_data:
                        violations.append(ContractViolation(
                            scope=AuthorityScope.P16,
                            violation_type=ViolationType.CERTAINTY_AMPLIFICATION,
                            field_path=f"p16.{key}",
                            expected=None,
                            observed=p16_data[key],
                            reason=f"Certainty signal 'p16.{key}' introduced despite upstream uncertainty",
                        ))

    def _check_acoustic_escalation(
        self,
        ctx: Any,
        snapshot: HashSnapshot,
        contract: P16InputContract,
        violations: List[ContractViolation],
    ) -> None:
        """Check that P16 has not modified acoustic/safety frames."""
        for scope in contract.acoustic_protected_scopes:
            expected_hash = snapshot.get_scope_hash(scope)
            if expected_hash is None or expected_hash == "not_present":
                continue

            attr_name = self.SCOPE_ATTR_MAP.get(scope)
            if attr_name is None:
                continue

            current_obj = getattr(ctx, attr_name, None)
            if current_obj is None:
                continue

            try:
                current_hash = stable_hash(current_obj)
            except (TypeError, ValueError):
                current_hash = f"unhashable:{type(current_obj).__name__}"

            if current_hash != expected_hash:
                violations.append(ContractViolation(
                    scope=scope,
                    violation_type=ViolationType.ACOUSTIC_ESCALATION,
                    field_path=attr_name,
                    expected=expected_hash,
                    observed=current_hash,
                    reason=f"Acoustic escalation: {scope.value} was modified",
                ))

    def _check_blocked_preservation(
        self,
        ctx: Any,
        snapshot: HashSnapshot,
        violations: List[ContractViolation],
    ) -> None:
        """Check that blocked state is preserved (blocked cannot become unblocked)."""
        if not snapshot.blocked_state:
            return  # No violation if wasn't blocked

        current_blocked = self._extract_blocked_state(ctx)

        if not current_blocked:
            violations.append(ContractViolation(
                scope=AuthorityScope.P15,
                violation_type=ViolationType.BLOCKED_UNBLOCK,
                field_path="blocked_state",
                expected=True,
                observed=False,
                reason="Blocked state was illegally unblocked",
            ))

    def _check_append_only(
        self,
        ctx: Any,
        path: str,
        before: Any,
        after: Any,
        violations: List[ContractViolation],
    ) -> None:
        """Check append-only semantics for a path."""
        if before is None:
            return  # Can add anything to empty

        if after is None:
            # Was replaced with None - violation
            violations.append(ContractViolation(
                scope=AuthorityScope.P16,
                violation_type=ViolationType.APPEND_ONLY_REPLACEMENT,
                field_path=path,
                expected="append-only",
                observed="replaced with None",
                reason=f"Append-only path '{path}' was replaced instead of appended",
            ))
            return

        # For lists/dicts, check that original content is preserved
        if isinstance(before, list) and isinstance(after, list):
            if len(after) < len(before):
                violations.append(ContractViolation(
                    scope=AuthorityScope.P16,
                    violation_type=ViolationType.APPEND_ONLY_REPLACEMENT,
                    field_path=path,
                    expected=f"len >= {len(before)}",
                    observed=f"len = {len(after)}",
                    reason=f"Append-only list '{path}' was truncated",
                ))
            # Check that original items are preserved
            for i, item in enumerate(before):
                if i >= len(after) or after[i] != item:
                    violations.append(ContractViolation(
                        scope=AuthorityScope.P16,
                        violation_type=ViolationType.APPEND_ONLY_REPLACEMENT,
                        field_path=f"{path}[{i}]",
                        expected=item,
                        observed=after[i] if i < len(after) else "removed",
                        reason=f"Append-only list '{path}' item {i} was modified",
                    ))
                    break  # Report first modification only

        elif isinstance(before, dict) and isinstance(after, dict):
            # Check that original keys are preserved
            for key, value in before.items():
                if key not in after:
                    violations.append(ContractViolation(
                        scope=AuthorityScope.P16,
                        violation_type=ViolationType.APPEND_ONLY_REPLACEMENT,
                        field_path=f"{path}.{key}",
                        expected=value,
                        observed="removed",
                        reason=f"Append-only dict '{path}' key '{key}' was removed",
                    ))
                elif after[key] != value:
                    violations.append(ContractViolation(
                        scope=AuthorityScope.P16,
                        violation_type=ViolationType.APPEND_ONLY_REPLACEMENT,
                        field_path=f"{path}.{key}",
                        expected=value,
                        observed=after[key],
                        reason=f"Append-only dict '{path}' key '{key}' was modified",
                    ))

    # =========================================================================
    # HELPER EXTRACTION METHODS
    # =========================================================================

    def _count_fields(self, obj: Any) -> int:
        """Count the number of fields in an object."""
        if hasattr(obj, "__dataclass_fields__"):
            return len(obj.__dataclass_fields__)
        if isinstance(obj, dict):
            return len(obj)
        if hasattr(obj, "__dict__"):
            return len(obj.__dict__)
        return 0

    def _extract_slot_set_hash(self, ctx: Any) -> str:
        """Extract hash of P8 semantic slot names."""
        semantic_frame = getattr(ctx, "semantic_frame", None)
        if semantic_frame is None:
            return ""

        slots = getattr(semantic_frame, "slots", None)
        if slots is None:
            return ""

        # Extract slot names
        if isinstance(slots, dict):
            slot_names = sorted(slots.keys())
        elif isinstance(slots, (list, tuple)):
            slot_names = sorted(str(s) for s in slots)
        else:
            return ""

        return stable_hash({"slot_names": slot_names})

    def _extract_slot_names(self, ctx: Any, from_snapshot: bool = False) -> Optional[Set[str]]:
        """Extract set of P8 slot names."""
        semantic_frame = getattr(ctx, "semantic_frame", None)
        if semantic_frame is None:
            return None

        slots = getattr(semantic_frame, "slots", None)
        if slots is None:
            return None

        if isinstance(slots, dict):
            return set(slots.keys())
        elif isinstance(slots, (list, tuple)):
            return set(str(s) for s in slots)

        return None

    def _extract_safety_bounds_hash(self, ctx: Any) -> str:
        """Extract hash of P13 safety envelope bounds."""
        safety_envelope = getattr(ctx, "p13_safety_envelope", None)
        if safety_envelope is None:
            return ""

        # Extract bound-related fields
        bounds_data = {}
        for field in ["max_energy", "max_rate", "allow_emphasis", "allow_pitch_contours"]:
            value = getattr(safety_envelope, field, None)
            if value is not None:
                bounds_data[field] = value

        if not bounds_data:
            return ""

        return stable_hash(bounds_data)

    def _extract_blocked_state(self, ctx: Any) -> bool:
        """Extract blocked state from context."""
        # Check interaction_directive.blocked first
        interaction_directive = getattr(ctx, "interaction_directive", None)
        if interaction_directive is not None:
            blocked = getattr(interaction_directive, "blocked", None)
            if blocked is not None:
                return bool(blocked)

        # Check phase_minus_one for BLOCKED policy
        phase_minus_one = getattr(ctx, "phase_minus_one", None)
        if phase_minus_one is not None:
            overall_policy = getattr(phase_minus_one, "overall_policy", None)
            if overall_policy is not None:
                if hasattr(overall_policy, "value"):
                    return overall_policy.value == "BLOCKED"
                return str(overall_policy) == "BLOCKED"

        # Check p6_regime for HOLD
        p6_regime = getattr(ctx, "p6_regime", None)
        if p6_regime is not None:
            regime = getattr(p6_regime, "regime", None)
            if regime is not None:
                if hasattr(regime, "value"):
                    return regime.value == "HOLD"
                return str(regime) == "HOLD"

        return False

    def _check_uncertainty_present(self, ctx: Any) -> bool:
        """Check if P8 has uncertainty markers."""
        semantic_frame = getattr(ctx, "semantic_frame", None)
        if semantic_frame is None:
            return False

        # Check for uncertainty field
        uncertainty = getattr(semantic_frame, "uncertainty", None)
        if uncertainty is not None:
            return bool(uncertainty)

        # Check for UNCERTAIN slot values
        slots = getattr(semantic_frame, "slots", None)
        if slots and isinstance(slots, dict):
            for value in slots.values():
                if isinstance(value, str) and "UNCERTAIN" in value.upper():
                    return True
                if hasattr(value, "value") and "UNCERTAIN" in str(value.value).upper():
                    return True

        return False

    # =========================================================================
    # CONVENIENCE METHOD
    # =========================================================================

    def validate(
        self,
        ctx: Any,
        snapshot: HashSnapshot,
        contract: Optional[P16InputContract] = None,
    ) -> P16GuardResult:
        """
        Full validation returning a P16GuardResult.

        Args:
            ctx: The current PipelineContext
            snapshot: The HashSnapshot captured before P16
            contract: Optional contract (defaults to P16InputContract())

        Returns:
            P16GuardResult with all violations
        """
        if contract is None:
            contract = P16InputContract()

        violations = self.assert_unchanged(ctx, snapshot, contract)

        return P16GuardResult(
            passed=len(violations) == 0,
            violations=tuple(violations),
            snapshot=snapshot,
            contract=contract,
        )


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = ["P16RegressionGuard"]
