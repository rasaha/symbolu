"""
Tests for Domain Semantic Policy Layer.

Comprehensive coverage of:
- DomainActionMode severity ordering
- DomainProfile construction and defaults
- DomainCoherenceRule matching
- DomainToolPermission matching
- DomainThresholdOverrides
- DomainPolicyInterpreter (action coherence matrix, rules, thresholds)
- DomainRegistry
- Fail-closed behavior
- resolve_domain_policy top-level entry
- All 3 built-in profiles (finance, devops, research)
- Cross-domain comparison (same state, different result)
- GovernanceService integration
- SafeMCPGateway integration
"""

import pytest
from unittest.mock import MagicMock

from agentic.agentic_framework.jepa_governance import (
    GovernanceRegime,
    RuntimeActionCategory,
    OntologySignal,
    VrittiSignal,
    JEPACompositeSignal,
    RuntimeProcessState,
    ResidualSignal,
    JEPAGovernanceAssessment,
    ONTOLOGY_LAYERS,
)
from agentic.agentic_framework.domain_policy import (
    DomainActionMode,
    DomainToolPermission,
    DomainCoherenceRule,
    DomainThresholdOverrides,
    DomainProfile,
    DomainPolicyResult,
    DomainPolicyInterpreter,
    DomainRegistry,
    resolve_domain_policy,
    fail_closed_result,
    create_default_registry,
    _tool_matches,
    _stricter,
    FINANCE_PROFILE,
    DEVOPS_PROFILE,
    RESEARCH_PROFILE,
)


# =========================================================================
# Helpers: build synthetic JEPA assessments for testing
# =========================================================================


def _make_ontology(primary="O7_REASONING", confidence=0.9):
    weights = {l: 0.1 for l in ONTOLOGY_LAYERS}
    weights[primary] = 0.9
    gov = sum(weights[l] for l in ONTOLOGY_LAYERS if l.startswith(("O7", "O8", "O9", "O10", "O11", "O12")))
    exe = sum(weights[l] for l in ONTOLOGY_LAYERS if l.startswith(("O1", "O2", "O3", "O4", "O5", "O6")))
    return OntologySignal(
        layer_weights=weights,
        primary_layer=primary,
        governance_strength=gov,
        execution_strength=exe,
        confidence=confidence,
        evidence="test",
    )


def _make_vritti(primary="pramana", coherence=0.9):
    dist = {"pramana": 0.1, "viparyaya": 0.1, "vikalpa": 0.1,
            "smrti": 0.1, "nidra": 0.1}
    dist[primary] = 0.6
    total = sum(dist.values())
    dist = {k: v / total for k, v in dist.items()}
    return VrittiSignal(
        distribution=dist,
        primary_vritti=primary,
        coherence=coherence,
        score=0.8,
        confidence=0.9,
        evidence="test",
    )


def _make_composite(vritti_primary="pramana", ontology_primary="O7_REASONING",
                    alignment=0.9, confidence=0.9):
    ont = _make_ontology(ontology_primary, confidence)
    vri = _make_vritti(vritti_primary)
    return JEPACompositeSignal(
        ontology=ont,
        vritti=vri,
        expected_ontology={l: 0.1 for l in ONTOLOGY_LAYERS},
        actual_ontology=ont.layer_weights,
        ontology_vritti_alignment=alignment,
        integrated_confidence=confidence,
        stability=0.8,
        summary="test",
        coupling_evidence=("pramana->O7",),
    )


def _make_runtime(action_cat=RuntimeActionCategory.READ_ONLY, tool="file_read",
                  risk="read_only"):
    return RuntimeProcessState(
        action_type="call_tool",
        tool_name=tool,
        action_category=action_cat,
        risk_level=risk,
        confidence_score=0.8,
        agency_level="FULL",
        requires_confirmation=False,
        execution_mode="full",
        escalation_level="none",
        session_id="s1",
        actor_id="a1",
        declared_capabilities=(),
        is_side_effecting=action_cat != RuntimeActionCategory.READ_ONLY,
    )


def _make_residual(regime=GovernanceRegime.NORMAL, magnitude=0.1,
                   semantic=0.9, coherence=0.9):
    return ResidualSignal(
        residual_magnitude=magnitude,
        semantic_consistency=semantic,
        action_state_coherence=coherence,
        regime=regime,
        risk_factors=(),
        reason_codes=("REGIME_NORMAL",),
        explanation="test",
    )


def _make_assessment(
    regime=GovernanceRegime.NORMAL,
    action="ALLOW",
    exec_override=None,
    esc_override=None,
    conf_adj=0.0,
    vritti_primary="pramana",
    ontology_primary="O7_REASONING",
    action_cat=RuntimeActionCategory.READ_ONLY,
    tool_name="file_read",
    alignment=0.9,
    confidence=0.9,
    residual_magnitude=0.1,
):
    composite = _make_composite(vritti_primary, ontology_primary,
                                alignment, confidence)
    runtime = _make_runtime(action_cat, tool_name)
    residual = _make_residual(regime, residual_magnitude)
    return JEPAGovernanceAssessment(
        regime=regime,
        recommended_action=action,
        execution_mode_override=exec_override,
        escalation_override=esc_override,
        confidence_adjustment=conf_adj,
        reason_codes=("REGIME_NORMAL",),
        rationale="test",
        jepa_composite=composite,
        runtime_state=runtime,
        residual=residual,
    )


