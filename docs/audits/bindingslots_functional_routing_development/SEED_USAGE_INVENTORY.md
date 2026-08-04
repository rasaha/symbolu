# Seed usage inventory

| set | seeds | role |
|---|---|---|
| used (frozen + PR #1300/#1319/#1324) | 0–17 | prior BindingSlots training |
| **Stage-1 (this phase)** | **18, 19, 20, 21, 22** | fresh single-intervention screen |
| Stage-2 reserved | 23, 24, 25, 26, 27 | deferred development holdout |
| independent-confirmation reserved | 28, 29, 30, 31, 32 | deferred confirmation |

**Selection rule:** next consecutive unused BindingSlots training seeds after the highest used (17),
outcome-independent. **Contamination check:** a repo-wide search finds none of 18–32 as a BindingSlots
model-init/training seed, nor in any five-seed / stabilization / confirmatory result artifact. The
constants 123/777/4321 are evaluation-RNG seeds, not training seeds.

**Replacement policy:** outcome-based replacement is forbidden; an infrastructure-only failure uses the
next unused integer chosen without inspecting quality; restarts retain the same seed and configuration.
