"""HTTP Metrics Server — serves /metrics endpoint for Prometheus scraping.

Runs a lightweight stdlib HTTP server in a daemon thread, serving the
Prometheus text exposition from a MetricsExporter instance.

Zero external dependencies — uses http.server from the standard library.

Usage:
    from cloud_scaling_operations.observability.exporter import MetricsExporter
    from cloud_scaling_operations.observability.metrics_server import MetricsServer

    exporter = MetricsExporter()
    server = MetricsServer(exporter, MetricsServerConfig(port=9090))
    server.start()
    # Prometheus scrapes http://localhost:9090/metrics
    server.stop()
"""

import logging
import threading
from dataclasses import dataclass
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

from cloud_scaling_operations.observability.exporter import MetricsExporter

logger = logging.getLogger(__name__)


@dataclass
class MetricsServerConfig:
    """Configuration for the HTTP metrics server."""
    host: str = "0.0.0.0"
    port: int = 9090
    # Path to serve metrics on
    metrics_path: str = "/metrics"
    # Health check path
    health_path: str = "/healthz"


def _make_handler(exporter: MetricsExporter, config: MetricsServerConfig):
    """Create a request handler class bound to the given exporter.

    We use a factory function instead of a class attribute because
    BaseHTTPRequestHandler doesn't support constructor arguments cleanly.
    """

    class _MetricsHandler(BaseHTTPRequestHandler):
        """Handles GET /metrics and GET /healthz."""

        def do_GET(self) -> None:
            if self.path == config.metrics_path:
                body = exporter.expose()
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "text/plain; version=0.0.4; charset=utf-8",
                )
                self.send_header("Content-Length", str(len(body.encode("utf-8"))))
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))
            elif self.path == config.health_path:
                body = "ok"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))
            else:
                self.send_error(404, "Not Found")

        def log_message(self, format, *args):
            """Suppress default stderr logging — use logger instead."""
            logger.debug("MetricsServer: %s", format % args)

    return _MetricsHandler


class MetricsServer:
    """HTTP server exposing /metrics for Prometheus scraping.

    Usage:
        server = MetricsServer(exporter, MetricsServerConfig(port=9090))
        server.start()
        # ...
        server.stop()

    As context manager:
        with MetricsServer(exporter) as server:
            # server is running
            pass
        # server is stopped
    """

    def __init__(
        self,
        exporter: MetricsExporter,
        config: Optional[MetricsServerConfig] = None,
    ):
        self.config = config or MetricsServerConfig()
        self._exporter = exporter
        self._httpd: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the HTTP server in a background daemon thread.

        Raises RuntimeError if the server is already running.
        """
        with self._lock:
            if self._httpd is not None:
                raise RuntimeError("MetricsServer is already running")

            handler_class = _make_handler(self._exporter, self.config)
            self._httpd = HTTPServer(
                (self.config.host, self.config.port),
                handler_class,
            )

            self._thread = threading.Thread(
                target=self._httpd.serve_forever,
                daemon=True,
            )
            self._thread.start()

            logger.info(
                "MetricsServer started on %s:%d%s",
                self.config.host,
                self.config.port,
                self.config.metrics_path,
            )

    def stop(self) -> None:
        """Stop the HTTP server and wait for the thread to exit."""
        with self._lock:
            if self._httpd is None:
                return

            self._httpd.shutdown()
            if self._thread is not None:
                self._thread.join(timeout=5)
            self._httpd.server_close()
            self._httpd = None
            self._thread = None

            logger.info("MetricsServer stopped")

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._httpd is not None

    @property
    def url(self) -> str:
        """Base URL of the running server."""
        host = self.config.host
        if host == "0.0.0.0":
            host = "127.0.0.1"
        return f"http://{host}:{self.config.port}"

    @property
    def metrics_url(self) -> str:
        """Full URL for the /metrics endpoint."""
        return f"{self.url}{self.config.metrics_path}"

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
