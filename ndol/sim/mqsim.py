"""MQSim trace export, workload-XML generation, run + result parsing.

MQSim ASCII trace line:  `arrival_ns  device_id  LBA  size_sectors  type`
where type is 0=write, 1=read (confirmed against MQSim's bundled traces).
Result file `<workload>_scenario_1.xml` carries, per Host.IO_Flow:
`Request_Count`, `Read_Request_Count`, `Device_Response_Time` (µs),
`End_to_End_Request_Delay` (µs).
"""
from __future__ import annotations

import os
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass


# --------------------------------------------------------------------------- #
# Trace writer
# --------------------------------------------------------------------------- #
class MQSimTrace:
    """Accumulates (arrival_ns, device, lba, size_sectors, is_read) and writes
    the MQSim ASCII trace format. Arrivals are sorted ascending on write; equal
    timestamps are nudged +1 ns to keep the stream strictly monotonic (a burst
    of concurrent requests at one decode step)."""

    def __init__(self) -> None:
        self._rows: list[tuple[int, int, int, int, int]] = []

    def add(self, arrival_ns: int, lba: int, size_sectors: int, is_read: bool, device: int = 0) -> None:
        self._rows.append((int(arrival_ns), device, int(lba), int(size_sectors), 1 if is_read else 0))

    def write(self, path: str) -> int:
        self._rows.sort(key=lambda r: r[0])
        last = -1
        with open(path, "w") as fh:
            for arrival, dev, lba, size, typ in self._rows:
                if arrival <= last:
                    arrival = last + 1
                last = arrival
                fh.write(f"{arrival} {dev} {lba} {size} {typ}\n")
        return len(self._rows)

    def __len__(self) -> int:
        return len(self._rows)


# --------------------------------------------------------------------------- #
# Workload XML
# --------------------------------------------------------------------------- #
_WORKLOAD_TEMPLATE = """<?xml version="1.0" encoding="us-ascii"?>
<MQSim_IO_Scenarios>
  <IO_Scenario>
    <IO_Flow_Parameter_Set_Trace_Based>
      <Priority_Class>HIGH</Priority_Class>
      <Device_Level_Data_Caching_Mode>WRITE_CACHE</Device_Level_Data_Caching_Mode>
      <Channel_IDs>0,1,2,3,4,5,6,7</Channel_IDs>
      <Chip_IDs>0,1,2,3</Chip_IDs>
      <Die_IDs>0,1</Die_IDs>
      <Plane_IDs>0,1</Plane_IDs>
      <Initial_Occupancy_Percentage>30</Initial_Occupancy_Percentage>
      <File_Path>{trace_path}</File_Path>
      <Percentage_To_Be_Executed>100</Percentage_To_Be_Executed>
      <Relay_Count>1</Relay_Count>
      <Time_Unit>NANOSECOND</Time_Unit>
    </IO_Flow_Parameter_Set_Trace_Based>
  </IO_Scenario>
</MQSim_IO_Scenarios>
"""


def write_workload_xml(path: str, trace_path: str) -> None:
    with open(path, "w") as fh:
        fh.write(_WORKLOAD_TEMPLATE.format(trace_path=os.path.abspath(trace_path)))


# --------------------------------------------------------------------------- #
# Run + parse
# --------------------------------------------------------------------------- #
@dataclass
class MQSimResult:
    request_count: int
    read_request_count: int
    device_response_time_us: float       # MQSim average device response time
    end_to_end_delay_us: float

    @property
    def is_valid(self) -> bool:
        return self.request_count > 0


def _parse_result(result_xml: str) -> MQSimResult:
    root = ET.parse(result_xml).getroot()
    flow = root.find(".//Host.IO_Flow")
    if flow is None:
        raise RuntimeError(f"no Host.IO_Flow in {result_xml}")

    def num(tag: str) -> float:
        el = flow.find(tag)
        return float(el.text) if el is not None and el.text else 0.0

    return MQSimResult(
        request_count=int(num("Request_Count")),
        read_request_count=int(num("Read_Request_Count")),
        device_response_time_us=num("Device_Response_Time"),
        end_to_end_delay_us=num("End_to_End_Request_Delay"),
    )


