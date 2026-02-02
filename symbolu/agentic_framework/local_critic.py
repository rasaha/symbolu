"""
Local Critic Module for Cheaper Reflection

Provides local model inference for quality evaluation, reducing API costs by 10-100x.

SUPPORTED BACKENDS:
    1. Ollama - Local model server (recommended for ease of use)
    2. HuggingFace Transformers - Direct model loading (more control)
    3. llama.cpp via ctypes - Lightweight C++ inference (lowest overhead)

RECOMMENDED MODELS (by size/quality trade-off):
    - Phi-3-mini (3.8B): Best quality/size ratio for critique
    - Llama-3.2-3B: Good general purpose
    - Mistral-7B: Higher quality, more resources
    - Qwen2.5-3B: Fast, good for simple checks

COST COMPARISON:
    | Method          | Cost per 1K tokens | Latency  |
    |-----------------|-------------------|----------|
    | GPT-4           | $0.03             | 500ms    |
    | Claude-3        | $0.015            | 400ms    |
    | Local Phi-3     | ~$0.0001          | 100-200ms|
    | Local Llama-3B  | ~$0.0001          | 80-150ms |

ARCHITECTURE:
    LocalCritic inherits from QualityCritic and uses local inference backends.
    CostAwareCriticSelector automatically routes to local or API based on complexity.
"""

from __future__ import annotations

import json
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .reflective_loop import LLMClient, QualityCritic, QualityCritique, RuleBasedCritic


# =============================================================================
# Local Inference Backends
# =============================================================================


class LocalInferenceBackend(ABC):
    """Abstract base for local model inference."""

    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        """Generate response from local model."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if backend is available and model is loaded."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name/identifier."""
        pass


class OllamaBackend(LocalInferenceBackend):
    """
    Ollama backend for local model inference.

    Requires Ollama to be running: https://ollama.ai
    Start with: ollama serve
    Pull model: ollama pull phi3:mini
    """

    def __init__(
        self,
        model: str = "phi3:mini",
        host: str = "http://localhost:11434",
        timeout: float = 30.0,
    ):
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout
        self._available: Optional[bool] = None

    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        """Generate using Ollama API."""
        import urllib.request
        import urllib.error

        url = f"{self.host}/api/generate"
        data = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.1,  # Low temp for consistent critique
            }
        }).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result.get("response", "")
        except urllib.error.URLError as e:
            raise ConnectionError(f"Ollama not available: {e}")

    def is_available(self) -> bool:
        """Check if Ollama is running and model exists."""
        if self._available is not None:
            return self._available

        import urllib.request
        import urllib.error

        try:
            # Check if Ollama is running
            url = f"{self.host}/api/tags"
            with urllib.request.urlopen(url, timeout=5) as response:
                result = json.loads(response.read().decode("utf-8"))
                models = [m.get("name", "") for m in result.get("models", [])]

                # Check if our model is available
                model_base = self.model.split(":")[0]
                self._available = any(model_base in m for m in models)
                return self._available
        except (urllib.error.URLError, Exception):
            self._available = False
            return False

    @property
    def model_name(self) -> str:
        return f"ollama:{self.model}"