# =========================================================================
# Test: DomainActionMode severity ordering
# =========================================================================


class TestDomainActionModeSeverity:

    def test_severity_ordering(self):
        modes = list(DomainActionMode)
        for i in range(len(modes)):
            for j in range(i + 1, len(modes)):
                assert modes[i].severity <= modes[j].severity, (
                    f"{modes[i]} should be <= {modes[j]}"
                )

    def test_is_stricter_than(self):
        assert DomainActionMode.BLOCKED.is_stricter_than(DomainActionMode.ALLOW)
        assert DomainActionMode.CONFIRM_REQUIRED.is_stricter_than(DomainActionMode.READ_ONLY)
        assert not DomainActionMode.ALLOW.is_stricter_than(DomainActionMode.BLOCKED)
        assert not DomainActionMode.ALLOW.is_stricter_than(DomainActionMode.ALLOW)

    def test_stricter_helper(self):
        assert _stricter(DomainActionMode.ALLOW, DomainActionMode.BLOCKED) == DomainActionMode.BLOCKED
        assert _stricter(DomainActionMode.BLOCKED, DomainActionMode.ALLOW) == DomainActionMode.BLOCKED
        assert _stricter(DomainActionMode.DRAFT_ONLY, DomainActionMode.DRAFT_ONLY) == DomainActionMode.DRAFT_ONLY


# =========================================================================
# Test: _tool_matches pattern matching
# =========================================================================


class TestToolMatches:

    def test_exact_match(self):
        assert _tool_matches("file_read", "file_read")
        assert not _tool_matches("file_read", "file_write")

    def test_prefix_glob(self):
        assert _tool_matches("db_*", "db_query")
        assert _tool_matches("db_*", "db_write")
        assert not _tool_matches("db_*", "file_read")

    def test_suffix_glob(self):
        assert _tool_matches("*_read", "file_read")
        assert _tool_matches("*_read", "db_read")
        assert not _tool_matches("*_read", "file_write")

    def test_universal_glob(self):
        assert _tool_matches("*", "anything")
        assert _tool_matches("*", "")

    def test_no_match(self):
        assert not _tool_matches("specific_tool", "other_tool")


# =========================================================================
# Test: DomainThresholdOverrides
# =========================================================================


class TestDomainThresholdOverrides:

    def test_defaults(self):
        t = DomainThresholdOverrides()
        assert t.effective_alignment_critical() == 0.60
        assert t.effective_alignment_low() == 0.70

    def test_stricter_override(self):
        t = DomainThresholdOverrides(alignment_critical=0.75)
        assert t.effective_alignment_critical() == 0.75

    def test_cannot_relax_below_default(self):
        t = DomainThresholdOverrides(alignment_critical=0.40)
        assert t.effective_alignment_critical() == 0.60

    def test_alignment_low_override(self):
        t = DomainThresholdOverrides(alignment_low=0.85)
        assert t.effective_alignment_low() == 0.85


# =========================================================================
# Test: DomainCoherenceRule matching
# =========================================================================


class TestDomainCoherenceRuleMatching:

    def test_empty_rule_matches_everything(self):
        rule = DomainCoherenceRule(name="catch_all", result_mode=DomainActionMode.BLOCKED)
        interp = DomainPolicyInterpreter(DomainProfile(
            domain_id="test", display_name="Test",
            coherence_rules=(rule,),
        ))
        assessment = _make_assessment()
        result = interp.interpret(assessment)
        assert "catch_all" in result.fired_rules

    def test_vritti_filter(self):
        rule = DomainCoherenceRule(
            name="viparyaya_only",
            vritti_modes=frozenset({"viparyaya"}),
            result_mode=DomainActionMode.BLOCKED,
        )
        interp = DomainPolicyInterpreter(DomainProfile(
            domain_id="test", display_name="Test",
            coherence_rules=(rule,),
        ))
        # pramana -> rule should NOT fire
        result = interp.interpret(_make_assessment(vritti_primary="pramana"))
        assert "viparyaya_only" not in result.fired_rules

        # viparyaya -> rule should fire
        result = interp.interpret(_make_assessment(vritti_primary="viparyaya"))
        assert "viparyaya_only" in result.fired_rules

    def test_regime_filter(self):
        rule = DomainCoherenceRule(
            name="drift_only",
            regimes=frozenset({GovernanceRegime.PROCESS_DRIFT}),
            result_mode=DomainActionMode.CONFIRM_REQUIRED,
        )
        interp = DomainPolicyInterpreter(DomainProfile(
            domain_id="test", display_name="Test",
            coherence_rules=(rule,),
        ))
        result = interp.interpret(_make_assessment(regime=GovernanceRegime.NORMAL))
        assert "drift_only" not in result.fired_rules

        result = interp.interpret(_make_assessment(
            regime=GovernanceRegime.PROCESS_DRIFT, action="DEGRADE",
        ))
        assert "drift_only" in result.fired_rules

    def test_min_confidence_filter(self):
        rule = DomainCoherenceRule(
            name="high_conf_only",
            min_confidence=0.8,
            result_mode=DomainActionMode.ALLOW,
        )
        interp = DomainPolicyInterpreter(DomainProfile(
            domain_id="test", display_name="Test",
            coherence_rules=(rule,),
        ))
        # Low confidence -> rule should NOT fire
        result = interp.interpret(_make_assessment(confidence=0.5))
        assert "high_conf_only" not in result.fired_rules

        # High confidence -> rule should fire
        result = interp.interpret(_make_assessment(confidence=0.9))
        assert "high_conf_only" in result.fired_rules


