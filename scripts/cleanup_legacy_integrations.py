#!/usr/bin/env python3
"""
Legacy Integration Cleanup Script
==================================

Creates a new clean training file by removing legacy control-plane integrations
from train_unified_llm.py. This prepares the codebase for the new unified
ControlPlaneGovernor (see docs/design/LATENT_SEMANTIC_TOKEN_BRIDGE_DESIGN.md,
Appendices E and F).

Legacy integrations removed:
1. SRK (Sovereign Reasoning Kernel) - V9.8.0
2. PIDv2 Governor - control-theoretic gating
3. CSR (Coherent Semantic Resonance) - phoneme-ontological grounding
4. Kosha Gyroscope / Vritti Resonance - homeostatic self-regulation losses
5. SGP (Stochastic Gradient Persistence) / Sattvic Controller - CSR cement
6. ResonanceStateScheduler (RSS) - staged CSR/Kosha engagement
7. ThreePhaseCurriculum - CSR/Kosha/PID curriculum controller
8. KV Supervision - Kosha-Vritti structured supervision
9. Friction Controller - PIDv2 companion
10. SovereignPhaseController - Vritti/Kosha diagnostic-driven phase control

What is KEPT:
- Core model architectures (PhaseTransformer, Hybrid, BindingCache, etc.)
- JEPA integration (part of new architecture)
- EvoFlow / Toroidal bridges (data-plane, not control-plane)
- OntologicalBridge (data-plane)
- Sovereign R-Matrix and Vrtti helper functions (used by OntologicalBridge, EvoFlow)
- ConfidenceScaler (emission-path)
- HiddenStateExtractor (utility)
- All general training infrastructure

Usage:
    python scripts/cleanup_legacy_integrations.py
"""

import re
import sys
from pathlib import Path


def read_file(path: str) -> list[str]:
    """Read file and return list of lines (with newlines preserved)."""
    with open(path, 'r') as f:
        return f.readlines()


def write_file(path: str, lines: list[str]):
    """Write lines to file."""
    with open(path, 'w') as f:
        f.writelines(lines)


# =============================================================================
# REMOVAL RULES
# =============================================================================

# Rule 1: Line ranges to remove entirely (1-indexed, inclusive)
# These are complete section blocks identified by their banner comments
SECTION_REMOVALS = []  # Will be populated dynamically below

# Rule 2: Patterns that mark the START of a multi-line block to remove.
# We track indentation to know when the block ends.
BLOCK_START_PATTERNS = []

# Rule 3: Individual line patterns to remove
# These match single lines (config fields, CLI args, inline references)
LINE_REMOVAL_PATTERNS = [
    # ---- SRK config fields ----
    re.compile(r'^\s+#.*SRK|^\s+#.*Sovereign Reasoning Kernel'),
    re.compile(r'^\s+enable_srk\b'),
    re.compile(r'^\s+srk_\w+'),
    re.compile(r'^\s+use_srk_annotation\b'),

    # ---- PIDv2 config fields ----
    re.compile(r'^\s+#.*PIDv2|^\s+#.*V9\.4\.4|^\s+#.*V9\.7\.0: PIDv2|^\s+#.*V9\.8\.7: Three-phase PID'),
    re.compile(r'^\s+controller:\s*str\s*=\s*"none"'),  # pidv2 controller field
    re.compile(r'^\s+pidv2_\w+'),
    re.compile(r'^\s+gc_floor\b'),

    # ---- CSR config fields ----
    re.compile(r'^\s+#.*CSR Phoneme|^\s+#.*V9\.6\.8: CSR|^\s+#.*V9\.7\.0: CSR Sparse|^\s+#.*V9\.9\.0 CRITICAL FIX.*CSR'),
    re.compile(r'^\s+enable_csr\b'),
    re.compile(r'^\s+csr_\w+'),
    re.compile(r'^\s+use_csr_annotation\b'),
    re.compile(r'^\s+untie_embeddings\b.*CSR'),

    # ---- SGP/Sattvic config fields ----
    re.compile(r'^\s+#.*SGP \(Stochastic|^\s+#.*Sattvic Controller|^\s+#.*"Cement" for CSR'),
    re.compile(r'^\s+enable_sgp\b'),
    re.compile(r'^\s+sgp_\w+'),
    re.compile(r'^\s+sattvic_\w+'),

    # ---- RSS config fields ----
    re.compile(r'^\s+#.*RSS \(Rational|^\s+#.*Key insight: Layer 7 \(CSR\)'),
    re.compile(r'^\s+enable_rss\b'),
    re.compile(r'^\s+rss_\w+'),

    # ---- Kosha steering/gyroscope config fields ----
    re.compile(r'^\s+enable_kosha_steering\b'),
    re.compile(r'^\s+kosha_steering_\w+'),
    re.compile(r'^\s+#.*Kosha Gyroscope|^\s+#.*docs/design/KOSHA_GYROSCOPE_DESIGN'),
    re.compile(r'^\s+enable_kosha_gyroscope\b'),
    re.compile(r'^\s+kosha_engage_ppl\b'),

    # ---- KV Supervision config fields ----
    re.compile(r'^\s+enable_kv_supervision\b'),
    re.compile(r'^\s+kv_\w+'),

    # ---- Friction controller config ----
    re.compile(r'^\s+disable_friction\b'),
    re.compile(r'^\s+friction_\w+'),

    # ---- SovereignPhaseController config ----
    re.compile(r'^\s+enable_sovereign_phase_controller\b'),
    re.compile(r'^\s+spc_\w+'),

    # ---- Binding annotator CSR/Kosha/SRK lines ----
    re.compile(r'^\s+use_binding_annotator\b'),
    re.compile(r'^\s+use_kosha_annotation\b'),
]