class TransformersBackend(LocalInferenceBackend):
    """
    HuggingFace Transformers backend for direct model loading.

    Requires: pip install transformers torch
    """

    def __init__(
        self,
        model_id: str = "microsoft/phi-3-mini-4k-instruct",
        device: str = "auto",
        torch_dtype: str = "auto",
        max_memory: Optional[Dict[int, str]] = None,
    ):
        self.model_id = model_id
        self.device = device
        self.torch_dtype = torch_dtype
        self.max_memory = max_memory
        self._model = None
        self._tokenizer = None
        self._available: Optional[bool] = None

    def _load_model(self):
        """Lazy load model on first use."""
        if self._model is not None:
            return

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            # Determine dtype
            if self.torch_dtype == "auto":
                dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            else:
                dtype = getattr(torch, self.torch_dtype)

            # Load tokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_id,
                trust_remote_code=True,
            )

            # Load model
            load_kwargs = {
                "torch_dtype": dtype,
                "trust_remote_code": True,
                "low_cpu_mem_usage": True,
            }

            if self.device == "auto":
                load_kwargs["device_map"] = "auto"
            if self.max_memory:
                load_kwargs["max_memory"] = self.max_memory

            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                **load_kwargs,
            )

            if self.device != "auto" and self.device != "cpu":
                self._model = self._model.to(self.device)

        except ImportError:
            raise ImportError(
                "transformers and torch are required. "
                "Install with: pip install transformers torch"
            )

    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        """Generate using loaded model."""
        self._load_model()

        inputs = self._tokenizer(prompt, return_tensors="pt")

        if hasattr(self._model, "device"):
            inputs = {k: v.to(self._model.device) for k, v in inputs.items()}

        import torch
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=0.1,
                do_sample=True,
                pad_token_id=self._tokenizer.eos_token_id,
            )

        # Decode only the new tokens
        input_length = inputs["input_ids"].shape[1]
        generated_tokens = outputs[0][input_length:]
        return self._tokenizer.decode(generated_tokens, skip_special_tokens=True)

    def is_available(self) -> bool:
        """Check if transformers is available."""
        if self._available is not None:
            return self._available

        try:
            import transformers
            import torch
            self._available = True
        except ImportError:
            self._available = False

        return self._available

    @property
    def model_name(self) -> str:
        return f"transformers:{self.model_id}"


class LlamaCppBackend(LocalInferenceBackend):
    """
    llama.cpp backend via llama-cpp-python.

    Requires: pip install llama-cpp-python
    Download GGUF model files from HuggingFace.
    """

    def __init__(
        self,
        model_path: str,
        n_ctx: int = 2048,
        n_gpu_layers: int = -1,  # -1 = all layers on GPU
        verbose: bool = False,
    ):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.verbose = verbose
        self._llm = None
        self._available: Optional[bool] = None

    def _load_model(self):
        """Lazy load model on first use."""
        if self._llm is not None:
            return

        try:
            from llama_cpp import Llama

            self._llm = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                verbose=self.verbose,
            )
        except ImportError:
            raise ImportError(
                "llama-cpp-python is required. "
                "Install with: pip install llama-cpp-python"
            )

    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        """Generate using llama.cpp."""
        self._load_model()

        output = self._llm(
            prompt,
            max_tokens=max_tokens,
            temperature=0.1,
            stop=["</s>", "\n\n\n"],
        )

        return output["choices"][0]["text"]

    def is_available(self) -> bool:
        """Check if llama.cpp is available and model exists."""
        if self._available is not None:
            return self._available

        try:
            from llama_cpp import Llama
            if os.path.exists(self.model_path):
                self._available = True
            else:
                self._available = False
        except ImportError:
            self._available = False

        return self._available

    @property
    def model_name(self) -> str:
        return f"llama.cpp:{os.path.basename(self.model_path)}"


# =============================================================================
# Local Critic Implementation
# =============================================================================


# Optimized prompt for small models - concise, structured
LOCAL_CRITIC_PROMPT = """Rate this response quality. Output ONLY JSON.

REQUEST: {prompt}

RESPONSE: {response}

Score 0.0-1.0 for each:
- coherence: logical, well-structured?
- correctness: accurate information?
- completeness: fully addresses request?
- relevance: on-topic, focused?

JSON format:
{{"coherence":0.0,"correctness":0.0,"completeness":0.0,"relevance":0.0,"issues":[],"suggestions":[]}}

OUTPUT:"""


# Even more minimal prompt for very small models
MINIMAL_CRITIC_PROMPT = """Rate response quality as JSON.
Request: {prompt}
Response: {response}
{{"coherence":X,"correctness":X,"completeness":X,"relevance":X}}
Scores (0-1):"""


