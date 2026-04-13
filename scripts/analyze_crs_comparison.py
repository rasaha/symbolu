#!/usr/bin/env python3
"""
CRS Phase 3: Post-run analysis for A vs B comparison.

Reads training logs from Mode A and Mode B, extracts metrics,
produces the validation report template, and gives a GO/NO-GO verdict.

Usage:
    python scripts/analyze_crs_comparison.py [--log-dir logs_crs_validation]
"""

import re
import sys
import os
import argparse
from collections import defaultdict


def parse_training_log(path):
    """Parse a Mistral_CG training log and extract all CRS-relevant metrics."""
    data = {
        'steps': [],
        'losses': [],
        'crs_C': [], 'crs_R': [], 'crs_S': [],
        'crs_Sg': [], 'crs_ovr': [],
        'col3_lines': [],
        'cg_grad_lines': [],
        'alpha_lines': [],
        'all_crs_lines': [],
    }

    if not os.path.exists(path):
        return None

    with open(path) as f:
        for line in f:
            # Step number
            step_m = re.search(r'[Ss]tep[=: ]+(\d+)', line)

            # Training loss
            loss_m = re.search(r'(?:train[_ ])?loss[=: ]+([\d.]+)', line)
            if loss_m and 'aux' not in line.lower() and 'bliss' not in line.lower():
                data['losses'].append(float(loss_m.group(1)))
                if step_m:
                    data['steps'].append(int(step_m.group(1)))

            # CRS diagnostic line: "CRS: C=... R=... S=... Sg=... ovr=..."
            crs_m = re.search(
                r'CRS:\s*C=([\d.e+-]+)\s*R=([\d.e+-]+)\s*S=([\d.e+-]+)\s*Sg=([\d.e+-]+)\s*ovr=([\d.e+-]+)',
                line
            )
            if crs_m:
                data['crs_C'].append(float(crs_m.group(1)))
                data['crs_R'].append(float(crs_m.group(2)))
                data['crs_S'].append(float(crs_m.group(3)))
                data['crs_Sg'].append(float(crs_m.group(4)))
                data['crs_ovr'].append(float(crs_m.group(5)))
                data['all_crs_lines'].append(line.strip())

            # CG-GRAD lines (gradient health)
            if 'CG-GRAD' in line:
                data['cg_grad_lines'].append(line.strip())

            # Alpha/routing lines
            if 'alpha' in line.lower() and ('csr' in line.lower() or 'crs' in line.lower()):
                data['alpha_lines'].append(line.strip())

    return data


def compute_stats(values, label=""):
    """Compute summary stats for a list of values."""
    if not values:
        return {'mean': None, 'std': None, 'min': None, 'max': None, 'n': 0}
    import statistics
    return {
        'mean': statistics.mean(values),
        'std': statistics.stdev(values) if len(values) > 1 else 0.0,
        'min': min(values),
        'max': max(values),
        'n': len(values),
    }


