#!/usr/bin/env python3
"""
Combined cleanup: creates a clean training file by removing ALL legacy
control-plane integrations from train_unified_llm.py in a single pass.

Iterates multiple times until convergence (no more removals).
"""
import re
import sys
from pathlib import Path


def read_lines(path):
    with open(path) as f:
        return f.readlines()


def write_lines(path, lines):
    with open(path, 'w') as f:
        f.writelines(lines)


def get_indent(line):
    return len(line) - len(line.lstrip())


def find_block_end(lines, start_idx):
    """Find end of an indented block starting at start_idx."""
    if start_idx >= len(lines):
        return start_idx
    base_indent = get_indent(lines[start_idx])
    end = start_idx
    for i in range(start_idx + 1, len(lines)):
        line = lines[i]
        if not line.strip():
            end = i
            continue
        if get_indent(line) <= base_indent:
            return end
        end = i
    return end


# Keywords that signal a line is part of legacy integration code
# Organized by system for clarity

LEGACY_KEYWORDS = [
    # ===== SRK (Sovereign Reasoning Kernel) =====
    'srk_', 'enable_srk', '.srk ', '.srk.', '= srk', 'srk =', 'srk,', 'srk)',
    'SRK', 'SovereignReasoningKernel', 'SRKConfig', 'SRKLoss',
    'SovereignAnnealer', 'PhaseExtractionHook', 'TeleologicalOptimizer',
    'SovereignEmbedding', 'build_srk_', 'Sovereign Reasoning Kernel',
    'use_srk_annotation', 'no_srk_annotation',

    # ===== PIDv2 Governor =====
    'pidv2_', 'PIDV2_', 'PIDv2', 'pidv2 ', 'pidv2=', 'pidv2)',
    'AuthorityPIDv2', 'EmergencyPD', 'EmergencyPDConfig',
    'authority_controller', 'pid_engaged', 'PID Governor', 'PIDGovernor',
    'compute_semantic_ppl', 'measure_friction',
    'FrictionController', 'friction_controller', 'friction_penalty',
    'friction_config', 'friction_dom', 'friction_align', 'disable_friction',
    'controller=args.controller', 'controller: str = "none"',
    "controller', type=str", "controller=args.",

    # ===== CSR (Coherent Semantic Resonance) =====
    'csr_', 'CSR_', 'enable_csr', 'disable_csr', ' CSR ', 'CSR,', 'CSR)',
    'CSREmbeddingProvider', 'CSRConfig', 'EntropySink', 'SynthesisGate',
    'create_csr_for_training', 'integrate_csr_into_forward',
    'csr_start_preload', 'csr_wait_preload',
    'WholeWordCSRHelper', 'calculate_sparse_csr_loss',
    'compute_csr_diagnostics', 'format_csr_diagnostic',
    'CSR_STOPWORDS', 'CSR Phoneme', 'CSR SPARSE',
    'untie_embeddings', 'CSR_AVAILABLE',
    'lambda_csr', 'csr aphasia', 'CSR alignment',
    'CSR Diagnostics', 'CSR Three-Phase',
    'CSR Projector', 'CSR Gradient',
    "'csr'", '"csr"', "'csr':", '"csr":',
    'CSR + Bridge',

    # ===== Kosha Gyroscope / Vritti Resonance (LOSS integration, not state dims) =====
    'kosha_gyroscope', 'KOSHA_GYROSCOPE', 'kosha_gyro',
    'kosha_steering', 'kosha_curriculum',
    'kosha_engage_ppl', 'kosha_disengage_ppl', 'kosha_rampdown',
    'enable_kosha_gyroscope', 'enable_kosha_steering',
    'KoshaGyroscopicLoss', 'KoshaGyroscopeConfig',
    'InvertedCurriculumController',
    'VrittiResonanceLoss', 'VrittiResonanceConfig',
    'SovereignStateRegularizer', 'SovereignStateRegularizerConfig',
    'GraduationMonitor', 'GraduationConfig',
    'SovereignDiagnosticLogger', 'RipEvent',
    'apply_kosha_phase_steering', 'compute_kosha_steering',
    'compute_kosha_vritti_diagnostics', 'format_kosha_diagnostic',
    'kosha_vritti_supervision', 'KoshaVrittiSupervis',
    'log_kv_metrics', 'kv_supervisor', 'KV_SUPERVISION',
    'enable_kv_supervision', 'kv_weight_',
    'kosha_log_every', 'kosha_log_interval',
    'enable_kosha_diagnostics', 'Kosha-Vritti Diagnostic',
    'use_kosha_annotation', 'no_kosha_annotation',
    'gyroscope_', 'state_reg_target_std_kosha',
    "'kosha'", "'enable_kosha_steering'",
    'kosha_loss', 'kosha_engage', 'kosha_ppl',

    # ===== SGP / Sattvic Controller =====
    'sgp_', 'SGP_', 'enable_sgp', 'SGPController', 'SGPConfig',
    'create_sgp_controller', 'create_synchronized_controllers',
    'SattvicController', 'SattvicConfig', 'create_sattvic_controller',
    'sattvic_', 'sattvic_controller', 'sgp_controller',
    'lambda_csr = sattvic', '"Cement" for CSR',

    # ===== RSS (ResonanceStateScheduler) =====
    'ResonanceStateScheduler', 'rss_weights',
    'enable_rss', 'rss_evoflow', 'rss_toroidal',
    'rss_csr', 'rss_kosha', 'rss_use_val',
    'ThreePhaseCurriculum', 'SovereignPhaseController',
    'sovereign_phase_controller',

    # ===== Binding Annotator (with CSR/Kosha/SRK) =====
    'use_binding_annotator', 'no_binding_annotator',
    'Binding Annotation (CSR',
    'OntologicalBindingAnnotator',

    # ===== Misc legacy =====
    'phase_div_weight_for_srk',
    'controller=args.controller',
    # Stress probe that was wrongly identified (keep this check later)
]

