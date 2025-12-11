#!/usr/bin/env python3
"""
Invariance Diff Analyzer

This script inspects git diffs for changes to critical pipeline modules and verifies
that any change to critical code is accompanied by:
  1. An appropriate invariance audit test file (existing or updated)
  2. A corresponding PHASE_NN_MERGE_SAFETY_REPORT.md (existing or updated)

Usage:
    python scripts/invariance_diff_analyzer.py --base main
    python scripts/invariance_diff_analyzer.py --base origin/main --head HEAD

CI Integration:
    This script can be integrated into CI to ensure invariance coverage:
        - Add a job "invariance-diff-check" that runs:
          python scripts/invariance_diff_analyzer.py --base origin/main
        - Configure it to fail the build on exit code 1 (YELLOW or RED status)

Exit Codes:
    0 - GREEN: All impacted phases have proper invariance coverage
    1 - YELLOW/RED: Missing or incomplete invariance coverage
"""

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional


# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


# Critical module paths that trigger invariance checks
CRITICAL_PATHS = [
    'symbolu/core/',
    'symbolu/mechanical/',
    'symbolu/policy/',
    'symbolu/formulas/',
    'symbolu/api/',
    'symbolu/adapter/',
    'symbolu/service/',
]


def run_git_command(cmd: List[str]) -> str:
    """Execute a git command and return its output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"{Colors.RED}Error running git command: {' '.join(cmd)}{Colors.RESET}")
        print(f"Error: {e.stderr}")
        sys.exit(1)


def get_changed_files(base: str, head: str) -> List[str]:
    """Get list of files changed between base and head."""
    output = run_git_command(['git', 'diff', '--name-only', f'{base}..{head}'])
    return [line for line in output.split('\n') if line]


def is_critical_file(filepath: str) -> bool:
    """Check if a file is in a critical module path."""
    if any(filepath.startswith(path) for path in CRITICAL_PATHS):
        return True
    # Also check for phase test files
    if filepath.startswith('tests/test_phase') and filepath.endswith('.py'):
        return True
    return False


def extract_phase_from_filename(filepath: str) -> Optional[int]:
    """Extract phase number from filename if present."""
    # Match patterns like test_phaseNN_, test_phaseNN_invariance, PHASE_NN_
    patterns = [
        r'test_phase(\d+)_',
        r'PHASE_(\d+)_',
        r'phase(\d+)_',
        r'Phase(\d+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, filepath, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def map_file_to_phases(filepath: str) -> Set[int]:
    """
    Map a changed file to relevant phase numbers.
    Returns a set of phase numbers (can be empty if no clear mapping).
    """
    phases = set()

    # Direct phase number extraction from filename
    phase_num = extract_phase_from_filename(filepath)
    if phase_num:
        phases.add(phase_num)

    # Map specific modules to known phases (based on codebase knowledge)
    # This is a heuristic mapping - can be extended
    module_phase_map = {
        'temporal_entropy': [1, 2],
        'guna_kosha': [8],
        'vritti': [13, 14],
        'semantic_integrity': [17],
        'drift_fusion': [19],
        'adaptive_continuity': [37],
        'temporal_coherence_forecasting': [38],
        'multi_horizon_temporal_forecasting': [39],
        'cross_horizon_resonance': [40],
        'unified_consciousness': [45],
        'trajectory_convergence': [46],
        'utsse': [47],
    }

    filepath_lower = filepath.lower()
    for keyword, phase_list in module_phase_map.items():
        if keyword in filepath_lower:
            phases.update(phase_list)

    return phases


def check_invariance_test_exists(phase: int) -> Tuple[bool, Optional[str]]:
    """
    Check if an invariance audit test exists for the given phase.
    Returns (exists, filepath).
    """
    # Common patterns for invariance test files
    patterns = [
        f'tests/test_phase{phase}_invariance_audit.py',
        f'tests/test_phase{phase:02d}_invariance_audit.py',
    ]

    # Check for specific named tests (based on existing files)
    specific_tests = {
        31: 'tests/test_phase31_apel_invariance_audit.py',
        38: 'tests/test_phase38_tcfm_invariance_audit.py',
        40: 'tests/test_phase40_chrae_invariance_audit.py',
        45: 'tests/test_phase45_mtsf_invariance_audit.py',
        46: 'tests/test_phase46_trajectory_convergence_invariance_audit.py',
        47: 'tests/test_phase47_utsse_invariance_audit.py',
    }

    if phase in specific_tests:
        patterns.insert(0, specific_tests[phase])

    for pattern in patterns:
        path = Path(pattern)
        if path.exists():
            return True, str(path)

    return False, None


def check_merge_safety_report_exists(phase: int) -> Tuple[bool, Optional[str]]:
    """
    Check if a merge safety report exists for the given phase.
    Returns (exists, filepath).
    """
    patterns = [
        f'PHASE_{phase}_MERGE_SAFETY_REPORT.md',
        f'PHASE_{phase:02d}_MERGE_SAFETY_REPORT.md',
    ]

    for pattern in patterns:
        path = Path(pattern)
        if path.exists():
            return True, str(path)

    return False, None


def check_file_modified_in_diff(filepath: str, changed_files: List[str]) -> bool:
    """Check if a specific file was modified in the diff."""
    return filepath in changed_files


def analyze_phase_invariance(
    phase: int,
    critical_files: List[str],
    changed_files: List[str]
) -> Dict:
    """
    Analyze invariance coverage for a specific phase.
    Returns a dict with analysis results.
    """
    result = {
        'phase': phase,
        'critical_files': critical_files,
        'invariance_test_exists': False,
        'invariance_test_path': None,
        'invariance_test_modified': False,
        'merge_report_exists': False,
        'merge_report_path': None,
        'merge_report_modified': False,
        'status': 'RED',  # RED, YELLOW, or GREEN
    }

    # Check invariance test
    test_exists, test_path = check_invariance_test_exists(phase)
    result['invariance_test_exists'] = test_exists
    result['invariance_test_path'] = test_path

    if test_path:
        result['invariance_test_modified'] = check_file_modified_in_diff(
            test_path, changed_files
        )

    # Check merge safety report
    report_exists, report_path = check_merge_safety_report_exists(phase)
    result['merge_report_exists'] = report_exists
    result['merge_report_path'] = report_path

    if report_path:
        result['merge_report_modified'] = check_file_modified_in_diff(
            report_path, changed_files
        )

    # Determine status
    if not test_exists or not report_exists:
        result['status'] = 'RED'
    elif not result['invariance_test_modified'] and not result['merge_report_modified']:
        # Critical files changed but invariance files didn't - warning
        result['status'] = 'YELLOW'
    else:
        result['status'] = 'GREEN'

    return result


def print_phase_report(analysis: Dict):
    """Print a formatted report for a single phase."""
    phase = analysis['phase']
    status = analysis['status']

    # Status color
    status_color = {
        'GREEN': Colors.GREEN,
        'YELLOW': Colors.YELLOW,
        'RED': Colors.RED,
    }[status]

    print(f"\n{Colors.BOLD}{Colors.CYAN}PHASE {phase}:{Colors.RESET}")
    print(f"  {Colors.BOLD}Critical files changed:{Colors.RESET}")
    for file in analysis['critical_files']:
        print(f"    - {file}")

    # Invariance tests
    test_status = f"{Colors.GREEN}YES{Colors.RESET}" if analysis['invariance_test_exists'] else f"{Colors.RED}NO{Colors.RESET}"
    test_info = f" ({analysis['invariance_test_path']})" if analysis['invariance_test_path'] else ""
    print(f"  {Colors.BOLD}Invariance tests present:{Colors.RESET} {test_status}{test_info}")

    # Merge safety report
    report_status = f"{Colors.GREEN}YES{Colors.RESET}" if analysis['merge_report_exists'] else f"{Colors.RED}NO{Colors.RESET}"
    report_info = f" ({analysis['merge_report_path']})" if analysis['merge_report_path'] else ""
    print(f"  {Colors.BOLD}Merge safety report present:{Colors.RESET} {report_status}{report_info}")

    # Modification status
    if analysis['invariance_test_exists']:
        if analysis['invariance_test_modified']:
            print(f"  {Colors.BOLD}Invariance tests modified:{Colors.RESET} {Colors.GREEN}YES → OK{Colors.RESET}")
        else:
            print(f"  {Colors.BOLD}Invariance tests modified:{Colors.RESET} {Colors.YELLOW}NO → WARNING{Colors.RESET}")

    if analysis['merge_report_exists'] and analysis['merge_report_modified']:
        print(f"  {Colors.BOLD}Merge safety report modified:{Colors.RESET} {Colors.GREEN}YES{Colors.RESET}")

    print(f"  {Colors.BOLD}Status:{Colors.RESET} {status_color}{status}{Colors.RESET}")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze git diff for invariance coverage',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--base',
        default='origin/main',
        help='Base git ref to compare against (default: origin/main)'
    )
    parser.add_argument(
        '--head',
        default='HEAD',
        help='Head git ref to compare (default: HEAD)'
    )
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )

    args = parser.parse_args()

    # Disable colors if requested
    if args.no_color:
        for attr in dir(Colors):
            if not attr.startswith('_'):
                setattr(Colors, attr, '')

    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}Invariance Diff Analyzer{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"\nAnalyzing changes from {Colors.CYAN}{args.base}{Colors.RESET} to {Colors.CYAN}{args.head}{Colors.RESET}\n")

    # Get changed files
    changed_files = get_changed_files(args.base, args.head)

    if not changed_files:
        print(f"{Colors.YELLOW}No files changed between {args.base} and {args.head}{Colors.RESET}")
        return 0

    print(f"Total files changed: {len(changed_files)}\n")

    # Filter critical files
    critical_files = [f for f in changed_files if is_critical_file(f)]

    if not critical_files:
        print(f"{Colors.GREEN}No critical files changed. Invariance check not required.{Colors.RESET}")
        return 0

    print(f"{Colors.YELLOW}Critical files changed: {len(critical_files)}{Colors.RESET}")

    # Map files to phases
    phase_files = defaultdict(list)
    unknown_files = []

    for file in critical_files:
        phases = map_file_to_phases(file)
        if phases:
            for phase in phases:
                phase_files[phase].append(file)
        else:
            unknown_files.append(file)

    # Analyze each phase
    phase_analyses = []
    for phase in sorted(phase_files.keys()):
        files = phase_files[phase]
        analysis = analyze_phase_invariance(phase, files, changed_files)
        phase_analyses.append(analysis)
        print_phase_report(analysis)

    # Report unknown files
    if unknown_files:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}UNCLASSIFIED CRITICAL FILES:{Colors.RESET}")
        print(f"  {Colors.YELLOW}The following critical files could not be mapped to a specific phase:{Colors.RESET}")
        for file in unknown_files:
            print(f"    - {file}")
        print(f"  {Colors.YELLOW}Consider updating the phase mapping in the script.{Colors.RESET}")

    # Calculate final status
    statuses = [a['status'] for a in phase_analyses]

    if 'RED' in statuses:
        final_status = 'RED'
        final_message = "MISSING INVARIANCE COVERAGE: Some phases lack required invariance tests or merge safety reports."
    elif 'YELLOW' in statuses:
        final_status = 'YELLOW'
        final_message = "INCOMPLETE INVARIANCE COVERAGE: Critical files changed but invariance tests/reports were not updated."
    else:
        final_status = 'GREEN'
        final_message = "INVARIANCE COVERAGE OK: All impacted phases have proper invariance coverage."

    # Print final status
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}FINAL STATUS:{Colors.RESET}")

    status_color = {
        'GREEN': Colors.GREEN,
        'YELLOW': Colors.YELLOW,
        'RED': Colors.RED,
    }[final_status]

    print(f"  {status_color}{Colors.BOLD}{final_status}: {final_message}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}\n")

    # Summary statistics
    print(f"{Colors.BOLD}Summary:{Colors.RESET}")
    print(f"  - Phases analyzed: {len(phase_analyses)}")
    print(f"  - GREEN: {statuses.count('GREEN')}")
    print(f"  - YELLOW: {statuses.count('YELLOW')}")
    print(f"  - RED: {statuses.count('RED')}")

    if unknown_files:
        print(f"  - Unclassified files: {len(unknown_files)}")

    # Exit with appropriate code
    exit_code = 0 if final_status == 'GREEN' else 1

    if exit_code != 0:
        print(f"\n{Colors.RED}Exiting with code {exit_code}{Colors.RESET}")

    return exit_code


if __name__ == '__main__':
    sys.exit(main())
