"""
LSTB Control Plane Governor Benchmarks (V11.0)

Tests the unified control-plane governor from LSTB Appendix E/F:
    1. 3-Axis computation (Stability, Depth, Exploration)
    2. EMA smoothing (anti-oscillation)
    3. Schmitt trigger gating (deadband hysteresis)
    4. Vritti mode override (discrete safety overrides)
    5. Policy function (deterministic S,D,E -> knob mapping)
    6. Truth table validation (Kosha x Vritti x Guna -> Policy)
    7. Progressive activation (RSS phase alignment)

CLI Usage::

    python train_hard_probes.py --test-control-plane
    python train_hard_probes.py --test-control-plane --cp-truth-table

References:
    - LATENT_SEMANTIC_TOKEN_BRIDGE_DESIGN.md Appendix E, Appendix F
"""

import math
import torch
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


# =============================================================================
# CONTROL PLANE GOVERNOR (from Appendix F)
# =============================================================================

@dataclass
class AuxiliarySignals:
    """Detached signals from all auxiliary observers."""
    # Kosha
    kosha_readiness: Optional[float] = None
    kosha_entropy: Optional[float] = None
    kosha_dominant_idx: Optional[int] = None
    # Vritti
    vritti_pramana: Optional[float] = None
    vritti_viparyaya: Optional[float] = None
    vritti_vikalpa: Optional[float] = None
    vritti_smrti: Optional[float] = None
    vritti_nidra: Optional[float] = None
    # Guna (always available)
    guna_sattva: float = 0.33
    guna_rajas: float = 0.33
    guna_tamas: float = 0.34
    # CSR
    csr_resonance: Optional[float] = None
    csr_confidence: Optional[float] = None
    # Ontology
    onto_abstraction: Optional[float] = None
    # JEPA
    jepa_residual: Optional[float] = None
    jepa_uncertainty: Optional[float] = None


@dataclass
class ControlPolicy:
    """Output knob vector consumed by Phase, Quad, and generation."""
    phase_gamma: float = 0.95
    phase_write_scale: float = 1.0
    phase_intent_rot_scale: float = 0.5
    quad_enabled: bool = True
    quad_k: int = 64
    quad_ontology_bias: float = 0.5
    quad_jepa_bias: float = 0.0
    hedge_mode: bool = False
    depth_cap: int = 12


@dataclass
class GovernorConfig:
    """Tunable thresholds for the control-plane governor."""
    ema_alpha: float = 0.1
    quad_on_threshold: float = 0.65
    quad_off_threshold: float = 0.55
    deep_on_threshold: float = 0.60
    deep_off_threshold: float = 0.45
    hedge_on_threshold: float = 0.40
    hedge_off_threshold: float = 0.50
    gamma_min: float = 0.90
    gamma_max: float = 0.999
    k_min: int = 16
    k_max: int = 128
    max_depth: int = 12
    viparyaya_override_threshold: float = 0.4
    nidra_override_threshold: float = 0.5


