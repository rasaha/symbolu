#!/usr/bin/env python3
"""Track A entrypoint — run the read-only live-shadow controller against a real
Prometheus and write the combined proof-of-value report.

Intended to run ON a real cluster (see deploy/local-shadow/). Point it at the
in-cluster Prometheus (e.g. a port-forward to kube-prometheus-stack):

    kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9090 &
    python scripts/run_live_shadow.py \
        --prometheus-url http://localhost:9090 \
        --namespace boutique --deployment frontend \
        --max-cycles 240 --out-dir artifacts/cloud_controller_real_validation

The controller is READ-ONLY: zero write permissions, never actuates. The guard's
blocks are a counterfactual. Output is labelled `live-shadow-self-run`.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cloud_controller.shadow.live_efficiency import (
    LiveEfficiencyShadow,
    LiveEfficiencyConfig,
)
from cloud_controller.shadow.runner import ShadowConfig
from cloud_controller.signals.pipeline import PipelineConfig
from cloud_controller.signals.prometheus import PrometheusConfig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prometheus-url", default="http://localhost:9090")
    ap.add_argument("--namespace", default="default")
    ap.add_argument("--deployment", default="")
    ap.add_argument("--poll-interval", type=float, default=15.0)
    ap.add_argument("--max-cycles", type=int, default=240)
    ap.add_argument("--period-label", default="live-shadow run")
    ap.add_argument("--out-dir", default="artifacts/cloud_controller_real_validation")
    args = ap.parse_args()

    pipeline = PipelineConfig(
        prometheus=PrometheusConfig(url=args.prometheus_url),
        namespace=args.namespace or None,
        deployment=args.deployment or None,
        poll_interval=args.poll_interval,
    )
    shadow = LiveEfficiencyShadow(LiveEfficiencyConfig(shadow=ShadowConfig(pipeline=pipeline)))

    if not shadow.runner.pipeline.prometheus.health_check():
        print(f"ERROR: Prometheus not reachable at {args.prometheus_url}", file=sys.stderr)
        sys.exit(2)

    print(f"Live shadow (READ-ONLY) on {args.namespace}/{args.deployment or '*'} "
          f"via {args.prometheus_url} — {args.max_cycles} cycles @ {args.poll_interval}s")

    def on_cycle(lc):
        o = lc.observed
        flag = " GUARD-WOULD-BLOCK" if o.blocked else ""
        print(f"  cycle {shadow._cycles}: raw_delta={o.raw_delta:+d} "
              f"state={o.state.value} slo_breach={lc.slo_breach}{flag}")

    try:
        shadow.run(callback=on_cycle, max_cycles=args.max_cycles)
    except KeyboardInterrupt:
        print("interrupted")
    finally:
        os.makedirs(args.out_dir, exist_ok=True)
        md = os.path.join(args.out_dir, "track_a_live_shadow.md")
        js = os.path.join(args.out_dir, "track_a_live_shadow.json")
        rep = shadow.write_report(md, js, period_label=args.period_label)
        shadow.close()
        print("\n" + rep.format_markdown())
        print(f"\nWrote {md} and {js}")


if __name__ == "__main__":
    main()