# =========================================================================
# Test: Action Coherence Matrix
# =========================================================================


class TestActionCoherenceMatrix:

    def test_matrix_lookup(self):
        profile = DomainProfile(
            domain_id="test", display_name="Test",
            action_coherence_matrix={
                (GovernanceRegime.NORMAL, RuntimeActionCategory.READ_ONLY):
                    DomainActionMode.ALLOW,
                (GovernanceRegime.NORMAL, RuntimeActionCategory.MUTATING):
                    DomainActionMode.CONFIRM_REQUIRED,
            },
        )
        interp = DomainPolicyInterpreter(profile)

        result = interp.interpret(_make_assessment(
            action_cat=RuntimeActionCategory.READ_ONLY,
        ))
        assert result.matrix_mode == DomainActionMode.ALLOW

        result = interp.interpret(_make_assessment(
            action_cat=RuntimeActionCategory.MUTATING,
        ))
        assert result.matrix_mode == DomainActionMode.CONFIRM_REQUIRED

    def test_missing_matrix_entry_uses_default(self):
        profile = DomainProfile(
            domain_id="test", display_name="Test",
            default_mode=DomainActionMode.BLOCKED,
        )
        interp = DomainPolicyInterpreter(profile)
        result = interp.interpret(_make_assessment())
        assert result.mode == DomainActionMode.BLOCKED
        assert "DEFAULT:blocked" in result.reason_codes


# =========================================================================
# Test: Tool Permissions
# =========================================================================


class TestToolPermissions:

    def test_tool_permission_max_mode(self):
        profile = DomainProfile(
            domain_id="test", display_name="Test",
            tool_permissions=(
                DomainToolPermission(
                    tool_pattern="db_*",
                    max_mode=DomainActionMode.CONFIRM_REQUIRED,
                ),
            ),
        )
        interp = DomainPolicyInterpreter(profile)
        result = interp.interpret(_make_assessment(), tool_name="db_query")
        assert result.tool_mode == DomainActionMode.CONFIRM_REQUIRED

    def test_tool_blocked_in_regime(self):
        profile = DomainProfile(
            domain_id="test", display_name="Test",
            tool_permissions=(
                DomainToolPermission(
                    tool_pattern="deploy_*",
                    max_mode=DomainActionMode.CONFIRM_REQUIRED,
                    blocked_in_regimes=frozenset({GovernanceRegime.PROCESS_DRIFT}),
                ),
            ),
        )
        interp = DomainPolicyInterpreter(profile)

        # NORMAL -> not blocked
        result = interp.interpret(_make_assessment(), tool_name="deploy_prod")
        assert result.tool_mode == DomainActionMode.CONFIRM_REQUIRED

        # PROCESS_DRIFT -> blocked
        result = interp.interpret(
            _make_assessment(regime=GovernanceRegime.PROCESS_DRIFT, action="DEGRADE"),
            tool_name="deploy_prod",
        )
        assert result.tool_mode == DomainActionMode.BLOCKED

    def test_no_tool_permission_returns_none(self):
        profile = DomainProfile(domain_id="test", display_name="Test")
        interp = DomainPolicyInterpreter(profile)
        result = interp.interpret(_make_assessment(), tool_name="unknown_tool")
        assert result.tool_mode is None


# =========================================================================
# Test: Threshold Checks
# =========================================================================