def run_mqsim(
    trace_path: str,
    *,
    mqsim_dir: str | None = None,
    ssdconfig: str | None = None,
    out_dir: str | None = None,
    timeout_s: int = 600,
) -> MQSimResult:
    """Replay one trace through MQSim, return measured latency.

    `mqsim_dir` defaults to $NDOL_MQSIM_DIR or /tmp/MQSim. Raises FileNotFoundError
    if the MQSim binary isn't built there.
    """
    mqsim_dir = mqsim_dir or os.environ.get("NDOL_MQSIM_DIR", "/tmp/MQSim")
    binary = os.path.join(mqsim_dir, "MQSim")
    if not os.path.exists(binary):
        raise FileNotFoundError(
            f"MQSim binary not found at {binary}. Build it: "
            f"git clone https://github.com/CMU-SAFARI/MQSim && cd MQSim && make -j"
        )
    out_dir = out_dir or os.path.dirname(os.path.abspath(trace_path))
    if ssdconfig is None:
        # Default to a shrunk device so MQSim's startup allocation fits a
        # memory-capped container (the full ssdconfig models ~512 GB → OOM).
        ssdconfig = os.path.join(out_dir, "ssd_small.xml")
        _configure(ET.parse(os.path.join(mqsim_dir, "ssdconfig.xml"))).write(ssdconfig)

    workload = os.path.join(out_dir, os.path.basename(trace_path) + ".workload.xml")
    write_workload_xml(workload, trace_path)

    subprocess.run(
        [binary, "-i", ssdconfig, "-w", workload],
        cwd=mqsim_dir,
        check=True,
        capture_output=True,
        # MQSim ends with a blocking "Press any key to exit" read on stdin; on an
        # interactive TTY that hangs forever. Feed it EOF so it exits immediately.
        stdin=subprocess.DEVNULL,
        timeout=timeout_s,
    )
    result_xml = workload[: -len(".xml")] + "_scenario_1.xml"
    return _parse_result(result_xml)


# --------------------------------------------------------------------------- #
# KV read-skip workload → baseline + NDOL traces
# --------------------------------------------------------------------------- #
def _retained_set(step: int, n_blocks: int, retained: int) -> list[int]:
    """A stable hot set + a sliding recency window — the attention shape
    read-skip exploits (persistent heavy hitters + recent tokens)."""
    hot = retained // 2
    window = retained - hot
    start = (step * window) % max(1, n_blocks - window)
    return list(range(hot)) + list(range(hot + start, hot + start + window))


def _configure(
    tree: "ET.ElementTree",
    *,
    t_r_us: float | None = None,
    blocks_per_plane: int = 16,
    pages_per_block: int = 64,
) -> "ET.ElementTree":
    """Shrink the simulated device and (optionally) set its tier read latency.

    The default ssdconfig models a ~512 GB device whose page-level FTL map +
    startup pre-conditioning allocate multiple GB — enough to be SIGKILL'd by a
    container memory cgroup. Our KV traces touch only a few MB of LBA space, so
    we shrink Block_No_Per_Plane / Page_No_Per_Block to a ~1 GB device. The
    channel/chip/die/plane parallelism (which drives the timing model) is
    untouched, so latencies stay representative; only the address space shrinks.
    """
    for el in tree.getroot().iter():
        if t_r_us is not None and el.tag.startswith("Page_Read_Latency"):
            el.text = str(int(t_r_us * 1000))
        elif el.tag == "Block_No_Per_Plane":
            el.text = str(blocks_per_plane)
        elif el.tag == "Page_No_Per_Block":
            el.text = str(pages_per_block)
    return tree


def make_tier_config(base_ssdconfig: str, out_path: str, t_r_us: float) -> str:
    """Write an ssdconfig variant whose every Page_Read_Latency_* equals `t_r_us`
    (µs → ns), on a shrunk device. Models an SLC/TLC/QLC tier by its array read
    time t_R — the term §2 says dominates a read."""
    tree = _configure(ET.parse(base_ssdconfig), t_r_us=t_r_us)
    tree.write(out_path)
    return out_path