class LocalCritic(QualityCritic):
    """
    Quality critic using local model inference.

    Uses small local models (Phi-3, Llama-3B, etc.) for evaluation,
    reducing costs by 100x compared to API calls.
    """

    def __init__(
        self,
        backend: LocalInferenceBackend,
        use_minimal_prompt: bool = False,
        fallback_to_rules: bool = True,
        max_response_length: int = 1000,  # Truncate long responses
    ):
        """
        Initialize local critic.

        Args:
            backend: Local inference backend (Ollama, Transformers, etc.)
            use_minimal_prompt: Use shorter prompt for faster/smaller models
            fallback_to_rules: Fall back to rule-based if local fails
            max_response_length: Max response length to evaluate (truncate)
        """
        self.backend = backend
        self.use_minimal_prompt = use_minimal_prompt
        self.fallback_to_rules = fallback_to_rules
        self.max_response_length = max_response_length
        self._rule_critic = RuleBasedCritic() if fallback_to_rules else None

    def evaluate(
        self,
        prompt: str,
        response: str,
        goal_state: Optional[Any] = None,
    ) -> QualityCritique:
        """Evaluate using local model."""
        # Truncate response if too long
        truncated_response = response
        if len(response) > self.max_response_length:
            truncated_response = response[:self.max_response_length] + "..."

        # Build evaluation prompt
        if self.use_minimal_prompt:
            eval_prompt = MINIMAL_CRITIC_PROMPT.format(
                prompt=prompt[:200],  # Truncate prompt too
                response=truncated_response,
            )
        else:
            eval_prompt = LOCAL_CRITIC_PROMPT.format(
                prompt=prompt,
                response=truncated_response,
            )

        try:
            # Generate evaluation
            result = self.backend.generate(eval_prompt, max_tokens=256)
            parsed = self._parse_response(result)
            return self._build_critique(parsed)

        except Exception as e:
            # Fall back to rule-based if configured
            if self.fallback_to_rules and self._rule_critic:
                return self._rule_critic.evaluate(prompt, response, goal_state)

            # Otherwise return moderate scores
            return QualityCritique(
                overall_score=0.6,
                coherence=0.6,
                correctness=0.6,
                completeness=0.6,
                relevance=0.6,
                revision_needed=True,
                revision_type="minor",
                issues=[f"Local evaluation failed: {str(e)}"],
                suggestions=["Review response manually"],
            )

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from local model response."""
        # Try to extract JSON
        json_match = re.search(r"\{[^{}]*\}", response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Try to extract scores manually
        scores = {}
        for key in ["coherence", "correctness", "completeness", "relevance"]:
            pattern = rf"{key}[\"']?\s*[:=]\s*([0-9.]+)"
            match = re.search(pattern, response.lower())
            if match:
                try:
                    scores[key] = float(match.group(1))
                except ValueError:
                    pass

        if scores:
            return scores

        raise ValueError("Could not parse local model response")

    def _build_critique(self, parsed: Dict[str, Any]) -> QualityCritique:
        """Build QualityCritique from parsed response."""
        coherence = min(1.0, max(0.0, float(parsed.get("coherence", 0.6))))
        correctness = min(1.0, max(0.0, float(parsed.get("correctness", 0.6))))
        completeness = min(1.0, max(0.0, float(parsed.get("completeness", 0.6))))
        relevance = min(1.0, max(0.0, float(parsed.get("relevance", 0.6))))

        overall = (coherence + correctness + completeness + relevance) / 4

        revision_needed = overall < 0.7
        if overall < 0.5:
            revision_type = "major"
        elif overall < 0.7:
            revision_type = "minor"
        else:
            revision_type = "none"

        return QualityCritique(
            overall_score=overall,
            coherence=coherence,
            correctness=correctness,
            completeness=completeness,
            relevance=relevance,
            revision_needed=revision_needed,
            revision_type=revision_type,
            issues=parsed.get("issues", []),
            suggestions=parsed.get("suggestions", []),
        )


# =============================================================================
# Cost-Aware Critic Selector
# =============================================================================


class CriticType(Enum):
    """Types of critics available."""
    RULE_BASED = "rule_based"
    LOCAL = "local"
    API = "api"
    HYBRID = "hybrid"


@dataclass
class CriticCost:
    """Cost metrics for a critic."""
    cost_per_eval: float  # USD per evaluation
    latency_ms: float  # Expected latency
    quality_score: float  # Expected quality 0-1


# Default cost estimates
CRITIC_COSTS = {
    CriticType.RULE_BASED: CriticCost(0.0, 1.0, 0.5),
    CriticType.LOCAL: CriticCost(0.0001, 150.0, 0.75),
    CriticType.API: CriticCost(0.01, 500.0, 0.9),
    CriticType.HYBRID: CriticCost(0.005, 300.0, 0.85),
}


@dataclass
class SelectionStrategy:
    """Strategy for selecting critic."""
    # Thresholds for using different critics
    complexity_threshold_local: float = 0.3  # Below this, use rules
    complexity_threshold_api: float = 0.7  # Above this, use API

    # Budget constraints
    max_cost_per_eval: float = 0.05  # Max USD per evaluation
    max_latency_ms: float = 1000.0  # Max acceptable latency

    # Quality requirements
    min_quality: float = 0.6  # Minimum acceptable quality


class CostAwareCriticSelector:
    """
    Automatically selects the most cost-effective critic.

    Selection based on:
    1. Response complexity (simple → rules, complex → API)
    2. Budget constraints
    3. Latency requirements
    4. Quality requirements
    """

    def __init__(
        self,
        rule_critic: Optional[QualityCritic] = None,
        local_critic: Optional[LocalCritic] = None,
        api_critic: Optional[QualityCritic] = None,
        strategy: Optional[SelectionStrategy] = None,
    ):
        """
        Initialize selector with available critics.

        Args:
            rule_critic: Fast rule-based critic
            local_critic: Local model critic
            api_critic: API-based critic (expensive)
            strategy: Selection strategy parameters
        """
        self.rule_critic = rule_critic or RuleBasedCritic()
        self.local_critic = local_critic
        self.api_critic = api_critic
        self.strategy = strategy or SelectionStrategy()

        # Track usage statistics
        self._usage_stats = {
            CriticType.RULE_BASED: {"count": 0, "total_time": 0.0},
            CriticType.LOCAL: {"count": 0, "total_time": 0.0},
            CriticType.API: {"count": 0, "total_time": 0.0},
        }

    def evaluate(
        self,
        prompt: str,
        response: str,
        goal_state: Optional[Any] = None,
        force_type: Optional[CriticType] = None,
    ) -> Tuple[QualityCritique, CriticType]:
        """
        Evaluate using most cost-effective critic.

        Args:
            prompt: Original prompt
            response: Response to evaluate
            goal_state: Optional goal state
            force_type: Force specific critic type

        Returns:
            Tuple of (critique, critic_type_used)
        """
        # Determine which critic to use
        if force_type:
            critic_type = force_type
        else:
            critic_type = self._select_critic(prompt, response)

        # Get the critic
        critic = self._get_critic(critic_type)

        # Evaluate with timing
        start_time = time.time()
        critique = critic.evaluate(prompt, response, goal_state)
        elapsed_ms = (time.time() - start_time) * 1000

        # Update stats
        self._usage_stats[critic_type]["count"] += 1
        self._usage_stats[critic_type]["total_time"] += elapsed_ms

        return critique, critic_type

    def _select_critic(self, prompt: str, response: str) -> CriticType:
        """Select most appropriate critic based on complexity and constraints."""
        complexity = self._estimate_complexity(prompt, response)

        # Check budget constraints
        if self.strategy.max_cost_per_eval < CRITIC_COSTS[CriticType.LOCAL].cost_per_eval:
            return CriticType.RULE_BASED

        # Check latency constraints
        if self.strategy.max_latency_ms < CRITIC_COSTS[CriticType.LOCAL].latency_ms:
            return CriticType.RULE_BASED

        # Simple responses: rule-based
        if complexity < self.strategy.complexity_threshold_local:
            return CriticType.RULE_BASED

        # Medium complexity: local if available
        if complexity < self.strategy.complexity_threshold_api:
            if self.local_critic and self.local_critic.backend.is_available():
                return CriticType.LOCAL
            return CriticType.RULE_BASED

        # High complexity: API if available and within budget
        if self.api_critic:
            if CRITIC_COSTS[CriticType.API].cost_per_eval <= self.strategy.max_cost_per_eval:
                return CriticType.API

        # Fall back to local or rules
        if self.local_critic and self.local_critic.backend.is_available():
            return CriticType.LOCAL
        return CriticType.RULE_BASED

    def _estimate_complexity(self, prompt: str, response: str) -> float:
        """
        Estimate response complexity for critic selection.

        Returns score 0.0 (simple) to 1.0 (complex).
        """
        complexity = 0.0

        # Length factor
        total_length = len(prompt) + len(response)
        if total_length > 2000:
            complexity += 0.3
        elif total_length > 500:
            complexity += 0.15

        # Technical content indicators
        technical_indicators = [
            r"\bcode\b", r"\bfunction\b", r"\bclass\b",
            r"\balgorithm\b", r"\bAPI\b", r"\bdatabase\b",
            r"```", r"\bSQL\b", r"\bJSON\b",
        ]
        for pattern in technical_indicators:
            if re.search(pattern, response, re.IGNORECASE):
                complexity += 0.05

        # Numerical/analytical content
        if re.search(r"\d+\.\d+", response):  # Decimal numbers
            complexity += 0.1
        if re.search(r"[\+\-\*\/\=]", response):  # Math operators
            complexity += 0.05

        # List/structured content
        if response.count("\n-") > 3 or response.count("\n*") > 3:
            complexity += 0.1
        if response.count("\n1.") > 2:
            complexity += 0.1

        return min(1.0, complexity)

    def _get_critic(self, critic_type: CriticType) -> QualityCritic:
        """Get critic instance by type."""
        if critic_type == CriticType.LOCAL and self.local_critic:
            return self.local_critic
        if critic_type == CriticType.API and self.api_critic:
            return self.api_critic
        return self.rule_critic

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        stats = {}
        for critic_type, data in self._usage_stats.items():
            count = data["count"]
            stats[critic_type.value] = {
                "count": count,
                "total_time_ms": data["total_time"],
                "avg_time_ms": data["total_time"] / count if count > 0 else 0,
                "estimated_cost": count * CRITIC_COSTS[critic_type].cost_per_eval,
            }
        return stats


# =============================================================================
# Factory Functions
# =============================================================================


def create_ollama_critic(
    model: str = "phi3:mini",
    host: str = "http://localhost:11434",
    fallback_to_rules: bool = True,
) -> LocalCritic:
    """
    Create a local critic using Ollama.

    Args:
        model: Ollama model name (e.g., "phi3:mini", "llama3.2:3b")
        host: Ollama server URL
        fallback_to_rules: Fall back to rule-based if Ollama unavailable

    Returns:
        LocalCritic instance
    """
    backend = OllamaBackend(model=model, host=host)
    return LocalCritic(
        backend=backend,
        fallback_to_rules=fallback_to_rules,
    )


def create_transformers_critic(
    model_id: str = "microsoft/phi-3-mini-4k-instruct",
    device: str = "auto",
    fallback_to_rules: bool = True,
) -> LocalCritic:
    """
    Create a local critic using HuggingFace Transformers.

    Args:
        model_id: HuggingFace model ID
        device: Device to load model on ("auto", "cuda", "cpu")
        fallback_to_rules: Fall back to rule-based if loading fails

    Returns:
        LocalCritic instance
    """
    backend = TransformersBackend(model_id=model_id, device=device)
    return LocalCritic(
        backend=backend,
        fallback_to_rules=fallback_to_rules,
    )


def create_llamacpp_critic(
    model_path: str,
    n_gpu_layers: int = -1,
    fallback_to_rules: bool = True,
) -> LocalCritic:
    """
    Create a local critic using llama.cpp.

    Args:
        model_path: Path to GGUF model file
        n_gpu_layers: Layers to offload to GPU (-1 = all)
        fallback_to_rules: Fall back to rule-based if loading fails

    Returns:
        LocalCritic instance
    """
    backend = LlamaCppBackend(model_path=model_path, n_gpu_layers=n_gpu_layers)
    return LocalCritic(
        backend=backend,
        fallback_to_rules=fallback_to_rules,
    )


def create_cost_aware_critic(
    local_model: str = "phi3:mini",
    api_critic: Optional[QualityCritic] = None,
    strategy: Optional[SelectionStrategy] = None,
) -> CostAwareCriticSelector:
    """
    Create a cost-aware critic selector.

    Automatically routes to the most cost-effective critic
    based on response complexity and constraints.

    Args:
        local_model: Ollama model for local inference
        api_critic: Optional API-based critic for complex cases
        strategy: Selection strategy parameters

    Returns:
        CostAwareCriticSelector instance
    """
    local_critic = create_ollama_critic(model=local_model)

    return CostAwareCriticSelector(
        rule_critic=RuleBasedCritic(),
        local_critic=local_critic,
        api_critic=api_critic,
        strategy=strategy or SelectionStrategy(),
    )