class TestThresholdChecks:

    def test_alignment_critical_blocks(self):
        profile = DomainProfile(
            domain_id="test", display_name="Test",
            thresholds=DomainThresholdOverrides(alignment_critical=0.70),
            action_coherence_matrix={
                (GovernanceRegime.NORMAL, RuntimeActionCategory.READ_ONLY):
                    DomainActionMode.ALLOW,
            },
        )
        interp = DomainPolicyInterpreter(profile)
        result = interp.interpret(_make_assessment(alignment=0.50))
        assert result.threshold_mode == DomainActionMode.BLOCKED
        assert result.mode == DomainActionMode.BLOCKED

    def test_alignment_low_confirms(self):
        profile = DomainProfile(
            domain_id="test", display_name="Test",
            thresholds=DomainThresholdOverrides(alignment_low=0.85),
            action_coherence_matrix={
                (GovernanceRegime.NORMAL, RuntimeActionCategory.READ_ONLY):
                    DomainActionMode.ALLOW,
            },
        )
        interp = DomainPolicyInterpreter(profile)
        result = interp.interpret(_make_assessment(alignment=0.80))
        assert result.threshold_mode == DomainActionMode.CONFIRM_REQUIRED

    def test_residual_too_high(self):
        profile = DomainProfile(
            domain_id="test", display_name="Test",
            thresholds=DomainThresholdOverrides(max_residual_for_allow=0.30),
            action_coherence_matrix={
                (GovernanceRegime.NORMAL, RuntimeActionCategory.READ_ONLY):
                    DomainActionMode.ALLOW,
            },
        )
        interp = DomainPolicyInterpreter(profile)
        result = interp.interpret(_make_assessment(residual_magnitude=0.50))
        assert result.threshold_mode == DomainActionMode.CONFIRM_REQUIRED


# =========================================================================
# Test: Vritti Execution Guard
# =========================================================================


class TestVrittiExecutionGuard:

    def test_blocked_vritti_for_mutating(self):
        profile = DomainProfile(
            domain_id="test", display_name="Test",
            allowed_vritti_for_execution=frozenset({"pramana"}),
            action_coherence_matrix={
                (GovernanceRegime.NORMAL, RuntimeActionCategory.MUTATING):
                    DomainActionMode.ALLOW,
            },
        )
        interp = DomainPolicyInterpreter(profile)
        result = interp.interpret(_make_assessment(
            vritti_primary="viparyaya",
            action_cat=RuntimeActionCategory.MUTATING,
        ))
        assert result.mode == DomainActionMode.BLOCKED
        assert any("VRITTI_GUARD" in c for c in result.reason_codes)

    def test_allowed_vritti_passes(self):
        profile = DomainProfile(
            domain_id="test", display_name="Test",
            allowed_vritti_for_execution=frozenset({"pramana", "smrti"}),
            action_coherence_matrix={
                (GovernanceRegime.NORMAL, RuntimeActionCategory.MUTATING):
                    DomainActionMode.ALLOW,
            },
        )
        interp = DomainPolicyInterpreter(profile)
        result = interp.interpret(_make_assessment(
            vritti_primary="pramana",
            action_cat=RuntimeActionCategory.MUTATING,
        ))
        assert result.mode == DomainActionMode.ALLOW

    def test_read_only_bypasses_vritti_guard(self):
        profile = DomainProfile(
            domain_id="test", display_name="Test",
            allowed_vritti_for_execution=frozenset({"pramana"}),
            action_coherence_matrix={
                (GovernanceRegime.NORMAL, RuntimeActionCategory.READ_ONLY):
                    DomainActionMode.ALLOW,
            },
        )
        interp = DomainPolicyInterpreter(profile)
        result = interp.interpret(_make_assessment(
            vritti_primary="viparyaya",
            action_cat=RuntimeActionCategory.READ_ONLY,
        ))
        # vritti guard only applies to mutating/destructive/privileged
        assert result.mode == DomainActionMode.ALLOW


# =========================================================================
# Test: Strictest-wins merge
# =========================================================================


class TestStrictestWinsMerge:

    def test_matrix_and_rule_merge_to_strictest(self):
        profile = DomainProfile(
            domain_id="test", display_name="Test",
            action_coherence_matrix={
                (GovernanceRegime.NORMAL, RuntimeActionCategory.READ_ONLY):
                    DomainActionMode.ALLOW,
            },
            coherence_rules=(
                DomainCoherenceRule(
                    name="escalate_all",
                    result_mode=DomainActionMode.CONFIRM_REQUIRED,
                ),
            ),
        )
        interp = DomainPolicyInterpreter(profile)
        result = interp.interpret(_make_assessment())
        # CONFIRM_REQUIRED > ALLOW
        assert result.mode == DomainActionMode.CONFIRM_REQUIRED

    def test_tool_permission_overrides_matrix(self):
        profile = DomainProfile(
            domain_id="test", display_name="Test",
            action_coherence_matrix={
                (GovernanceRegime.NORMAL, RuntimeActionCategory.READ_ONLY):
                    DomainActionMode.ALLOW,
            },
            tool_permissions=(
                DomainToolPermission(
                    tool_pattern="sensitive_*",
                    max_mode=DomainActionMode.BLOCKED,
                ),
            ),
        )
        interp = DomainPolicyInterpreter(profile)
        result = interp.interpret(_make_assessment(), tool_name="sensitive_data")
        assert result.mode == DomainActionMode.BLOCKED


# =========================================================================
# Test: DomainRegistry
# =========================================================================