# Tier array-read times (µs): SLC fast/low-density, QLC slow/high-density.
TIER_T_R_US = {"SLC": 25.0, "TLC": 50.0, "QLC": 100.0}


def tiered_kv_traces(
    out_dir: str,
    *,
    n_protected: int = 8,
    n_bulk_window: int = 24,
    n_bulk_total: int = 256,
    n_steps: int = 32,
    block_sectors: int = 8,
    step_interval_ns: int = 300_000,
) -> dict:
    """Emit traces for the W3 protect-mask tiering experiment.

    Access model (the attention shape that makes tiering pay off):
      * protected / hot blocks  — re-read EVERY step (persistent heavy hitters)
      * bulk / cold blocks       — read once, via a sliding recency window

    Produces three read streams from the SAME workload:
      uniform.trace  — protected + bulk together (for a uniform-TLC baseline)
      tier_slc.trace — protected (hot) reads only  (→ run on the SLC config)
      tier_qlc.trace — bulk (cold) reads only       (→ run on the QLC config)
    """
    os.makedirs(out_dir, exist_ok=True)
    uniform, slc, qlc = MQSimTrace(), MQSimTrace(), MQSimTrace()
    base_lba = (n_protected + 1) * block_sectors  # bulk LBAs start past protected

    for s in range(n_steps):
        burst = s * step_interval_ns
        for i in range(n_protected):                       # hot: re-read every step
            lba = i * block_sectors
            uniform.add(burst + i, lba, block_sectors, is_read=True)
            slc.add(burst + i, lba, block_sectors, is_read=True)
        start = (s * n_bulk_window) % max(1, n_bulk_total - n_bulk_window)
        for j in range(n_bulk_window):                     # cold: read once (sliding)
            lba = base_lba + (start + j) * block_sectors
            uniform.add(burst + n_protected + j, lba, block_sectors, is_read=True)
            qlc.add(burst + n_protected + j, lba, block_sectors, is_read=True)

    paths = {
        "uniform_trace": os.path.join(out_dir, "uniform.trace"),
        "tier_slc_trace": os.path.join(out_dir, "tier_slc.trace"),
        "tier_qlc_trace": os.path.join(out_dir, "tier_qlc.trace"),
    }
    return {
        **paths,
        "uniform_requests": uniform.write(paths["uniform_trace"]),
        "slc_requests": slc.write(paths["tier_slc_trace"]),
        "qlc_requests": qlc.write(paths["tier_qlc_trace"]),
    }


def kv_read_skip_traces(
    out_dir: str,
    *,
    n_blocks: int = 256,
    n_steps: int = 32,
    retained: int = 32,
    block_sectors: int = 8,
    step_interval_ns: int = 300_000,
    prefill: bool = True,
) -> dict:
    """Emit two MQSim traces from one KV workload:

      baseline.trace : full attention — read ALL blocks every decode step.
      ndol.trace     : read-skip — read only the retained set every step.

    Both share identical write-once prefill (fair). Returns request counts.
    """
    os.makedirs(out_dir, exist_ok=True)
    base, ndol = MQSimTrace(), MQSimTrace()

    t = 0
    if prefill:  # write-once-at-prefill, identical in both streams
        for b in range(n_blocks):
            lba = b * block_sectors
            base.add(t, lba, block_sectors, is_read=False)
            ndol.add(t, lba, block_sectors, is_read=False)
            t += 1_000
    decode_start = t + 1_000_000

    for s in range(n_steps):
        burst = decode_start + s * step_interval_ns
        for i in range(n_blocks):                       # baseline: full attention
            base.add(burst + i, i * block_sectors, block_sectors, is_read=True)
        for i, b in enumerate(_retained_set(s, n_blocks, retained)):  # NDOL: read-skip
            ndol.add(burst + i, b * block_sectors, block_sectors, is_read=True)

    base_path = os.path.join(out_dir, "baseline.trace")
    ndol_path = os.path.join(out_dir, "ndol.trace")
    return {
        "baseline_trace": base_path,
        "ndol_trace": ndol_path,
        "baseline_requests": base.write(base_path),
        "ndol_requests": ndol.write(ndol_path),
    }
