"""
Ontological Engine - Multi-Domain Dataset
==========================================

Dataset generator for all 10 ontological layers with multi-label support.

The 10 Ontological Layers:
- O1_THINKING: Contemplation, philosophy, reflection
- O2_FORMING: Structure, creation, art, creativity
- O3_ACTING: Procedures, commands, action
- O4_TAGGING: Emotional tagging/classification
- O6_AGENCY: Guidance, instruction, leadership
- O7_REASONING: Logic, analysis, problem-solving
- O8_PURPOSE: Goals, intention, purposefulness
- O9_WITNESSES: Meta-awareness, observation
- O10_UNIFYING: Integration, synthesis, unity
- O12_ABSOLVING: Resolution, completion, transcendence

Usage:
    from symbolu.ontological.multi_domain_dataset import MultiDomainDataset

    dataset = MultiDomainDataset.generate(samples_per_domain=100)
    dataset.save("data/multi_domain.json")
"""

import json
import random
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict, field
from pathlib import Path

from symbolu.ontological.types import LAYER_NAMES, LAYER_INDEX


@dataclass
class DomainSample:
    """A sample with multi-label ontological annotations."""
    text: str
    primary_domain: str  # Main domain (O1-O10)
    secondary_domains: List[str] = field(default_factory=list)  # Additional domains
    domain_scores: Dict[str, float] = field(default_factory=dict)  # Soft labels
    category: str = ""  # Sub-category within domain

    def to_text(self) -> str:
        """Get text for training."""
        return self.text

    def get_label_vector(self) -> List[float]:
        """Get 10D label vector with soft labels."""
        vector = [0.0] * 10
        # Primary domain gets highest score
        if self.primary_domain in LAYER_INDEX:
            vector[LAYER_INDEX[self.primary_domain]] = 1.0
        # Secondary domains get partial scores
        for domain in self.secondary_domains:
            if domain in LAYER_INDEX:
                vector[LAYER_INDEX[domain]] = 0.5
        # Override with explicit scores if provided
        for domain, score in self.domain_scores.items():
            if domain in LAYER_INDEX:
                vector[LAYER_INDEX[domain]] = score
        return vector