class TestDomainRegistry:

    def test_register_and_get(self):
        reg = DomainRegistry()
        profile = DomainProfile(domain_id="test", display_name="Test")
        reg.register(profile)
        assert reg.get("test") is profile
        assert "test" in reg
        assert len(reg) == 1

    def test_duplicate_raises(self):
        reg = DomainRegistry()
        profile = DomainProfile(domain_id="test", display_name="Test")
        reg.register(profile)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(profile)

    def test_get_missing_returns_none(self):
        reg = DomainRegistry()
        assert reg.get("missing") is None

    def test_get_or_raise(self):
        reg = DomainRegistry()
        with pytest.raises(KeyError, match="not registered"):
            reg.get_or_raise("missing")

    def test_list_domains(self):
        reg = create_default_registry()
        domains = reg.list_domains()
        assert "devops" in domains
        assert "finance" in domains
        assert "research" in domains

    def test_interpreter_for(self):
        reg = create_default_registry()
        interp = reg.interpreter_for("finance")
        assert interp.domain_id == "finance"


# =========================================================================
# Test: Fail-closed behavior
# =========================================================================


class TestFailClosed:

    def test_fail_closed_result(self):
        result = fail_closed_result()
        assert result.mode == DomainActionMode.BLOCKED
        assert result.domain_id == "__unknown__"
        assert "DOMAIN_UNAVAILABLE" in result.reason_codes

    def test_fail_closed_with_reason(self):
        result = fail_closed_result("mydom", "profile not found")
        assert result.domain_id == "mydom"
        assert "profile not found" in result.rationale

    def test_resolve_missing_domain_fails_closed(self):
        reg = DomainRegistry()
        assessment = _make_assessment()
        result = resolve_domain_policy(assessment, reg, "nonexistent")
        assert result.mode == DomainActionMode.BLOCKED

    def test_resolve_domain_exception_fails_closed(self):
        reg = DomainRegistry()
        # Register a profile but pass a broken assessment (no spec -> will
        # fail when interpreter tries to access nested attributes properly)
        profile = DomainProfile(domain_id="test", display_name="Test")
        reg.register(profile)
        # Use a bare MagicMock that will return mocks for nested attrs
        # but those mocks won't be valid enum values -> triggers exception
        bad_assessment = MagicMock()
        bad_assessment.regime = "not_an_enum"  # will fail comparisons
        result = resolve_domain_policy(bad_assessment, reg, "test")
        # Should not raise — returns fail-closed
        assert isinstance(result, DomainPolicyResult)
        assert result.mode == DomainActionMode.BLOCKED

    def test_default_mode_is_fail_closed(self):
        profile = DomainProfile(
            domain_id="test", display_name="Test",
            default_mode=DomainActionMode.BLOCKED,
        )
        interp = DomainPolicyInterpreter(profile)
        # No matrix, no rules, no tools -> hits default
        result = interp.interpret(_make_assessment())
        assert result.mode == DomainActionMode.BLOCKED


# =========================================================================
# Test: DomainPolicyResult audit serialization
# =========================================================================


class TestDomainPolicyResultAudit:

    def test_to_audit_dict(self):
        result = DomainPolicyResult(
            domain_id="finance",
            mode=DomainActionMode.BLOCKED,
            matrix_mode=DomainActionMode.CONFIRM_REQUIRED,
            rule_modes=(("rule1", DomainActionMode.BLOCKED),),
            tool_mode=DomainActionMode.BLOCKED,
            fired_rules=("rule1",),
            reason_codes=("MATRIX:normal:read_only:confirm_required",),
            rationale="test",
        )
        d = result.to_audit_dict()
        assert d["domain_id"] == "finance"
        assert d["mode"] == "blocked"
        assert d["matrix_mode"] == "confirm_required"
        assert len(d["rule_modes"]) == 1
        assert d["rule_modes"][0]["rule"] == "rule1"
        assert d["tool_mode"] == "blocked"

    def test_to_audit_dict_none_fields(self):
        result = DomainPolicyResult(
            domain_id="test",
            mode=DomainActionMode.ALLOW,
        )
        d = result.to_audit_dict()
        assert d["matrix_mode"] is None
        assert d["tool_mode"] is None
        assert d["threshold_mode"] is None


# =========================================================================
# Test: Built-in Finance Profile
# =========================================================================


