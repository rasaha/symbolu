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

## Honest notes

- **Flash timing lives in `ssdconfig.xml`** (`Flash_Parameter_Set`: `Page_Read_Latency`, etc.), not in NDOL. To model TLC/QLC specifically, edit that file — the measured numbers will move accordingly.
- The per-request latency multiple depends on arrival cadence (`step_interval_ns`) and step count. The defensible measured claim is the **volume reduction**; the contention relief is real but workload-dependent.
- This measures the **read-skip gather** (W1 mechanism). It does *not* yet model the protect-mask SLC/QLC tiering (W3) — that needs a multi-region MQSim config and is the next step.
- MQSim runtime grows with request count; keep `blocks × steps` modest for quick runs.