def print_report(data_a, data_b):
    """Print the full comparison report."""

    print("=" * 70)
    print("CRS PHASE 3: A vs B COMPARISON REPORT")
    print("=" * 70)

    # --- Mode A ---
    print("\n" + "=" * 70)
    print("MODE A: Legacy CSR")
    print("=" * 70)
    if data_a is None:
        print("  LOG NOT FOUND")
    else:
        losses = data_a['losses']
        if losses:
            print(f"  Steps logged:    {len(losses)}")
            print(f"  Loss start:      {losses[0]:.4f}")
            print(f"  Loss end:        {losses[-1]:.4f}")
            print(f"  Loss min:        {min(losses):.4f}")
            # Column-3 info not directly in log for legacy — note this
            print(f"  CRS diagnostics: N/A (legacy mode)")
        else:
            print(f"  No loss data found in log")

    # --- Mode B ---
    print("\n" + "=" * 70)
    print("MODE B: Full CRS")
    print("=" * 70)
    if data_b is None:
        print("  LOG NOT FOUND")
    else:
        losses = data_b['losses']
        if losses:
            print(f"  Steps logged:    {len(losses)}")
            print(f"  Loss start:      {losses[0]:.4f}")
            print(f"  Loss end:        {losses[-1]:.4f}")
            print(f"  Loss min:        {min(losses):.4f}")
        else:
            print(f"  No loss data found in log")

        # CRS branch diagnostics
        if data_b['crs_C']:
            n = len(data_b['crs_C'])
            tail = min(n, 10)

            print(f"\n  Branch diagnostics ({n} measurements):")
            print(f"  {'':4s} {'Overall':>12s}  {'Last {}'.format(tail):>12s}")

            for key, label in [('crs_C', 'C_mean'), ('crs_R', 'R_mean'),
                               ('crs_S', 'S_mean'), ('crs_Sg', 'S_gate'),
                               ('crs_ovr', 'Override')]:
                vals = data_b[key]
                overall = compute_stats(vals)
                recent = compute_stats(vals[-tail:])
                print(f"  {label:12s} {overall['mean']:>+10.4f}   {recent['mean']:>+10.4f}")

            # Key health checks
            print(f"\n  Health checks:")

            # R alive?
            r_stats = compute_stats(data_b['crs_R'][-tail:])
            r_alive = r_stats['mean'] is not None and (abs(r_stats['mean']) > 0.001 or r_stats['std'] > 0.001)
            print(f"    R branch alive:     {'YES' if r_alive else 'NO (R_mean≈0)'}")

            # S_gate saturation?
            sg_stats = compute_stats(data_b['crs_Sg'][-tail:])
            sg_ok = sg_stats['mean'] is not None and 0.15 < sg_stats['mean'] < 0.85
            print(f"    S_gate healthy:     {'YES ({:.2f})'.format(sg_stats['mean']) if sg_ok else 'WARNING ({:.2f})'.format(sg_stats['mean'] if sg_stats['mean'] else 0)}")

            # Override rate
            ovr_stats = compute_stats(data_b['crs_ovr'][-tail:])
            if ovr_stats['mean'] is not None:
                if ovr_stats['mean'] < 0.01:
                    ovr_verdict = "INERT (<1%)"
                elif ovr_stats['mean'] < 0.15:
                    ovr_verdict = "HEALTHY ({:.1f}%)".format(ovr_stats['mean'] * 100)
                elif ovr_stats['mean'] < 0.30:
                    ovr_verdict = "HIGH ({:.1f}%)".format(ovr_stats['mean'] * 100)
                else:
                    ovr_verdict = "WARNING: TOO HIGH ({:.1f}%)".format(ovr_stats['mean'] * 100)
            else:
                ovr_verdict = "NO DATA"
            print(f"    Override rate:       {ovr_verdict}")

            # C alive?
            c_stats = compute_stats(data_b['crs_C'][-tail:])
            c_alive = c_stats['mean'] is not None and (abs(c_stats['mean']) > 0.005 or c_stats['std'] > 0.005)
            print(f"    C branch alive:     {'YES' if c_alive else 'WEAK/DEAD'}")

        else:
            print(f"  No CRS diagnostic lines found in log")
            print(f"  Check that --enable_cg_diagnostics and --log_every are set")

        # Print last few CRS diagnostic lines for manual inspection
        if data_b['all_crs_lines']:
            print(f"\n  Last 5 CRS diagnostic lines:")
            for line in data_b['all_crs_lines'][-5:]:
                print(f"    {line}")

    # --- Comparison ---
    print("\n" + "=" * 70)
    print("A vs B COMPARISON")
    print("=" * 70)

    if data_a and data_b and data_a['losses'] and data_b['losses']:
        a_end = data_a['losses'][-1]
        b_end = data_b['losses'][-1]
        ratio = b_end / (a_end + 1e-8)
        print(f"  Loss (end): A={a_end:.4f}, B={b_end:.4f}, B/A={ratio:.3f}x")
        if ratio < 1.5:
            print(f"  Loss comparison: ACCEPTABLE (< 1.5x)")
        elif ratio < 2.0:
            print(f"  Loss comparison: WARNING (1.5-2.0x)")
        else:
            print(f"  Loss comparison: DEGRADED (> 2.0x)")
    else:
        print(f"  Cannot compare losses — missing data")

    # --- Verdict ---
    print("\n" + "=" * 70)
    print("VERDICT TEMPLATE (fill in after review)")
    print("=" * 70)
    print("""
  Legacy path intact:     ___
  CRS runs cleanly:       ___
  R branch alive:         ___
  S separating from base: ___
  Gate active:            ___
  Override meaningful:    ___
  Loss stability:         ___
  Scale compatible:       ___

  RECOMMENDATION:         GO / TUNE / FIX / ABORT
  Issues:                 ___
  Next steps:             ___
""")


def main():
    parser = argparse.ArgumentParser(description="Analyze CRS A vs B comparison logs")
    parser.add_argument("--log-dir", default="logs_crs_validation",
                       help="Directory containing mode_A.log and mode_B.log")
    args = parser.parse_args()

    log_a = os.path.join(args.log_dir, "mode_A.log")
    log_b = os.path.join(args.log_dir, "mode_B.log")

    print(f"Reading logs from: {args.log_dir}/")
    data_a = parse_training_log(log_a)
    data_b = parse_training_log(log_b)

    if data_a is None and data_b is None:
        print(f"\nNo logs found. Run scripts/run_crs_ab_comparison.sh first.")
        sys.exit(1)

    print_report(data_a, data_b)


if __name__ == "__main__":
    main()