class TestFinanceProfile:

    def test_normal_read_allowed(self):
        interp = DomainPolicyInterpreter(FINANCE_PROFILE)
        result = interp.interpret(_make_assessment(
            action_cat=RuntimeActionCategory.READ_ONLY,
        ))
        assert result.mode == DomainActionMode.ALLOW

    def test_normal_mutating_needs_confirm(self):
        interp = DomainPolicyInterpreter(FINANCE_PROFILE)
        result = interp.interpret(_make_assessment(
            action_cat=RuntimeActionCategory.MUTATING,
        ))
        # Finance blocks mutating via blocked_action_categories or matrix
        # Matrix says CONFIRM_REQUIRED, but vritti guard may block if not pramana
        assert result.mode.severity >= DomainActionMode.CONFIRM_REQUIRED.severity

    def test_destructive_always_blocked(self):
        interp = DomainPolicyInterpreter(FINANCE_PROFILE)
        result = interp.interpret(_make_assessment(
            action_cat=RuntimeActionCategory.DESTRUCTIVE,
        ))
        assert result.mode == DomainActionMode.BLOCKED

    def test_drift_blocks_writes(self):
        interp = DomainPolicyInterpreter(FINANCE_PROFILE)
        result = interp.interpret(_make_assessment(
            regime=GovernanceRegime.PROCESS_DRIFT,
            action="DEGRADE",
            action_cat=RuntimeActionCategory.MUTATING,
        ))
        assert result.mode == DomainActionMode.BLOCKED

    def test_viparyaya_blocked(self):
        interp = DomainPolicyInterpreter(FINANCE_PROFILE)
        result = interp.interpret(_make_assessment(
            vritti_primary="viparyaya",
        ))
        assert result.mode == DomainActionMode.BLOCKED

    def test_ledger_tool_blocked_in_drift(self):
        interp = DomainPolicyInterpreter(FINANCE_PROFILE)
        result = interp.interpret(
            _make_assessment(
                regime=GovernanceRegime.PROCESS_DRIFT,
                action="DEGRADE",
            ),
            tool_name="ledger_write",
        )
        assert result.tool_mode == DomainActionMode.BLOCKED

    def test_high_alignment_threshold(self):
        interp = DomainPolicyInterpreter(FINANCE_PROFILE)
        result = interp.interpret(_make_assessment(alignment=0.65))
        # Finance alignment_critical is 0.70 -> 0.65 is below -> BLOCKED
        assert result.threshold_mode == DomainActionMode.BLOCKED


# =========================================================================
# Test: Built-in DevOps Profile
# =========================================================================


class TestDevOpsProfile:

    def test_normal_read_allowed(self):
        interp = DomainPolicyInterpreter(DEVOPS_PROFILE)
        result = interp.interpret(_make_assessment(
            action_cat=RuntimeActionCategory.READ_ONLY,
        ))
        assert result.mode == DomainActionMode.ALLOW

    def test_normal_mutating_allowed(self):
        interp = DomainPolicyInterpreter(DEVOPS_PROFILE)
        result = interp.interpret(_make_assessment(
            action_cat=RuntimeActionCategory.MUTATING,
        ))
        assert result.mode == DomainActionMode.ALLOW

    def test_destructive_sandboxed_in_normal(self):
        interp = DomainPolicyInterpreter(DEVOPS_PROFILE)
        result = interp.interpret(_make_assessment(
            action_cat=RuntimeActionCategory.DESTRUCTIVE,
        ))
        # Matrix says CONFIRM_REQUIRED, rule says SANDBOX_ONLY
        assert result.mode.severity >= DomainActionMode.CONFIRM_REQUIRED.severity

    def test_drift_writes_draft_only(self):
        interp = DomainPolicyInterpreter(DEVOPS_PROFILE)
        result = interp.interpret(_make_assessment(
            regime=GovernanceRegime.PROCESS_DRIFT,
            action="DEGRADE",
            action_cat=RuntimeActionCategory.MUTATING,
        ))
        assert result.mode.severity >= DomainActionMode.DRAFT_ONLY.severity

    def test_deploy_blocked_in_drift(self):
        interp = DomainPolicyInterpreter(DEVOPS_PROFILE)
        result = interp.interpret(
            _make_assessment(
                regime=GovernanceRegime.PROCESS_DRIFT,
                action="DEGRADE",
            ),
            tool_name="deploy_prod",
        )
        assert result.tool_mode == DomainActionMode.BLOCKED

    def test_db_drop_always_blocked(self):
        interp = DomainPolicyInterpreter(DEVOPS_PROFILE)
        result = interp.interpret(_make_assessment(), tool_name="db_drop_table")
        assert result.tool_mode == DomainActionMode.BLOCKED


# =========================================================================
# Test: Built-in Research Profile
# =========================================================================


class TestResearchProfile:

    def test_normal_read_allowed(self):
        interp = DomainPolicyInterpreter(RESEARCH_PROFILE)
        result = interp.interpret(_make_assessment(
            action_cat=RuntimeActionCategory.READ_ONLY,
        ))
        assert result.mode == DomainActionMode.ALLOW

    def test_normal_mutating_draft_only(self):
        interp = DomainPolicyInterpreter(RESEARCH_PROFILE)
        result = interp.interpret(_make_assessment(
            action_cat=RuntimeActionCategory.MUTATING,
        ))
        assert result.mode.severity >= DomainActionMode.DRAFT_ONLY.severity

    def test_destructive_blocked(self):
        interp = DomainPolicyInterpreter(RESEARCH_PROFILE)
        result = interp.interpret(_make_assessment(
            action_cat=RuntimeActionCategory.DESTRUCTIVE,
        ))
        assert result.mode == DomainActionMode.BLOCKED

    def test_vikalpa_allowed_for_reads(self):
        interp = DomainPolicyInterpreter(RESEARCH_PROFILE)
        result = interp.interpret(_make_assessment(
            vritti_primary="vikalpa",
            action_cat=RuntimeActionCategory.READ_ONLY,
        ))
        # Research allows vikalpa for execution and has a rule for vikalpa reads
        assert result.mode == DomainActionMode.ALLOW

    def test_drift_denies_memory_writes(self):
        interp = DomainPolicyInterpreter(RESEARCH_PROFILE)
        result = interp.interpret(_make_assessment(
            regime=GovernanceRegime.PROCESS_DRIFT,
            action="DEGRADE",
            action_cat=RuntimeActionCategory.READ_ONLY,
        ))
        # research_memory_deny_on_drift rule fires
        assert any("research_memory_deny_on_drift" in r for r in result.fired_rules)


