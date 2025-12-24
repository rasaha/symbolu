#!/usr/bin/env python3
"""
12D Migration Script for Formulas Data Files
=============================================

This script migrates the formulas/data JSON files from the old 10D
layer naming convention to the new 12D patent-exact sequence.

Old 10D Layers:
    O1_ACTING, O2_TAGGING, O3_FORMING, O4_THINKING, O5_DIRECTING,
    O6_REASONING, O7_PURPOSING, O8_META_OBSERVING, O9_UNIFYING, O10_ABSOLVING

New 12D Layers:
    O1_POTENTIAL, O2_IDENTITY, O3_EXECUTION, O4_STRUCTURE, O5_COGNITION,
    O6_AGENCY, O7_REASONING, O8_PURPOSE, O9_WITNESSES, O10_UNIFYING,
    O11_INTEGRATION, O12_ABSOLVING

Usage:
    python scripts/migrate_12d_formulas.py --dry-run  # Preview changes
    python scripts/migrate_12d_formulas.py            # Apply changes
"""

import json
import argparse
from pathlib import Path
from typing import Any

# Layer mapping: old_name -> new_name
# Note: This is a semantic mapping, not just renaming
LAYER_MAPPING = {
    "O1_ACTING": "O3_EXECUTION",        # Action/karma layer moved to position 3
    "O2_TAGGING": "O2_IDENTITY",        # Tagging/classification stays at position 2
    "O3_FORMING": "O4_STRUCTURE",       # Forming/embodiment moved to position 4
    "O4_THINKING": "O5_COGNITION",      # Thinking merged into cognition at position 5
    "O5_DIRECTING": "O6_AGENCY",        # Directing/control moved to position 6
    "O6_REASONING": "O7_REASONING",     # Reasoning moves to position 7
    "O7_PURPOSING": "O8_PURPOSE",       # Purpose/meaning moves to position 8
    "O8_META_OBSERVING": "O9_WITNESSES", # Meta-observation moves to position 9
    "O9_UNIFYING": "O10_UNIFYING",      # Unifying moves to position 10
    "O10_ABSOLVING": "O12_ABSOLVING",   # Absolving moves to position 12
}

# New layers that need to be added
NEW_LAYERS = ["O1_POTENTIAL", "O11_INTEGRATION"]

# Template entries for new layers
NEW_LAYER_TEMPLATES = {
    "O1_POTENTIAL": {
        "polarity": "neutral",
        "bridge_layer": {
            "description": "dormant capacity state",
            "flow": "upward to O2_IDENTITY"
        },
        "distortion": {
            "direction": "upward",
            "intensity": "low",
            "flow_mode": "nascent",
            "targets": ["O2_IDENTITY"]
        },
        "interaction": {
            "manifestation_positive": "latent potential ready for activation",
            "manifestation_negative": "stagnant dormancy without activation",
            "distortion_vector": "lateral",
            "sublimate_vector": "upward"
        }
    },
    "O11_INTEGRATION": {
        "polarity": "constructive",
        "bridge_layer": {
            "description": "consolidation and resolution state",
            "flow": "upward to O12_ABSOLVING"
        },
        "distortion": {
            "direction": "upward",
            "intensity": "moderate",
            "flow_mode": "consolidating",
            "targets": ["O12_ABSOLVING"]
        },
        "interaction": {
            "manifestation_positive": "parts come together in resolution",
            "manifestation_negative": "incomplete consolidation fragments",
            "distortion_vector": "lateral",
            "sublimate_vector": "upward"
        }
    }
}


def migrate_layer_references(obj: Any) -> Any:
    """Recursively migrate all layer name references in a JSON object."""
    if isinstance(obj, str):
        # Direct string replacement
        return LAYER_MAPPING.get(obj, obj)
    elif isinstance(obj, list):
        return [migrate_layer_references(item) for item in obj]
    elif isinstance(obj, dict):
        new_dict = {}
        for key, value in obj.items():
            # Migrate the key if it's a layer name
            new_key = LAYER_MAPPING.get(key, key)
            new_dict[new_key] = migrate_layer_references(value)
        return new_dict
    else:
        return obj


def add_new_layers_to_polarity_map(data: dict) -> dict:
    """Add new layer entries to the polarity map."""
    if "polarity_map" not in data:
        return data

    for varna, layers in data["polarity_map"].items():
        # Add new layers
        layers["O1_POTENTIAL"] = NEW_LAYER_TEMPLATES["O1_POTENTIAL"]["polarity"]
        layers["O11_INTEGRATION"] = NEW_LAYER_TEMPLATES["O11_INTEGRATION"]["polarity"]

    return data


def add_new_layers_to_bridge_map(data: dict) -> dict:
    """Add new layer entries to consonant bridge mappings."""
    if "consonants" not in data:
        return data

    for consonant, info in data["consonants"].items():
        if "layers" in info:
            layers = info["layers"]
            # Add new layers based on patterns
            layers["O1_POTENTIAL"] = "dormant activation threshold"
            layers["O11_INTEGRATION"] = "consolidation orientation"

    return data


