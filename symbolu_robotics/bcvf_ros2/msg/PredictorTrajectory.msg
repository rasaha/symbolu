# PredictorTrajectory.msg — one predictor's trajectory output for one planning step.
#
# Topic convention: /bcvf/predictor/<name>/trajectory
#
# See ROS2_DDS_SBOM_DESIGN.md §3.1 for the full design rationale.
#
# Fields:
#   header           — std_msgs/Header — stamp + frame_id ("map" or "base_link")
#   predictor_name   — predictor identifier (e.g. "M1", "M2", "imu_odometry")
#   horizon          — H (number of timesteps in the trajectory)
#   num_rollouts     — K (1 for single-trajectory predictors; >1 for sample-based)
#   poses            — geometry_msgs/Pose2D[K * H] row-major (rollout, step)

std_msgs/Header header
string predictor_name
uint32 horizon
uint32 num_rollouts
geometry_msgs/Pose2D[] poses
