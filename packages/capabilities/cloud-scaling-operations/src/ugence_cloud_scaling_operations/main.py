"""CLI entrypoint for the Neural Cloud Controller.

Usage:
    python -m cloud_scaling_operations.main --config /etc/ncc/controller.yaml
    python -m cloud_scaling_operations.main --dry-run          # defaults, no scaling
    python -m cloud_scaling_operations.main --shadow           # shadow mode vs HPA
"""

import argparse
import logging
import os
import signal
import sys
from typing import Any, Dict, Optional

from ugence_cloud_scaling_controller.config import InfraControllerConfig
from ugence_cloud_scaling_controller.controller import Controller
from ugence_cloud_scaling_operations.observability.exporter import (
    ExporterConfig,
    ExporterMode,
)
from ugence_cloud_scaling_operations.observability.metrics_server import MetricsServerConfig
from ugence_cloud_scaling_operations.observability.otel_exporter import OtelExporterConfig
from ugence_cloud_scaling_operations.orchestrator import (
    OrchestratorConfig,
    ProductionOrchestrator,
)
from ugence_cloud_scaling_controller.signals.pipeline import PipelineConfig
from ugence_cloud_scaling_controller.signals.prometheus import PrometheusConfig
from ugence_cloud_scaling_operations.recommend.engine import RecommendConfig
from ugence_cloud_scaling_controller.recommend.confidence import ConfidenceConfig
from ugence_cloud_scaling_controller.recommend.safety import SafetyConfig
from ugence_cloud_scaling_operations.action.k8s_actuator import ActuatorConfig, ActuatorMode
from ugence_cloud_scaling_operations.action.feedback import FeedbackConfig

logger = logging.getLogger("ncc")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Neural Cloud Controller — adaptive scaling for Kubernetes",
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default="",
        help="Path to YAML config file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run with defaults in dry-run mode (no config file needed)",
    )
    parser.add_argument(
        "--shadow",
        action="store_true",
        help="Run in shadow mode — observe and compare with HPA, no scaling",
    )
    parser.add_argument(
        "--prometheus-url",
        type=str,
        default="",
        help="Override Prometheus URL",
    )
    parser.add_argument(
        "--namespace",
        type=str,
        default="",
        help="Target Kubernetes namespace",
    )
    parser.add_argument(
        "--deployment",
        type=str,
        default="",
        help="Target deployment name",
    )
    parser.add_argument(
        "--metrics-port",
        type=int,
        default=0,
        help="Port for /metrics HTTP server (0 = use config or disable)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="",
        help="Log level (DEBUG, INFO, WARNING, ERROR)",
    )
    return parser.parse_args()


def _load_config(path: str) -> Dict[str, Any]:
    """Load YAML config file.

    ``PyYAML`` is an optional dependency (the ``shadow`` extra). It is imported
    lazily here so importing this module never requires it.
    """
    try:
        import yaml
    except ImportError:  # pragma: no cover - optional extra not installed
        raise ImportError(
            "Loading a YAML config requires PyYAML. Install the optional extra: "
            "pip install ugence-cloud-scaling-controller[shadow]"
        )
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _build_orchestrator_config(
    raw: Dict[str, Any],
    args: argparse.Namespace,
) -> OrchestratorConfig:
    """Build OrchestratorConfig from parsed YAML + CLI overrides."""
    # Prometheus
    prom_cfg = raw.get("prometheus", {})
    prom_url = args.prometheus_url or prom_cfg.get("url", "http://localhost:9090")
    prometheus = PrometheusConfig(
        url=prom_url,
        timeout_seconds=prom_cfg.get("timeout_seconds", 10.0),
    )

    # Target workload
    target = raw.get("target", {})
    ns = args.namespace or target.get("namespace", "default")
    deploy = args.deployment or target.get("deployment", "")

    # Controller tuning
    ctrl_cfg = raw.get("controller", {})
    controller_config = InfraControllerConfig(
        G_base=ctrl_cfg.get("G_base", 1.0),
        G_min=ctrl_cfg.get("G_min", 0.0),
        G_max=ctrl_cfg.get("G_max", 3.0),
        k_dv=ctrl_cfg.get("k_dv", 1.0),
        k_dc=ctrl_cfg.get("k_dc", 0.5),
        cycle_interval_seconds=ctrl_cfg.get("cycle_interval_seconds", 15.0),
        warmup_steps=ctrl_cfg.get("warmup_steps", 100),
    )

    # Pipeline
    pipeline = PipelineConfig(
        prometheus=prometheus,
        controller=controller_config,
        poll_interval=controller_config.cycle_interval_seconds,
        namespace=ns,
        deployment=deploy,
    )

    # Safety
    safety_cfg = raw.get("safety", {})
    safety = SafetyConfig(
        max_scale_out_fraction=safety_cfg.get("max_scale_out_fraction", 0.50),
        max_scale_in_fraction=safety_cfg.get("max_scale_in_fraction", 0.25),
        min_replicas=safety_cfg.get("min_replicas", 1),
        cooldown_seconds=safety_cfg.get("cooldown_seconds", 120.0),
    )

    # Actuator
    act_cfg = raw.get("actuator", {})
    mode_str = act_cfg.get("mode", "dry_run")
    actuator_mode = {
        "dry_run": ActuatorMode.DRY_RUN,
        "scale_patch": ActuatorMode.SCALE_PATCH,
        "hpa_metric": ActuatorMode.HPA_METRIC,
    }.get(mode_str, ActuatorMode.DRY_RUN)
    actuator = ActuatorConfig(mode=actuator_mode)

    # Feedback
    fb_cfg = raw.get("feedback", {})
    feedback = None
    if fb_cfg.get("enabled", True):
        feedback = FeedbackConfig(
            enabled=True,
            max_adjustment_rate=fb_cfg.get("max_adjustment_rate", 0.10),
        )

    # Recommend
    recommend = RecommendConfig(
        service=deploy or "default-service",
        namespace=ns,
        safety=safety,
        actuator=actuator,
        feedback=feedback,
    )

    # Exporter
    exp_cfg = raw.get("exporter", {})
    exporter = ExporterConfig(
        mode=ExporterMode.BUILTIN,
        prefix=exp_cfg.get("prefix", "ncc"),
        service=deploy,
        namespace=ns,
    )

    # Metrics server
    ms_cfg = raw.get("metrics_server", {})
    metrics_port = args.metrics_port or ms_cfg.get("port", 0)
    metrics_server = None
    if metrics_port > 0:
        metrics_server = MetricsServerConfig(
            host="0.0.0.0",
            port=metrics_port,
            metrics_path=ms_cfg.get("metrics_path", "/metrics"),
            health_path=ms_cfg.get("health_path", "/healthz"),
        )

    # Auto-approve
    auto_approve = raw.get("auto_approve_threshold", None)

    return OrchestratorConfig(
        pipeline=pipeline,
        recommend=recommend,
        exporter=exporter,
        metrics_server=metrics_server,
        auto_approve_threshold=auto_approve,
        bootstrap_on_start=True,
    )