# =========================================================================
# Test: Cross-domain comparison
# =========================================================================


class TestCrossDomainComparison:

    def test_same_state_different_domains(self):
        """Same JEPA state produces different modes in different domains."""
        assessment = _make_assessment(
            action_cat=RuntimeActionCategory.MUTATING,
            vritti_primary="pramana",
            confidence=0.9,
            alignment=0.9,
        )
        finance_result = DomainPolicyInterpreter(FINANCE_PROFILE).interpret(assessment)
        devops_result = DomainPolicyInterpreter(DEVOPS_PROFILE).interpret(assessment)
        research_result = DomainPolicyInterpreter(RESEARCH_PROFILE).interpret(assessment)

        # Finance is strictest for mutating (CONFIRM_REQUIRED or BLOCKED)
        assert finance_result.mode.severity >= DomainActionMode.CONFIRM_REQUIRED.severity
        # DevOps allows mutating in NORMAL
        assert devops_result.mode == DomainActionMode.ALLOW
        # Research uses DRAFT_ONLY for mutating
        assert research_result.mode.severity >= DomainActionMode.DRAFT_ONLY.severity

    def test_dual_anomaly_blocks_mutating_all_domains(self):
        """DUAL_ANOMALY blocks mutating actions in all built-in profiles."""
        assessment = _make_assessment(
            regime=GovernanceRegime.DUAL_ANOMALY,
            action="HALT",
            exec_override="BLOCKED",
            esc_override="HALT",
            conf_adj=-0.40,
            action_cat=RuntimeActionCategory.MUTATING,
        )
        for profile in [FINANCE_PROFILE, DEVOPS_PROFILE, RESEARCH_PROFILE]:
            result = DomainPolicyInterpreter(profile).interpret(assessment)
            assert result.mode == DomainActionMode.BLOCKED, (
                f"{profile.domain_id} should block mutating on DUAL_ANOMALY"
            )

    def test_unknown_regime_blocks_mutating_all_domains(self):
        """UNKNOWN regime blocks mutating in all built-in profiles."""
        assessment = _make_assessment(
            regime=GovernanceRegime.UNKNOWN,
            action="HALT",
            exec_override="BLOCKED",
            esc_override="HALT",
            conf_adj=-0.50,
            action_cat=RuntimeActionCategory.MUTATING,
        )
        for profile in [FINANCE_PROFILE, DEVOPS_PROFILE, RESEARCH_PROFILE]:
            result = DomainPolicyInterpreter(profile).interpret(assessment)
            assert result.mode == DomainActionMode.BLOCKED, (
                f"{profile.domain_id} should block mutating on UNKNOWN"
            )


# =========================================================================
# Test: GovernanceService integration
# =========================================================================


class TestGovernanceServiceDomainIntegration:

    def test_service_without_domain_unchanged(self):
        """GovernanceService without domain registry works as before."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest, APIGovernanceDecision,
        )
        service = GovernanceService()
        request = AuthorizationRequest(
            actor_id="test",
            action_type="file_read",
            quality_score=0.9,
            coherence_score=0.9,
            internal_consistency=0.9,
            goal_alignment=0.9,
            trajectory_confidence=0.9,
        )
        response = service.authorize(request)
        # Should work without domain policy
        assert response.governance_decision in (
            APIGovernanceDecision.ALLOW,
            APIGovernanceDecision.DENY,
            APIGovernanceDecision.DEFER,
        )
        # No domain_policy in audit
        snapshot = response.audit_event.request_snapshot
        assert snapshot.get("domain_policy") is None

    def test_service_with_finance_domain_blocks_destructive(self):
        """GovernanceService with finance domain blocks destructive."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest, APIGovernanceDecision,
        )
        registry = create_default_registry()
        service = GovernanceService(
            domain_registry=registry,
            domain_id="finance",
        )
        request = AuthorizationRequest(
            actor_id="test",
            action_type="database_delete",
            tool_name="db_drop",
            quality_score=0.9,
            coherence_score=0.9,
            internal_consistency=0.9,
            goal_alignment=0.9,
            trajectory_confidence=0.9,
        )
        response = service.authorize(request)
        # Finance blocks destructive operations
        assert response.governance_decision in (
            APIGovernanceDecision.DENY,
            APIGovernanceDecision.DEFER,
        )
        # Domain policy should be in audit
        snapshot = response.audit_event.request_snapshot
        assert snapshot.get("domain_policy") is not None
        assert snapshot["domain_policy"]["domain_id"] == "finance"