class ControlPlaneGovernor:
    """
    Unified control-plane governor for Phase-Quad architecture.

    Non-trained. No nn.Module. No gradients. Pure deterministic function.
    """

    def __init__(self, config: GovernorConfig = None):
        self.config = config or GovernorConfig()
        self._s_ema = 0.5
        self._d_ema = 0.5
        self._e_ema = 0.5
        self._quad_latch = True
        self._deep_latch = False
        self._hedge_latch = False
        self._step = 0

    def step(self, signals: AuxiliarySignals) -> ControlPolicy:
        """Compute one step of the governor."""
        self._step += 1

        s_raw = self._compute_stability(signals)
        d_raw = self._compute_depth(signals)
        e_raw = self._compute_exploration(signals)

        alpha = self.config.ema_alpha
        self._s_ema = (1 - alpha) * self._s_ema + alpha * s_raw
        self._d_ema = (1 - alpha) * self._d_ema + alpha * d_raw
        self._e_ema = (1 - alpha) * self._e_ema + alpha * e_raw

        S, D, E = self._s_ema, self._d_ema, self._e_ema

        cfg = self.config
        self._quad_latch = self._schmitt(S, self._quad_latch, cfg.quad_on_threshold, cfg.quad_off_threshold)
        self._deep_latch = self._schmitt(D, self._deep_latch, cfg.deep_on_threshold, cfg.deep_off_threshold)
        self._hedge_latch = self._schmitt_inverted(S, self._hedge_latch, cfg.hedge_off_threshold, cfg.hedge_on_threshold)

        vritti_override = self._check_vritti_override(signals)

        policy = ControlPolicy(
            phase_gamma=cfg.gamma_min + S * (cfg.gamma_max - cfg.gamma_min),
            phase_write_scale=max(0.1, min(1.0, S * (1.0 - 0.5 * E))),
            phase_intent_rot_scale=D,
            quad_enabled=self._quad_latch and self._deep_latch,
            quad_k=cfg.k_min + int(E * (cfg.k_max - cfg.k_min)),
            quad_ontology_bias=D,
            quad_jepa_bias=D * (signals.jepa_residual or 0.0),
            hedge_mode=self._hedge_latch,
            depth_cap=max(1, int(D * cfg.max_depth)),
        )

        if vritti_override == "viparyaya":
            policy.hedge_mode = True
            policy.quad_k = min(policy.quad_k, cfg.k_min)
            policy.phase_write_scale = min(policy.phase_write_scale, 0.3)
        elif vritti_override == "nidra":
            policy.phase_write_scale = 0.0
            policy.quad_enabled = False

        return policy

    def _compute_stability(self, sig: AuxiliarySignals) -> float:
        terms, weights = [], []
        if sig.kosha_readiness is not None:
            terms.append(sig.kosha_readiness)
            weights.append(2.0)
        if sig.kosha_entropy is not None:
            terms.append(1.0 - min(sig.kosha_entropy / 1.386, 1.0))
            weights.append(1.0)
        terms.append(sig.guna_sattva)
        weights.append(1.5)
        terms.append(1.0 - sig.guna_tamas)
        weights.append(1.0)
        if sig.vritti_viparyaya is not None and sig.vritti_nidra is not None:
            terms.append(1.0 - min(sig.vritti_viparyaya + sig.vritti_nidra, 1.0))
            weights.append(1.5)
        if sig.csr_resonance is not None:
            terms.append(min(sig.csr_resonance, 1.0))
            weights.append(0.5)
        if not terms:
            return 0.5
        return sum(t * w for t, w in zip(terms, weights)) / sum(weights)

    def _compute_depth(self, sig: AuxiliarySignals) -> float:
        terms, weights = [], []
        if sig.kosha_dominant_idx is not None:
            terms.append(sig.kosha_dominant_idx / 4.0)
            weights.append(2.0)
        if sig.onto_abstraction is not None:
            terms.append(sig.onto_abstraction)
            weights.append(1.5)
        if sig.jepa_residual is not None:
            terms.append(min(sig.jepa_residual / 2.0, 1.0))
            weights.append(1.0)
        if not terms:
            return 0.5
        return sum(t * w for t, w in zip(terms, weights)) / sum(weights)

    def _compute_exploration(self, sig: AuxiliarySignals) -> float:
        terms, weights = [], []
        if sig.vritti_vikalpa is not None:
            terms.append(sig.vritti_vikalpa)
            weights.append(2.0)
        if sig.vritti_smrti is not None:
            terms.append(sig.vritti_smrti * 0.5)
            weights.append(1.0)
        terms.append(sig.guna_rajas)
        weights.append(1.5)
        if sig.jepa_uncertainty is not None:
            terms.append(min(sig.jepa_uncertainty, 1.0))
            weights.append(1.0)
        if not terms:
            return 0.5
        return sum(t * w for t, w in zip(terms, weights)) / sum(weights)

    @staticmethod
    def _schmitt(value, latch, on_threshold, off_threshold):
        if latch:
            return value >= off_threshold
        return value > on_threshold

    @staticmethod
    def _schmitt_inverted(value, latch, off_threshold, on_threshold):
        if latch:
            return value <= off_threshold
        return value < on_threshold

    def _check_vritti_override(self, sig: AuxiliarySignals) -> Optional[str]:
        cfg = self.config
        if sig.vritti_viparyaya is not None and sig.vritti_viparyaya > cfg.viparyaya_override_threshold:
            return "viparyaya"
        if sig.vritti_nidra is not None and sig.vritti_nidra > cfg.nidra_override_threshold:
            return "nidra"
        return None

    def get_diagnostics(self) -> dict:
        return {
            'gov_S': self._s_ema, 'gov_D': self._d_ema, 'gov_E': self._e_ema,
            'gov_quad_latch': self._quad_latch, 'gov_deep_latch': self._deep_latch,
            'gov_hedge_latch': self._hedge_latch, 'gov_step': self._step,
        }

    def state_dict(self) -> dict:
        return {
            's_ema': self._s_ema, 'd_ema': self._d_ema, 'e_ema': self._e_ema,
            'quad_latch': self._quad_latch, 'deep_latch': self._deep_latch,
            'hedge_latch': self._hedge_latch, 'step': self._step,
        }

    def load_state_dict(self, state: dict):
        self._s_ema = state.get('s_ema', 0.5)
        self._d_ema = state.get('d_ema', 0.5)
        self._e_ema = state.get('e_ema', 0.5)
        self._quad_latch = state.get('quad_latch', True)
        self._deep_latch = state.get('deep_latch', False)
        self._hedge_latch = state.get('hedge_latch', False)
        self._step = state.get('step', 0)