class MultiDomainDataset:
    """
    Multi-domain dataset generator for training all 10 ontological layers.

    Supports multi-label annotations where samples can belong to multiple domains.
    """

    def __init__(self, samples: List[DomainSample] = None):
        self.samples = samples or []

    def __len__(self) -> int:
        return len(self.samples)

    def get_texts(self) -> List[str]:
        """Get all texts."""
        return [s.text for s in self.samples]

    def get_labels(self) -> List[List[float]]:
        """Get all label vectors."""
        return [s.get_label_vector() for s in self.samples]

    def get_by_domain(self, domain: str) -> List[DomainSample]:
        """Get samples by primary domain."""
        return [s for s in self.samples if s.primary_domain == domain]

    def get_domain_counts(self) -> Dict[str, int]:
        """Get sample counts per domain."""
        counts = {name: 0 for name in LAYER_NAMES}
        for s in self.samples:
            counts[s.primary_domain] = counts.get(s.primary_domain, 0) + 1
        return counts

    def save(self, path: str) -> None:
        """Save to JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "count": len(self.samples),
            "domain_counts": self.get_domain_counts(),
            "samples": [asdict(s) for s in self.samples]
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"Saved {len(self.samples)} multi-domain samples to {path}")

    @classmethod
    def load(cls, path: str) -> "MultiDomainDataset":
        """Load from JSON."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        samples = [DomainSample(**s) for s in data["samples"]]
        print(f"Loaded {len(samples)} multi-domain samples from {path}")
        return cls(samples)

    @classmethod
    def generate(
        cls,
        samples_per_domain: int = 100,
        seed: int = None
    ) -> "MultiDomainDataset":
        """Generate samples for all 10 domains."""
        if seed is not None:
            random.seed(seed)

        samples = []

        # Generate for each domain
        samples.extend(cls._generate_thinking(samples_per_domain))
        samples.extend(cls._generate_forming(samples_per_domain))
        samples.extend(cls._generate_acting(samples_per_domain))
        samples.extend(cls._generate_tagging(samples_per_domain))
        samples.extend(cls._generate_directing(samples_per_domain))
        samples.extend(cls._generate_reasoning(samples_per_domain))
        samples.extend(cls._generate_purposing(samples_per_domain))
        samples.extend(cls._generate_meta_observing(samples_per_domain))
        samples.extend(cls._generate_unifying(samples_per_domain))
        samples.extend(cls._generate_absolving(samples_per_domain))

        random.shuffle(samples)

        print(f"Generated {len(samples)} samples across 10 domains")
        return cls(samples)

    # ==================== O1_THINKING ====================
    @classmethod
    def _generate_thinking(cls, count: int) -> List[DomainSample]:
        """O1: Contemplation, philosophy, reflection."""
        templates = [
            # Philosophy
            ("What is the nature of {concept}? Perhaps it is {reflection}.",
             ["philosophy"], ["O9_WITNESSES"]),
            ("I wonder about {concept}. It seems that {reflection}.",
             ["wonder"], ["O9_WITNESSES"]),
            ("The question of {concept} leads us to consider {reflection}.",
             ["inquiry"], ["O7_REASONING"]),
            # Reflection
            ("Looking back, I realize that {insight}.",
             ["reflection"], ["O9_WITNESSES"]),
            ("Upon reflection, {insight} becomes clear.",
             ["contemplation"], []),
            ("In quiet moments, I find myself thinking about {concept}.",
             ["introspection"], []),
            # Existential
            ("What does it mean to {verb}? Perhaps {reflection}.",
             ["existential"], ["O12_ABSOLVING"]),
            ("The deeper meaning of {concept} reveals {insight}.",
             ["meaning"], ["O10_UNIFYING"]),
        ]

        concepts = ["consciousness", "existence", "time", "truth", "beauty",
                   "reality", "knowledge", "self", "meaning", "purpose",
                   "freedom", "identity", "being", "nothing", "infinity"]
        reflections = [
            "more than we initially perceive",
            "a dance between opposites",
            "layers within layers of understanding",
            "both everything and nothing at once",
            "the foundation of all experience"
        ]
        insights = [
            "simplicity holds profound wisdom",
            "questions matter more than answers",
            "understanding changes us forever",
            "each moment contains eternity",
            "we are both the observer and observed"
        ]
        verbs = ["exist", "know", "love", "create", "understand", "be"]

        samples = []
        for i in range(count):
            template, categories, secondary = random.choice(templates)
            text = template.format(
                concept=random.choice(concepts),
                reflection=random.choice(reflections),
                insight=random.choice(insights),
                verb=random.choice(verbs)
            )
            samples.append(DomainSample(
                text=text,
                primary_domain="O5_COGNITION",
                secondary_domains=secondary,
                category=random.choice(categories)
            ))

        return samples[:count]

    # ==================== O2_FORMING ====================
    @classmethod
    def _generate_forming(cls, count: int) -> List[DomainSample]:
        """O2: Structure, creation, art, creativity."""
        templates = [
            # Creative process
            ("The {material} takes shape as {creation}, flowing into {form}.",
             ["creation"], []),
            ("Imagine {creation} emerging from {source}—{quality} and alive.",
             ["imagination"], ["O5_COGNITION"]),
            ("Let the colors dance: {color1} meets {color2} in a symphony of {quality}.",
             ["art"], []),
            # Structure
            ("The architecture of {concept} reveals {pattern} within {pattern}.",
             ["structure"], ["O10_UNIFYING"]),
            ("Building {creation} requires balancing {element1} with {element2}.",
             ["construction"], ["O3_EXECUTION"]),
            # Artistic expression
            ("The {art_form} speaks of {emotion}, capturing {quality} in every {element}.",
             ["expression"], ["O4_TAGGING"]),
            ("Through {medium}, we shape {concept} into something tangible.",
             ["craft"], []),
            ("Beauty emerges where {element1} and {element2} intersect.",
             ["aesthetics"], ["O5_COGNITION"]),
        ]

        materials = ["clay", "light", "sound", "words", "stone", "code", "fabric"]
        creations = ["a sculpture", "a melody", "a story", "a garden", "a painting"]
        forms = ["graceful curves", "bold statements", "subtle whispers", "infinite depth"]
        sources = ["silence", "chaos", "nature", "dreams", "memory"]
        qualities = ["luminous", "textured", "harmonious", "dynamic", "serene"]
        colors = ["amber", "indigo", "vermillion", "jade", "silver", "ochre"]
        concepts = ["space", "time", "emotion", "memory", "identity"]
        patterns = ["fractals", "spirals", "symmetry", "rhythm", "harmony"]
        elements = ["form", "void", "light", "shadow", "texture", "rhythm"]
        art_forms = ["poem", "dance", "sculpture", "symphony", "painting"]
        emotions = ["longing", "joy", "wonder", "melancholy", "hope"]
        mediums = ["paint", "words", "movement", "sound", "digital pixels"]

        samples = []
        for i in range(count):
            template, categories, secondary = random.choice(templates)
            text = template.format(
                material=random.choice(materials),
                creation=random.choice(creations),
                form=random.choice(forms),
                source=random.choice(sources),
                quality=random.choice(qualities),
                color1=random.choice(colors),
                color2=random.choice(colors),
                concept=random.choice(concepts),
                pattern=random.choice(patterns),
                element=random.choice(elements),
                element1=random.choice(elements),
                element2=random.choice(elements),
                art_form=random.choice(art_forms),
                emotion=random.choice(emotions),
                medium=random.choice(mediums)
            )
            samples.append(DomainSample(
                text=text,
                primary_domain="O4_STRUCTURE",
                secondary_domains=secondary,
                category=random.choice(categories)
            ))

        return samples[:count]

    # ==================== O3_ACTING ====================
    @classmethod
    def _generate_acting(cls, count: int) -> List[DomainSample]:
        """O3: Procedures, commands, action."""
        templates = [
            # Commands
            ("Run {command} to {action}.",
             ["command"], []),
            ("Execute the following: {step1}, then {step2}.",
             ["procedure"], []),
            ("First, {step1}. Next, {step2}. Finally, {step3}.",
             ["sequence"], []),
            # Instructions
            ("To {goal}, you must {step1} before {step2}.",
             ["instruction"], ["O6_AGENCY"]),
            ("The process requires: {step1} → {step2} → {result}.",
             ["process"], []),
            # Action-oriented
            ("Act now: {action} while the opportunity exists.",
             ["urgency"], ["O8_PURPOSE"]),
            ("Implement {change} by {step1} and {step2}.",
             ["implementation"], []),
            ("Do {action}. Don't hesitate. Results follow action.",
             ["imperative"], []),
        ]

        commands = ["the script", "the build", "the test suite", "the deployment"]
        actions = ["initialize the system", "process the data", "update the config",
                  "clean the cache", "restart the service"]
        steps = ["gather the requirements", "prepare the environment",
                "validate the inputs", "execute the main logic",
                "verify the results", "document the changes",
                "commit the updates", "notify stakeholders"]
        goals = ["complete the migration", "fix the bug", "deploy the feature",
                "optimize performance", "secure the system"]
        results = ["successful completion", "verified output", "stable state"]
        changes = ["the new feature", "the hotfix", "the refactor", "the upgrade"]

        samples = []
        for i in range(count):
            template, categories, secondary = random.choice(templates)
            text = template.format(
                command=random.choice(commands),
                action=random.choice(actions),
                step1=random.choice(steps),
                step2=random.choice(steps),
                step3=random.choice(steps),
                goal=random.choice(goals),
                result=random.choice(results),
                change=random.choice(changes)
            )
            samples.append(DomainSample(
                text=text,
                primary_domain="O3_EXECUTION",
                secondary_domains=secondary,
                category=random.choice(categories)
            ))

        return samples[:count]

    # ==================== O4_TAGGING ====================
    @classmethod
    def _generate_tagging(cls, count: int) -> List[DomainSample]:
        """O4: Emotional tagging/classification."""
        templates = [
            # Emotional labeling
            ("This feels {emotion}—{intensity} and {quality}.",
             ["emotion"], []),
            ("The {subject} evokes {emotion}, a sense of {quality}.",
             ["evocation"], ["O4_STRUCTURE"]),
            ("I categorize this as {category}: {emotion} with hints of {emotion2}.",
             ["classification"], []),
            # Sentiment
            ("Sentiment: {sentiment}. Confidence: {confidence}.",
             ["sentiment"], []),
            ("The tone here is {tone}, conveying {emotion}.",
             ["tone"], []),
            # Labeling
            ("Label: {label}. Tags: {tag1}, {tag2}, {tag3}.",
             ["tagging"], []),
            ("This belongs to {category}, characterized by {quality}.",
             ["categorization"], ["O7_REASONING"]),
            ("Classification: {category} ({confidence} confidence).",
             ["classification"], []),
        ]

        emotions = ["joy", "sadness", "anger", "fear", "surprise", "disgust",
                   "anticipation", "trust", "melancholy", "serenity", "excitement"]
        intensities = ["deeply", "mildly", "overwhelmingly", "subtly", "profoundly"]
        qualities = ["raw", "refined", "complex", "pure", "layered", "nuanced"]
        subjects = ["music", "painting", "story", "moment", "memory", "scene"]
        categories = ["positive", "negative", "neutral", "mixed", "ambiguous"]
        sentiments = ["positive", "negative", "neutral", "very positive", "very negative"]
        confidences = ["high", "medium", "low", "85%", "92%", "78%"]
        tones = ["formal", "casual", "urgent", "calm", "assertive", "contemplative"]
        labels = ["important", "urgent", "routine", "creative", "technical"]
        tags = ["emotion:joy", "topic:art", "style:formal", "priority:high",
               "category:work", "mood:positive", "type:creative"]

        samples = []
        for i in range(count):
            template, categories_list, secondary = random.choice(templates)
            text = template.format(
                emotion=random.choice(emotions),
                emotion2=random.choice(emotions),
                intensity=random.choice(intensities),
                quality=random.choice(qualities),
                subject=random.choice(subjects),
                category=random.choice(categories),
                sentiment=random.choice(sentiments),
                confidence=random.choice(confidences),
                tone=random.choice(tones),
                label=random.choice(labels),
                tag1=random.choice(tags),
                tag2=random.choice(tags),
                tag3=random.choice(tags)
            )
            samples.append(DomainSample(
                text=text,
                primary_domain="O4_TAGGING",
                secondary_domains=secondary,
                category=random.choice(categories_list)
            ))

        return samples[:count]

    # ==================== O6_AGENCY ====================
    @classmethod
    def _generate_directing(cls, count: int) -> List[DomainSample]:
        """O5: Guidance, instruction, leadership."""
        templates = [
            # Leadership
            ("Lead the team toward {goal}. {strategy} will ensure success.",
             ["leadership"], ["O8_PURPOSE"]),
            ("Guide your people through {challenge}. Show them {approach}.",
             ["guidance"], []),
            ("A leader must {quality}. Without this, {consequence}.",
             ["wisdom"], ["O5_COGNITION"]),
            # Instruction
            ("Teach them to {skill}. Start with {foundation}, then build.",
             ["teaching"], ["O3_EXECUTION"]),
            ("Mentor by {approach}: show, explain, practice, master.",
             ["mentoring"], []),
            # Direction
            ("The path forward requires {direction}. Focus on {priority}.",
             ["direction"], ["O8_PURPOSE"]),
            ("Steer the project toward {goal} by {strategy}.",
             ["steering"], []),
            ("Direct your attention to {priority}. Everything else follows.",
             ["focus"], ["O9_WITNESSES"]),
        ]

        goals = ["excellence", "innovation", "growth", "stability", "transformation"]
        strategies = ["Clear communication", "Consistent action", "Strategic thinking"]
        challenges = ["uncertainty", "change", "conflict", "complexity", "pressure"]
        approaches = ["the way forward", "their potential", "what matters"]
        qualities = ["listen deeply", "decide firmly", "inspire others", "stay humble"]
        consequences = ["trust erodes", "momentum fades", "vision blurs"]
        skills = ["think critically", "communicate clearly", "solve problems", "lead"]
        foundations = ["the basics", "core principles", "fundamentals", "strong habits"]
        directions = ["clarity of purpose", "focused effort", "unified vision"]
        priorities = ["what matters most", "the core mission", "team alignment"]

        samples = []
        for i in range(count):
            template, categories, secondary = random.choice(templates)
            text = template.format(
                goal=random.choice(goals),
                strategy=random.choice(strategies),
                challenge=random.choice(challenges),
                approach=random.choice(approaches),
                quality=random.choice(qualities),
                consequence=random.choice(consequences),
                skill=random.choice(skills),
                foundation=random.choice(foundations),
                direction=random.choice(directions),
                priority=random.choice(priorities)
            )
            samples.append(DomainSample(
                text=text,
                primary_domain="O6_AGENCY",
                secondary_domains=secondary,
                category=random.choice(categories)
            ))

        return samples[:count]

    # ==================== O7_REASONING ====================
    @classmethod
    def _generate_reasoning(cls, count: int) -> List[DomainSample]:
        """O6: Logic, analysis, problem-solving."""
        templates = [
            # Logic
            ("If {premise1}, and {premise2}, then {conclusion}.",
             ["logic"], []),
            ("Given {condition}, we can deduce that {conclusion}.",
             ["deduction"], []),
            ("The logical sequence is: {step1} → {step2} → {step3}.",
             ["sequence"], []),
            # Analysis
            ("Analyzing {subject}: {aspect1} shows {finding1}, while {aspect2} reveals {finding2}.",
             ["analysis"], ["O9_WITNESSES"]),
            ("Break down {problem}: first {component1}, then {component2}.",
             ["decomposition"], []),
            # Problem-solving
            ("The solution requires {approach}. Consider {factor1} and {factor2}.",
             ["problem-solving"], []),
            ("To solve {problem}, apply {method}: {step1}, {step2}, verify.",
             ["methodology"], ["O3_EXECUTION"]),
            ("The optimal path: maximize {benefit} while minimizing {cost}.",
             ["optimization"], []),
        ]

        premises = ["A implies B", "all X are Y", "the condition holds",
                   "the hypothesis is true", "P is greater than Q"]
        conditions = ["the constraints are met", "the data is valid",
                     "the assumptions hold", "the system is stable"]
        conclusions = ["the theorem follows", "the result is verified",
                      "the claim is proven", "the solution exists"]
        steps = ["identify variables", "establish relationships",
                "apply transformations", "verify results", "generalize findings"]
        subjects = ["the system", "the data", "the algorithm", "the model"]
        aspects = ["performance", "accuracy", "complexity", "stability", "scalability"]
        findings = ["significant improvement", "linear growth", "exponential decay",
                   "stable equilibrium", "periodic behavior"]
        problems = ["the optimization challenge", "the scaling issue",
                   "the consistency problem", "the complexity bottleneck"]
        components = ["the input processing", "the core algorithm",
                     "the output validation", "the error handling"]
        approaches = ["systematic analysis", "divide and conquer",
                     "iterative refinement", "constraint satisfaction"]
        factors = ["computational cost", "accuracy requirements",
                  "memory constraints", "time complexity"]
        methods = ["the standard algorithm", "the optimized approach",
                  "the heuristic method", "the exact solution"]
        benefits = ["efficiency", "accuracy", "robustness", "simplicity"]
        costs = ["complexity", "resource usage", "latency", "maintenance burden"]

        samples = []
        for i in range(count):
            template, categories, secondary = random.choice(templates)
            text = template.format(
                premise1=random.choice(premises),
                premise2=random.choice(premises),
                condition=random.choice(conditions),
                conclusion=random.choice(conclusions),
                step1=random.choice(steps),
                step2=random.choice(steps),
                step3=random.choice(steps),
                subject=random.choice(subjects),
                aspect1=random.choice(aspects),
                aspect2=random.choice(aspects),
                finding1=random.choice(findings),
                finding2=random.choice(findings),
                problem=random.choice(problems),
                component1=random.choice(components),
                component2=random.choice(components),
                approach=random.choice(approaches),
                factor1=random.choice(factors),
                factor2=random.choice(factors),
                method=random.choice(methods),
                benefit=random.choice(benefits),
                cost=random.choice(costs)
            )
            samples.append(DomainSample(
                text=text,
                primary_domain="O7_REASONING",
                secondary_domains=secondary,
                category=random.choice(categories)
            ))

        return samples[:count]

    # ==================== O8_PURPOSE ====================
    @classmethod
    def _generate_purposing(cls, count: int) -> List[DomainSample]:
        """O7: Goals, intention, purposefulness."""
        templates = [
            # Goals
            ("The goal is clear: {goal}. Every action aligns with this purpose.",
             ["goal"], []),
            ("We aim to {objective} by {timeframe}. This drives all decisions.",
             ["objective"], ["O6_AGENCY"]),
            ("Our mission: {mission}. Our vision: {vision}.",
             ["mission"], []),
            # Intention
            ("I intend to {action} because {reason}.",
             ["intention"], []),
            ("The purpose behind {action} is {purpose}.",
             ["purpose"], ["O5_COGNITION"]),
            ("With deliberate intention, we {action} to achieve {outcome}.",
             ["deliberation"], []),
            # Motivation
            ("What drives us: {motivation}. What sustains us: {sustainer}.",
             ["motivation"], []),
            ("{goal} is not just an objective—it's a calling.",
             ["calling"], ["O12_ABSOLVING"]),
        ]

        goals = ["excellence in every detail", "sustainable growth",
                "meaningful impact", "continuous improvement", "lasting change"]
        objectives = ["transform the industry", "serve our community",
                     "build something lasting", "solve the core problem"]
        timeframes = ["this quarter", "within the year", "the next decade"]
        missions = ["to empower through knowledge", "to create lasting value",
                   "to innovate with purpose", "to serve with excellence"]
        visions = ["a world where everyone thrives", "technology that uplifts",
                  "sustainable prosperity for all", "mastery accessible to all"]
        actions = ["build", "create", "transform", "serve", "lead", "innovate"]
        reasons = ["it aligns with our values", "the impact matters",
                  "future generations depend on it", "excellence demands it"]
        purposes = ["creating lasting value", "making a difference",
                   "fulfilling our potential", "honoring our commitment"]
        outcomes = ["meaningful results", "sustainable success", "positive change"]
        motivations = ["the desire to excel", "service to others",
                      "the pursuit of truth", "creative expression"]
        sustainers = ["purpose", "community", "growth", "impact", "meaning"]

        samples = []
        for i in range(count):
            template, categories, secondary = random.choice(templates)
            text = template.format(
                goal=random.choice(goals),
                objective=random.choice(objectives),
                timeframe=random.choice(timeframes),
                mission=random.choice(missions),
                vision=random.choice(visions),
                action=random.choice(actions),
                reason=random.choice(reasons),
                purpose=random.choice(purposes),
                outcome=random.choice(outcomes),
                motivation=random.choice(motivations),
                sustainer=random.choice(sustainers)
            )
            samples.append(DomainSample(
                text=text,
                primary_domain="O8_PURPOSE",
                secondary_domains=secondary,
                category=random.choice(categories)
            ))

        return samples[:count]

    # ==================== O9_WITNESSES ====================
    @classmethod
    def _generate_meta_observing(cls, count: int) -> List[DomainSample]:
        """O8: Meta-awareness, observation."""
        templates = [
            # Meta-awareness
            ("I notice that I am {observation}. This awareness itself is {quality}.",
             ["meta-awareness"], ["O5_COGNITION"]),
            ("Observing my own {process}, I see {pattern}.",
             ["self-observation"], []),
            ("The observer notices the observing. {insight}.",
             ["recursion"], []),
            # Watching
            ("From a distance, {subject} reveals {pattern}.",
             ["perspective"], []),
            ("Step back and observe: {observation}. The pattern becomes clear.",
             ["stepping-back"], []),
            ("Watching without judgment: {subject} simply is {quality}.",
             ["witnessing"], ["O12_ABSOLVING"]),
            # Analysis of process
            ("The process of {activity} involves {layers} layers of awareness.",
             ["process-awareness"], ["O7_REASONING"]),
            ("Notice how {subject} changes when observed. {insight}.",
             ["observation-effect"], []),
        ]

        observations = ["thinking about thinking", "aware of my awareness",
                       "observing my reactions", "noticing my patterns"]
        processes = ["thinking", "creating", "deciding", "learning", "perceiving"]
        patterns = ["recurring themes", "hidden biases", "automatic responses",
                   "unconscious assumptions", "habitual reactions"]
        qualities = ["fascinating", "revealing", "liberating", "instructive"]
        insights = ["Awareness transforms what it touches",
                   "The map is not the territory",
                   "Observation changes both observer and observed",
                   "Meta-cognition enables growth"]
        subjects = ["the mind", "the process", "the system", "the pattern",
                   "behavior", "thought", "emotion"]
        activities = ["understanding", "learning", "creating", "solving problems"]
        layers = ["multiple", "nested", "interconnected", "recursive"]

        samples = []
        for i in range(count):
            template, categories, secondary = random.choice(templates)
            text = template.format(
                observation=random.choice(observations),
                process=random.choice(processes),
                pattern=random.choice(patterns),
                quality=random.choice(qualities),
                insight=random.choice(insights),
                subject=random.choice(subjects),
                activity=random.choice(activities),
                layers=random.choice(layers)
            )
            samples.append(DomainSample(
                text=text,
                primary_domain="O9_WITNESSES",
                secondary_domains=secondary,
                category=random.choice(categories)
            ))

        return samples[:count]

    # ==================== O10_UNIFYING ====================
    @classmethod
    def _generate_unifying(cls, count: int) -> List[DomainSample]:
        """O9: Integration, synthesis, unity."""
        templates = [
            # Integration
            ("Bringing together {element1} and {element2} reveals {unity}.",
             ["integration"], []),
            ("The synthesis of {concept1} with {concept2} creates {emergence}.",
             ["synthesis"], ["O4_STRUCTURE"]),
            ("What seemed separate—{element1}, {element2}—is actually one.",
             ["unity"], ["O5_COGNITION"]),
            # Holistic
            ("The whole is greater than the sum: {parts} become {whole}.",
             ["holism"], []),
            ("Every part contains the whole. {element} reflects {totality}.",
             ["fractality"], ["O9_WITNESSES"]),
            # Connection
            ("The connection between {concept1} and {concept2}: {relationship}.",
             ["connection"], []),
            ("All {concepts} share a common thread: {essence}.",
             ["commonality"], []),
            ("Unity emerges from diversity: {elements} form {whole}.",
             ["emergence"], []),
        ]

        elements = ["science", "art", "reason", "intuition", "mind", "body",
                   "theory", "practice", "analysis", "synthesis", "parts", "whole"]
        concepts = ["knowledge", "wisdom", "experience", "understanding",
                   "logic", "emotion", "structure", "flow"]
        unity = ["a deeper truth", "unexpected harmony", "fundamental oneness",
               "coherent understanding", "integrated wisdom"]
        emergence = ["new understanding", "emergent properties", "transcendent truth",
                    "holistic awareness", "synergistic insight"]
        parts = ["scattered pieces", "diverse elements", "separate domains"]
        wholes = ["coherent systems", "unified theory", "integrated understanding"]
        totality = ["the entire system", "universal patterns", "fundamental truth"]
        relationships = ["deeper than it appears", "fundamentally the same",
                        "complementary aspects of one reality"]
        essences = ["the pursuit of truth", "creative expression",
                   "the desire to understand", "connection to the whole"]

        samples = []
        for i in range(count):
            template, categories, secondary = random.choice(templates)
            text = template.format(
                element=random.choice(elements),
                element1=random.choice(elements),
                element2=random.choice(elements),
                elements=random.choice(parts),
                concept1=random.choice(concepts),
                concept2=random.choice(concepts),
                concepts=random.choice(concepts),
                unity=random.choice(unity),
                emergence=random.choice(emergence),
                parts=random.choice(parts),
                whole=random.choice(wholes),
                totality=random.choice(totality),
                relationship=random.choice(relationships),
                essence=random.choice(essences)
            )
            samples.append(DomainSample(
                text=text,
                primary_domain="O10_UNIFYING",
                secondary_domains=secondary,
                category=random.choice(categories)
            ))

        return samples[:count]

    # ==================== O12_ABSOLVING ====================
    @classmethod
    def _generate_absolving(cls, count: int) -> List[DomainSample]:
        """O10: Resolution, completion, transcendence."""
        templates = [
            # Resolution
            ("The struggle resolves into {resolution}. Peace follows.",
             ["resolution"], []),
            ("What was {conflict} becomes {resolution}.",
             ["transformation"], ["O10_UNIFYING"]),
            ("Release {burden}. What remains is {essence}.",
             ["release"], []),
            # Completion
            ("The journey completes. From {beginning} to {ending}—whole.",
             ["completion"], []),
            ("It is finished. {accomplishment} stands complete.",
             ["finality"], []),
            ("{cycle} ends, and in ending, begins again. Eternal return.",
             ["cycle"], ["O10_UNIFYING"]),
            # Transcendence
            ("Beyond {limitation} lies {transcendence}.",
             ["transcendence"], ["O5_COGNITION"]),
            ("Let go of {attachment}. {freedom} awaits.",
             ["letting-go"], []),
            ("In acceptance of {reality}, find {peace}.",
             ["acceptance"], []),
        ]

        conflicts = ["tension", "struggle", "chaos", "discord", "opposition"]
        resolutions = ["harmony", "clarity", "stillness", "understanding", "peace"]
        burdens = ["the weight of expectation", "the need to control",
                  "attachment to outcome", "the illusion of separation"]
        essences = ["pure presence", "simple truth", "clear awareness", "love"]
        beginnings = ["uncertainty", "chaos", "seeking", "questioning"]
        endings = ["clarity", "peace", "completion", "wisdom"]
        accomplishments = ["the work", "the creation", "the transformation"]
        cycles = ["this chapter", "the old way", "the pattern", "the season"]
        limitations = ["fear", "doubt", "separation", "the small self"]
        transcendences = ["infinite possibility", "boundless awareness",
                         "unconditional love", "eternal presence"]
        attachments = ["what was", "what should be", "control", "expectation"]
        freedoms = ["true freedom", "liberation", "spacious awareness", "peace"]
        realities = ["what is", "impermanence", "this moment", "our nature"]
        peaces = ["deep peace", "lasting serenity", "quiet joy", "contentment"]

        samples = []
        for i in range(count):
            template, categories, secondary = random.choice(templates)
            text = template.format(
                conflict=random.choice(conflicts),
                resolution=random.choice(resolutions),
                burden=random.choice(burdens),
                essence=random.choice(essences),
                beginning=random.choice(beginnings),
                ending=random.choice(endings),
                accomplishment=random.choice(accomplishments),
                cycle=random.choice(cycles),
                limitation=random.choice(limitations),
                transcendence=random.choice(transcendences),
                attachment=random.choice(attachments),
                freedom=random.choice(freedoms),
                reality=random.choice(realities),
                peace=random.choice(peaces)
            )
            samples.append(DomainSample(
                text=text,
                primary_domain="O12_ABSOLVING",
                secondary_domains=secondary,
                category=random.choice(categories)
            ))

        return samples[:count]


def create_multi_domain_dataset(
    output_path: str = "data/multi_domain.json",
    samples_per_domain: int = 100,
    seed: int = 42,
) -> MultiDomainDataset:
    """Generate and save multi-domain dataset."""
    dataset = MultiDomainDataset.generate(
        samples_per_domain=samples_per_domain,
        seed=seed
    )
    dataset.save(output_path)
    return dataset


# CLI support
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate Multi-Domain Dataset")
    parser.add_argument("--samples", type=int, default=100,
                       help="Samples per domain (default: 100)")
    parser.add_argument("--output", type=str, default="data/multi_domain.json",
                       help="Output path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    dataset = create_multi_domain_dataset(
        output_path=args.output,
        samples_per_domain=args.samples,
        seed=args.seed,
    )

    # Print statistics
    print("\n" + "=" * 60)
    print("MULTI-DOMAIN DATASET STATISTICS")
    print("=" * 60)

    counts = dataset.get_domain_counts()
    for domain, count in counts.items():
        print(f"  {domain}: {count}")

    print("\nSample from each domain:")
    for domain in LAYER_NAMES:
        samples = dataset.get_by_domain(domain)
        if samples:
            print(f"\n--- {domain} ---")
            print(f"  {samples[0].text[:100]}...")