# =========================================================================
# Test: SafeMCPGateway integration
# =========================================================================


class TestMCPGatewayDomainIntegration:

    @pytest.mark.asyncio
    async def test_gateway_domain_blocks_finance_write(self):
        """MCP gateway with finance domain blocks write tools."""
        from agentic.agentic_framework.mcp_gateway import (
            SafeMCPGateway, MCPToolCall, MCPToolDefinition,
            ToolRiskLevel, GatewayDecision,
        )

        mock_client = MagicMock()
        registry = create_default_registry()
        gateway = SafeMCPGateway(
            mcp_client=mock_client,
            domain_registry=registry,
            domain_id="finance",
        )
        # Register a write tool
        gateway.register_tool(MCPToolDefinition(
            name="ledger_write",
            description="Write to ledger",
            risk_level=ToolRiskLevel.WRITE,
            capabilities=["ledger_write"],
        ))
        tool_call = MCPToolCall(
            tool_name="ledger_write",
            parameters={"entry": "test"},
            quality_score=0.9,
            coherence_score=0.9,
        )
        result = await gateway.call_tool(tool_call)
        # Finance should block or escalate ledger writes
        assert result.decision in (
            GatewayDecision.BLOCKED,
            GatewayDecision.ESCALATE,
        )

    @pytest.mark.asyncio
    async def test_gateway_without_domain_unchanged(self):
        """MCP gateway without domain registry works as before."""
        from agentic.agentic_framework.mcp_gateway import (
            SafeMCPGateway, MCPToolCall, MCPToolDefinition,
            ToolRiskLevel,
        )

        mock_client = MagicMock()
        mock_client.call_tool = MagicMock(return_value="result")
        gateway = SafeMCPGateway(mcp_client=mock_client)
        gateway.register_tool(MCPToolDefinition(
            name="file_read",
            description="Read file",
            risk_level=ToolRiskLevel.READ_ONLY,
        ))
        tool_call = MCPToolCall(
            tool_name="file_read",
            parameters={"path": "/tmp/test"},
            quality_score=0.9,
            coherence_score=0.9,
        )
        result = await gateway.call_tool(tool_call)
        # Should work without domain policy
        assert result is not None


# =========================================================================
# Test: Blocked action categories
# =========================================================================


class TestBlockedActionCategories:

    def test_blocked_category_overrides_matrix(self):
        profile = DomainProfile(
            domain_id="test", display_name="Test",
            action_coherence_matrix={
                (GovernanceRegime.NORMAL, RuntimeActionCategory.PRIVILEGED):
                    DomainActionMode.CONFIRM_REQUIRED,
            },
            blocked_action_categories=frozenset({RuntimeActionCategory.PRIVILEGED}),
        )
        interp = DomainPolicyInterpreter(profile)
        result = interp.interpret(_make_assessment(
            action_cat=RuntimeActionCategory.PRIVILEGED,
        ))
        assert result.mode == DomainActionMode.BLOCKED
        assert any("BLOCKED_CATEGORY" in c for c in result.reason_codes)


# =========================================================================
# Test: Multiple rules fire and merge
# =========================================================================


class TestMultipleRulesMerge:

    def test_multiple_rules_strictest_wins(self):
        profile = DomainProfile(
            domain_id="test", display_name="Test",
            coherence_rules=(
                DomainCoherenceRule(
                    name="rule1",
                    result_mode=DomainActionMode.DRAFT_ONLY,
                ),
                DomainCoherenceRule(
                    name="rule2",
                    result_mode=DomainActionMode.CONFIRM_REQUIRED,
                ),
                DomainCoherenceRule(
                    name="rule3",
                    result_mode=DomainActionMode.READ_ONLY,
                ),
            ),
        )
        interp = DomainPolicyInterpreter(profile)
        result = interp.interpret(_make_assessment())
        assert result.mode == DomainActionMode.CONFIRM_REQUIRED
        assert len(result.fired_rules) == 3


# =========================================================================
# Test: resolve_domain_policy top-level
# =========================================================================


class TestResolveDomainPolicy:

    def test_resolve_with_valid_domain(self):
        reg = create_default_registry()
        assessment = _make_assessment()
        result = resolve_domain_policy(assessment, reg, "devops")
        assert result.domain_id == "devops"
        assert isinstance(result.mode, DomainActionMode)

    def test_resolve_with_tool_name(self):
        reg = create_default_registry()
        assessment = _make_assessment()
        result = resolve_domain_policy(
            assessment, reg, "devops", tool_name="git_commit",
        )
        assert result.domain_id == "devops"

    def test_resolve_missing_domain(self):
        reg = DomainRegistry()
        assessment = _make_assessment()
        result = resolve_domain_policy(assessment, reg, "nonexistent")
        assert result.mode == DomainActionMode.BLOCKED
        assert "DOMAIN_UNAVAILABLE" in result.reason_codes
