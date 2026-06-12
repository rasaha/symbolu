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
    ssdconfig = ssdconfig or os.path.join(mqsim_dir, "ssdconfig.xml")
    out_dir = out_dir or os.path.dirname(os.path.abspath(trace_path))

    workload = os.path.join(out_dir, os.path.basename(trace_path) + ".workload.xml")
    write_workload_xml(workload, trace_path)

    subprocess.run(
        [binary, "-i", ssdconfig, "-w", workload],
        cwd=mqsim_dir,
        check=True,
        capture_output=True,
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
