"""
Experimental Reasoning Extensions for SymbolU v2.7
===================================================

EXPERIMENTAL: These extensions add reasoning capabilities to the
Bayesian 2.7 system. They are NOT part of the core deterministic
architecture and should be used with caution.

Extensions:
1. DPO (Direct Preference Optimization) - External goal: user engagement
2. ToT (Tree-of-Thoughts) - Utility-guided branch selection
3. MCTS (Monte Carlo Tree Search) - Utility-based node evaluation

Version: 2.7.4-experimental
Date: 2025-12-22

WARNING: These extensions introduce:
- Non-determinism (MCTS randomness)
- External preference signals (DPO)
- Computational overhead (tree search)

They do NOT introduce:
- Autonomous goals (preferences are external)
- World models (just search over thought space)
- True concept formation (pattern matching only)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Callable, Tuple, Dict, Any
import random
import math

from symbolu.guna_modulation.v27_config import (
    BayesianPosterior,
    BayesianStateRegister,
)
from symbolu.guna_modulation.state_types import StateRegister, DEFAULT_STATE
from symbolu.guna_modulation.observables import Observables
from symbolu.guna_modulation.utility import compute_utility


# =============================================================================
# DPO: Direct Preference Optimization
# =============================================================================

class PreferenceGoal(Enum):
    """External goals for DPO optimization."""
    USER_ENGAGEMENT = "user_engagement"
    CLARITY = "clarity"
    SAFETY = "safety"
    HELPFULNESS = "helpfulness"


@dataclass
class PreferencePair:
    """
    A preference pair for DPO learning.

    Attributes:
        preferred: The preferred state/output
        rejected: The rejected state/output
        goal: External goal this preference serves
        strength: Preference strength (β in DPO)
    """
    preferred: StateRegister
    rejected: StateRegister
    goal: PreferenceGoal = PreferenceGoal.USER_ENGAGEMENT
    strength: float = 1.0


@dataclass
class DPOConfig:
    """
    Configuration for DPO preference learning.

    Attributes:
        beta: Temperature parameter (higher = more deterministic)
        goal: External optimization goal
        min_preference_delta: Minimum difference to update
        max_update_magnitude: Cap on single update size
    """
    beta: float = 0.1
    goal: PreferenceGoal = PreferenceGoal.USER_ENGAGEMENT
    min_preference_delta: float = 0.01
    max_update_magnitude: float = 0.2


class DPOUpdater:
    """
    DPO-style preference learning for Bayesian posteriors.

    Uses external preference signals to bias parameter updates
    toward configurations that produce preferred outputs.

    Note: This is NOT autonomous learning - preferences come from
    external sources (users, reward models, etc.).
    """

    def __init__(self, config: DPOConfig = DPOConfig()):
        self._config = config
        self._preference_history: List[PreferencePair] = []

    @property
    def goal(self) -> PreferenceGoal:
        """Current optimization goal."""
        return self._config.goal

    def compute_preference_weight(
        self,
        preferred: StateRegister,
        rejected: StateRegister,
    ) -> float:
        """
        Compute preference-based weight for Bayesian update.

        DPO formula (simplified):
            weight = 1 + β × sigmoid(score(preferred) - score(rejected))

        Args:
            preferred: Preferred state configuration
            rejected: Rejected state configuration

        Returns:
            Weight factor for Bayesian update [0.5, 1.5]
        """
        # Compute utility scores for both
        pref_score = self._state_score(preferred)
        rej_score = self._state_score(rejected)

        # Preference delta
        delta = pref_score - rej_score

        # Skip if delta too small
        if abs(delta) < self._config.min_preference_delta:
            return 1.0

        # Sigmoid scaling
        scaled = self._config.beta * delta
        sigmoid = 1.0 / (1.0 + math.exp(-scaled))

        # Weight in [0.5, 1.5] range
        weight = 0.5 + sigmoid

        return weight

    def _state_score(self, state: StateRegister) -> float:
        """Score a state based on current goal."""
        # w_guna is a tuple (S, R, T)
        sattva = state.w_guna[0] if isinstance(state.w_guna, tuple) else 0.33

        if self._config.goal == PreferenceGoal.USER_ENGAGEMENT:
            # Higher tau_768 (clarity) + higher Sattva = engagement
            return state.tau_768 * 0.6 + sattva * 0.4
        elif self._config.goal == PreferenceGoal.CLARITY:
            return state.tau_768
        elif self._config.goal == PreferenceGoal.SAFETY:
            # Lower tau_768 (more conservative) = safer
            return 1.0 - state.tau_768
        elif self._config.goal == PreferenceGoal.HELPFULNESS:
            return state.tau_768 * 0.5 + state.tau_175 * 0.5
        return 0.5

    def update_posterior_with_preference(
        self,
        posterior: BayesianPosterior,
        preferred: StateRegister,
        rejected: StateRegister,
        observation: float,
    ) -> BayesianPosterior:
        """
        Update posterior with preference-weighted observation.

        Args:
            posterior: Current Bayesian posterior
            preferred: Preferred state
            rejected: Rejected state
            observation: New observation value

        Returns:
            Updated posterior biased toward preferred
        """
        weight = self.compute_preference_weight(preferred, rejected)

        # Cap update magnitude
        capped_weight = min(weight, 1.0 + self._config.max_update_magnitude)

        # Record preference
        self._preference_history.append(PreferencePair(
            preferred=preferred,
            rejected=rejected,
            goal=self._config.goal,
            strength=weight,
        ))

        return posterior.update(observation, weight=capped_weight)

    @property
    def preference_count(self) -> int:
        """Number of preferences learned."""
        return len(self._preference_history)


# =============================================================================
# ToT: Tree-of-Thoughts
# =============================================================================

@dataclass
class ThoughtNode:
    """
    A node in the thought tree.

    Attributes:
        thought: The thought/reasoning step content
        state: Observable state at this node
        utility: Computed utility score
        children: Child thought nodes
        parent: Parent node (None for root)
        depth: Depth in tree
    """
    thought: str
    state: Optional[Observables] = None
    utility: float = 0.0
    children: List["ThoughtNode"] = field(default_factory=list)
    parent: Optional["ThoughtNode"] = None
    depth: int = 0

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0

    @property
    def is_root(self) -> bool:
        return self.parent is None


@dataclass
class ToTConfig:
    """
    Configuration for Tree-of-Thoughts.

    Attributes:
        max_depth: Maximum tree depth
        branching_factor: Number of branches per node
        utility_threshold: Minimum utility to expand
        search_strategy: 'bfs' or 'dfs'
    """
    max_depth: int = 3
    branching_factor: int = 3
    utility_threshold: float = 0.3
    search_strategy: str = "bfs"  # or "dfs"


class TreeOfThoughts:
    """
    Tree-of-Thoughts reasoning with utility-guided branch selection.

    Uses SymbolU utility function to score and prune thought branches.
    Higher utility thoughts are explored preferentially.
    """

    def __init__(
        self,
        config: ToTConfig = ToTConfig(),
        thought_generator: Optional[Callable[[str, int], List[str]]] = None,
        state_extractor: Optional[Callable[[str], Observables]] = None,
    ):
        self._config = config
        self._thought_generator = thought_generator or self._default_generator
        self._state_extractor = state_extractor
        self._root: Optional[ThoughtNode] = None
        self._best_path: List[ThoughtNode] = []

    def _default_generator(self, thought: str, n: int) -> List[str]:
        """Default thought generator (placeholder)."""
        return [f"{thought} -> branch_{i}" for i in range(n)]

    def build_tree(self, initial_thought: str) -> ThoughtNode:
        """
        Build thought tree from initial thought.

        Args:
            initial_thought: Starting thought/query

        Returns:
            Root node of thought tree
        """
        self._root = ThoughtNode(thought=initial_thought, depth=0)

        if self._config.search_strategy == "bfs":
            self._build_bfs(self._root)
        else:
            self._build_dfs(self._root, 0)

        return self._root

    def _build_bfs(self, root: ThoughtNode):
        """Breadth-first tree construction."""
        queue = [root]

        while queue:
            node = queue.pop(0)

            if node.depth >= self._config.max_depth:
                continue

            # Score current node
            if self._state_extractor and node.state is None:
                try:
                    node.state = self._state_extractor(node.thought)
                    _, audit = compute_utility(node.state, DEFAULT_STATE)
                    node.utility = audit.utility
                except Exception:
                    node.utility = 0.0

            # Prune low-utility branches
            if node.utility < self._config.utility_threshold and node.depth > 0:
                continue

            # Generate children
            child_thoughts = self._thought_generator(
                node.thought,
                self._config.branching_factor,
            )

            for thought in child_thoughts:
                child = ThoughtNode(
                    thought=thought,
                    parent=node,
                    depth=node.depth + 1,
                )
                node.children.append(child)
                queue.append(child)

    def _build_dfs(self, node: ThoughtNode, depth: int):
        """Depth-first tree construction."""
        if depth >= self._config.max_depth:
            return

        # Score current node
        if self._state_extractor and node.state is None:
            try:
                node.state = self._state_extractor(node.thought)
                _, audit = compute_utility(node.state, DEFAULT_STATE)
                node.utility = audit.utility
            except Exception:
                node.utility = 0.0

        # Prune low-utility branches
        if node.utility < self._config.utility_threshold and depth > 0:
            return

        # Generate children
        child_thoughts = self._thought_generator(
            node.thought,
            self._config.branching_factor,
        )

        for thought in child_thoughts:
            child = ThoughtNode(
                thought=thought,
                parent=node,
                depth=depth + 1,
            )
            node.children.append(child)
            self._build_dfs(child, depth + 1)

    def find_best_path(self) -> List[ThoughtNode]:
        """
        Find highest-utility path through tree.

        Returns:
            List of nodes from root to best leaf
        """
        if self._root is None:
            return []

        best_leaf = self._find_best_leaf(self._root)

        # Trace back to root
        path = []
        node = best_leaf
        while node is not None:
            path.append(node)
            node = node.parent

        self._best_path = list(reversed(path))
        return self._best_path

    def _find_best_leaf(self, node: ThoughtNode) -> ThoughtNode:
        """Recursively find best leaf by utility."""
        if node.is_leaf:
            return node

        best = node
        best_utility = node.utility

        for child in node.children:
            leaf = self._find_best_leaf(child)
            if leaf.utility > best_utility:
                best = leaf
                best_utility = leaf.utility

        return best

    def get_best_thought_chain(self) -> List[str]:
        """Get thoughts along best path."""
        if not self._best_path:
            self.find_best_path()
        return [node.thought for node in self._best_path]

    @property
    def tree_size(self) -> int:
        """Total nodes in tree."""
        if self._root is None:
            return 0
        return self._count_nodes(self._root)

    def _count_nodes(self, node: ThoughtNode) -> int:
        return 1 + sum(self._count_nodes(c) for c in node.children)


# =============================================================================
# MCTS: Monte Carlo Tree Search
# =============================================================================

@dataclass
class MCTSNode:
    """
    A node in the MCTS tree.

    Attributes:
        state: Observable state at this node
        action: Action that led to this node
        parent: Parent node
        children: Child nodes
        visits: Number of visits
        total_utility: Sum of utilities from rollouts
        prior: Prior probability (from policy)
    """
    state: Optional[Observables] = None
    action: Optional[str] = None
    parent: Optional["MCTSNode"] = None
    children: Dict[str, "MCTSNode"] = field(default_factory=dict)
    visits: int = 0
    total_utility: float = 0.0
    prior: float = 1.0

    @property
    def mean_utility(self) -> float:
        if self.visits == 0:
            return 0.0
        return self.total_utility / self.visits

    @property
    def is_expanded(self) -> bool:
        return len(self.children) > 0

    def ucb_score(self, exploration_weight: float = 1.414) -> float:
        """
        Upper Confidence Bound score.

        UCB = mean_utility + c × sqrt(ln(parent_visits) / visits)
        """
        if self.visits == 0:
            return float('inf')

        if self.parent is None or self.parent.visits == 0:
            return self.mean_utility

        exploitation = self.mean_utility
        exploration = exploration_weight * math.sqrt(
            math.log(self.parent.visits) / self.visits
        )

        return exploitation + exploration


@dataclass
class MCTSConfig:
    """
    Configuration for MCTS.

    Attributes:
        num_simulations: Number of MCTS iterations
        exploration_weight: UCB exploration constant (c)
        max_depth: Maximum rollout depth
        discount_factor: Future utility discount (gamma)
    """
    num_simulations: int = 100
    exploration_weight: float = 1.414  # sqrt(2)
    max_depth: int = 10
    discount_factor: float = 0.95


class MonteCarloTreeSearch:
    """
    MCTS with SymbolU utility as value function.

    Uses utility scores to guide tree search and select actions.
    Provides structured reasoning with exploration/exploitation balance.
    """

    def __init__(
        self,
        config: MCTSConfig = MCTSConfig(),
        action_generator: Optional[Callable[[Observables], List[str]]] = None,
        transition_fn: Optional[Callable[[Observables, str], Observables]] = None,
    ):
        self._config = config
        self._action_generator = action_generator or self._default_actions
        self._transition_fn = transition_fn or self._default_transition
        self._root: Optional[MCTSNode] = None

    def _default_actions(self, state: Observables) -> List[str]:
        """Default action generator."""
        return ["explore", "exploit", "refine"]

    def _default_transition(self, state: Observables, action: str) -> Observables:
        """Default state transition (identity with noise)."""
        # Add small random perturbation
        noise = random.uniform(-0.05, 0.05)
        new_s = max(0, min(1, state.s + noise))
        new_r = max(0, min(1, state.r - noise * 0.5))
        new_t = 1.0 - new_s - new_r
        new_t = max(0, min(1, new_t))

        # Renormalize
        total = new_s + new_r + new_t
        if total > 0:
            new_s, new_r, new_t = new_s/total, new_r/total, new_t/total
        else:
            new_s, new_r, new_t = 0.34, 0.33, 0.33

        return Observables(
            s=new_s, r=new_r, t=new_t,
            H=state.H,
            delta_sem=state.delta_sem,
            C_contr=state.C_contr,
            F_fail=state.F_fail,
        )

    def search(self, initial_state: Observables) -> str:
        """
        Run MCTS and return best action.

        Args:
            initial_state: Starting observable state

        Returns:
            Best action to take
        """
        self._root = MCTSNode(state=initial_state)

        for _ in range(self._config.num_simulations):
            # Selection
            node = self._select(self._root)

            # Expansion
            if node.visits > 0 and not node.is_expanded:
                node = self._expand(node)

            # Simulation (rollout)
            utility = self._simulate(node)

            # Backpropagation
            self._backpropagate(node, utility)

        # Return best action from root
        return self._best_action(self._root)

    def _select(self, node: MCTSNode) -> MCTSNode:
        """Select leaf node using UCB."""
        while node.is_expanded and node.children:
            # Select child with highest UCB
            best_score = float('-inf')
            best_child = None

            for child in node.children.values():
                score = child.ucb_score(self._config.exploration_weight)
                if score > best_score:
                    best_score = score
                    best_child = child

            if best_child is None:
                break
            node = best_child

        return node

    def _expand(self, node: MCTSNode) -> MCTSNode:
        """Expand node by adding children."""
        if node.state is None:
            return node

        actions = self._action_generator(node.state)

        for action in actions:
            if action not in node.children:
                new_state = self._transition_fn(node.state, action)
                child = MCTSNode(
                    state=new_state,
                    action=action,
                    parent=node,
                )
                node.children[action] = child

        # Return random unexplored child
        unexplored = [c for c in node.children.values() if c.visits == 0]
        if unexplored:
            return random.choice(unexplored)
        return node

    def _simulate(self, node: MCTSNode) -> float:
        """
        Rollout simulation using utility as reward.

        Returns discounted cumulative utility.
        """
        if node.state is None:
            return 0.0

        state = node.state
        total_utility = 0.0
        discount = 1.0

        for _ in range(self._config.max_depth):
            # Compute utility at current state
            _, audit = compute_utility(state, DEFAULT_STATE)
            total_utility += discount * audit.utility
            discount *= self._config.discount_factor

            # Random action
            actions = self._action_generator(state)
            if not actions:
                break
            action = random.choice(actions)

            # Transition
            state = self._transition_fn(state, action)

        return total_utility

    def _backpropagate(self, node: MCTSNode, utility: float):
        """Backpropagate utility up the tree."""
        while node is not None:
            node.visits += 1
            node.total_utility += utility
            node = node.parent

    def _best_action(self, node: MCTSNode) -> str:
        """Select best action by visit count."""
        if not node.children:
            return "none"

        best_visits = -1
        best_action = "none"

        for action, child in node.children.items():
            if child.visits > best_visits:
                best_visits = child.visits
                best_action = action

        return best_action

    def get_action_values(self) -> Dict[str, float]:
        """Get utility estimates for all root actions."""
        if self._root is None or not self._root.children:
            return {}

        return {
            action: child.mean_utility
            for action, child in self._root.children.items()
        }

    @property
    def total_simulations(self) -> int:
        """Total simulations run."""
        if self._root is None:
            return 0
        return self._root.visits


# =============================================================================
# Factory Functions
# =============================================================================

def create_dpo_updater(
    goal: PreferenceGoal = PreferenceGoal.USER_ENGAGEMENT,
    beta: float = 0.1,
) -> DPOUpdater:
    """
    Create DPO updater with external goal.

    Args:
        goal: External optimization goal
        beta: Temperature parameter

    Returns:
        Configured DPO updater
    """
    config = DPOConfig(beta=beta, goal=goal)
    return DPOUpdater(config)


def create_tree_of_thoughts(
    max_depth: int = 3,
    branching_factor: int = 3,
    strategy: str = "bfs",
) -> TreeOfThoughts:
    """
    Create Tree-of-Thoughts reasoner.

    Args:
        max_depth: Maximum tree depth
        branching_factor: Branches per node
        strategy: 'bfs' or 'dfs'

    Returns:
        Configured ToT instance
    """
    config = ToTConfig(
        max_depth=max_depth,
        branching_factor=branching_factor,
        search_strategy=strategy,
    )
    return TreeOfThoughts(config)


def create_mcts(
    num_simulations: int = 100,
    exploration_weight: float = 1.414,
) -> MonteCarloTreeSearch:
    """
    Create MCTS reasoner.

    Args:
        num_simulations: Number of iterations
        exploration_weight: UCB exploration constant

    Returns:
        Configured MCTS instance
    """
    config = MCTSConfig(
        num_simulations=num_simulations,
        exploration_weight=exploration_weight,
    )
    return MonteCarloTreeSearch(config)


# =============================================================================
# Capability Summary
# =============================================================================

CAPABILITY_MATRIX = {
    "DPO": {
        "adds": ["Preference learning", "Goal-directed updates"],
        "requires": ["External preference signal"],
        "does_not_add": ["Autonomous goals", "Self-direction"],
    },
    "ToT": {
        "adds": ["Structured reasoning", "Branch pruning"],
        "requires": ["Thought generator", "State extractor"],
        "does_not_add": ["Concept formation", "Transfer learning"],
    },
    "MCTS": {
        "adds": ["Exploration/exploitation", "Lookahead planning"],
        "requires": ["Action space", "Transition model"],
        "does_not_add": ["World model", "True planning"],
    },
}
