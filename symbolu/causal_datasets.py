#!/usr/bin/env python3
"""
Causal Datasets for Phase-Quad Training
=======================================

Provides datasets with causal structure for training and evaluating
the Causal World Model:

1. COPA (Choice of Plausible Alternatives)
   - Causal reasoning benchmark
   - Binary choice between cause/effect alternatives
   - Tests commonsense causal understanding

2. e-CARE (Explainable CAusal REasoning)
   - Causal reasoning with explanations
   - Conceptual explanations for causal relations
   - Tests explanation generation

3. Synthetic SCM (Structural Causal Models)
   - Programmatically generated causal graphs
   - Known ground-truth for validation
   - Configurable complexity and structure

Author: Claude (Architecture Implementation)
Date: February 2026
Version: 1.0
"""

from __future__ import annotations

import json
import math
import os
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

import torch
from torch import Tensor
from torch.utils.data import Dataset, IterableDataset


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class CausalDatasetConfig:
    """Configuration for causal datasets."""
    # General
    max_seq_len: int = 256
    seed: int = 42
    cache_dir: str = "./data/causal_cache"

    # COPA
    copa_split: str = "train"  # train, validation, test

    # e-CARE
    ecare_split: str = "train"
    ecare_include_explanations: bool = True

    # Synthetic SCM
    scm_num_samples: int = 10000
    scm_num_variables: int = 10
    scm_edge_probability: float = 0.3
    scm_noise_std: float = 0.1
    scm_intervention_prob: float = 0.2
    scm_include_counterfactuals: bool = True


class CausalRelationType(Enum):
    """Types of causal relations."""
    CAUSE = "cause"
    EFFECT = "effect"
    ENABLES = "enables"
    PREVENTS = "prevents"
    NO_RELATION = "no_relation"


# =============================================================================
# BASE CLASSES
# =============================================================================


@dataclass
class CausalExample:
    """
    A single causal reasoning example.

    Attributes:
        premise: The context/premise text
        hypothesis: The hypothesis to evaluate (or question)
        alternatives: List of alternative answers (for multiple choice)
        label: Correct answer index or label
        relation_type: Type of causal relation being tested
        explanation: Optional explanation of the causal relationship
        causal_graph: Optional explicit causal graph
        intervention: Optional intervention information
        counterfactual: Optional counterfactual information
    """
    premise: str
    hypothesis: str
    alternatives: List[str] = field(default_factory=list)
    label: int = 0
    relation_type: CausalRelationType = CausalRelationType.CAUSE
    explanation: Optional[str] = None
    causal_graph: Optional[Dict[str, List[str]]] = None
    intervention: Optional[Dict[str, Any]] = None
    counterfactual: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "premise": self.premise,
            "hypothesis": self.hypothesis,
            "alternatives": self.alternatives,
            "label": self.label,
            "relation_type": self.relation_type.value,
            "explanation": self.explanation,
            "causal_graph": self.causal_graph,
            "intervention": self.intervention,
            "counterfactual": self.counterfactual,
        }


class CausalDataset(Dataset, ABC):
    """Abstract base class for causal datasets."""

    @abstractmethod
    def __len__(self) -> int:
        pass

    @abstractmethod
    def __getitem__(self, idx: int) -> CausalExample:
        pass

    @abstractmethod
    def get_causal_graph(self, idx: int) -> Optional[Dict[str, List[str]]]:
        """Get the causal graph for an example if available."""
        pass


# =============================================================================
# COPA DATASET
# =============================================================================