# =============================================================================
# TESTS
# =============================================================================

def test_axis_computation() -> Dict[str, float]:
    """Test that S, D, E axes compute correctly from signals."""
    gov = ControlPlaneGovernor()
    results = {}

    # High stability signals
    high_stability = AuxiliarySignals(
        kosha_readiness=0.9, kosha_entropy=0.2,
        guna_sattva=0.8, guna_rajas=0.1, guna_tamas=0.1,
        vritti_pramana=0.8, vritti_viparyaya=0.02, vritti_vikalpa=0.05,
        vritti_smrti=0.03, vritti_nidra=0.1,
    )
    _ = gov.step(high_stability)
    diag = gov.get_diagnostics()
    # After one step with alpha=0.1, S should move toward high
    results['high_stability_S'] = diag['gov_S']
    results['high_stability_S_above_neutral'] = diag['gov_S'] > 0.5

    # Reset and test low stability
    gov2 = ControlPlaneGovernor()
    low_stability = AuxiliarySignals(
        kosha_readiness=0.1, kosha_entropy=1.2,
        guna_sattva=0.1, guna_rajas=0.3, guna_tamas=0.6,
        vritti_pramana=0.1, vritti_viparyaya=0.4, vritti_vikalpa=0.2,
        vritti_smrti=0.1, vritti_nidra=0.2,
    )
    _ = gov2.step(low_stability)
    diag2 = gov2.get_diagnostics()
    results['low_stability_S'] = diag2['gov_S']
    results['stability_ordering'] = diag['gov_S'] > diag2['gov_S']

    # High depth signals
    gov3 = ControlPlaneGovernor()
    deep = AuxiliarySignals(
        kosha_dominant_idx=4,  # Blissful (deepest)
        onto_abstraction=0.9, jepa_residual=1.5,
        guna_sattva=0.33, guna_rajas=0.33, guna_tamas=0.34,
    )
    _ = gov3.step(deep)
    diag3 = gov3.get_diagnostics()
    results['deep_D'] = diag3['gov_D']
    results['deep_D_above_neutral'] = diag3['gov_D'] > 0.5

    # High exploration
    gov4 = ControlPlaneGovernor()
    exploratory = AuxiliarySignals(
        vritti_vikalpa=0.7, vritti_smrti=0.1,
        guna_sattva=0.1, guna_rajas=0.8, guna_tamas=0.1,
        jepa_uncertainty=0.8,
    )
    _ = gov4.step(exploratory)
    diag4 = gov4.get_diagnostics()
    results['exploratory_E'] = diag4['gov_E']
    results['exploratory_E_above_neutral'] = diag4['gov_E'] > 0.5

    return results


