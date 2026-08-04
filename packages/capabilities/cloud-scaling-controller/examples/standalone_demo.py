"""Standalone demo: no monorepo, no network, no credentials.

Run: python standalone_demo.py   (after: pip install ugence-cloud-scaling-controller)
"""
from ugence_cloud_scaling_controller import CloudScalingController, ScalingObservation

ctrl = CloudScalingController()
obs = ScalingObservation(
    metrics={"cpu": 0.92, "memory": 0.88, "latency_p99": 0.81,
             "error_rate": 0.2, "queue_depth": 0.7},
    current_replicas=4,
    phase="peak",
    correlation_id="example-001",
)
rec = ctrl.recommend(obs)
print(rec.to_json(indent=2))
assert rec.advisory_only and not rec.actuation_performed
