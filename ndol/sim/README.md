# NDOL × MQSim — device-measured timing (Phase P1)

This package replaces NDOL's analytical latency model (`ndol.model.NANDModel`,
Phase **P0** in the design doc §6) with **device-measured** timing from
[MQSim](https://github.com/CMU-SAFARI/MQSim), a validated trace-driven SSD
simulator with a real FTL, channel/chip/die/plane parallelism, GC, and flash
timing — Phase **P1**. No hardware; MQSim is a software simulator.

## Methodology

NDOL emits the *physical request stream* it would issue to the device, for two
policies on one KV workload:

- `baseline.trace` — **full attention**: read every KV block every decode step.
- `ndol.trace` — **read-skip**: read only the retained set every step.

Both share an identical write-once prefill (fair). MQSim replays each stream and
reports measured `Device_Response_Time` / `End_to_End_Request_Delay`. The
speedup is then MQSim's, not ours.

## Build MQSim (one time)

```bash
git clone https://github.com/CMU-SAFARI/MQSim /tmp/MQSim
cd /tmp/MQSim && make -j
```

## Run

```bash
python -m ndol.sim.run --mqsim /tmp/MQSim --blocks 256 --steps 32 --retained 32
# or: export NDOL_MQSIM_DIR=/tmp/MQSim
```

## Measured result (2026-06-12, MQSim default `ssdconfig.xml`)

| policy | requests | device_response (µs) |
|---|---|---|
| baseline (full attention) | 8448 | 80247 |
| ndol (read-skip) | 1280 | 7550 |

- **Request-volume reduction: 6.6×** — this is the read-skip A_BW (the clean, load-independent number).
- **Per-request latency ratio: 10.6×** — read-skip also relieves queue contention; **this multiple is load-dependent** (the baseline saturates the device at this arrival cadence). Do not quote it as a fixed speedup.

## W3 — protect-mask tiering experiment

```bash
python -m ndol.sim.run_tiered --mqsim /tmp/MQSim --protected 24 --bulk-window 4 --steps 32
```

MQSim models one flash technology per device, so each tier is run on its own
`Page_Read_Latency`-configured device (SLC 25µs / TLC 50µs / QLC 100µs, varying
only t_R) and the tiers are composed by read volume — the physical claim being
that SLC and QLC are independent regions. **Honest hybrid:** MQSim measures each
tier; we volume-weight. Compared against a uniform-TLC device.

Measured (2026-06-12), device response time (µs):

| config | protected:bulk volume | uniform (TLC) | tiered (SLC+QLC) | ratio | verdict |
|---|---|---|---|---|---|
| bulk-dominated (P=8, W=24) | 256 : 768 | 139 | 176 | **0.79×** | tiering **loses** on latency |
| hot-dominated (P=24, W=4) | 768 : 128 | 122 | 92 | **1.33×** | tiering **wins** on latency |

**Finding:** protect-mask tiering is a **latency win only when the protected/hot
reads dominate read volume**; with a small hot set + large recency churn (the
common attention shape) the QLC bulk majority makes uniform-TLC faster. This
confirms design doc §3.4: **tiering's primary value is density/capacity** (bulk
in dense QLC at preserved quality — int4_protected's thesis), and the latency
effect is conditional, not a given. Do not claim a tiering latency speedup
unconditionally.

## Honest notes

- **Flash timing lives in `ssdconfig.xml`** (`Flash_Parameter_Set`: `Page_Read_Latency`, etc.), not in NDOL. To model TLC/QLC specifically, edit that file — the measured numbers will move accordingly.
- The per-request latency multiple depends on arrival cadence (`step_interval_ns`) and step count. The defensible measured claim is the **volume reduction**; the contention relief is real but workload-dependent.
- This measures the **read-skip gather** (W1 mechanism). It does *not* yet model the protect-mask SLC/QLC tiering (W3) — that needs a multi-region MQSim config and is the next step.
- MQSim runtime grows with request count; keep `blocks × steps` modest for quick runs.