def test_ema_smoothing() -> Dict[str, float]:
    """Test that EMA smoothing prevents oscillation."""
    gov = ControlPlaneGovernor(GovernorConfig(ema_alpha=0.1))
    results = {}

    # Alternating high/low signals (would oscillate without EMA)
    s_values = []
    for i in range(50):
        if i % 2 == 0:
            sig = AuxiliarySignals(guna_sattva=0.9, guna_rajas=0.05, guna_tamas=0.05)
        else:
            sig = AuxiliarySignals(guna_sattva=0.1, guna_rajas=0.45, guna_tamas=0.45)
        _ = gov.step(sig)
        s_values.append(gov._s_ema)

    # Measure oscillation: std of differences should be low after warmup
    diffs = [abs(s_values[i] - s_values[i - 1]) for i in range(20, len(s_values))]
    results['oscillation_amplitude'] = max(diffs)
    results['mean_oscillation'] = sum(diffs) / len(diffs)

    # Without EMA (alpha=1.0) oscillation would be ~0.4
    gov_no_ema = ControlPlaneGovernor(GovernorConfig(ema_alpha=1.0))
    s_no_ema = []
    for i in range(50):
        if i % 2 == 0:
            sig = AuxiliarySignals(guna_sattva=0.9, guna_rajas=0.05, guna_tamas=0.05)
        else:
            sig = AuxiliarySignals(guna_sattva=0.1, guna_rajas=0.45, guna_tamas=0.45)
        _ = gov_no_ema.step(sig)
        s_no_ema.append(gov_no_ema._s_ema)

    diffs_no_ema = [abs(s_no_ema[i] - s_no_ema[i - 1]) for i in range(20, len(s_no_ema))]
    results['oscillation_no_ema'] = max(diffs_no_ema)

    results['ema_reduces_oscillation'] = results['oscillation_amplitude'] < results['oscillation_no_ema']

    return results


def test_schmitt_triggers() -> Dict[str, float]:
    """Test Schmitt trigger deadband hysteresis."""
    gov = ControlPlaneGovernor(GovernorConfig(
        ema_alpha=1.0,  # No smoothing to isolate Schmitt behavior
        quad_on_threshold=0.65,
        quad_off_threshold=0.55,
    ))
    results = {}

    # Ramp S from 0.4 to 0.8 and back
    states = []
    s_values = list(range(40, 81, 2)) + list(range(80, 39, -2))

    for s_val in s_values:
        s = s_val / 100.0
        sig = AuxiliarySignals(
            guna_sattva=s, guna_rajas=(1 - s) / 2, guna_tamas=(1 - s) / 2,
            kosha_dominant_idx=2, onto_abstraction=0.7,  # Keep depth high for quad
        )
        policy = gov.step(sig)
        states.append({
            'S': gov._s_ema,
            'quad_enabled': policy.quad_enabled,
            'quad_latch': gov._quad_latch,
        })

    # Find transitions
    on_transitions = []
    off_transitions = []
    for i in range(1, len(states)):
        if states[i]['quad_latch'] and not states[i - 1]['quad_latch']:
            on_transitions.append(states[i]['S'])
        elif not states[i]['quad_latch'] and states[i - 1]['quad_latch']:
            off_transitions.append(states[i]['S'])

    results['on_transitions'] = on_transitions
    results['off_transitions'] = off_transitions
    results['has_hysteresis'] = len(on_transitions) > 0 and len(off_transitions) > 0

    # Check deadband: on threshold > off threshold
    if on_transitions and off_transitions:
        results['on_above_off'] = min(on_transitions) > max(off_transitions)
        results['deadband_width'] = min(on_transitions) - max(off_transitions)
    else:
        results['on_above_off'] = False
        results['deadband_width'] = 0.0

    return results


