#!/usr/bin/env python3
"""
Second-pass cleanup: aggressively removes remaining legacy references.
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


def should_remove_line(line, in_config_class=False, in_argparser=False, in_config_build=False):
    """Check if a single line should be removed."""
    stripped = line.strip()
    if not stripped:
        return False

    # Legacy keywords for matching
    srk_kw = ['srk_', 'enable_srk', 'SRK', 'srk ', 'srk=', 'srk.', 'srk,',
              'SovereignReasoningKernel', 'SRKConfig', 'SRKLoss',
              'SovereignAnnealer', 'PhaseExtractionHook', 'TeleologicalOptimizer',
              'SovereignEmbedding', 'srk_config', 'srk_loss', 'srk_annealer',
              'srk_phase_hook', 'srk_karma', 'srk_result', 'srk_diagnostics',
              'srk_metrics', 'build_srk_config', 'build_srk_loss',
              'no_srk_annotation', 'use_srk_annotation',
              'Sovereign Reasoning Kernel']

    pid_kw = ['pidv2_', 'PIDV2_', 'PIDv2', 'pidv2 ', 'pidv2=',
              'AuthorityPIDv2', 'EmergencyPD',
              'authority_controller', 'pid_engaged',
              'compute_semantic_ppl', 'measure_friction',
              'FrictionController', 'friction_controller',
              'friction_penalty', 'friction_config',
              'friction_dom', 'friction_align',
              'disable_friction', 'PID Governor',
              'controller=args.controller',
              'controller: str = "none"',
              'PIDGovernor']

    csr_kw = ['csr_', 'CSR_', 'enable_csr', 'disable_csr',
              'CSREmbeddingProvider', 'CSRConfig',
              'EntropySink', 'SynthesisGate',
              'create_csr_for_training', 'integrate_csr_into_forward',
              'csr_start_preload', 'csr_wait_preload',
              'WholeWordCSRHelper', 'calculate_sparse_csr_loss',
              'compute_csr_diagnostics', 'format_csr_diagnostic',
              'CSR_STOPWORDS', 'CSR Phoneme', 'csr_provider',
              'csr_output', 'csr_emb', 'csr_affinity',
              'csr_confidence', 'csr_hidden', 'csr_loss',
              'csr_metrics', 'csr_scale', 'csr_diag',
              'csr_layer', 'csr_d_model',
              'no_csr_annotation', 'use_csr_annotation',
              'untie_embeddings',
              'csr_entropy_sink', 'csr_synthesis_gate',
              'csr_graduated', 'csr_curriculum',
              'CSR AVAILABLE', 'CSR_AVAILABLE']

    kosha_vritti_kw = ['kosha_gyroscope', 'KOSHA_GYROSCOPE',
                       'kosha_steering', 'kosha_curriculum',
                       'kosha_engage', 'kosha_ppl',
                       'enable_kosha_gyroscope', 'enable_kosha_steering',
                       'KoshaGyroscopicLoss', 'KoshaGyroscopeConfig',
                       'InvertedCurriculumController',
                       'VrittiResonanceLoss', 'VrittiResonanceConfig',
                       'SovereignStateRegularizer',
                       'GraduationMonitor', 'GraduationConfig',
                       'SovereignDiagnosticLogger', 'RipEvent',
                       'kv_supervisor', 'KV_SUPERVISION',
                       'KoshaVrittiSupervisionConfig', 'KoshaVrittiSupervisor',
                       'log_kv_metrics', 'enable_kv_supervision',
                       'kosha_gyro', 'kosha_loss']

    sgp_sat_kw = ['sgp_', 'SGP_', 'enable_sgp',
                  'SGPController', 'SGPConfig',
                  'create_sgp_controller', 'create_synchronized_controllers',
                  'SattvicController', 'SattvicConfig',
                  'create_sattvic_controller',
                  'sattvic_', 'sattvic_controller', 'sgp_controller',
                  'lambda_csr = sattvic']

    rss_kw = ['ResonanceStateScheduler', 'rss_weights',
              'enable_rss', 'rss_evoflow', 'rss_toroidal',
              'rss_csr', 'rss_kosha',
              'ThreePhaseCurriculum',
              'SovereignPhaseController',
              'sovereign_phase_controller']

    misc_kw = ['phase_div_weight_for_srk',
               'Binding Annotation (CSR',
               'use_binding_annotator',
               'Kosha-Vritti Diagnostic',
               'enable_kosha_diagnostics']

    all_kw = srk_kw + pid_kw + csr_kw + kosha_vritti_kw + sgp_sat_kw + rss_kw + misc_kw

    for kw in all_kw:
        if kw in line:
            return True

    return False


def process(input_path, output_path):
    lines = read_lines(input_path)
    print(f"Read {len(lines)} lines from {input_path}")

    remove_set = set()
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if should_remove_line(line):
            # Check if this is the start of a block (if/elif/for/while/with/def/class/try)
            if stripped.startswith(('if ', 'elif ', 'for ', 'while ', 'with ', 'try:')):
                block_end = find_block_end(lines, i)

                # Also handle elif/else/except chains
                j = block_end + 1
                while j < len(lines):
                    next_stripped = lines[j].strip()
                    if not next_stripped:
                        j += 1
                        continue
                    next_indent = get_indent(lines[j])
                    if next_indent == get_indent(lines[i]):
                        if next_stripped.startswith(('elif ', 'else:', 'except', 'finally:')):
                            block_end = find_block_end(lines, j)
                            j = block_end + 1
                        else:
                            break
                    else:
                        break

                for k in range(i, block_end + 1):
                    remove_set.add(k)
                i = block_end + 1
                continue

            # Check if this is a function/class definition
            elif stripped.startswith(('def ', 'class ')):
                block_end = find_block_end(lines, i)
                for k in range(i, block_end + 1):
                    remove_set.add(k)
                i = block_end + 1
                continue

            # For config field assignments (inside dataclass or config builder)
            # Also remove preceding comment lines
            j = i - 1
            while j >= 0 and j not in remove_set:
                prev_stripped = lines[j].strip()
                if prev_stripped.startswith('#') and should_remove_line(lines[j]):
                    remove_set.add(j)
                    j -= 1
                elif prev_stripped.startswith('#') and not prev_stripped:
                    j -= 1
                else:
                    break

            remove_set.add(i)

            # Handle multi-line expressions (lines ending with , or continuing with indent)
            j = i + 1
            while j < len(lines):
                next_stripped = lines[j].strip()
                if not next_stripped:
                    break
                # Continuation of a function call or dict
                if get_indent(lines[j]) > get_indent(lines[i]):
                    remove_set.add(j)
                    j += 1
                elif next_stripped.startswith(('help=', '"', "'")):
                    # CLI arg help text continuation
                    remove_set.add(j)
                    j += 1
                else:
                    break

        i += 1

    # Also look for lines with just the variable name on the left side of =
    # that reference removed systems
    var_patterns = [
        re.compile(r'^\s+srk\s*=\s'),
        re.compile(r'^\s+srk\s+'),
        re.compile(r'^\s+loss\s*=\s*srk_loss'),
        re.compile(r'srk_state='),
        re.compile(r'csr_curriculum_state='),
        re.compile(r'pidv2_curriculum_state='),
        re.compile(r'kosha_curriculum_state='),
        re.compile(r'kosha_gyroscope_state='),
        re.compile(r'kv_supervisor_state='),
    ]

    for i, line in enumerate(lines):
        if i in remove_set:
            continue
        for pattern in var_patterns:
            if pattern.search(line):
                remove_set.add(i)
                break

    # Build output
    output_lines = []
    consecutive_blanks = 0
    for i, line in enumerate(lines):
        if i in remove_set:
            continue
        if not line.strip():
            consecutive_blanks += 1
            if consecutive_blanks <= 2:
                output_lines.append(line)
        else:
            consecutive_blanks = 0
            output_lines.append(line)

    num_removed = len(remove_set)
    print(f"Pass 2: Removed {num_removed} additional lines")
    print(f"Output: {len(output_lines)} lines")

    write_lines(output_path, output_lines)
    return num_removed


if __name__ == "__main__":
    root = Path(__file__).parent.parent
    input_file = str(root / "train_unified_llm_clean.py")
    output_file = str(root / "train_unified_llm_clean.py")  # overwrite

    print("=" * 70)
    print("  PASS 2: AGGRESSIVE LEGACY CLEANUP")
    print("=" * 70)

    num_removed = process(input_file, output_file)

    print(f"\n{'=' * 70}")
    print(f"  PASS 2 COMPLETE: Removed {num_removed} more lines")
    print(f"{'=' * 70}")
