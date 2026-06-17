"""Prometheus HTTP client for metric ingestion.

Wraps the Prometheus HTTP API (/api/v1/query, /api/v1/query_range).
No Prometheus client library dependency — uses plain HTTP via requests.

Designed for polling at 15-second intervals. Each query returns the most
recent value (instant query) or a time series (range query).
"""

import math
import re
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


@dataclass
class PrometheusConfig:
    """Configuration for Prometheus connection."""
    url: str = "http://localhost:9090"
    timeout_seconds: float = 10.0
    # Optional auth headers (e.g., Bearer token for Thanos/Cortex)
    headers: Dict[str, str] = field(default_factory=dict)
    # Retry on transient failures
    max_retries: int = 2
    retry_delay_seconds: float = 1.0


# Default PromQL queries for the MVP metric set.
# Each entry: (metric_name, promql, description)
DEFAULT_QUERIES: List[Tuple[str, str, str]] = [
    (
        "cpu",
        'avg(rate(node_cpu_seconds_total{mode!="idle"}[2m]))',
        "Average CPU utilization across nodes",
    ),
    (
        "memory",
        "1 - avg(node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)",
        "Average memory pressure (1 = fully used)",
    ),
    (
        "latency_p99",
        'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[2m])) by (le, job))',
        "HTTP request latency p99 in seconds",
    ),
    (
        "error_rate",
        'sum(rate(http_requests_total{code=~"5.."}[2m])) / clamp_min(sum(rate(http_requests_total[2m])), 0.001)',
        "5xx error rate as fraction of total requests (safe division)",
    ),
    (
        "queue_depth",
        "sum(queue_messages_ready)",
        "Total messages waiting in queues",
    ),
]

# Kubernetes-specific queries for system state.
#
# Label selectors are injected at the `__NSSEL__` / `__HPASEL__` tokens by
# query_k8s_state (NOT by naive brace-splicing). HPA replica counts use the
# modern kube-state-metrics names (kube_horizontalpodautoscaler_status_*) with an
# `or` fallback to the legacy names (kube_hpa_status_*) so the same query works
# across kube-state-metrics versions. Note the HPA series is labelled by
# `horizontalpodautoscaler` (the HPA's name), not `deployment`; the `deployment`
# argument is matched against that label (HPA name == target name by convention).
K8S_QUERIES: List[Tuple[str, str, str]] = [
    (
        "pod_restarts",
        "sum(rate(kube_pod_container_status_restarts_total__NSSEL__[10m]))",
        "Pod restart rate over last 10 minutes",
    ),
    (
        "current_replicas",
        "kube_horizontalpodautoscaler_status_current_replicas__HPASEL__ "
        "or kube_hpa_status_current_replicas__HPASEL__",
        "Current replica count from HPA (modern name, legacy fallback)",
    ),
    (
        "desired_replicas",
        "kube_horizontalpodautoscaler_status_desired_replicas__HPASEL__ "
        "or kube_hpa_status_desired_replicas__HPASEL__",
        "Desired replica count from HPA (modern name, legacy fallback)",
    ),
]


