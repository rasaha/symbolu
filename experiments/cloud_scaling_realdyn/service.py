"""A real concurrent service with *emergent* latency dynamics.

This is NOT a model of latency — latency emerges from a real worker pool draining
a real bounded queue under a real arrival process, with real per-request timing.
It exists so the EfficiencyEstimator can be calibrated against real system
dynamics instead of the closed-form `_demand_to_metrics` used in simulation.

Three modes give known ground truth:
  - "capacity"   : fixed per-request service time. With too few workers the queue
                   backs up and tail latency rises; adding workers drains it →
                   scaling SHOULD help.
  - "bottleneck" : every request must hold a single global lock for a fixed time
                   (a serialized downstream). Throughput is capped at 1/lock_time
                   no matter how many workers exist → scaling should NOT help.
  - "noisy"      : capacity-like, but a fraction of requests get a large random
                   latency multiplier (interference / GC pauses / noisy neighbor).

Threads + time.sleep model an I/O-bound service faithfully: sleep releases the
GIL, so N workers really do overlap. Latency percentiles are computed from real
measured completion times.
"""

from __future__ import annotations

import random
import threading
import time
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple


class RealService:
    def __init__(
        self,
        mode: str = "capacity",
        workers: int = 2,
        arrival_rate: float = 40.0,     # requests/sec offered load
        service_time: float = 0.040,    # seconds of real work per request
        bottleneck_time: float = 0.020, # serialized critical-section time (bottleneck mode)
        queue_max: int = 200,
        noise_prob: float = 0.15,
        noise_mult: float = 6.0,
        seed: int = 1234,
    ):
        self.mode = mode
        self.service_time = service_time
        self.bottleneck_time = bottleneck_time
        self.arrival_rate = arrival_rate
        self.noise_prob = noise_prob
        self.noise_mult = noise_mult
        self._rng = random.Random(seed)

        self._queue: "deque[float]" = deque()           # enqueue timestamps
        self._queue_max = queue_max
        self._qlock = threading.Condition()
        self._ext_lock = threading.Lock()               # the shared bottleneck

        self._completions: Deque[Tuple[float, float]] = deque()  # (done_ts, latency)
        self._clock = threading.Lock()
        self._errors = 0
        self._accepted = 0
        self._busy = 0
        self._busy_lock = threading.Lock()
        # CPU model: a worker consumes CPU only while doing actual work (service
        # sleep / holding the lock), NOT while blocked acquiring the bottleneck
        # lock — mirroring a real pod, which is idle-CPU while waiting on a slow
        # downstream. Accumulated as worker-seconds and time-averaged in snapshot.
        self._active_seconds = 0.0

        self._running = True
        self._target_workers = workers
        self._worker_threads: List[threading.Thread] = []
        self._workers_lock = threading.RLock()  # reentrant: set_workers() calls _spawn_worker()
        for _ in range(workers):
            self._spawn_worker()

        self._arrival = threading.Thread(target=self._arrival_loop, daemon=True)
        self._arrival.start()

    # ---- workers ----
    def _spawn_worker(self) -> None:
        t = threading.Thread(target=self._worker_loop, daemon=True)
        t._ncc_alive = True  # type: ignore[attr-defined]
        with self._workers_lock:
            self._worker_threads.append(t)
        t.start()

    def set_workers(self, n: int) -> None:
        """Scale the worker pool to n (the 'replica count')."""
        n = max(1, n)
        with self._workers_lock:
            cur = sum(1 for t in self._worker_threads if getattr(t, "_ncc_alive", False))
            if n > cur:
                for _ in range(n - cur):
                    self._spawn_worker()
            elif n < cur:
                # retire (cur - n) workers by flipping their alive flag
                alive = [t for t in self._worker_threads if getattr(t, "_ncc_alive", False)]
                for t in alive[: cur - n]:
                    t._ncc_alive = False  # type: ignore[attr-defined]
            self._target_workers = n

    def current_workers(self) -> int:
        with self._workers_lock:
            return sum(1 for t in self._worker_threads if getattr(t, "_ncc_alive", False))

    def _worker_loop(self) -> None:
        me = threading.current_thread()
        while self._running and getattr(me, "_ncc_alive", True):
            with self._qlock:
                if not self._queue:
                    self._qlock.wait(timeout=0.05)
                    continue
                enq = self._queue.popleft()
            with self._busy_lock:
                self._busy += 1
            try:
                st = self.service_time
                if self.mode == "noisy" and self._rng.random() < self.noise_prob:
                    st *= self.noise_mult
                if self.mode == "bottleneck":
                    # Blocking to ACQUIRE the lock is idle-CPU wait (not counted as
                    # active). Only the time holding the lock + doing work is active.
                    self._ext_lock.acquire()
                    try:
                        t0 = time.time()
                        time.sleep(self.bottleneck_time)
                        time.sleep(max(0.0, st - self.bottleneck_time) * 0.1)
                        self._account_active(time.time() - t0)
                    finally:
                        self._ext_lock.release()
                else:
                    t0 = time.time()
                    time.sleep(st)
                    self._account_active(time.time() - t0)
                latency = time.time() - enq
                with self._clock:
                    self._completions.append((time.time(), latency))
            finally:
                with self._busy_lock:
                    self._busy -= 1

    # ---- arrivals ----
    def _arrival_loop(self) -> None:
        while self._running:
            time.sleep(1.0 / max(1e-6, self.arrival_rate))
            with self._qlock:
                if len(self._queue) >= self._queue_max:
                    with self._clock:
                        self._errors += 1
                    continue
                self._queue.append(time.time())
                self._accepted += 1
                self._qlock.notify()

    def set_arrival_rate(self, rate: float) -> None:
        self.arrival_rate = max(0.1, rate)

    def _account_active(self, dur: float) -> None:
        with self._clock:
            self._active_seconds += dur

    # ---- measurement ----
    def snapshot(self, window: float = 15.0) -> Dict[str, float]:
        """Real measured metrics over the last `window` seconds, then trim."""
        now = time.time()
        with self._clock:
            recent = [(ts, lat) for ts, lat in self._completions if now - ts <= window]
            completed = len(recent)
            errors = self._errors
            self._errors = 0
            active_seconds = self._active_seconds
            self._active_seconds = 0.0
            # keep only the window
            self._completions = deque((ts, lat) for ts, lat in self._completions if now - ts <= window)
        lats = sorted(lat for _, lat in recent)
        p99 = lats[min(len(lats) - 1, int(0.99 * (len(lats) - 1)))] if lats else 0.0
        p50 = lats[len(lats) // 2] if lats else 0.0
        with self._qlock:
            qd = len(self._queue)
        with self._busy_lock:
            busy = self._busy
        w = max(1, self.current_workers())
        total = completed + errors
        # Time-averaged active workers over the window → fleet CPU utilisation in
        # [0,1] (worker-seconds of real work / window / workers). Excludes lock-wait.
        avg_active_workers = active_seconds / max(1e-9, window)
        active_fraction = min(1.0, avg_active_workers / w)
        return {
            "p99_seconds": p99,
            "p50_seconds": p50,
            "error_rate_raw": (errors / total) if total else 0.0,
            "throughput_rps": completed / window,
            "queue_depth_raw": float(qd),
            "busy_workers": float(busy),
            "workers": float(w),
            "busy_fraction": busy / w,
            "active_fraction": active_fraction,   # CPU-utilisation proxy (excludes lock-wait)
        }

    def metrics_text(self) -> str:
        """Prometheus exposition so a real Prometheus can scrape this service."""
        s = self.snapshot(window=15.0)
        lines = [
            "# TYPE ncc_request_latency_p99_seconds gauge",
            f"ncc_request_latency_p99_seconds {s['p99_seconds']:.6f}",
            "# TYPE ncc_request_error_rate gauge",
            f"ncc_request_error_rate {s['error_rate_raw']:.6f}",
            "# TYPE ncc_busy_fraction gauge",
            f"ncc_busy_fraction {s['busy_fraction']:.6f}",
            "# TYPE ncc_queue_depth gauge",
            f"ncc_queue_depth {s['queue_depth_raw']:.0f}",
            "# TYPE ncc_workers gauge",
            f"ncc_workers {s['workers']:.0f}",
        ]
        return "\n".join(lines) + "\n"

    def stop(self) -> None:
        self._running = False
