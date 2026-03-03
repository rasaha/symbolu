"""
Spatial-Causal Module Benchmarks (V10.11)

Tests spatial reasoning integrated with causal reasoning:
    1. Spatial state encoding
    2. Spatial relation prediction
    3. Physics causal edge computation
    4. Spatial interventions (move/rotate/place)
    5. Physics simulation
    6. Spatial counterfactual reasoning

CLI Usage::

    python train_hard_probes.py --test-spatial-causal
    python train_hard_probes.py --test-spatial-causal --scm-scenario all
"""

import time
import torch
import torch.nn as nn
from typing import Dict, Optional

from ..imports import SPATIAL_CAUSAL_AVAILABLE
if SPATIAL_CAUSAL_AVAILABLE:
    from symbolu.spatial_causal_module import (
        SpatialCausalConfig, SpatialCausalModule,
        SpatialCausalBenchmark, create_spatial_causal_module,
        create_test_world_with_scenario,
    )

# =============================================================================
# SPATIAL-CAUSAL MODULE BENCHMARKS (V10.11)
# =============================================================================

def run_spatial_causal_benchmarks(
    args,
    config,
    device: str = "cpu",
) -> Dict[str, any]:
    """
    Run Spatial-Causal Module benchmarks.

    Tests:
        1. Spatial state encoding
        2. Spatial relation prediction
        3. Physics causal edge computation
        4. Spatial interventions (move/rotate/place)
        5. Physics simulation
        6. Spatial counterfactual reasoning

    Args:
        args: CLI arguments
        config: Model config
        device: Device to run on

    Returns:
        Dictionary with benchmark results
    """
    print("\n" + "=" * 70)
    print("SPATIAL-CAUSAL MODULE BENCHMARK (V10.11)")
    print("=" * 70)

    if not SPATIAL_CAUSAL_AVAILABLE:
        print("\nSpatial-Causal Module not available. Skipping benchmarks.")
        return {"error": "Module not available"}

    results = {}

    # Get configuration from args
    hidden_dim = getattr(args, 'scm_hidden_dim', 256)
    max_objects = getattr(args, 'scm_max_objects', 64)
    num_heads = getattr(args, 'scm_num_heads', 8)
    gravity = getattr(args, 'scm_gravity', [0.0, -9.81, 0.0])
    simulation_dt = getattr(args, 'scm_simulation_dt', 0.01)
    simulation_steps = getattr(args, 'scm_simulation_steps', 100)
    propagation_radius = getattr(args, 'scm_propagation_radius', 2.0)
    contact_threshold = getattr(args, 'scm_contact_threshold', 0.1)
    scenario = getattr(args, 'scm_scenario', 'falling_ball')

    print(f"\nConfiguration:")
    print(f"  Hidden dim: {hidden_dim}")
    print(f"  Max objects: {max_objects}")
    print(f"  Gravity: {gravity}")
    print(f"  Simulation dt: {simulation_dt}")
    print(f"  Scenario: {scenario}")

    # Create config
    spatial_config = SpatialCausalConfig(
        hidden_dim=hidden_dim,
        max_objects=max_objects,
        num_heads=num_heads,
        gravity=tuple(gravity),
        simulation_dt=simulation_dt,
        max_simulation_steps=simulation_steps,
        propagation_radius=propagation_radius,
        contact_threshold=contact_threshold,
    )

    # Create module
    print("\nCreating Spatial-Causal Module...")
    module = SpatialCausalModule(spatial_config)
    module.to(device)

    # -------------------------------------------------------------------------
    # TEST 1: Spatial State Encoding
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Spatial State Encoding ---")

    # Create test world
    world = create_test_world_with_scenario(scenario)
    print(f"  Created world with {len(world.objects)} objects")
    for obj_id, obj in world.objects.items():
        print(f"    {obj_id}: pos={obj.position.tolist()}, scale={obj.scale.tolist()}")

    # Encode world
    import time
    start_time = time.time()
    encoding = module.encode_world(world)
    encode_time = (time.time() - start_time) * 1000

    results["encoding"] = {
        "shape": list(encoding.shape),
        "time_ms": encode_time,
        "num_objects": len(world.objects),
    }
    print(f"  Encoding shape: {encoding.shape}")
    print(f"  Encoding time: {encode_time:.3f}ms")

    # -------------------------------------------------------------------------
    # TEST 2: Spatial Relation Prediction
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Spatial Relation Prediction ---")

    start_time = time.time()
    relations = module.compute_relations(world)
    relation_time = (time.time() - start_time) * 1000

    results["relations"] = {
        "num_relations": len(relations),
        "time_ms": relation_time,
        "relation_types": {},
    }

    # Count relation types
    for rel in relations:
        rel_type = rel.relation.value
        if rel_type not in results["relations"]["relation_types"]:
            results["relations"]["relation_types"][rel_type] = 0
        results["relations"]["relation_types"][rel_type] += 1

    print(f"  Found {len(relations)} spatial relations")
    print(f"  Relation computation time: {relation_time:.3f}ms")
    print(f"  Relation types:")
    for rel_type, count in results["relations"]["relation_types"].items():
        print(f"    {rel_type}: {count}")

    # Show sample relations
    print(f"  Sample relations:")
    for rel in relations[:5]:
        print(f"    {rel.source_id} --[{rel.relation.value}]--> {rel.target_id} "
              f"(conf={rel.confidence:.2f}, dist={rel.distance:.3f})")

    # -------------------------------------------------------------------------
    # TEST 3: Physics Causal Edges
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Physics Causal Edge Computation ---")

    start_time = time.time()
    causal_edges = module.compute_causal_edges(world)
    causal_time = (time.time() - start_time) * 1000

    results["causal_edges"] = {
        "num_edges": len(causal_edges),
        "time_ms": causal_time,
        "edge_types": {},
    }

    # Count edge types
    for edge in causal_edges:
        edge_type = edge.physics_type.value
        if edge_type not in results["causal_edges"]["edge_types"]:
            results["causal_edges"]["edge_types"][edge_type] = 0
        results["causal_edges"]["edge_types"][edge_type] += 1

    print(f"  Found {len(causal_edges)} physics-causal edges")
    print(f"  Causal edge computation time: {causal_time:.3f}ms")
    print(f"  Edge types:")
    for edge_type, count in results["causal_edges"]["edge_types"].items():
        print(f"    {edge_type}: {count}")

    # -------------------------------------------------------------------------
    # TEST 4: Spatial Interventions
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Spatial Interventions ---")

    # Test MOVE intervention
    print("  Testing MOVE intervention...")
    move_intervention = SpatialIntervention(
        intervention_type=InterventionType.MOVE,
        obj_id=list(world.objects.keys())[0],
        value=torch.tensor([0.0, 1.0, 0.0]),
    )

    start_time = time.time()
    moved_world = module.intervene(world, move_intervention)
    move_time = (time.time() - start_time) * 1000

    obj_id = move_intervention.obj_id
    old_pos = world.objects[obj_id].position.tolist()
    new_pos = moved_world.objects[obj_id].position.tolist()

    print(f"    Object '{obj_id}' moved from {old_pos} to {new_pos}")
    print(f"    MOVE time: {move_time:.3f}ms")

    # Test ROTATE intervention
    print("  Testing ROTATE intervention...")
    rotate_intervention = SpatialIntervention(
        intervention_type=InterventionType.ROTATE,
        obj_id=obj_id,
        value=torch.tensor([0.707, 0.0, 0.707, 0.0]),  # 90 degree rotation
    )

    start_time = time.time()
    rotated_world = module.intervene(world, rotate_intervention)
    rotate_time = (time.time() - start_time) * 1000

    old_orient = world.objects[obj_id].orientation.tolist()
    new_orient = rotated_world.objects[obj_id].orientation.tolist()

    print(f"    Object '{obj_id}' rotated")
    print(f"    ROTATE time: {rotate_time:.3f}ms")

    # Test PLACE intervention (if there are at least 2 objects)
    if len(world.objects) >= 2:
        print("  Testing PLACE intervention...")
        obj_ids = list(world.objects.keys())
        place_intervention = SpatialIntervention(
            intervention_type=InterventionType.PLACE,
            obj_id=obj_ids[0],
            reference_id=obj_ids[1],
            relation=SpatialRelation.ON,
        )

        start_time = time.time()
        placed_world = module.intervene(world, place_intervention)
        place_time = (time.time() - start_time) * 1000

        print(f"    Placed '{obj_ids[0]}' ON '{obj_ids[1]}'")
        print(f"    PLACE time: {place_time:.3f}ms")
    else:
        place_time = 0.0

    results["interventions"] = {
        "move_time_ms": move_time,
        "rotate_time_ms": rotate_time,
        "place_time_ms": place_time,
    }

    # -------------------------------------------------------------------------
    # TEST 5: Physics Simulation
    # -------------------------------------------------------------------------
    print("\n--- TEST 5: Physics Simulation ---")

    # Create a world with a falling ball
    sim_world = create_test_world_with_scenario("falling_ball")
    print(f"  Simulating '{scenario}' scenario...")

    # Get initial state
    ball_id = None
    for obj_id in sim_world.objects:
        if "ball" in obj_id.lower():
            ball_id = obj_id
            break
    if ball_id is None:
        ball_id = list(sim_world.objects.keys())[0]

    initial_pos = sim_world.objects[ball_id].position.clone()
    print(f"  Initial position of '{ball_id}': {initial_pos.tolist()}")

    # Run simulation
    start_time = time.time()
    trajectory = module.simulate(sim_world, steps=50)
    sim_time = (time.time() - start_time) * 1000

    final_pos = trajectory[-1].objects[ball_id].position
    print(f"  Final position after 50 steps: {final_pos.tolist()}")
    print(f"  Simulation time: {sim_time:.3f}ms")

    # Analyze trajectory
    positions = [t.objects[ball_id].position.tolist() for t in trajectory]
    velocities = [t.objects[ball_id].velocity.tolist() for t in trajectory]

    # Check if fell (y decreased significantly)
    fell = final_pos[1].item() < initial_pos[1].item() - 0.5

    results["simulation"] = {
        "num_steps": len(trajectory),
        "time_ms": sim_time,
        "initial_pos": initial_pos.tolist(),
        "final_pos": final_pos.tolist(),
        "fell": fell,
        "per_step_ms": sim_time / len(trajectory),
    }

    print(f"  Object fell: {'YES' if fell else 'NO'}")
    print(f"  Per-step time: {results['simulation']['per_step_ms']:.3f}ms")

    # -------------------------------------------------------------------------
    # TEST 6: Spatial Counterfactual Reasoning
    # -------------------------------------------------------------------------
    print("\n--- TEST 6: Spatial Counterfactual Reasoning ---")

    # Create counterfactual: "What if the ball was in the center?"
    cf_world = create_test_world_with_scenario("falling_ball")

    # Ball starts near edge with velocity
    cf_intervention = SpatialIntervention(
        intervention_type=InterventionType.MOVE,
        obj_id=ball_id,
        value=torch.tensor([0.0, 0.65, 0.0]),  # Move to center
    )

    print(f"  Question: 'What if {ball_id} was at the center instead of the edge?'")
    print(f"  Intervention: do(position({ball_id}) = [0.0, 0.65, 0.0])")

    start_time = time.time()
    cf_result = module.counterfactual(cf_world, cf_intervention, steps=50)
    cf_time = (time.time() - start_time) * 1000

    factual_final = cf_result["factual_final"].objects[ball_id].position
    cf_final = cf_result["counterfactual_final"].objects[ball_id].position

    print(f"\n  Factual outcome:")
    print(f"    Final position: {factual_final.tolist()}")

    print(f"\n  Counterfactual outcome:")
    print(f"    Final position: {cf_final.tolist()}")

    print(f"\n  Outcome difference:")
    for key, value in cf_result["outcome_difference"].items():
        print(f"    {key}: {value}")

    print(f"\n  Counterfactual reasoning time: {cf_time:.3f}ms")

    results["counterfactual"] = {
        "time_ms": cf_time,
        "factual_final": factual_final.tolist(),
        "counterfactual_final": cf_final.tolist(),
        "outcome_difference": cf_result["outcome_difference"],
    }

    # -------------------------------------------------------------------------
    # TEST 7: Forward Pass Integration
    # -------------------------------------------------------------------------
    print("\n--- TEST 7: Forward Pass Integration ---")

    batch_size = 2
    seq_len = 10

    hidden_states = torch.randn(batch_size, seq_len, hidden_dim).to(device)

    start_time = time.time()
    output, state = module(hidden_states, world=world)
    forward_time = (time.time() - start_time) * 1000

    results["forward_pass"] = {
        "input_shape": [batch_size, seq_len, hidden_dim],
        "output_shape": list(output.shape),
        "has_state": state is not None,
        "time_ms": forward_time,
    }

    print(f"  Input shape: {[batch_size, seq_len, hidden_dim]}")
    print(f"  Output shape: {list(output.shape)}")
    print(f"  State computed: {state is not None}")
    print(f"  Forward time: {forward_time:.3f}ms")

    if state is not None:
        print(f"  Spatial embedding shape: {state.spatial_embedding.shape}")
        print(f"  Relation matrix shape: {state.relation_matrix.shape}")
        print(f"  Physics causal matrix shape: {state.physics_causal_matrix.shape}")

    # -------------------------------------------------------------------------
    # TEST 8: Multiple Scenarios (if --scm-scenario=all)
    # -------------------------------------------------------------------------
    if scenario == "all":
        print("\n--- TEST 8: Multiple Scenarios ---")

        scenarios = ["falling_ball", "collision", "domino", "stacking"]
        results["scenarios"] = {}

        for sc in scenarios:
            print(f"\n  Testing scenario: {sc}")
            sc_world = create_test_world_with_scenario(sc)
            print(f"    Objects: {list(sc_world.objects.keys())}")

            # Quick simulation
            sc_trajectory = module.simulate(sc_world, steps=30)
            print(f"    Simulated 30 steps")

            # Get first object's final position
            first_obj = list(sc_world.objects.keys())[0]
            final_pos = sc_trajectory[-1].objects[first_obj].position

            results["scenarios"][sc] = {
                "num_objects": len(sc_world.objects),
                "final_pos": final_pos.tolist(),
            }
            print(f"    {first_obj} final position: {final_pos.tolist()}")

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("SPATIAL-CAUSAL MODULE BENCHMARK SUMMARY")
    print("=" * 70)

    print(f"""
  Spatial State Tracking:
    - Objects encoded: {results['encoding']['num_objects']}
    - Encoding time: {results['encoding']['time_ms']:.3f}ms

  Spatial Relations:
    - Relations found: {results['relations']['num_relations']}
    - Relation types: {len(results['relations']['relation_types'])}

  Physics-Causal Edges:
    - Causal edges found: {results['causal_edges']['num_edges']}
    - Edge types: {len(results['causal_edges']['edge_types'])}

  Spatial Interventions:
    - MOVE: {results['interventions']['move_time_ms']:.3f}ms
    - ROTATE: {results['interventions']['rotate_time_ms']:.3f}ms
    - PLACE: {results['interventions']['place_time_ms']:.3f}ms

  Physics Simulation:
    - Steps simulated: {results['simulation']['num_steps']}
    - Total time: {results['simulation']['time_ms']:.3f}ms
    - Per-step: {results['simulation']['per_step_ms']:.3f}ms

  Counterfactual Reasoning:
    - Time: {results['counterfactual']['time_ms']:.3f}ms
    - Outcome changed: {results['counterfactual']['outcome_difference'].get('position_distance', 0):.3f}

  Capabilities Enabled:
    - Spatial queries: "Is X above Y?"
    - Physics prediction: "What happens if I push X?"
    - Spatial counterfactuals: "Would X have fallen if placed elsewhere?"
    - Physics-grounded causality: Spatial configuration → Effect
""")

    return results