# Rule 4: CLI argument patterns (parser.add_argument lines)
CLI_ARG_PATTERNS = [
    re.compile(r'parser\.add_argument\("--(?:enable_srk|srk_|no_srk)'),
    re.compile(r'parser\.add_argument\("--(?:pidv2_|controller)'),
    re.compile(r'parser\.add_argument\("--(?:enable_csr|disable_csr|csr_|no_csr)'),
    re.compile(r'parser\.add_argument\("--(?:enable_sgp|sgp_|sattvic_)'),
    re.compile(r'parser\.add_argument\("--(?:enable_rss|rss_)'),
    re.compile(r'parser\.add_argument\("--(?:enable_kosha_steering|kosha_steering|enable_kosha_gyroscope|kosha_engage)'),
    re.compile(r'parser\.add_argument\("--(?:enable_kv_supervision|kv_)'),
    re.compile(r'parser\.add_argument\("--(?:disable_friction|friction_)'),
    re.compile(r'parser\.add_argument\("--(?:enable_sovereign_phase_controller|spc_)'),
    re.compile(r'parser\.add_argument\("--(?:use_binding_annotator|no_binding_annotator)'),
    re.compile(r'parser\.add_argument\("--(?:use_csr_annotation|no_csr_annotation)'),
    re.compile(r'parser\.add_argument\("--(?:use_kosha_annotation|no_kosha_annotation)'),
    re.compile(r'parser\.add_argument\("--(?:use_srk_annotation|no_srk_annotation)'),
    re.compile(r'parser\.add_argument\("--untie_embeddings'),
    re.compile(r'parser\.add_argument\("--(?:gc_floor)'),
]

# Rule 5: Config building assignment patterns (at bottom of file)
CONFIG_ASSIGN_PATTERNS = [
    re.compile(r'^\s+enable_srk=|^\s+srk_\w+='),
    re.compile(r'^\s+controller=args\.controller'),
    re.compile(r'^\s+pidv2_\w+='),
    re.compile(r'^\s+enable_csr=|^\s+csr_\w+='),
    re.compile(r'^\s+enable_sgp=|^\s+sgp_\w+='),
    re.compile(r'^\s+sattvic_\w+='),
    re.compile(r'^\s+enable_rss=|^\s+rss_\w+='),
    re.compile(r'^\s+enable_kosha_steering=|^\s+kosha_steering_\w+='),
    re.compile(r'^\s+enable_kosha_gyroscope='),
    re.compile(r'^\s+kosha_engage_ppl='),
    re.compile(r'^\s+enable_kv_supervision=|^\s+kv_\w+='),
    re.compile(r'^\s+disable_friction=|^\s+friction_\w+='),
    re.compile(r'^\s+enable_sovereign_phase_controller=|^\s+spc_\w+='),
    re.compile(r'^\s+use_binding_annotator=|^\s+use_csr_annotation=|^\s+use_kosha_annotation=|^\s+use_srk_annotation='),
    re.compile(r'^\s+gc_floor='),
    re.compile(r'^\s+untie_embeddings='),
]


def find_section_end(lines: list[str], start: int, banner_pattern: str = '# =====') -> int:
    """Find the end of a section that starts with a banner comment.

    Returns the line index BEFORE the next section banner or class/def at same level.
    """
    # Find the next banner or top-level definition
    for i in range(start + 1, len(lines)):
        line = lines[i]
        stripped = line.strip()
        # Next section banner at same level
        if stripped.startswith(banner_pattern) and i > start + 3:
            return i - 1
        # Top-level class or function definition
        if (line.startswith('class ') or line.startswith('def ')) and i > start + 3:
            return i - 1
    return len(lines) - 1