class COPADataset(CausalDataset):
    """
    COPA (Choice of Plausible Alternatives) Dataset.

    A causal reasoning benchmark where the model must choose between
    two alternatives that are either the cause or effect of a premise.

    Example:
        Premise: "The man broke his toe."
        Question: "What was the CAUSE of this?"
        Alternative 1: "He got a__(splinter." (incorrect)
        Alternative 2: "He dropped a__(hammer on his foot." (correct)
        Label: 1

    Source: https://people.ict.usc.edu/~gordon/copa.html
    HuggingFace: super_glue/copa
    """

    def __init__(
        self,
        split: str = "train",
        cache_dir: str = "./data/causal_cache",
        max_samples: Optional[int] = None,
    ):
        self.split = split
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_samples = max_samples

        self.examples: List[CausalExample] = []
        self._load_data()

    def _load_data(self):
        """Load COPA data from HuggingFace or cache."""
        cache_file = self.cache_dir / f"copa_{self.split}.json"

        if cache_file.exists():
            print(f"  Loading COPA {self.split} from cache...")
            with open(cache_file, "r") as f:
                data = json.load(f)
            self._parse_cached(data)
        else:
            print(f"  Downloading COPA {self.split} from HuggingFace...")
            self._download_and_parse()
            self._save_cache(cache_file)

    def _download_and_parse(self):
        """Download from HuggingFace and parse."""
        try:
            from datasets import load_dataset

            # COPA is part of SuperGLUE
            dataset = load_dataset("super_glue", "copa", split=self.split)

            for item in dataset:
                relation_type = (
                    CausalRelationType.CAUSE
                    if item["question"] == "cause"
                    else CausalRelationType.EFFECT
                )

                example = CausalExample(
                    premise=item["premise"],
                    hypothesis=f"What was the {item['question']}?",
                    alternatives=[item["choice1"], item["choice2"]],
                    label=item["label"],
                    relation_type=relation_type,
                    explanation=None,
                    causal_graph=self._infer_causal_graph(
                        item["premise"],
                        [item["choice1"], item["choice2"]],
                        item["label"],
                        relation_type,
                    ),
                )
                self.examples.append(example)

                if self.max_samples and len(self.examples) >= self.max_samples:
                    break

        except ImportError:
            print("  Warning: 'datasets' not installed. Using synthetic COPA data.")
            self._generate_synthetic_copa()
        except Exception as e:
            print(f"  Warning: Could not load COPA: {e}. Using synthetic data.")
            self._generate_synthetic_copa()

    def _generate_synthetic_copa(self):
        """Generate synthetic COPA-like examples."""
        synthetic_examples = [
            # Cause examples
            {
                "premise": "The man broke his toe.",
                "question": "cause",
                "choice1": "He got a splinter.",
                "choice2": "He dropped a hammer on his foot.",
                "label": 1,
            },
            {
                "premise": "The woman felt exhausted.",
                "question": "cause",
                "choice1": "She had been working all night.",
                "choice2": "She took a long nap.",
                "label": 0,
            },
            {
                "premise": "The plant died.",
                "question": "cause",
                "choice1": "It was watered too much.",
                "choice2": "It grew new leaves.",
                "label": 0,
            },
            {
                "premise": "The roads were icy.",
                "question": "cause",
                "choice1": "The temperature dropped below freezing.",
                "choice2": "Cars drove slowly.",
                "label": 0,
            },
            {
                "premise": "The company went bankrupt.",
                "question": "cause",
                "choice1": "It hired more employees.",
                "choice2": "Its sales declined sharply.",
                "label": 1,
            },
            # Effect examples
            {
                "premise": "It started to rain.",
                "question": "effect",
                "choice1": "People opened their umbrellas.",
                "choice2": "The sun came out.",
                "label": 0,
            },
            {
                "premise": "The child ate too much candy.",
                "question": "effect",
                "choice1": "She got a stomachache.",
                "choice2": "She lost her appetite.",
                "label": 0,
            },
            {
                "premise": "The alarm went off.",
                "question": "effect",
                "choice1": "The man woke up.",
                "choice2": "The man fell asleep.",
                "label": 0,
            },
            {
                "premise": "The politician made a controversial statement.",
                "question": "effect",
                "choice1": "The media ignored him.",
                "choice2": "There was public outrage.",
                "label": 1,
            },
            {
                "premise": "The scientist made a breakthrough discovery.",
                "question": "effect",
                "choice1": "She received recognition.",
                "choice2": "She changed careers.",
                "label": 0,
            },
        ]

        # Duplicate to create more samples
        while len(self.examples) < (self.max_samples or 100):
            for item in synthetic_examples:
                relation_type = (
                    CausalRelationType.CAUSE
                    if item["question"] == "cause"
                    else CausalRelationType.EFFECT
                )

                example = CausalExample(
                    premise=item["premise"],
                    hypothesis=f"What was the {item['question']}?",
                    alternatives=[item["choice1"], item["choice2"]],
                    label=item["label"],
                    relation_type=relation_type,
                    causal_graph=self._infer_causal_graph(
                        item["premise"],
                        [item["choice1"], item["choice2"]],
                        item["label"],
                        relation_type,
                    ),
                )
                self.examples.append(example)

                if self.max_samples and len(self.examples) >= self.max_samples:
                    break

            if self.max_samples and len(self.examples) >= self.max_samples:
                break

    def _infer_causal_graph(
        self,
        premise: str,
        alternatives: List[str],
        label: int,
        relation_type: CausalRelationType,
    ) -> Dict[str, List[str]]:
        """Infer a simple causal graph from the example."""
        correct_alt = alternatives[label]

        if relation_type == CausalRelationType.CAUSE:
            # correct_alt causes premise
            return {
                "nodes": [correct_alt, premise],
                "edges": [(correct_alt, premise)],
            }
        else:
            # premise causes correct_alt
            return {
                "nodes": [premise, correct_alt],
                "edges": [(premise, correct_alt)],
            }

    def _parse_cached(self, data: List[Dict]):
        """Parse cached data."""
        for item in data:
            self.examples.append(CausalExample(
                premise=item["premise"],
                hypothesis=item["hypothesis"],
                alternatives=item["alternatives"],
                label=item["label"],
                relation_type=CausalRelationType(item["relation_type"]),
                explanation=item.get("explanation"),
                causal_graph=item.get("causal_graph"),
            ))

            if self.max_samples and len(self.examples) >= self.max_samples:
                break

    def _save_cache(self, cache_file: Path):
        """Save to cache."""
        data = [ex.to_dict() for ex in self.examples]
        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> CausalExample:
        return self.examples[idx]

    def get_causal_graph(self, idx: int) -> Optional[Dict[str, List[str]]]:
        return self.examples[idx].causal_graph


