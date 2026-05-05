# ConsensusOutput.msg — BCVF trust-shaping output + safety state for one planning step.
#
# Topic: /bcvf/consensus
#
# Published by BCVFNode at publish_rate_hz (default 100 Hz). One message
# per planning step. See ROS2_DDS_SBOM_DESIGN.md §3.2 for the full design
# rationale.
#
# Fields:
#   header                     — std_msgs/Header — stamp + frame_id
#   predictor_names            — length M, ordered same as trust_weights second axis
#   trust_weights              — length K * M, row-major (rollout, predictor)
#   num_rollouts               — K
#   bcvf_total                 — length K, diagnostic (per-rollout BCVF cost)
#   ema_mean                   — length M, may be empty if EMA disabled
#   ema_std                    — length M, may be empty if EMA disabled
#   deadband_active_count      — uint32 K-side count
#   is_excluded                — length M (uint8 0/1), may be empty if exclusion off
#   safety_state               — NORMAL | DEGRADED | FAULT | FAILSAFE
#   safety_state_asil_class    — 0 (N/A), 2 (ASIL-B), 4 (ASIL-D)

std_msgs/Header header
string[] predictor_names
float64[] trust_weights
uint32 num_rollouts
float64[] bcvf_total
float64[] ema_mean
float64[] ema_std
uint32 deadband_active_count
uint8[] is_excluded
string safety_state
uint8 safety_state_asil_class