def add_new_layers_to_distortion_map(data: dict) -> dict:
    """Add new layer entries to the distortion map."""
    if "distortion_map" not in data:
        return data

    for varna, layers in data["distortion_map"].items():
        # Add O1_POTENTIAL entry (links to O2_IDENTITY)
        if "O2_IDENTITY" in layers or "O3_EXECUTION" in layers:
            layers["O1_POTENTIAL"] = {
                "direction": "upward",
                "intensity": "low",
                "flow_mode": "nascent",
                "targets": ["O2_IDENTITY"]
            }

        # Add O11_INTEGRATION entry (links to O12_ABSOLVING)
        if "O12_ABSOLVING" in layers:
            layers["O11_INTEGRATION"] = {
                "direction": "upward",
                "intensity": "moderate",
                "flow_mode": "consolidating",
                "targets": ["O12_ABSOLVING"]
            }

    return data


def add_new_layers_to_interaction_map(data: dict) -> dict:
    """Add new layer entries to the varna interaction map."""
    if "interaction_map" not in data:
        return data

    for varna, layers in data["interaction_map"].items():
        # Get a template from an existing layer for pattern consistency
        template_layer = layers.get("O2_IDENTITY") or layers.get("O3_EXECUTION")

        if template_layer:
            # Add O1_POTENTIAL based on the varna's general pattern
            layers["O1_POTENTIAL"] = {
                "manifestation_positive": "latent potential ready for activation",
                "manifestation_negative": "dormant capacity without direction",
                "distortion_vector": template_layer.get("distortion_vector", "lateral"),
                "sublimate_vector": "upward"
            }

            # Add O11_INTEGRATION based on adjacency to O10 and O12
            template_10 = layers.get("O10_UNIFYING", {})
            layers["O11_INTEGRATION"] = {
                "manifestation_positive": "parts consolidated into coherent resolution",
                "manifestation_negative": "fragmented integration without completion",
                "distortion_vector": template_10.get("distortion_vector", "lateral"),
                "sublimate_vector": "upward"
            }

    return data


def migrate_file(filepath: Path, dry_run: bool = False) -> dict:
    """Migrate a single JSON file to 12D layer naming."""
    print(f"\nProcessing: {filepath.name}")

    with open(filepath, "r") as f:
        data = json.load(f)

    # Update version in meta
    if "meta" in data:
        old_version = data["meta"].get("version", "1.0")
        data["meta"]["version"] = "2.0"
        data["meta"]["migration_note"] = "Migrated from 10D to 12D layer naming (2024-12-24)"
        print(f"  Version: {old_version} -> 2.0")

    # Migrate all layer references
    data = migrate_layer_references(data)
    print("  Layer references migrated")

    # Add new layers based on file type
    filename = filepath.name

    if "polarity_map" in filename:
        data = add_new_layers_to_polarity_map(data)
        print("  Added O1_POTENTIAL and O11_INTEGRATION to polarity maps")

    if "bridge_map" in filename:
        data = add_new_layers_to_bridge_map(data)
        print("  Added O1_POTENTIAL and O11_INTEGRATION to bridge maps")

    if "distortion_map" in filename:
        data = add_new_layers_to_distortion_map(data)
        print("  Added O1_POTENTIAL and O11_INTEGRATION to distortion maps")

    if "layer_interaction" in filename:
        data = add_new_layers_to_interaction_map(data)
        print("  Added O1_POTENTIAL and O11_INTEGRATION to interaction maps")

    if not dry_run:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  Saved: {filepath}")
    else:
        print(f"  [DRY RUN] Would save: {filepath}")

    return data


def main():
    parser = argparse.ArgumentParser(
        description="Migrate formulas data files from 10D to 12D layer naming"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Migrate a specific file (default: all formulas/data files)"
    )
    args = parser.parse_args()

    # Find formulas data directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    formulas_data = project_root / "symbolu" / "formulas" / "data"

    if not formulas_data.exists():
        print(f"Error: Directory not found: {formulas_data}")
        return 1

    print("=" * 60)
    print("12D MIGRATION: Formulas Data Files")
    print("=" * 60)
    print(f"Source directory: {formulas_data}")
    print(f"Dry run: {args.dry_run}")

    # Get files to process
    if args.file:
        files = [formulas_data / args.file]
    else:
        # Skip ontological_layers_v1.json as it was already migrated
        files = [
            f for f in formulas_data.glob("*.json")
            if f.name != "ontological_layers_v1.json"
        ]

    print(f"\nFiles to process: {len(files)}")

    # Show layer mapping
    print("\nLayer Mapping (10D -> 12D):")
    print("-" * 40)
    for old, new in LAYER_MAPPING.items():
        print(f"  {old:20} -> {new}")
    print(f"\nNew layers: {', '.join(NEW_LAYERS)}")

    # Process files
    for filepath in sorted(files):
        if filepath.exists():
            migrate_file(filepath, dry_run=args.dry_run)
        else:
            print(f"\nWarning: File not found: {filepath}")

    print("\n" + "=" * 60)
    if args.dry_run:
        print("DRY RUN COMPLETE - No files were modified")
        print("Run without --dry-run to apply changes")
    else:
        print("MIGRATION COMPLETE")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