def find_try_except_block(lines: list[str], start: int) -> int:
    """Find the end of a try/except block starting at 'start'.

    Returns the index of the last line in the block (inclusive).
    """
    # Track indentation of the try statement
    try_indent = len(lines[start]) - len(lines[start].lstrip())

    in_except = False
    end = start
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if not line.strip():  # empty lines
            end = i
            continue

        current_indent = len(line) - len(line.lstrip())

        # We've hit something at the same or lower indentation as try
        if current_indent <= try_indent and line.strip():
            # Check if it's the except clause
            if line.strip().startswith('except'):
                in_except = True
                end = i
                continue
            elif in_except:
                # We're past the except block - this is the end
                return end
            else:
                # Still in try body
                end = i
                continue
        else:
            end = i

    return end


def find_indented_block_end(lines: list[str], start: int) -> int:
    """Find the end of an indented block (if/for/class/def) starting at 'start'.

    Returns the index of the last line in the block (inclusive).
    """
    base_indent = len(lines[start]) - len(lines[start].lstrip())

    end = start
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if not line.strip():  # empty lines are part of the block
            end = i
            continue

        current_indent = len(line) - len(line.lstrip())
        if current_indent <= base_indent:
            return end
        end = i

    return end


def is_cli_arg_continuation(line: str) -> bool:
    """Check if a line is a continuation of a parser.add_argument call."""
    stripped = line.strip()
    return stripped.startswith('help=') or stripped.startswith('"') or stripped.startswith("'")


