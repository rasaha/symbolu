#!/usr/bin/env python3
"""
Apply Phase 13, 19, 31 Integration Changes
Systematically applies all necessary code changes for full integration
"""

import os
import sys

def read_file(filepath):
    with open(filepath, 'r') as f:
        return f.read()

def write_file(filepath, content):
    with open(filepath, 'w') as f:
        f.write(content)

def apply_phase13_temporal_state():
    """Add enhanced_smi field to TemporalState"""
    filepath = 'symbolu/temporal/temporal_bhava_tracker.py'
    content = read_file(filepath)

    # Add enhanced_smi field to TemporalState
    old = """    bhava_gap: Optional[float] = None

    # State classification"""
    new = """    bhava_gap: Optional[float] = None
    enhanced_smi: Optional[float] = None  # Phase 13: Enhanced SMI

    # State classification"""

    if old in content and 'enhanced_smi: Optional[float] = None  # Phase 13' not in content:
        content = content.replace(old, new)
        write_file(filepath, content)
        print(f"✓ Added enhanced_smi to TemporalState")
    else:
        print(f"⚠ TemporalState already has enhanced_smi or pattern not found")

def apply_phase13_compute_formulas():
    """Wire enhanced SMI computation in compute_formulas"""
    filepath = 'symbolu/temporal/temporal_bhava_tracker.py'
    content = read_file(filepath)

    # Find the compute_formulas method and add enhanced SMI computation
    marker = "# Store formulas in snapshot"

    if marker in content and "compute_enhanced_smi_snapshot" not in content.split(marker)[0]:
        # Add computation before creating snapshot
        insert_code = """
        # Phase 13: Enhanced SMI (observation only - not used in state classification)
        enhanced_smi_value = None
        if len(self.entries) > 0:
            enhanced_smi_snapshot = compute_enhanced_smi_snapshot(
                dim_resonance=dimensional_resonance if dimensional_resonance is not None else None,
                vrtti_balance=vrtti_intensity if vrtti_intensity is not None else None,
                bhava_alignment=bhava_position if bhava_position is not None else None,
                semantic_weighting=0.5,  # Default neutral value
                temporal_decay=0.5,  # Default neutral value
                noise_suppression=0.7,  # Default moderate suppression
            )
            if enhanced_smi_snapshot is not None:
                enhanced_smi_value = enhanced_smi_snapshot.enhanced_smi

"""
        content = content.replace(marker, insert_code + "        " + marker)
        write_file(filepath, content)
        print(f"✓ Added enhanced SMI computation in compute_formulas")
    else:
        print(f"⚠ Enhanced SMI computation already present or marker not found")

def apply_phase13_snapshot_creation():
    """Add enhanced_smi to snapshot creation"""
    filepath = 'symbolu/temporal/temporal_bhava_tracker.py'
    content = read_file(filepath)

    # Update TemporalFormulaSnapshot instantiation
    old = """            mirror_time_loop=None,  # Phase 21: Populated separately
            mirror_time_cycle_summary=None,  # Phase 22: Populated separately
        )"""
    new = """            mirror_time_loop=None,  # Phase 21: Populated separately
            mirror_time_cycle_summary=None,  # Phase 22: Populated separately
            enhanced_smi=enhanced_smi_value,
        )"""

    if old in content:
        content = content.replace(old, new)
        write_file(filepath, content)
        print(f"✓ Added enhanced_smi to TemporalFormulaSnapshot instantiation")
    else:
        print(f"⚠ TemporalFormulaSnapshot instantiation already updated or pattern not found")

def apply_phase13_temporal_state_creation():
    """Add enhanced_smi to TemporalState instantiation"""
    filepath = 'symbolu/temporal/temporal_bhava_tracker.py'
    content = read_file(filepath)

    # Update TemporalState instantiation
    old = """            bhava_gap=bhava_gap,
            state=state_label,"""
    new = """            bhava_gap=bhava_gap,
            enhanced_smi=enhanced_smi_value,
            state=state_label,"""

    if old in content and 'enhanced_smi=enhanced_smi_value,' not in content:
        content = content.replace(old, new)
        write_file(filepath, content)
        print(f"✓ Added enhanced_smi to TemporalState instantiation")
    else:
        print(f"⚠ TemporalState instantiation already updated or pattern not found")

def apply_phase13_pattern_summary():
    """Add enhanced_smi to get_pattern_summary output"""
    filepath = 'symbolu/temporal/temporal_bhava_tracker.py'
    content = read_file(filepath)

    # Update get_pattern_summary
    old = """        return {
            "formulas": {
                "smi": self.formulas.smi if self.formulas else None,"""
    new = """        return {
            "formulas": {
                "enhanced_smi": self.formulas.enhanced_smi if self.formulas else None,
                "smi": self.formulas.smi if self.formulas else None,"""

    if old in content and '"enhanced_smi"' not in content.split('"formulas": {')[1].split('}')[0]:
        content = content.replace(old, new)
        write_file(filepath, content)
        print(f"✓ Added enhanced_smi to get_pattern_summary")
    else:
        print(f"⚠ get_pattern_summary already updated or pattern not found")

def main():
    """Apply all integration changes"""
    print("=" * 60)
    print("Phase 13, 19, 31 Integration Patch Application")
    print("=" * 60)
    print()

    # Change to repo root
    if not os.path.exists('symbolu'):
        print("ERROR: Must run from repository root")
        sys.exit(1)

    print("Phase 13: Enhanced SMI Integration")
    print("-" * 60)
    apply_phase13_temporal_state()
    apply_phase13_compute_formulas()
    apply_phase13_snapshot_creation()
    apply_phase13_temporal_state_creation()
    apply_phase13_pattern_summary()

    print()
    print("=" * 60)
    print("Patch application complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Review changes: git diff")
    print("2. Run tests: pytest symbolu/core/formula_drift_tests/test_phase13_enhanced_smi.py -q")
    print("3. Commit and push if tests pass")
    print()

if __name__ == "__main__":
    main()