def test_vritti_override() -> Dict[str, float]:
    """Test Vritti mode override safety mechanisms."""
    gov = ControlPlaneGovernor(GovernorConfig(ema_alpha=1.0))
    results = {}

    # Normal operation (no override)
    normal = AuxiliarySignals(
        vritti_pramana=0.7, vritti_viparyaya=0.1, vritti_vikalpa=0.1,
        vritti_smrti=0.05, vritti_nidra=0.05,
        guna_sattva=0.7, guna_rajas=0.15, guna_tamas=0.15,
    )
    policy_normal = gov.step(normal)
    results['normal_hedge'] = policy_normal.hedge_mode
    results['normal_write_scale'] = policy_normal.phase_write_scale

    # Viparyaya override (misperception)
    gov2 = ControlPlaneGovernor(GovernorConfig(ema_alpha=1.0))
    viparyaya = AuxiliarySignals(
        vritti_pramana=0.1, vritti_viparyaya=0.6,  # > 0.4 threshold
        vritti_vikalpa=0.1, vritti_smrti=0.1, vritti_nidra=0.1,
        guna_sattva=0.7, guna_rajas=0.15, guna_tamas=0.15,
    )
    policy_vipar = gov2.step(viparyaya)
    results['viparyaya_hedge'] = policy_vipar.hedge_mode
    results['viparyaya_write_clamped'] = policy_vipar.phase_write_scale <= 0.3
    results['viparyaya_k_clamped'] = policy_vipar.quad_k <= gov2.config.k_min

    # Nidra override (dormancy)
    gov3 = ControlPlaneGovernor(GovernorConfig(ema_alpha=1.0))
    nidra = AuxiliarySignals(
        vritti_pramana=0.1, vritti_viparyaya=0.05,
        vritti_vikalpa=0.05, vritti_smrti=0.2, vritti_nidra=0.6,  # > 0.5
        guna_sattva=0.7, guna_rajas=0.15, guna_tamas=0.15,
    )
    policy_nidra = gov3.step(nidra)
    results['nidra_write_frozen'] = policy_nidra.phase_write_scale == 0.0
    results['nidra_quad_disabled'] = not policy_nidra.quad_enabled

    # Overrides must trigger
    results['viparyaya_triggered'] = results['viparyaya_hedge'] and results['viparyaya_write_clamped']
    results['nidra_triggered'] = results['nidra_write_frozen'] and results['nidra_quad_disabled']

    return results


def test_truth_table() -> Dict[str, float]:
    """
    Validate the Kosha x Vritti x Guna truth table from Appendix E.8.

    10 critical state combinations from the design doc.
    """
    results = {}

    # Table from E.8 (K, Vr, G) -> expected (S, D, E, gamma, write, quad, hedge)
    truth_table = [
        # (kosha_idx, vritti_dist, guna, expected_S_range, expected_hedge)
        {
            'name': 'ideal_reasoning',
            'kosha_idx': 3,  # Intellectual
            'vritti': (0.8, 0.02, 0.05, 0.03, 0.1),  # Pr dominant
            'guna': (0.8, 0.1, 0.1),  # Sattva
            'expected_S_high': True,
            'expected_D_high': True,
            'expected_hedge': False,
        },
        {
            'name': 'creative_exploration',
            'kosha_idx': 2,  # Mental
            'vritti': (0.1, 0.05, 0.7, 0.05, 0.1),  # Vikalpa dominant
            'guna': (0.2, 0.6, 0.2),  # Rajas
            'expected_S_high': False,
            'expected_E_high': True,
            'expected_hedge': False,
        },
        {
            'name': 'danger_misperception',
            'kosha_idx': 0,  # Physical
            'vritti': (0.1, 0.6, 0.05, 0.05, 0.2),  # Viparyaya dominant
            'guna': (0.1, 0.2, 0.7),  # Tamas
            'expected_S_high': False,
            'expected_hedge': True,  # Viparyaya override
        },
        {
            'name': 'dormancy',
            'kosha_idx': 0,  # Physical
            'vritti': (0.05, 0.05, 0.05, 0.1, 0.75),  # Nidra dominant
            'guna': (0.1, 0.1, 0.8),  # Tamas
            'expected_write_frozen': True,
            'expected_quad_off': True,
        },
    ]

    for entry in truth_table:
        name = entry['name']
        gov = ControlPlaneGovernor(GovernorConfig(ema_alpha=1.0))

        vr = entry['vritti']
        gn = entry['guna']

        sig = AuxiliarySignals(
            kosha_dominant_idx=entry['kosha_idx'],
            kosha_readiness=0.5,
            vritti_pramana=vr[0], vritti_viparyaya=vr[1],
            vritti_vikalpa=vr[2], vritti_smrti=vr[3], vritti_nidra=vr[4],
            guna_sattva=gn[0], guna_rajas=gn[1], guna_tamas=gn[2],
            onto_abstraction=0.5,
        )

        policy = gov.step(sig)
        diag = gov.get_diagnostics()

        if 'expected_S_high' in entry:
            results[f'{name}_S_correct'] = (diag['gov_S'] > 0.5) == entry['expected_S_high']
        if 'expected_D_high' in entry:
            results[f'{name}_D_correct'] = (diag['gov_D'] > 0.5) == entry['expected_D_high']
        if 'expected_E_high' in entry:
            results[f'{name}_E_correct'] = (diag['gov_E'] > 0.5) == entry['expected_E_high']
        if 'expected_hedge' in entry:
            results[f'{name}_hedge_correct'] = policy.hedge_mode == entry['expected_hedge']
        if 'expected_write_frozen' in entry:
            results[f'{name}_write_frozen'] = policy.phase_write_scale == 0.0
        if 'expected_quad_off' in entry:
            results[f'{name}_quad_off'] = not policy.quad_enabled

    # Count correct
    correct = sum(1 for v in results.values() if v is True)
    total = len(results)
    results['truth_table_accuracy'] = correct / max(total, 1)

    return results