def process_file(input_path: str, output_path: str):
    """Process the training file and produce a clean version."""
    lines = read_file(input_path)
    num_original = len(lines)
    print(f"Read {num_original} lines from {input_path}")

    # Track which lines to remove (set of 0-indexed line numbers)
    remove_set = set()

    # =========================================================================
    # PASS 1: Remove entire section blocks by detecting banner markers
    # =========================================================================

    # Define section markers and their types
    section_markers = [
        # (start_pattern, description)
        ("# V9.7.0: CSR SPARSE DELAYED SUPERVISION", "CSR Sparse Supervision section"),
        ("# V9.7.0: CSR DIAGNOSTICS", "CSR Diagnostics section"),
        ("# V9.8.0: SRK BACKWARD COMPATIBILITY BRIDGE", "SRK backward compat bridge"),
        ("# V9.8.6: THREE-PHASE CURRICULUM CONTROLLER", "ThreePhaseCurriculum section"),
    ]

    for i, line in enumerate(lines):
        stripped = line.strip()
        for marker, desc in section_markers:
            if marker in stripped and stripped.startswith('#'):
                # Find the banner block (usually 3-4 lines of # ===)
                banner_start = i
                # Look back for banner start
                while banner_start > 0 and lines[banner_start - 1].strip().startswith('# =='):
                    banner_start -= 1

                # Find section end (next banner or top-level def/class)
                section_end = find_section_end(lines, i)

                # Also include trailing blank lines
                while section_end + 1 < len(lines) and not lines[section_end + 1].strip():
                    section_end += 1

                print(f"  SECTION: {desc} (lines {banner_start+1}-{section_end+1})")
                for j in range(banner_start, section_end + 1):
                    remove_set.add(j)
                break

    # Remove specific classes
    class_removals = [
        "class ResonanceStateScheduler:",
        "class SovereignPhaseController:",
    ]

    for i, line in enumerate(lines):
        stripped = line.strip()
        for class_marker in class_removals:
            if stripped.startswith(class_marker):
                # Look back for banner and docstrings
                block_start = i
                while block_start > 0:
                    prev = lines[block_start - 1].strip()
                    if prev.startswith('#') or prev == '' or prev.startswith('"""'):
                        block_start -= 1
                    else:
                        break

                # Find end of class (next top-level entity)
                block_end = find_indented_block_end(lines, i)

                # Include trailing blank lines
                while block_end + 1 < len(lines) and not lines[block_end + 1].strip():
                    block_end += 1

                desc = class_marker.rstrip(':')
                print(f"  CLASS: {desc} (lines {block_start+1}-{block_end+1})")
                for j in range(block_start, block_end + 1):
                    remove_set.add(j)
                break

    # =========================================================================
    # PASS 2: Remove import try/except blocks
    # =========================================================================

    import_removals = [
        "from symbolu.training.kosha_vritti_supervision import",
        "from symbolu.sovereign import (\n        SRKConfig",  # SRK specific import
        "SRKConfig,",
        "from train_pid import",
        "from symbolu.losses import (\n        KoshaGyroscopicLoss",
        "KoshaGyroscopicLoss,",
        "from csr_phoneme_provider import",
        "from symbolu.resonance.sgp import",
    ]

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Check if this is a try: block containing a legacy import
        if stripped == 'try:':
            # Look at the next non-empty line
            block_content = ""
            for j in range(i + 1, min(i + 10, len(lines))):
                block_content += lines[j]

            is_legacy_import = False
            for pattern in import_removals:
                if pattern in block_content:
                    is_legacy_import = True
                    break

            if is_legacy_import:
                # Find the end of the try/except block
                block_end = find_try_except_block(lines, i)

                # Include trailing blank lines
                while block_end + 1 < len(lines) and not lines[block_end + 1].strip():
                    block_end += 1

                # Check for immediately following related code
                # (e.g., csr_start_preload() call right after the try/except)
                while block_end + 1 < len(lines):
                    next_line = lines[block_end + 1].strip()
                    if next_line.startswith('csr_start_preload') or next_line.startswith('csr_wait_preload'):
                        block_end += 1
                    else:
                        break

                print(f"  IMPORT: Legacy import block (lines {i+1}-{block_end+1})")
                for j in range(i, block_end + 1):
                    remove_set.add(j)
        i += 1

    # =========================================================================
    # PASS 3: Remove legacy initialization blocks in train() function
    # =========================================================================

    init_block_markers = [
        "# Initialize CSR Phoneme-Ontological Grounding",
        "# V9.8.6: Initialize CSR Three-Phase Curriculum Controller",
        "# Initialize SGP (Stochastic Gradient Persistence) and Sattvic Controller",
        "# V9.8.0: Sovereign Reasoning Kernel (SRK) Initialization",
        "# Initialize PIDv2 Controller",
        "# V9.4.5: Initialize Friction Controller",
        "# V9.5.2 Emergency Stress-Probe",  # Keep this one... actually no, let me check
        "# Kosha-Vritti Diagnostic System",
        "# V9.8.8: Sovereign Phase Controller (Graduated Phase Interventions)",
        "# Also create HiddenStateExtractor for CSR safety layers",
    ]

    # More targeted init blocks that need careful handling
    init_var_markers = [
        "resumed_csr_curriculum_state = None",
        "resumed_kosha_curriculum_state = None",
        "resumed_pidv2_curriculum_state = None",
        "resumed_kosha_gyroscope_state = None",
        "resumed_kv_supervisor_state = None",
        "resumed_srk_state = None",
        "csr_provider = None",
        "csr_entropy_sink = None",
        "csr_synthesis_gate = None",
        "csr_curriculum = None",
        "csr_graduated = False",
        "sattvic_controller = None",
        "sgp_controller = None",
        "srk = None",
        "srk_loss_fn = None",
        "srk_annealer = None",
        "srk_phase_hook = None",
        "srk_karma_state = None",
        "authority_controller = None",
        "friction_controller = None",
        "kosha_gyroscope = None",
        "kv_supervisor = None",
    ]

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Check init block markers - remove entire indented blocks
        for marker in init_block_markers:
            if marker in stripped and stripped.startswith('#'):
                block_start = i
                # Find the end of this section (it's a comment followed by code)
                # The block ends when we hit another comment block at the same indentation
                # or another major section
                base_indent = len(line) - len(line.lstrip())

                # Find end of this initialization block
                block_end = i
                in_if_block = False
                for j in range(i + 1, len(lines)):
                    jline = lines[j]
                    jstripped = jline.strip()

                    if not jstripped:  # blank line
                        block_end = j
                        continue

                    j_indent = len(jline) - len(jline.lstrip())

                    # If we hit another top-level comment or section at same indent
                    if j_indent <= base_indent and jstripped.startswith('#') and j > i + 1:
                        # Check if this is a continuation comment for same block
                        is_continuation = False
                        for m in init_block_markers:
                            if m in jstripped:
                                is_continuation = True
                                break
                        if not is_continuation:
                            break
                    elif j_indent <= base_indent and not jstripped.startswith('#') and j > i + 2:
                        # Check if this is part of the same logical block
                        # (e.g., elif after if for the same feature)
                        if jstripped.startswith('elif') and in_if_block:
                            block_end = find_indented_block_end(lines, j)
                            continue
                        elif jstripped.startswith('else:') and in_if_block:
                            block_end = find_indented_block_end(lines, j)
                            continue
                        break

                    if jstripped.startswith('if ') and j_indent == base_indent:
                        in_if_block = True

                    block_end = j

                # Include trailing blank lines
                while block_end + 1 < len(lines) and not lines[block_end + 1].strip():
                    block_end += 1

                # Don't remove already-removed lines
                new_removals = set(range(block_start, block_end + 1)) - remove_set
                if new_removals:
                    print(f"  INIT: {marker[:60]}... (lines {block_start+1}-{block_end+1})")
                    remove_set.update(new_removals)
                break

        # Check individual variable initializations
        for var_marker in init_var_markers:
            if stripped == var_marker or stripped.startswith(var_marker.split('=')[0] + ' ='):
                if var_marker.rstrip() in stripped:
                    remove_set.add(i)
                    break

    # =========================================================================
    # PASS 4: Remove training loop integration code (pattern-based)
    # =========================================================================

    # These patterns identify blocks of code in the training loop that handle
    # legacy integrations. We remove the line and any continuation.

    training_loop_patterns = [
        # SRK training loop
        re.compile(r'^\s+# V9\.8\.0: Sovereign Reasoning Kernel \(SRK\) Integration'),
        re.compile(r'^\s+srk_metrics\s*=\s*\{\}'),
        re.compile(r'^\s+if srk is not None'),
        re.compile(r'^\s+srk_metrics\b'),
        re.compile(r'^\s+srk_karma_state\b'),
        re.compile(r'^\s+phase_div_weight_for_srk\b'),
        re.compile(r'^\s+phase_div_loss_tensor\b.*SRK'),
        re.compile(r'^\s+# V9\.9\.12c: Phase diversity.*SRK'),
        re.compile(r'^\s+# V9\.9\.6:.*after SRK'),
        re.compile(r'^\s+# These may be set by.*SRK'),

        # CSR training loop
        re.compile(r'^\s+# CSR Phoneme-Ontological Grounding Integration'),
        re.compile(r'^\s+csr_metrics\s*=\s*\{\}'),
        re.compile(r'^\s+if csr_provider is not None'),
        re.compile(r'^\s+csr_\w+\s*=\b'),

        # PIDv2 training loop
        re.compile(r'^\s+if authority_controller is not None'),
        re.compile(r'^\s+auth_factor\s*=\s*authority_controller'),

        # Kosha gyroscope training loop
        re.compile(r'^\s+if kosha_gyroscope is not None'),
        re.compile(r'^\s+kosha_gyroscope\b'),

        # KV supervisor training loop
        re.compile(r'^\s+if kv_supervisor is not None'),
        re.compile(r'^\s+kv_supervisor\b'),

        # RSS training loop
        re.compile(r'^\s+if.*enable_rss\b'),
        re.compile(r'^\s+rss_weights\s*='),

        # Friction controller
        re.compile(r'^\s+if friction_controller is not None'),
        re.compile(r'^\s+friction_controller\b'),

        # SGP/Sattvic
        re.compile(r'^\s+if.*sattvic_controller\b'),
        re.compile(r'^\s+sattvic_controller\b'),
        re.compile(r'^\s+if.*sgp_controller\b'),
        re.compile(r'^\s+sgp_controller\b'),
        re.compile(r'^\s+lambda_csr\s*=\s*sattvic'),

        # CSR diagnostics logging
        re.compile(r'^\s+# V9\.7\.0: CSR Diagnostics'),
        re.compile(r'^\s+if csr_provider is not None and global_step'),

        # CSR curriculum update
        re.compile(r'^\s+# V9\.8\.6: CSR Three-Phase'),
        re.compile(r'^\s+if csr_curriculum is not None'),
        re.compile(r'^\s+csr_curriculum\b'),

        # Kosha curriculum
        re.compile(r'^\s+if kosha_curriculum is not None'),
        re.compile(r'^\s+kosha_curriculum\b'),

        # Sovereign phase controller usage
        re.compile(r'^\s+sovereign_phase_controller\b'),
    ]

    # =========================================================================
    # PASS 5: Remove checkpoint save/load lines referencing legacy systems
    # =========================================================================

    checkpoint_patterns = [
        re.compile(r'srk_state='),
        re.compile(r'csr_curriculum_state='),
        re.compile(r'pidv2_curriculum_state='),
        re.compile(r'kosha_curriculum_state='),
        re.compile(r'kosha_gyroscope_state='),
        re.compile(r'kv_supervisor_state='),
        re.compile(r'"srk_state"'),
        re.compile(r'"csr_curriculum_state"'),
        re.compile(r'"pidv2_curriculum_state"'),
        re.compile(r'"kosha_curriculum_state"'),
        re.compile(r'"kosha_gyroscope_state"'),
        re.compile(r'"kv_supervisor_state"'),
        re.compile(r'resumed_srk_state'),
        re.compile(r'resumed_csr_curriculum'),
        re.compile(r'resumed_pidv2_curriculum'),
        re.compile(r'resumed_kosha_'),
        re.compile(r'resumed_kv_supervisor'),
    ]

    # =========================================================================
    # PASS 6: Remove individual lines matching patterns
    # =========================================================================

    for i, line in enumerate(lines):
        if i in remove_set:
            continue

        stripped = line.strip()
        if not stripped:
            continue

        # Check line removal patterns (config fields)
        for pattern in LINE_REMOVAL_PATTERNS:
            if pattern.search(stripped):
                remove_set.add(i)
                # Also remove any comment lines immediately before this one
                j = i - 1
                while j >= 0 and lines[j].strip().startswith('#') and j not in remove_set:
                    comment = lines[j].strip()
                    # Only remove if the comment seems related
                    if any(kw in comment.lower() for kw in ['srk', 'pid', 'csr', 'kosha', 'vritti', 'sgp', 'sattvic', 'friction', 'sovereign phase']):
                        remove_set.add(j)
                        j -= 1
                    else:
                        break
                break

        # Check CLI arg patterns
        for pattern in CLI_ARG_PATTERNS:
            if pattern.search(stripped):
                remove_set.add(i)
                # Remove continuation lines (help= string on next line)
                j = i + 1
                while j < len(lines):
                    next_stripped = lines[j].strip()
                    if next_stripped.startswith('help=') or next_stripped.startswith('"') or next_stripped == ')':
                        remove_set.add(j)
                        if next_stripped.endswith(')'):
                            break
                        j += 1
                    else:
                        break
                break

        # Check config assignment patterns
        for pattern in CONFIG_ASSIGN_PATTERNS:
            if pattern.search(stripped):
                remove_set.add(i)
                # Also remove comment lines before
                j = i - 1
                while j >= 0 and lines[j].strip().startswith('#'):
                    comment = lines[j].strip()
                    if any(kw in comment.lower() for kw in ['srk', 'pid', 'csr', 'kosha', 'vritti', 'sgp', 'sattvic', 'friction', 'sovereign phase', 'kv ', 'rss']):
                        remove_set.add(j)
                        j -= 1
                    else:
                        break
                break

        # Check checkpoint patterns
        for pattern in checkpoint_patterns:
            if pattern.search(stripped):
                remove_set.add(i)
                break

        # Check training loop patterns (these need block-level removal)
        for pattern in training_loop_patterns:
            if pattern.search(line):
                # For if/elif blocks, remove the entire block
                if stripped.startswith(('if ', 'elif ')):
                    block_end = find_indented_block_end(lines, i)
                    for j in range(i, block_end + 1):
                        remove_set.add(j)
                else:
                    remove_set.add(i)
                break

    # =========================================================================
    # PASS 7: Clean up specific known blocks that are harder to pattern-match
    # =========================================================================

    # Find and remove the Kosha Gyroscope initialization block (lines ~14886-15020)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if '# Reference: docs/design/KOSHA_GYROSCOPE_DESIGN.md' in stripped:
            # Find the block that follows
            block_start = i
            block_end = i
            for j in range(i + 1, min(i + 200, len(lines))):
                jline = lines[j].strip()
                if jline.startswith('# V9.8.6: Three-Phase Kosha') or 'kosha_curriculum' in jline or 'kosha_gyroscope' in jline or 'KoshaGyroscopicLoss' in jline:
                    block_end = j
                elif jline.startswith('#') and 'kosha' not in jline.lower() and 'vritti' not in jline.lower() and j > i + 5:
                    break
                elif not jline:
                    block_end = j
                elif 'kosha' in jline.lower() or 'vritti' in jline.lower() or 'gyro' in jline.lower():
                    block_end = j
                elif j > block_end + 3 and jline and not any(kw in jline.lower() for kw in ['kosha', 'vritti', 'gyro', 'print', 'if ', 'else', 'elif']):
                    break
                else:
                    block_end = j

            if block_end > block_start:
                for j in range(block_start, block_end + 1):
                    remove_set.add(j)
                print(f"  KOSHA_GYRO: Gyroscope init block (lines {block_start+1}-{block_end+1})")

    # Find and remove Kosha steering initialization
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('if config.enable_kosha_steering:'):
            block_end = find_indented_block_end(lines, i)
            for j in range(i, block_end + 1):
                remove_set.add(j)
            print(f"  KOSHA_STEER: Steering init block (lines {i+1}-{block_end+1})")

    # Find and remove KV Supervisor initialization block
    for i, line in enumerate(lines):
        stripped = line.strip()
        if '# Reference: symbolu/training/kosha_vritti_supervision.py' in stripped:
            block_start = i
            block_end = i
            for j in range(i + 1, min(i + 100, len(lines))):
                jline = lines[j].strip()
                if 'kv_supervisor' in jline or 'KV_SUPERVISION' in jline or 'KoshaVrittiSupervis' in jline:
                    block_end = j
                elif not jline:
                    block_end = j
                elif 'kv_' in jline.lower() or 'kv ' in jline.lower():
                    block_end = j
                elif jline.startswith('#') and 'kv' not in jline.lower() and j > i + 3:
                    break
                elif j > block_end + 3:
                    break
                else:
                    block_end = j
            if block_end > block_start:
                for j in range(block_start, block_end + 1):
                    remove_set.add(j)
                print(f"  KV_SUPER: KV Supervisor init block (lines {block_start+1}-{block_end+1})")

    # =========================================================================
    # PASS 8: Update docstring header
    # =========================================================================

    # Find and update the module docstring
    docstring_removals = [
        "5. V9.8.0: Sovereign Reasoning Kernel (SRK)",
        "Now includes PIDv2 Governor",
        "- Dynamic SNR-Adjusted Kp",
        "- Semantic Validation (W_s weight)",
        "- Handshake D-term Dampening",
        "- Stress Test Framework",
        "- V9.4.5: Friction Controller",
        "V9.8.0 SRK Features:",
        "- Centralized ontological intervention",
        "- Layer-specific interventions: L4",
        "- Isomorphic Mapping Router (IMR)",
        "- Consistency Lagrangian (B1)",
        "- Lambda annealing for training",
        "- Mauna Protocol for inference",
        "- Backward compatibility bridge for legacy",
        "# Train with Sovereign Reasoning Kernel",
        "--enable_srk",
        "# Train Hybrid model (Local + Phase) with PIDv2 Governor",
        "--controller pidv2",
    ]

    for i, line in enumerate(lines):
        stripped = line.strip()
        for doc_removal in docstring_removals:
            if doc_removal in stripped:
                remove_set.add(i)
                break

    # =========================================================================
    # PASS 9: Remove TensorBoard logging lines for removed metrics
    # =========================================================================

    tb_removal_patterns = [
        re.compile(r'tb_writer\.add_scalar\("csr/'),
        re.compile(r'tb_writer\.add_scalar\("ctrl/'),
        re.compile(r'tb_writer\.add_scalar\("fric/'),
        re.compile(r'tb_writer\.add_scalar\("srk/'),
        re.compile(r'tb_writer\.add_scalar\("kosha_gyro/'),
        re.compile(r'tb_writer\.add_scalar\("kv/'),
        re.compile(r'# CSR Phoneme-Ontological Metrics'),
        re.compile(r'if csr_metrics:'),
    ]

    for i, line in enumerate(lines):
        if i in remove_set:
            continue
        for pattern in tb_removal_patterns:
            if pattern.search(line):
                remove_set.add(i)
                break

    # =========================================================================
    # PASS 10: Remove lines that reference removed variables
    # =========================================================================

    orphan_patterns = [
        re.compile(r'\bcsr_provider\b'),
        re.compile(r'\bcsr_entropy_sink\b'),
        re.compile(r'\bcsr_synthesis_gate\b'),
        re.compile(r'\bcsr_curriculum\b'),
        re.compile(r'\bcsr_graduated\b'),
        re.compile(r'\bcsr_output\b'),
        re.compile(r'\bcsr_emb\b'),
        re.compile(r'\bcsr_affinity\b'),
        re.compile(r'\bcsr_confidence\b'),
        re.compile(r'\bcsr_hidden\b'),
        re.compile(r'\bcsr_loss\b'),
        re.compile(r'\bcsr_metrics\b'),
        re.compile(r'\bcsr_scale\b'),
        re.compile(r'\bcsr_diag\b'),
        re.compile(r'\bsrk\b(?!_)'),  # srk but not srk_ (already handled)
        re.compile(r'\bsrk_loss_fn\b'),
        re.compile(r'\bsrk_annealer\b'),
        re.compile(r'\bsrk_phase_hook\b'),
        re.compile(r'\bsrk_karma_state\b'),
        re.compile(r'\bsrk_result\b'),
        re.compile(r'\bsrk_diagnostics\b'),
        re.compile(r'\bsrk_loss\b'),
        re.compile(r'\bsrk_metrics\b'),
        re.compile(r'\bauthority_controller\b'),
        re.compile(r'\bfriction_controller\b'),
        re.compile(r'\bfriction_penalty\b'),
        re.compile(r'\bkosha_gyroscope\b'),
        re.compile(r'\bkosha_curriculum\b'),
        re.compile(r'\bkv_supervisor\b'),
        re.compile(r'\bsattvic_controller\b'),
        re.compile(r'\bsgp_controller\b'),
        re.compile(r'\bsovereign_phase_controller\b'),
        re.compile(r'\brss_weights\b'),
        re.compile(r'\bCSR_STOPWORDS\b'),
        re.compile(r'\bCSR_AVAILABLE\b'),
        re.compile(r'\bSRK_AVAILABLE\b'),
        re.compile(r'\bPIDV2_AVAILABLE\b'),
        re.compile(r'\bKOSHA_GYROSCOPE_AVAILABLE\b'),
        re.compile(r'\bKV_SUPERVISION_AVAILABLE\b'),
        re.compile(r'\bSGP_AVAILABLE\b'),
        re.compile(r'\bWholeWordCSRHelper\b'),
        re.compile(r'\bcalculate_sparse_csr_loss\b'),
        re.compile(r'\bcompute_csr_diagnostics\b'),
        re.compile(r'\bformat_csr_diagnostic\b'),
        re.compile(r'\bThreePhaseCurriculum\b'),
        re.compile(r'\bResonanceStateScheduler\b'),
        re.compile(r'\bbuild_srk_config_from_legacy\b'),
        re.compile(r'\bbuild_srk_loss_config\b'),
        re.compile(r'\bSovereignPhaseController\b'),
        re.compile(r'\bpid_engaged\b'),
        re.compile(r'\bSovereignAnnealer\b'),
        re.compile(r'\bPhaseExtractionHook\b'),
        re.compile(r'\bSovereignReasoningKernel\b'),
        re.compile(r'\bSRKConfig\b'),
        re.compile(r'\bSRKLossConfig\b'),
        re.compile(r'\bSRKLoss\b'),
        re.compile(r'\bTeleologicalOptimizer\b'),
        re.compile(r'\bSovereignEmbedding\b'),
        re.compile(r'\bAuthorityPIDv2\b'),
        re.compile(r'\bAuthorityPIDv2Config\b'),
        re.compile(r'\bEmergencyPD\b'),
        re.compile(r'\bEmergencyPDConfig\b'),
        re.compile(r'\bcompute_semantic_ppl\b'),
        re.compile(r'\bmeasure_friction\b'),
        re.compile(r'\bFrictionController\b'),
        re.compile(r'\bFrictionControllerConfig\b'),
        re.compile(r'\bCSREmbeddingProvider\b'),
        re.compile(r'\bCSRConfig\b'),
        re.compile(r'\bEntropySink\b'),
        re.compile(r'\bSynthesisGate\b'),
        re.compile(r'\bcreate_csr_for_training\b'),
        re.compile(r'\bintegrate_csr_into_forward\b'),
        re.compile(r'\bcsr_start_preload\b'),
        re.compile(r'\bcsr_wait_preload\b'),
        re.compile(r'\bKoshaGyroscopicLoss\b'),
        re.compile(r'\bKoshaGyroscopeConfig\b'),
        re.compile(r'\bInvertedCurriculumController\b'),
        re.compile(r'\bVrittiResonanceLoss\b'),
        re.compile(r'\bVrittiResonanceConfig\b'),
        re.compile(r'\bSovereignStateRegularizer\b'),
        re.compile(r'\bSovereignStateRegularizerConfig\b'),
        re.compile(r'\bGraduationMonitor\b'),
        re.compile(r'\bGraduationConfig\b'),
        re.compile(r'\bSovereignDiagnosticLogger\b'),
        re.compile(r'\bRipEvent\b'),
        re.compile(r'\bSGPController\b'),
        re.compile(r'\bSGPConfig\b'),
        re.compile(r'\bcreate_sgp_controller\b'),
        re.compile(r'\bcreate_synchronized_controllers\b'),
        re.compile(r'\bSattvicController\b'),
        re.compile(r'\bSattvicConfig\b'),
        re.compile(r'\bcreate_sattvic_controller\b'),
        re.compile(r'\bKoshaVrittiSupervisionConfig\b'),
        re.compile(r'\bKoshaVrittiSupervisor\b'),
        re.compile(r'\blog_kv_metrics\b'),
    ]

    # Be careful with orphan patterns - only remove lines that are NOT
    # part of retained code (like comments explaining architecture, etc.)
    # We'll skip lines that are just comments unless they're in already-identified blocks
    for i, line in enumerate(lines):
        if i in remove_set:
            continue

        stripped = line.strip()
        if not stripped:
            continue

        # Skip pure comments in retained sections (they might explain architecture)
        # Only check actual code lines
        if stripped.startswith('#'):
            # Only remove comments that explicitly reference removed systems
            is_legacy_comment = any(kw in stripped.lower() for kw in [
                'srk', 'pid governor', 'pidv2', 'csr phoneme', 'csr alignment',
                'kosha gyroscope', 'kosha steering', 'kv supervision',
                'friction controller', 'sgp controller', 'sattvic controller',
                'resonance state scheduler', 'three-phase curriculum',
            ])
            if is_legacy_comment:
                remove_set.add(i)
            continue

        for pattern in orphan_patterns:
            if pattern.search(stripped):
                # Don't remove lines that are part of the save_checkpoint function
                # signature (they'll be handled separately)
                remove_set.add(i)
                break

    # =========================================================================
    # PASS 11: Remove consecutive blank lines (> 2)
    # =========================================================================

    # Build output lines (excluding removed ones)
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

    # =========================================================================
    # FINAL: Write output
    # =========================================================================

    num_removed = len(remove_set)
    num_output = len(output_lines)
    print(f"\nRemoved {num_removed} lines ({num_removed/num_original*100:.1f}%)")
    print(f"Output: {num_output} lines")

    write_file(output_path, output_lines)
    print(f"Written to {output_path}")

    return num_removed, num_output


if __name__ == "__main__":
    root = Path(__file__).parent.parent
    input_file = str(root / "train_unified_llm.py")
    output_file = str(root / "train_unified_llm_clean.py")

    print("=" * 70)
    print("  LEGACY INTEGRATION CLEANUP")
    print("  Removing: SRK, PIDv2, CSR, Kosha/Vritti, SGP/Sattvic, RSS")
    print("=" * 70)

    num_removed, num_output = process_file(input_file, output_file)

    print(f"\n{'=' * 70}")
    print(f"  CLEANUP COMPLETE")
    print(f"  Original: {num_removed + num_output} lines")
    print(f"  Removed:  {num_removed} lines")
    print(f"  Clean:    {num_output} lines")
    print(f"  Output:   {output_file}")
    print(f"{'=' * 70}")