class PrometheusClient:
    """HTTP client for Prometheus instant and range queries.

    Usage:
        client = PrometheusClient(PrometheusConfig(url="http://prometheus:9090"))
        value = client.instant_query('avg(rate(node_cpu_seconds_total{mode!="idle"}[2m]))')
        series = client.range_query('...', start, end, step="15s")
    """

    def __init__(self, config: Optional[PrometheusConfig] = None):
        self.config = config or PrometheusConfig()
        self._session = requests.Session()
        self._session.headers.update(self.config.headers)

    def instant_query(self, query: str, time_: Optional[float] = None) -> Optional[float]:
        """Execute an instant query and return a scalar value.

        Args:
            query: PromQL expression.
            time_: Optional evaluation timestamp (Unix seconds). Defaults to now.

        Returns:
            Float value if query returns a single scalar/vector result, None otherwise.
        """
        params = {"query": query}
        if time_ is not None:
            params["time"] = str(time_)

        data = self._request("/api/v1/query", params)
        if data is None:
            return None

        value = self._extract_scalar(data)
        if value is not None and not math.isfinite(value):
            logger.warning("Query returned non-finite value (%s): %s", value, query)
            return None
        return value

    def range_query(
        self,
        query: str,
        start: float,
        end: float,
        step: str = "15s",
    ) -> Optional[List[Tuple[float, float]]]:
        """Execute a range query and return time series.

        Args:
            query: PromQL expression.
            start: Start timestamp (Unix seconds).
            end: End timestamp (Unix seconds).
            step: Query resolution step (e.g., "15s", "1m").

        Returns:
            List of (timestamp, value) tuples, or None on failure.
        """
        params = {
            "query": query,
            "start": str(start),
            "end": str(end),
            "step": step,
        }

        data = self._request("/api/v1/query_range", params)
        if data is None:
            return None

        return self._extract_series(data)

    def query_metrics(
        self,
        queries: Optional[List[Tuple[str, str, str]]] = None,
    ) -> Dict[str, Optional[float]]:
        """Run all metric queries and return name → value mapping.

        Args:
            queries: List of (name, promql, description). Defaults to DEFAULT_QUERIES.

        Returns:
            Dict of metric_name → value (None if query failed).
        """
        if queries is None:
            queries = DEFAULT_QUERIES

        results: Dict[str, Optional[float]] = {}
        for name, promql, _ in queries:
            results[name] = self.instant_query(promql)

        return results

    # Label value validation: only allow safe characters to prevent PromQL injection
    _LABEL_RE = re.compile(r'^[a-zA-Z0-9._/-]+$')

    @classmethod
    def _validate_label(cls, value: str) -> bool:
        """Validate a Prometheus label value is safe for query injection."""
        return bool(cls._LABEL_RE.match(value))

    def query_k8s_state(
        self,
        namespace: Optional[str] = None,
        deployment: Optional[str] = None,
    ) -> Dict[str, Optional[float]]:
        """Query Kubernetes-specific state metrics.

        Args:
            namespace: Filter by K8s namespace.
            deployment: Filter by scaling target name (matched against the HPA's
                `horizontalpodautoscaler` label; HPA name == target by convention).

        Returns:
            Dict of state_name → value.
        """
        # Validate label values to prevent PromQL injection
        if namespace and not self._validate_label(namespace):
            logger.warning("Invalid namespace label rejected: %s", namespace)
            namespace = None
        if deployment and not self._validate_label(deployment):
            logger.warning("Invalid deployment label rejected: %s", deployment)
            deployment = None

        # Build label selectors and splice them in at the explicit tokens. This
        # is correct for aggregations (sum/rate) and `or` expressions, unlike
        # naive first-brace replacement.
        ns_sel = f'{{namespace="{namespace}"}}' if namespace else ""
        hpa_parts = []
        if namespace:
            hpa_parts.append(f'namespace="{namespace}"')
        if deployment:
            hpa_parts.append(f'horizontalpodautoscaler="{deployment}"')
        hpa_sel = "{" + ",".join(hpa_parts) + "}" if hpa_parts else ""

        results: Dict[str, Optional[float]] = {}
        for name, promql, _ in K8S_QUERIES:
            q = promql.replace("__NSSEL__", ns_sel).replace("__HPASEL__", hpa_sel)
            results[name] = self.instant_query(q)

        return results

    def health_check(self) -> bool:
        """Check if Prometheus is reachable."""
        try:
            url = f"{self.config.url}/-/healthy"
            resp = self._session.get(url, timeout=self.config.timeout_seconds)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def _request(self, path: str, params: Dict) -> Optional[Dict]:
        """Make an HTTP request to Prometheus with retry logic."""
        url = f"{self.config.url}{path}"

        for attempt in range(self.config.max_retries + 1):
            try:
                resp = self._session.get(
                    url,
                    params=params,
                    timeout=self.config.timeout_seconds,
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("status") != "success":
                    logger.warning(
                        "Prometheus query failed: %s — %s",
                        params.get("query", ""),
                        data.get("error", "unknown"),
                    )
                    return None

                return data.get("data", {})

            except requests.RequestException as e:
                if attempt < self.config.max_retries:
                    logger.debug(
                        "Prometheus request retry %d/%d: %s",
                        attempt + 1,
                        self.config.max_retries,
                        e,
                    )
                    time.sleep(self.config.retry_delay_seconds)
                else:
                    logger.warning("Prometheus request failed after retries: %s", e)
                    return None

        return None

    @staticmethod
    def _extract_scalar(data: Dict) -> Optional[float]:
        """Extract a single float from Prometheus query result.

        Handles both scalar and vector result types.
        For vector results with multiple elements, returns the first.
        """
        result_type = data.get("resultType")
        results = data.get("result", [])

        if result_type == "scalar":
            # [timestamp, "value"]
            if len(results) >= 2:
                try:
                    return float(results[1])
                except (ValueError, TypeError):
                    return None

        elif result_type == "vector":
            # [{"metric": {...}, "value": [timestamp, "value"]}, ...]
            if results and "value" in results[0]:
                try:
                    return float(results[0]["value"][1])
                except (ValueError, TypeError, IndexError):
                    return None

        return None

    @staticmethod
    def _extract_series(data: Dict) -> Optional[List[Tuple[float, float]]]:
        """Extract time series from Prometheus range query result."""
        results = data.get("result", [])
        if not results:
            return None

        # Take the first result set
        values = results[0].get("values", [])
        series = []
        for ts, val in values:
            try:
                series.append((float(ts), float(val)))
            except (ValueError, TypeError):
                continue

        return series if series else None

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