# Patterns that should NOT be removed even if they contain legacy keywords
# (architectural constants, state dimensions, etc.)
KEEP_PATTERNS = [
    re.compile(r'^\s*(KOSHA_NAMES|VRITTI_NAMES|KOSHA_SLICE|VRITTI_SLICE|GUNA_SLICE)\b'),
    re.compile(r'^\s*CONTROL_STATE_DIM\b'),
    re.compile(r'^\s*BHAVA_SLICE\b'),
    re.compile(r'^\s*get_sovereign_state_summary\b'),
    # Keep references in sovereign state summary functions
    re.compile(r"^\s+# Kosha activations \[12:17\]"),
    re.compile(r"^\s+kosha_vals\b"),
    re.compile(r"^\s+'active_kosha"),
    re.compile(r"^\s+'kosha_activation"),
    re.compile(r"^\s+'kosha_activations"),
    # Keep the architectural comment about 32D state
    re.compile(r'^\s+# with principled 32D:.*Kosha.*Vritti.*Guna'),
    # Keep ConfidenceScaler VrittiRiskHead (emission path, not control)
    re.compile(r'^\s+VrittiRiskHead\b'),
    # Keep imports from phase_transformer
    re.compile(r'^\s+(KOSHA_NAMES|VRITTI_NAMES|KOSHA_SLICE|VRITTI_SLICE|CONTROL_STATE_DIM)\s*,'),
    # Keep Ontological Bridge comment about Kosha at Layer 9
    re.compile(r'^# while Kosha \(consciousness/awareness\)'),
]


def should_remove_line(line):
    """Check if a line contains legacy integration keywords."""
    # First check keep patterns
    for pattern in KEEP_PATTERNS:
        if pattern.search(line):
            return False

    # Then check removal keywords
    for kw in LEGACY_KEYWORDS:
        if kw in line:
            return True

    return False


def process(input_path, output_path):
    lines = read_lines(input_path)
    total_original = len(lines)
    print(f"Read {total_original} lines from {input_path}")

    iteration = 0
    while True:
        iteration += 1
        remove_set = set()
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if i not in remove_set and should_remove_line(line):
                # Block-level removal for control structures
                if stripped.startswith(('if ', 'elif ', 'for ', 'while ', 'with ', 'try:')):
                    block_end = find_block_end(lines, i)
                    # Handle elif/else/except chains
                    j = block_end + 1
                    while j < len(lines):
                        ns = lines[j].strip() if j < len(lines) else ''
                        if not ns:
                            j += 1
                            continue
                        ni = get_indent(lines[j])
                        if ni == get_indent(lines[i]) and ns.startswith(('elif ', 'else:', 'except', 'finally:')):
                            block_end = find_block_end(lines, j)
                            j = block_end + 1
                        else:
                            break
                    for k in range(i, block_end + 1):
                        remove_set.add(k)
                    i = block_end + 1
                    continue

                elif stripped.startswith(('def ', 'class ')):
                    block_end = find_block_end(lines, i)
                    for k in range(i, block_end + 1):
                        remove_set.add(k)
                    i = block_end + 1
                    continue

                else:
                    remove_set.add(i)
                    # Also remove continuation lines
                    j = i + 1
                    while j < len(lines):
                        ns = lines[j].strip()
                        if not ns:
                            break
                        if get_indent(lines[j]) > get_indent(lines[i]):
                            remove_set.add(j)
                            j += 1
                        elif ns.startswith(('help=', '"', "'")):
                            remove_set.add(j)
                            j += 1
                        else:
                            break

            i += 1

        if not remove_set:
            print(f"  Iteration {iteration}: No more removals. Converged.")
            break

        print(f"  Iteration {iteration}: Removing {len(remove_set)} lines")

        # Remove and compact
        new_lines = []
        consecutive_blanks = 0
        for i, line in enumerate(lines):
            if i in remove_set:
                continue
            if not line.strip():
                consecutive_blanks += 1
                if consecutive_blanks <= 2:
                    new_lines.append(line)
            else:
                consecutive_blanks = 0
                new_lines.append(line)
        lines = new_lines

    # Final cleanup: remove orphaned comment blocks
    # (comments that now precede nothing because the code was removed)
    final_lines = []
    for i, line in enumerate(lines):
        final_lines.append(line)

    total_removed = total_original - len(final_lines)
    print(f"\nTotal removed: {total_removed} lines ({total_removed/total_original*100:.1f}%)")
    print(f"Output: {len(final_lines)} lines")

    write_lines(output_path, final_lines)
    return total_removed


if __name__ == "__main__":
    root = Path(__file__).parent.parent
    input_file = str(root / "train_unified_llm.py")
    output_file = str(root / "train_unified_llm_clean.py")

    print("=" * 70)
    print("  COMBINED LEGACY CLEANUP (iterative until convergence)")
    print("  Removing: SRK, PIDv2, CSR, Kosha/Vritti, SGP/Sattvic, RSS")
    print("=" * 70)

    process(input_file, output_file)