def test_checkpoint_roundtrip() -> Dict[str, float]:
    """Test checkpoint save/restore preserves governor state."""
    gov = ControlPlaneGovernor()

    # Run some steps
    for i in range(10):
        sig = AuxiliarySignals(guna_sattva=0.5 + 0.03 * i, guna_rajas=0.25, guna_tamas=0.25)
        gov.step(sig)

    # Save state
    state = gov.state_dict()

    # Restore to new governor
    gov2 = ControlPlaneGovernor()
    gov2.load_state_dict(state)

    results = {}
    results['s_match'] = abs(gov._s_ema - gov2._s_ema) < 1e-10
    results['d_match'] = abs(gov._d_ema - gov2._d_ema) < 1e-10
    results['e_match'] = abs(gov._e_ema - gov2._e_ema) < 1e-10
    results['step_match'] = gov._step == gov2._step
    results['latch_match'] = (
        gov._quad_latch == gov2._quad_latch and
        gov._deep_latch == gov2._deep_latch and
        gov._hedge_latch == gov2._hedge_latch
    )
    results['roundtrip_perfect'] = all(results.values())

    return results


def test_progressive_activation() -> Dict[str, float]:
    """Test graceful degradation when auxiliaries are not yet active."""
    results = {}

    # FOUNDATION phase: No auxiliaries
    gov1 = ControlPlaneGovernor(GovernorConfig(ema_alpha=1.0))
    sig_foundation = AuxiliarySignals()  # All None except Guna defaults
    policy1 = gov1.step(sig_foundation)
    diag1 = gov1.get_diagnostics()

    results['foundation_S'] = diag1['gov_S']
    results['foundation_D'] = diag1['gov_D']
    results['foundation_E'] = diag1['gov_E']
    # Should be near neutral (0.5)
    results['foundation_near_neutral'] = all(
        0.3 < v < 0.7 for v in [diag1['gov_S'], diag1['gov_D'], diag1['gov_E']]
    )

    # SOVEREIGN phase: Full signals
    gov2 = ControlPlaneGovernor(GovernorConfig(ema_alpha=1.0))
    sig_sovereign = AuxiliarySignals(
        kosha_readiness=0.8, kosha_entropy=0.3, kosha_dominant_idx=3,
        vritti_pramana=0.7, vritti_viparyaya=0.05, vritti_vikalpa=0.1,
        vritti_smrti=0.05, vritti_nidra=0.1,
        guna_sattva=0.7, guna_rajas=0.15, guna_tamas=0.15,
        csr_resonance=0.8, csr_confidence=0.9,
        onto_abstraction=0.6, jepa_residual=0.3, jepa_uncertainty=0.2,
    )
    policy2 = gov2.step(sig_sovereign)
    diag2 = gov2.get_diagnostics()

    results['sovereign_S'] = diag2['gov_S']
    results['sovereign_D'] = diag2['gov_D']
    results['sovereign_E'] = diag2['gov_E']

    # Sovereign should have more decisive axes (farther from 0.5)
    foundation_decisiveness = sum(abs(v - 0.5) for v in [diag1['gov_S'], diag1['gov_D'], diag1['gov_E']])
    sovereign_decisiveness = sum(abs(v - 0.5) for v in [diag2['gov_S'], diag2['gov_D'], diag2['gov_E']])
    results['sovereign_more_decisive'] = sovereign_decisiveness > foundation_decisiveness

    return results


# =============================================================================
# MAIN BENCHMARK RUNNER
# =============================================================================

