"""MQSim integration — replace NDOL's analytical latency model (P0) with
device-measured timing from the MQSim SSD simulator (P1, §6 of the design doc).

NDOL emits the *physical* request stream it would issue to the device
(baseline full-attention vs. read-skip-reduced); MQSim replays each stream on a
validated FTL + flash-timing model and reports measured latency. The speedup
then comes from MQSim, not from `ndol.model.NANDModel` arithmetic.
"""
from .mqsim import MQSimTrace, MQSimResult, run_mqsim, kv_read_skip_traces

__all__ = ["MQSimTrace", "MQSimResult", "run_mqsim", "kv_read_skip_traces"]