def _setup_logging(level_str: str) -> None:
    level = getattr(logging, level_str.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def _run_shadow(config: Dict[str, Any], args: argparse.Namespace) -> None:
    """Run in shadow mode — compare controller vs HPA without scaling."""
    from ugence_cloud_scaling_operations.shadow.runner import ShadowConfig, ShadowRunner

    target = config.get("target", {})
    ns = args.namespace or target.get("namespace", "default")
    deploy = args.deployment or target.get("deployment", "")

    prom_cfg = config.get("prometheus", {})
    prom_url = args.prometheus_url or prom_cfg.get("url", "http://localhost:9090")

    pipeline = PipelineConfig(
        prometheus=PrometheusConfig(url=prom_url),
        namespace=ns,
        deployment=deploy,
    )

    shadow_config = ShadowConfig(pipeline=pipeline)
    runner = ShadowRunner(shadow_config)

    logger.info("Shadow mode: watching %s/%s", ns, deploy)
    logger.info("Prometheus: %s", prom_url)
    logger.info("Press Ctrl+C to stop and print report")

    def on_cycle(result):
        if result.divergence:
            logger.info(
                "Cycle %d: %s (controller=%s, hpa=%s)",
                result.cycle_number,
                result.divergence.verdict.value,
                result.controller_action,
                result.hpa_action,
            )

    try:
        runner.run(callback=on_cycle)
    except KeyboardInterrupt:
        runner.stop()
        report = runner.report()
        print("\n" + report.format_text())


def main() -> None:
    args = _parse_args()

    # Logging
    log_level = args.log_level or os.environ.get("NCC_LOG_LEVEL", "INFO")
    _setup_logging(log_level)

    # Load config
    raw: Dict[str, Any] = {}
    if args.config:
        logger.info("Loading config from %s", args.config)
        raw = _load_config(args.config)
    elif args.dry_run:
        logger.info("Dry-run mode with defaults")
        raw = {"actuator": {"mode": "dry_run"}}
    elif not args.shadow:
        logger.warning("No --config, --dry-run, or --shadow specified; using defaults")

    # Shadow mode
    if args.shadow:
        _run_shadow(raw, args)
        return

    # Build orchestrator
    orch_config = _build_orchestrator_config(raw, args)
    target = raw.get("target", {})
    deploy = args.deployment or target.get("deployment", "(not set)")
    ns = args.namespace or target.get("namespace", "default")

    logger.info("Neural Cloud Controller starting")
    logger.info("  Target: %s/%s", ns, deploy)
    logger.info("  Prometheus: %s", orch_config.pipeline.prometheus.url)
    logger.info("  Actuator: %s", orch_config.recommend.actuator.mode.value if orch_config.recommend.actuator else "dry_run")
    if orch_config.metrics_server:
        logger.info("  Metrics: http://0.0.0.0:%d/metrics", orch_config.metrics_server.port)
    logger.info("  Auto-approve: %s", orch_config.auto_approve_threshold or "disabled")

    with ProductionOrchestrator(config=orch_config) as orch:
        # Graceful shutdown
        def _shutdown(sig, frame):
            logger.info("Received signal %s, shutting down", sig)
            orch.stop()

        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)

        def on_cycle(result):
            if result.success:
                rec = result.recommend
                logger.info(
                    "Cycle %d: action=%.4f rec=%s confidence=%s (%.2fs)",
                    result.cycle_number,
                    result.pipeline.action.action_score,
                    rec.recommendation if rec else "n/a",
                    rec.confidence.level if rec else "n/a",
                    result.cycle_duration,
                )
            else:
                logger.warning("Cycle %d: pipeline poll failed", result.cycle_number)

        try:
            orch.run(callback=on_cycle)
        except KeyboardInterrupt:
            logger.info("Interrupted, shutting down")


if __name__ == "__main__":
    main()