def run_control_plane_benchmarks(
    args,
    config,
    device: str,
) -> Dict[str, any]:
    """Run comprehensive Control Plane Governor benchmarks."""
    print("\n" + "=" * 70)
    print("V11.0: CONTROL PLANE GOVERNOR BENCHMARKS (LSTB Appendix E/F)")
    print("=" * 70)

    results = {}

    # TEST 1: Axis Computation
    print("\n--- TEST 1: 3-Axis Computation (S, D, E) ---")
    axis_results = test_axis_computation()
    results['axis'] = axis_results
    print(f"  High stability S: {axis_results['high_stability_S']:.4f} (above neutral: {axis_results['high_stability_S_above_neutral']})")
    print(f"  Low stability S: {axis_results['low_stability_S']:.4f}")
    print(f"  Stability ordering correct: {axis_results['stability_ordering']}")
    print(f"  Deep D: {axis_results['deep_D']:.4f} (above neutral: {axis_results['deep_D_above_neutral']})")
    print(f"  Exploratory E: {axis_results['exploratory_E']:.4f} (above neutral: {axis_results['exploratory_E_above_neutral']})")

    # TEST 2: EMA Smoothing
    print("\n--- TEST 2: EMA Smoothing (Anti-Oscillation) ---")
    ema_results = test_ema_smoothing()
    results['ema'] = ema_results
    print(f"  With EMA oscillation: {ema_results['oscillation_amplitude']:.4f}")
    print(f"  Without EMA oscillation: {ema_results['oscillation_no_ema']:.4f}")
    print(f"  EMA reduces oscillation: {ema_results['ema_reduces_oscillation']}")

    # TEST 3: Schmitt Triggers
    print("\n--- TEST 3: Schmitt Trigger Hysteresis ---")
    schmitt_results = test_schmitt_triggers()
    results['schmitt'] = schmitt_results
    print(f"  Has hysteresis: {schmitt_results['has_hysteresis']}")
    print(f"  ON above OFF: {schmitt_results['on_above_off']}")
    print(f"  Deadband width: {schmitt_results['deadband_width']:.4f}")

    # TEST 4: Vritti Override
    print("\n--- TEST 4: Vritti Mode Override ---")
    vritti_results = test_vritti_override()
    results['vritti_override'] = vritti_results
    print(f"  Normal hedge: {vritti_results['normal_hedge']} (should be False)")
    print(f"  Viparyaya triggered: {vritti_results['viparyaya_triggered']}")
    print(f"  Nidra triggered: {vritti_results['nidra_triggered']}")

    # TEST 5: Truth Table
    print("\n--- TEST 5: Truth Table (Kosha x Vritti x Guna -> Policy) ---")
    truth_results = test_truth_table()
    results['truth_table'] = truth_results
    print(f"  Truth table accuracy: {truth_results['truth_table_accuracy']:.0%}")
    for key, val in truth_results.items():
        if key != 'truth_table_accuracy':
            marker = "OK" if val else "FAIL"
            print(f"    {key}: {marker}")

    # TEST 6: Checkpoint Roundtrip
    print("\n--- TEST 6: Checkpoint Save/Restore ---")
    checkpoint_results = test_checkpoint_roundtrip()
    results['checkpoint'] = checkpoint_results
    print(f"  Roundtrip perfect: {checkpoint_results['roundtrip_perfect']}")

    # TEST 7: Progressive Activation
    print("\n--- TEST 7: Progressive Activation (RSS Alignment) ---")
    progressive_results = test_progressive_activation()
    results['progressive'] = progressive_results
    print(f"  Foundation near neutral: {progressive_results['foundation_near_neutral']}")
    print(f"  Sovereign more decisive: {progressive_results['sovereign_more_decisive']}")

    # SUMMARY
    print("\n" + "=" * 70)
    print("CONTROL PLANE GOVERNOR BENCHMARK SUMMARY")
    print("=" * 70)
    all_pass = all([
        axis_results['stability_ordering'],
        ema_results['ema_reduces_oscillation'],
        schmitt_results['has_hysteresis'],
        vritti_results['viparyaya_triggered'],
        vritti_results['nidra_triggered'],
        checkpoint_results['roundtrip_perfect'],
        progressive_results['sovereign_more_decisive'],
    ])
    print(f"  All core tests pass: {all_pass}")
    print(f"  Truth table accuracy: {truth_results['truth_table_accuracy']:.0%}")

    return results


def run_control_plane_benchmark_integration(args, config):
    """CLI routing wrapper."""
    device = getattr(args, 'device', 'cuda' if torch.cuda.is_available() else 'cpu')
    results = run_control_plane_benchmarks(args, config, device)
    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)
    return results