# =============================================================================
# e-CARE DATASET
# =============================================================================


class ECareDataset(CausalDataset):
    """
    e-CARE (Explainable CAusal REasoning) Dataset.

    A dataset for causal reasoning with conceptual explanations.
    Each example includes a causal question and an explanation of
    the underlying causal mechanism.

    Example:
        Premise: "Tom studied hard for the exam."
        Hypothesis: "Tom passed the exam."
        Label: 1 (correct causal relation)
        Explanation: "Studying improves knowledge, which leads to better exam performance."

    Source: https://github.com/Waste-Wood/e-CARE
    """

    def __init__(
        self,
        split: str = "train",
        cache_dir: str = "./data/causal_cache",
        include_explanations: bool = True,
        max_samples: Optional[int] = None,
    ):
        self.split = split
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.include_explanations = include_explanations
        self.max_samples = max_samples

        self.examples: List[CausalExample] = []
        self._load_data()

    def _load_data(self):
        """Load e-CARE data."""
        cache_file = self.cache_dir / f"ecare_{self.split}.json"

        if cache_file.exists():
            print(f"  Loading e-CARE {self.split} from cache...")
            with open(cache_file, "r") as f:
                data = json.load(f)
            self._parse_cached(data)
        else:
            print(f"  Generating e-CARE-style {self.split} data...")
            self._generate_ecare_data()
            self._save_cache(cache_file)

    def _generate_ecare_data(self):
        """Generate e-CARE-style examples with explanations."""
        # Template-based generation with causal explanations
        causal_templates = [
            # Physical causation
            {
                "premise": "The glass fell off the table.",
                "hypothesis": "The glass shattered.",
                "label": 1,
                "explanation": "When fragile objects like glass fall from a height, the impact force exceeds their structural integrity, causing them to break.",
                "causal_chain": ["fall", "impact", "shatter"],
            },
            {
                "premise": "Water was heated to 100°C.",
                "hypothesis": "The water boiled.",
                "label": 1,
                "explanation": "Water boils at 100°C at standard atmospheric pressure because molecules gain enough energy to escape the liquid phase.",
                "causal_chain": ["heat", "energy_increase", "phase_change", "boiling"],
            },
            {
                "premise": "The car ran out of fuel.",
                "hypothesis": "The car stopped running.",
                "label": 1,
                "explanation": "Internal combustion engines require fuel to produce the explosions that drive the pistons. Without fuel, no combustion occurs.",
                "causal_chain": ["no_fuel", "no_combustion", "engine_stops"],
            },
            # Biological causation
            {
                "premise": "The patient took antibiotics.",
                "hypothesis": "The bacterial infection cleared.",
                "label": 1,
                "explanation": "Antibiotics kill bacteria or inhibit their growth, allowing the immune system to eliminate the remaining infection.",
                "causal_chain": ["antibiotics", "bacteria_killed", "infection_cleared"],
            },
            {
                "premise": "The plant was kept in darkness.",
                "hypothesis": "The plant could not photosynthesize.",
                "label": 1,
                "explanation": "Photosynthesis requires light energy to convert CO2 and water into glucose. Without light, this process cannot occur.",
                "causal_chain": ["no_light", "no_photosynthesis", "no_glucose"],
            },
            # Social/psychological causation
            {
                "premise": "The company raised its prices significantly.",
                "hypothesis": "Customer demand decreased.",
                "label": 1,
                "explanation": "According to the law of demand, higher prices reduce the quantity demanded as consumers seek alternatives or reduce consumption.",
                "causal_chain": ["price_increase", "value_perception_drop", "demand_decrease"],
            },
            {
                "premise": "The student received praise for her work.",
                "hypothesis": "The student felt motivated.",
                "label": 1,
                "explanation": "Positive reinforcement through praise activates reward centers in the brain, increasing motivation and engagement.",
                "causal_chain": ["praise", "reward_signal", "motivation_increase"],
            },
            # Negative examples (no causal relation)
            {
                "premise": "It rained yesterday.",
                "hypothesis": "The stock market went up.",
                "label": 0,
                "explanation": "Rain and stock market performance are generally independent events with no direct causal mechanism connecting them.",
                "causal_chain": [],
            },
            {
                "premise": "The cat sat on the mat.",
                "hypothesis": "The sun rose in the east.",
                "label": 0,
                "explanation": "The cat's position and the sun's movement are independent events. The sun rises due to Earth's rotation, not animal behavior.",
                "causal_chain": [],
            },
            {
                "premise": "John wore a blue shirt.",
                "hypothesis": "The train arrived on time.",
                "label": 0,
                "explanation": "A person's clothing choice has no causal influence on train schedules, which depend on operational factors.",
                "causal_chain": [],
            },
            # Counterfactual examples
            {
                "premise": "If the bridge had been inspected, the collapse would not have occurred.",
                "hypothesis": "The bridge collapsed due to lack of inspection.",
                "label": 1,
                "explanation": "Regular inspection identifies structural weaknesses before they become critical. The counterfactual implies inspection would have prevented the collapse.",
                "causal_chain": ["no_inspection", "undetected_weakness", "collapse"],
                "counterfactual": {
                    "antecedent": "bridge_inspected",
                    "consequent": "no_collapse",
                },
            },
            {
                "premise": "Had the driver not been texting, the accident would have been avoided.",
                "hypothesis": "Texting while driving caused the accident.",
                "label": 1,
                "explanation": "Texting diverts attention from the road, reducing reaction time. The counterfactual establishes texting as the cause.",
                "causal_chain": ["texting", "distraction", "delayed_reaction", "accident"],
                "counterfactual": {
                    "antecedent": "no_texting",
                    "consequent": "no_accident",
                },
            },
        ]

        # Expand with variations
        variations = []
        for template in causal_templates:
            # Original
            variations.append(template)

            # Swap premise/hypothesis for effect->cause
            if template["label"] == 1:
                swapped = {
                    "premise": template["hypothesis"],
                    "hypothesis": template["premise"],
                    "label": 1,
                    "explanation": f"Reverse reasoning: {template['explanation']}",
                    "causal_chain": list(reversed(template["causal_chain"])),
                }
                if "counterfactual" in template:
                    swapped["counterfactual"] = template["counterfactual"]
                variations.append(swapped)

        # Create examples
        for item in variations:
            causal_graph = {
                "nodes": item["causal_chain"],
                "edges": [(item["causal_chain"][i], item["causal_chain"][i+1])
                         for i in range(len(item["causal_chain"])-1)]
            } if item["causal_chain"] else None

            example = CausalExample(
                premise=item["premise"],
                hypothesis=item["hypothesis"],
                alternatives=[],
                label=item["label"],
                relation_type=CausalRelationType.CAUSE if item["label"] == 1 else CausalRelationType.NO_RELATION,
                explanation=item["explanation"] if self.include_explanations else None,
                causal_graph=causal_graph,
                counterfactual=item.get("counterfactual"),
            )
            self.examples.append(example)

        # Duplicate to reach max_samples
        if self.max_samples:
            original_len = len(self.examples)
            while len(self.examples) < self.max_samples:
                self.examples.append(self.examples[len(self.examples) % original_len])

    def _parse_cached(self, data: List[Dict]):
        """Parse cached data."""
        for item in data:
            self.examples.append(CausalExample(
                premise=item["premise"],
                hypothesis=item["hypothesis"],
                alternatives=item.get("alternatives", []),
                label=item["label"],
                relation_type=CausalRelationType(item["relation_type"]),
                explanation=item.get("explanation") if self.include_explanations else None,
                causal_graph=item.get("causal_graph"),
                counterfactual=item.get("counterfactual"),
            ))

            if self.max_samples and len(self.examples) >= self.max_samples:
                break

    def _save_cache(self, cache_file: Path):
        """Save to cache."""
        data = [ex.to_dict() for ex in self.examples]
        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> CausalExample:
        return self.examples[idx]

    def get_causal_graph(self, idx: int) -> Optional[Dict[str, List[str]]]:
        return self.examples[idx].causal_graph


