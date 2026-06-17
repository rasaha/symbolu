// k6 load profiles for the live-shadow validation.
//
// Each "stage block" reproduces the load-shape of a synthetic scenario against
// the real Online Boutique frontend, so the controller sees a real arrival
// process (not a synthetic demand_fn). k6 also remote-writes its RED metrics
// (http_req_duration, http_reqs, http_req_failed) to Prometheus, which the
// controller reads as latency_p99 / error_rate.
//
// Run:
//   K6_PROMETHEUS_RW_SERVER_URL=http://<prom>/api/v1/write \
//   k6 run -o experimental-prometheus-rw \
//       -e BASE_URL=http://<frontend> -e PROFILE=sudden_10x_spike k6-load.js
//
// PROFILE selects which synthetic scenario's load-shape to drive. Profiles that
// are purely controller-internal or infra-config (plasticity_stuck_low,
// budget_cap, …) are NOT load shapes — drive those via the controller config /
// HPA manifest / chaos experiments instead (see chaos/ and README mapping).

import http from "k6/http";
import { sleep } from "k6";

const BASE = __ENV.BASE_URL || "http://localhost:8080";
const PROFILE = __ENV.PROFILE || "sudden_10x_spike";

// Arrival-rate (req/s) stage blocks keyed by scenario load-shape.
const PROFILES = {
  // #6 sudden 10x spike
  sudden_10x_spike: [
    { duration: "2m", target: 5 },
    { duration: "30s", target: 50 },
    { duration: "3m", target: 25 },
  ],
  // #14 gradual drift — ultra-slow ramp
  gradual_drift: [
    { duration: "1m", target: 5 },
    { duration: "8m", target: 40 },
    { duration: "1m", target: 40 },
  ],
  // #17 partial recovery — spike, dip, spike
  partial_recovery: [
    { duration: "1m", target: 5 },
    { duration: "1m", target: 45 },
    { duration: "1m", target: 20 },
    { duration: "1m", target: 45 },
    { duration: "1m", target: 18 },
    { duration: "1m", target: 42 },
    { duration: "1m", target: 5 },
  ],
  // #18 cold start — hot from t0
  cold_start_amplification: [
    { duration: "10s", target: 45 },
    { duration: "3m", target: 45 },
    { duration: "2m", target: 30 },
  ],
  // #10 coherence oscillation — oscillate near threshold
  coherence_oscillation: [
    { duration: "30s", target: 30 },
    { duration: "30s", target: 12 },
    { duration: "30s", target: 30 },
    { duration: "30s", target: 12 },
    { duration: "30s", target: 30 },
    { duration: "30s", target: 12 },
  ],
};

export const options = {
  scenarios: {
    load: {
      executor: "ramping-arrival-rate",
      startRate: 5,
      timeUnit: "1s",
      preAllocatedVUs: 50,
      maxVUs: 200,
      stages: PROFILES[PROFILE] || PROFILES.sudden_10x_spike,
    },
  },
};

// Browse + add-to-cart hits the real frontend → product/cart/currency deps.
const PRODUCTS = ["OLJCESPC7Z", "66VCHSJNUP", "1YMWWN1N4O", "L9ECAV7KIM", "2ZYFJ3GM2N"];
export default function () {
  http.get(`${BASE}/`);
  const p = PRODUCTS[Math.floor(Math.random() * PRODUCTS.length)];
  http.get(`${BASE}/product/${p}`);
  http.post(`${BASE}/cart`, { product_id: p, quantity: "1" });
  sleep(0.2 + Math.random() * 0.4);
}