def run_spatial_causal_benchmark_integration(args, config):
    """
    Integration entry point for Spatial-Causal Module benchmarks.

    Called from main() when --test-spatial-causal is specified.
    """
    print("\n" + "=" * 70)
    print("SPATIAL-CAUSAL MODULE BENCHMARK: Integration Mode")
    print("=" * 70)

    results = run_spatial_causal_benchmarks(args, config, config.device)

    if "error" in results:
        print(f"\nBenchmark failed: {results['error']}")
        return

    # Print CLI usage
    print("\n" + "-" * 70)
    print("CLI USAGE:")
    print("-" * 70)
    print("""
  # Run Spatial-Causal Module benchmarks
  python train_hard_probes.py --test-spatial-causal

  # Custom configuration
  python train_hard_probes.py --test-spatial-causal \\
      --scm-hidden-dim 512 --scm-max-objects 128

  # Test specific scenario
  python train_hard_probes.py --test-spatial-causal --scm-scenario collision

  # Test all scenarios
  python train_hard_probes.py --test-spatial-causal --scm-scenario all

  # Run with Causal World Model
  python train_hard_probes.py --test-spatial-causal --test-causal-world-model
""")

    return results


# =============================================================================
# REAL LANGUAGE MODE: WikiText Dataset and LM Training
# =============================================================================