# =============================================================================
# SYNTHETIC SCM DATASET
# =============================================================================


@dataclass
class SCMVariable:
    """A variable in a Structural Causal Model."""
    name: str
    parents: List[str] = field(default_factory=list)
    coefficients: Dict[str, float] = field(default_factory=dict)
    noise_std: float = 0.1
    value: Optional[float] = None


@dataclass
class SCMGraph:
    """A Structural Causal Model graph."""
    variables: Dict[str, SCMVariable]
    adjacency: Dict[str, List[str]]  # parent -> children

    def get_topological_order(self) -> List[str]:
        """Get variables in topological order (parents before children)."""
        visited = set()
        order = []

        def dfs(var: str):
            if var in visited:
                return
            visited.add(var)
            for parent in self.variables[var].parents:
                dfs(parent)
            order.append(var)

        for var in self.variables:
            dfs(var)

        return order

    def sample(self, interventions: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        """Sample from the SCM, optionally with interventions."""
        values = {}

        for var_name in self.get_topological_order():
            var = self.variables[var_name]

            # Check for intervention
            if interventions and var_name in interventions:
                values[var_name] = interventions[var_name]
                continue

            # Compute based on parents
            value = 0.0
            for parent in var.parents:
                coef = var.coefficients.get(parent, 1.0)
                value += coef * values[parent]

            # Add noise
            noise = random.gauss(0, var.noise_std)
            value += noise

            # Clamp to [0, 1] for interpretability
            values[var_name] = max(0.0, min(1.0, value))

        return values

    def counterfactual(
        self,
        factual: Dict[str, float],
        intervention: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Compute counterfactual: given factual observation, what would happen
        under intervention?

        Uses the three-step process:
        1. Abduction: Infer noise terms from factual
        2. Action: Apply intervention
        3. Prediction: Compute counterfactual values
        """
        # Step 1: Abduction - infer noise terms
        noise_terms = {}
        for var_name in self.get_topological_order():
            var = self.variables[var_name]

            # Compute deterministic part
            deterministic = 0.0
            for parent in var.parents:
                coef = var.coefficients.get(parent, 1.0)
                deterministic += coef * factual[parent]

            # Noise = observed - deterministic
            noise_terms[var_name] = factual[var_name] - deterministic

        # Step 2 & 3: Action and Prediction
        cf_values = {}
        for var_name in self.get_topological_order():
            var = self.variables[var_name]

            # Check for intervention
            if var_name in intervention:
                cf_values[var_name] = intervention[var_name]
                continue

            # Compute based on (possibly counterfactual) parent values
            value = 0.0
            for parent in var.parents:
                coef = var.coefficients.get(parent, 1.0)
                parent_val = cf_values.get(parent, factual[parent])
                value += coef * parent_val

            # Add original noise (abducted)
            value += noise_terms[var_name]

            cf_values[var_name] = max(0.0, min(1.0, value))

        return cf_values


class SyntheticSCMDataset(CausalDataset):
    """
    Synthetic Structural Causal Model Dataset.

    Generates data from random SCMs with known ground-truth causal structure.
    Useful for validating causal discovery and inference algorithms.

    Features:
    - Random DAG generation
    - Linear SCM with configurable noise
    - Interventional data generation
    - Counterfactual data generation
    - Ground-truth causal graphs
    """

    def __init__(
        self,
        num_samples: int = 10000,
        num_variables: int = 10,
        edge_probability: float = 0.3,
        noise_std: float = 0.1,
        intervention_prob: float = 0.2,
        include_counterfactuals: bool = True,
        seed: int = 42,
        cache_dir: str = "./data/causal_cache",
    ):
        self.num_samples = num_samples
        self.num_variables = num_variables
        self.edge_probability = edge_probability
        self.noise_std = noise_std
        self.intervention_prob = intervention_prob
        self.include_counterfactuals = include_counterfactuals
        self.seed = seed
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        random.seed(seed)

        self.scm: Optional[SCMGraph] = None
        self.examples: List[CausalExample] = []
        self.observational_data: List[Dict[str, float]] = []
        self.interventional_data: List[Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]] = []
        self.counterfactual_data: List[Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]] = []

        self._generate_scm()
        self._generate_data()

    def _generate_scm(self):
        """Generate a random SCM."""
        print(f"  Generating SCM with {self.num_variables} variables...")

        # Create variable names
        var_names = [f"X{i}" for i in range(self.num_variables)]

        # Generate random DAG using topological ordering trick
        variables = {}
        adjacency = {name: [] for name in var_names}

        for i, var_name in enumerate(var_names):
            parents = []
            coefficients = {}

            # Only earlier variables can be parents (ensures DAG)
            for j in range(i):
                if random.random() < self.edge_probability:
                    parent_name = var_names[j]
                    parents.append(parent_name)
                    # Random coefficient in [-1, 1]
                    coefficients[parent_name] = random.uniform(-1, 1)
                    adjacency[parent_name].append(var_name)

            variables[var_name] = SCMVariable(
                name=var_name,
                parents=parents,
                coefficients=coefficients,
                noise_std=self.noise_std,
            )

        self.scm = SCMGraph(variables=variables, adjacency=adjacency)

        # Count edges
        num_edges = sum(len(children) for children in adjacency.values())
        print(f"    Variables: {self.num_variables}, Edges: {num_edges}")

    def _generate_data(self):
        """Generate observational, interventional, and counterfactual data."""
        print(f"  Generating {self.num_samples} samples...")

        var_names = list(self.scm.variables.keys())

        for i in range(self.num_samples):
            # Observational sample
            obs = self.scm.sample()
            self.observational_data.append(obs)

            # Create text description
            premise_parts = []
            for var, val in obs.items():
                level = "high" if val > 0.5 else "low"
                premise_parts.append(f"{var}={level}")
            premise = f"Observed: {', '.join(premise_parts[:3])}"

            # Random intervention with some probability
            if random.random() < self.intervention_prob:
                # Pick random variable to intervene on
                int_var = random.choice(var_names[:-2])  # Not the last variables
                int_val = random.random()

                # Get interventional sample
                int_sample = self.scm.sample(interventions={int_var: int_val})

                self.interventional_data.append((obs, {int_var: int_val}, int_sample))

                # Find affected variables (descendants)
                affected = self._get_descendants(int_var)

                # Create intervention example
                hypothesis = f"If we set {int_var}={'high' if int_val > 0.5 else 'low'}, " \
                           f"then {affected[0] if affected else 'nothing'} changes."

                example = CausalExample(
                    premise=premise,
                    hypothesis=hypothesis,
                    label=1 if affected else 0,
                    relation_type=CausalRelationType.CAUSE,
                    explanation=f"Intervention on {int_var} propagates to descendants: {affected}",
                    causal_graph=self._get_graph_dict(),
                    intervention={
                        "variable": int_var,
                        "value": int_val,
                        "affected": affected,
                    },
                )
                self.examples.append(example)

                # Generate counterfactual if enabled
                if self.include_counterfactuals and random.random() < 0.5:
                    cf_sample = self.scm.counterfactual(obs, {int_var: int_val})
                    self.counterfactual_data.append((obs, {int_var: int_val}, cf_sample))

                    # Create counterfactual example
                    cf_hypothesis = f"If {int_var} had been {'high' if int_val > 0.5 else 'low'}, " \
                                  f"{affected[0] if affected else 'nothing'} would have changed."

                    cf_example = CausalExample(
                        premise=premise,
                        hypothesis=cf_hypothesis,
                        label=1 if affected else 0,
                        relation_type=CausalRelationType.CAUSE,
                        explanation=f"Counterfactual: changing {int_var} would affect {affected}",
                        causal_graph=self._get_graph_dict(),
                        counterfactual={
                            "factual": obs,
                            "intervention": {int_var: int_val},
                            "counterfactual": cf_sample,
                        },
                    )
                    self.examples.append(cf_example)
            else:
                # Create simple observational example
                # Pick two variables and test if one causes the other
                if len(var_names) >= 2:
                    v1, v2 = random.sample(var_names, 2)
                    is_causal = v2 in self._get_descendants(v1)

                    hypothesis = f"{v1} causes {v2}."

                    example = CausalExample(
                        premise=premise,
                        hypothesis=hypothesis,
                        label=1 if is_causal else 0,
                        relation_type=CausalRelationType.CAUSE if is_causal else CausalRelationType.NO_RELATION,
                        explanation=f"{'Yes' if is_causal else 'No'}, {v1} {'is' if is_causal else 'is not'} an ancestor of {v2}",
                        causal_graph=self._get_graph_dict(),
                    )
                    self.examples.append(example)

        print(f"    Generated {len(self.examples)} examples")
        print(f"    Observational: {len(self.observational_data)}")
        print(f"    Interventional: {len(self.interventional_data)}")
        print(f"    Counterfactual: {len(self.counterfactual_data)}")

    def _get_descendants(self, var: str) -> List[str]:
        """Get all descendants of a variable."""
        descendants = []
        to_visit = list(self.scm.adjacency[var])

        while to_visit:
            current = to_visit.pop(0)
            if current not in descendants:
                descendants.append(current)
                to_visit.extend(self.scm.adjacency[current])

        return descendants

    def _get_graph_dict(self) -> Dict[str, Any]:
        """Get causal graph as dictionary."""
        return {
            "nodes": list(self.scm.variables.keys()),
            "edges": [
                (parent, child)
                for parent, children in self.scm.adjacency.items()
                for child in children
            ],
        }

    def get_adjacency_matrix(self) -> Tensor:
        """Get ground-truth adjacency matrix."""
        n = len(self.scm.variables)
        var_names = list(self.scm.variables.keys())

        adj = torch.zeros(n, n)
        for parent, children in self.scm.adjacency.items():
            i = var_names.index(parent)
            for child in children:
                j = var_names.index(child)
                adj[i, j] = 1.0

        return adj

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> CausalExample:
        return self.examples[idx]

    def get_causal_graph(self, idx: int) -> Optional[Dict[str, List[str]]]:
        return self.examples[idx].causal_graph


# =============================================================================
# COMBINED DATALOADER
# =============================================================================


class CausalDataLoader:
    """
    Unified data loader for causal datasets.

    Supports loading any combination of COPA, e-CARE, and Synthetic SCM.
    """

    def __init__(
        self,
        datasets: List[str] = ["copa", "ecare", "scm"],
        config: Optional[CausalDatasetConfig] = None,
        batch_size: int = 32,
        shuffle: bool = True,
    ):
        self.config = config or CausalDatasetConfig()
        self.batch_size = batch_size
        self.shuffle = shuffle

        self.datasets: Dict[str, CausalDataset] = {}
        self.combined_examples: List[Tuple[str, int]] = []  # (dataset_name, idx)

        self._load_datasets(datasets)

    def _load_datasets(self, dataset_names: List[str]):
        """Load requested datasets."""
        print(f"\nLoading causal datasets: {dataset_names}")

        for name in dataset_names:
            name_lower = name.lower()

            if name_lower == "copa":
                self.datasets["copa"] = COPADataset(
                    split=self.config.copa_split,
                    cache_dir=self.config.cache_dir,
                )
            elif name_lower == "ecare":
                self.datasets["ecare"] = ECareDataset(
                    split=self.config.ecare_split,
                    cache_dir=self.config.cache_dir,
                    include_explanations=self.config.ecare_include_explanations,
                )
            elif name_lower == "scm":
                self.datasets["scm"] = SyntheticSCMDataset(
                    num_samples=self.config.scm_num_samples,
                    num_variables=self.config.scm_num_variables,
                    edge_probability=self.config.scm_edge_probability,
                    noise_std=self.config.scm_noise_std,
                    intervention_prob=self.config.scm_intervention_prob,
                    include_counterfactuals=self.config.scm_include_counterfactuals,
                    seed=self.config.seed,
                    cache_dir=self.config.cache_dir,
                )
            else:
                print(f"  Warning: Unknown dataset '{name}', skipping.")

        # Build combined index
        for ds_name, ds in self.datasets.items():
            for i in range(len(ds)):
                self.combined_examples.append((ds_name, i))

        print(f"  Total examples: {len(self.combined_examples)}")

    def __len__(self) -> int:
        return len(self.combined_examples)

    def __iter__(self) -> Iterator[List[CausalExample]]:
        """Iterate over batches."""
        indices = list(range(len(self.combined_examples)))

        if self.shuffle:
            random.shuffle(indices)

        for start in range(0, len(indices), self.batch_size):
            batch_indices = indices[start:start + self.batch_size]
            batch = []

            for idx in batch_indices:
                ds_name, ex_idx = self.combined_examples[idx]
                example = self.datasets[ds_name][ex_idx]
                batch.append(example)

            yield batch

    def get_dataset(self, name: str) -> Optional[CausalDataset]:
        """Get a specific dataset by name."""
        return self.datasets.get(name.lower())


# =============================================================================
# PYTORCH DATASET WRAPPER
# =============================================================================


class CausalTorchDataset(Dataset):
    """
    PyTorch Dataset wrapper for causal datasets.

    Converts text examples to tensor format suitable for model training.
    """

    def __init__(
        self,
        causal_dataset: CausalDataset,
        tokenizer: Optional[Any] = None,
        max_seq_len: int = 256,
        d_model: int = 128,
    ):
        self.dataset = causal_dataset
        self.tokenizer = tokenizer
        self.max_seq_len = max_seq_len
        self.d_model = d_model

        # If no tokenizer, we'll create embeddings directly
        if tokenizer is None:
            print("  Note: No tokenizer provided. Using hash-based embeddings.")

    def __len__(self) -> int:
        return len(self.dataset)

    def __getitem__(self, idx: int) -> Dict[str, Tensor]:
        """
        Get a single example as tensors.

        Returns:
            Dict with:
            - input_embeds: [N, D] input embeddings
            - label: scalar label
            - causal_adjacency: [V, V] ground-truth adjacency (if available)
        """
        example = self.dataset[idx]

        # Combine premise and hypothesis
        text = f"{example.premise} {example.hypothesis}"

        # Create embeddings
        if self.tokenizer is not None:
            # Use tokenizer
            tokens = self.tokenizer.encode(
                text,
                max_length=self.max_seq_len,
                truncation=True,
                padding="max_length",
            )
            input_ids = torch.tensor(tokens)
            # Would need an embedding layer here
            input_embeds = torch.randn(len(tokens), self.d_model)  # Placeholder
        else:
            # Hash-based embeddings
            input_embeds = self._text_to_embedding(text)

        # Label
        label = torch.tensor(example.label, dtype=torch.long)

        # Causal graph adjacency (if available)
        causal_adjacency = torch.zeros(10, 10)  # Default
        if example.causal_graph and "edges" in example.causal_graph:
            nodes = example.causal_graph.get("nodes", [])
            edges = example.causal_graph.get("edges", [])
            n = len(nodes)
            if n > 0:
                causal_adjacency = torch.zeros(n, n)
                for edge in edges:
                    if isinstance(edge, (list, tuple)) and len(edge) == 2:
                        src, tgt = edge
                        if src in nodes and tgt in nodes:
                            i, j = nodes.index(src), nodes.index(tgt)
                            causal_adjacency[i, j] = 1.0

        return {
            "input_embeds": input_embeds,
            "label": label,
            "causal_adjacency": causal_adjacency,
            "text": text,
        }

    def _text_to_embedding(self, text: str) -> Tensor:
        """Convert text to embedding using hash-based method."""
        # Simple hash-based embedding (for testing)
        words = text.lower().split()[:self.max_seq_len]

        embeds = []
        for word in words:
            # Create deterministic embedding from word hash
            h = hash(word)
            torch.manual_seed(h % (2**31))
            embed = torch.randn(self.d_model)
            embeds.append(embed)

        # Pad to max_seq_len
        while len(embeds) < self.max_seq_len:
            embeds.append(torch.zeros(self.d_model))

        return torch.stack(embeds[:self.max_seq_len])


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_causal_dataloader(
    datasets: List[str] = ["copa", "ecare", "scm"],
    batch_size: int = 32,
    **kwargs,
) -> CausalDataLoader:
    """
    Factory function to create a causal data loader.

    Args:
        datasets: List of dataset names to load
        batch_size: Batch size
        **kwargs: Additional config parameters

    Returns:
        CausalDataLoader instance
    """
    config = CausalDatasetConfig(**kwargs)
    return CausalDataLoader(datasets, config, batch_size)


def load_copa(split: str = "train", **kwargs) -> COPADataset:
    """Load COPA dataset."""
    return COPADataset(split=split, **kwargs)


def load_ecare(split: str = "train", **kwargs) -> ECareDataset:
    """Load e-CARE dataset."""
    return ECareDataset(split=split, **kwargs)


def load_synthetic_scm(**kwargs) -> SyntheticSCMDataset:
    """Load Synthetic SCM dataset."""
    return SyntheticSCMDataset(**kwargs)
