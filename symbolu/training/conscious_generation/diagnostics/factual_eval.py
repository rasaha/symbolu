"""
Factual Evaluation Probes for Conscious Generation Training.

Feeds paired fact/hallucination sentences through the model and checks
whether CG primitives (JEPA + Vritti) can distinguish them. This is the
real proof that auxiliaries are changing embeddings in the right direction.

Metrics:
  1. JEPA separation    — do factual continuations get higher JEPA scores?
  2. Vritti FACT ratio   — does Vritti assign higher P(FACT) to true statements?
  3. Vritti ERROR ratio   — does Vritti assign higher P(ERROR) to hallucinations?
  4. Bliss separation    — do factual tokens get higher coherence (Bliss)?
  5. Aggregate accuracy   — binary classification: can the primitives tell them apart?

Usage:
    --enable_factual_eval               Master toggle
    --factual_eval_interval 500         Steps between eval runs (default: 500)
    --factual_eval_probes 50            Number of probe pairs per eval (default: 50)
"""

from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


# ── Built-in Probe Dataset ──────────────────────────────────────────────
# Each entry: (context, factual_continuation, hallucinated_continuation)
# Covers: physical plausibility, common knowledge, temporal, causal, numerical

FACTUAL_PROBES: List[Tuple[str, str, str]] = [
    # Physical plausibility (JEPA should catch these)
    ("He dropped the glass on the floor and it", " shattered into pieces.", " floated up to the ceiling."),
    ("She placed the ice cube in the sun and it", " melted within minutes.", " grew larger and froze solid."),
    ("The heavy rock was thrown into the lake and it", " sank to the bottom.", " bounced back into the air."),
    ("Water was heated to 100 degrees Celsius and it", " began to boil.", " turned into ice."),
    ("The candle was left burning all night and the wax", " slowly melted down.", " expanded and grew taller."),
    ("He released the balloon filled with helium and it", " floated upward.", " fell straight to the ground."),
    ("The metal spoon was left in hot soup and it", " became hot to touch.", " stayed completely cold."),
    ("She left the milk out of the fridge for days and it", " spoiled and smelled bad.", " became fresher over time."),
    ("The car ran out of fuel and it", " stopped on the road.", " accelerated to full speed."),
    ("He turned off the lamp and the room", " became dark.", " became brighter than before."),

    # Common knowledge (Vritti FACT vs ERROR)
    ("The capital of France is", " Paris, a city on the Seine.", " Toronto, a city in Canada."),
    ("The Earth orbits around", " the Sun once per year.", " the Moon once per week."),
    ("Water is composed of", " hydrogen and oxygen atoms.", " iron and copper atoms."),
    ("Humans need oxygen to", " breathe and survive.", " photosynthesize like plants."),
    ("The speed of light is approximately", " 300,000 kilometers per second.", " 300 meters per hour."),
    ("The Pacific Ocean is the", " largest ocean on Earth.", " smallest ocean on Earth."),
    ("DNA carries the", " genetic instructions for life.", " electrical charge of atoms."),
    ("Mount Everest is located in", " the Himalayas between Nepal and Tibet.", " the Sahara Desert in Africa."),
    ("Antibiotics are used to treat", " bacterial infections.", " broken bones and fractures."),
    ("The human heart pumps", " blood throughout the body.", " air into the lungs directly."),

    # Temporal / causal reasoning
    ("After planting the seed and watering it for weeks, a", " small sprout appeared.", " fully grown tree appeared overnight."),
    ("The student studied hard for months and", " passed the exam.", " forgot everything she ever knew."),
    ("Winter comes after autumn and before", " spring in the seasonal cycle.", " summer, skipping spring entirely."),
    ("She put bread in the toaster and after two minutes it", " was golden and toasted.", " was raw and frozen."),
    ("He trained for the marathon every day for a year and", " completed the race.", " could no longer walk at all."),

    # Numerical / quantitative
    ("A triangle has exactly", " three sides and three angles.", " five sides and seven angles."),
    ("There are approximately 7 billion", " people living on Earth.", " stars inside the Earth."),
    ("A standard deck of playing cards contains", " 52 cards in four suits.", " 100 cards in ten suits."),
    ("One kilometer is equal to", " 1000 meters.", " 10 meters."),
    ("A year on Earth lasts approximately", " 365 days.", " 30 days."),

    # Biological facts
    ("Photosynthesis in plants converts sunlight into", " chemical energy stored in glucose.", " metallic compounds like iron ore."),
    ("Birds are the only living animals that have", " feathers.", " six legs."),
    ("The liver is responsible for", " filtering toxins from the blood.", " pumping blood through the body."),
    ("Mammals give birth to live young and", " nurse them with milk.", " abandon them immediately at birth."),
    ("Cats are obligate carnivores, meaning they", " need meat to survive.", " only eat vegetables and grains."),

    # Historical
    ("World War II ended in", " 1945 after the surrender of Japan.", " 1820 after the fall of Rome."),
    ("The first moon landing occurred in", " 1969 when Apollo 11 landed.", " 2005 when SpaceX launched."),
    ("The printing press was invented by", " Johannes Gutenberg around 1440.", " Albert Einstein in 1905."),
    ("The Berlin Wall fell in", " 1989, reunifying East and West Germany.", " 1776 during the American Revolution."),
    ("Penicillin was discovered by", " Alexander Fleming in 1928.", " Isaac Newton in 1687."),

    # Material / chemical properties
    ("Gold is a metal that does not", " rust or corrode easily.", " exist in solid form at room temperature."),
    ("Glass is made primarily from", " silica sand heated to high temperatures.", " compressed cotton fibers."),
    ("Iron exposed to moisture will", " develop rust over time.", " become transparent."),
    ("Diamonds are formed from", " carbon under extreme pressure.", " liquid nitrogen at low pressure."),
    ("Salt dissolves in", " water readily at room temperature.", " oil more easily than in water."),

    # Everyday physics
    ("Sound travels faster through", " water than through air.", " vacuum than through any material."),
    ("A shadow forms when an object", " blocks light from a source.", " emits its own light outward."),
    ("Friction between surfaces causes them to", " heat up and resist motion.", " become frictionless and slippery."),
    ("Magnets attract", " iron and certain metals.", " wood and plastic equally."),
    ("Hot air rises because it is", " less dense than cool air.", " heavier than cool air."),
]


class FactualEval:
    """
    Runs factual probe evaluation during training to verify CG primitives
    can distinguish facts from hallucinations.
    """

    def __init__(
        self,
        interval: int = 500,
        num_probes: int = 50,
        start_step: int = 0,
    ):
        self.interval = interval
        self.num_probes = min(num_probes, len(FACTUAL_PROBES))
        self.start_step = start_step
        self.history: List[Dict[str, float]] = []

        # Select probes (deterministic)
        self._probes = FACTUAL_PROBES[:self.num_probes]

    @torch.no_grad()
    def evaluate(
        self,
        model: nn.Module,
        tokenizer: Any,
        global_step: int,
        token_cache: Optional[Any] = None,
    ) -> Optional[Dict[str, float]]:
        """
        Run factual probes through the model and score with CG primitives.

        Returns:
            Dict of evaluation metrics, or None if not an eval step.
        """
        if global_step % self.interval != 0:
            return None
        if global_step < self.start_step:
            return None
        if tokenizer is None:
            return None

        metrics: Dict[str, float] = {"step": global_step}

        # Unwrap DDP if needed
        raw_model = getattr(model, 'module', model)
        device = next(raw_model.parameters()).device
        was_training = raw_model.training
        raw_model.eval()

        try:
            jepa_fact_scores = []
            jepa_hallu_scores = []
            vritti_fact_on_fact = []     # P(FACT) for factual continuations
            vritti_fact_on_hallu = []    # P(FACT) for hallucinated continuations
            vritti_error_on_fact = []    # P(ERROR) for factual continuations
            vritti_error_on_hallu = []   # P(ERROR) for hallucinated continuations
            bliss_fact_scores = []
            bliss_hallu_scores = []

            has_tet = (hasattr(raw_model, 'conscious_gen')
                       and 'token_eval_tensor' in raw_model.conscious_gen)
            has_bliss = (hasattr(raw_model, 'conscious_gen')
                         and 'bliss_gate' in raw_model.conscious_gen)
            has_kosha = (hasattr(raw_model, 'conscious_gen')
                         and 'kosha_router' in raw_model.conscious_gen)

            if not has_tet:
                metrics["status"] = -1  # no TET available
                return metrics

            _tet = raw_model.conscious_gen['token_eval_tensor']
            _cache = raw_model.conscious_gen.get('token_cache', token_cache)
            _bliss = raw_model.conscious_gen.get('bliss_gate', None)
            _kosha = raw_model.conscious_gen.get('kosha_router', None)
            _integ = raw_model.conscious_gen.get('integrated_scorer', None)

            for context, fact_cont, hallu_cont in self._probes:
                fact_text = context + fact_cont
                hallu_text = context + hallu_cont

                # Tokenize both
                fact_enc = tokenizer(
                    fact_text, return_tensors="pt",
                    truncation=True, max_length=128, padding=False,
                )
                hallu_enc = tokenizer(
                    hallu_text, return_tensors="pt",
                    truncation=True, max_length=128, padding=False,
                )

                fact_ids = fact_enc["input_ids"].to(device)
                hallu_ids = hallu_enc["input_ids"].to(device)

                # Forward pass — get hidden states + sovereign state
                fact_out = raw_model(
                    fact_ids,
                    attention_mask=fact_enc.get("attention_mask", None),
                    return_last_hidden=True,
                )
                hallu_out = raw_model(
                    hallu_ids,
                    attention_mask=hallu_enc.get("attention_mask", None),
                    return_last_hidden=True,
                )

                if not isinstance(fact_out, dict) or not isinstance(hallu_out, dict):
                    continue

                fact_hidden = fact_out.get('last_hidden_state')
                fact_state = fact_out.get('state')
                fact_logits = fact_out.get('logits')
                hallu_hidden = hallu_out.get('last_hidden_state')
                hallu_state = hallu_out.get('state')
                hallu_logits = hallu_out.get('logits')

                if any(v is None for v in [
                    fact_hidden, fact_state, fact_logits,
                    hallu_hidden, hallu_state, hallu_logits,
                ]):
                    continue

                # Sovereign state is [B, 32], need to expand to [B, T, 32]
                fact_sov = fact_state.unsqueeze(1).expand(-1, fact_hidden.shape[1], -1)
                hallu_sov = hallu_state.unsqueeze(1).expand(-1, hallu_hidden.shape[1], -1)

                # Build Token Evaluation Tensors
                fact_tet = _tet(
                    logits=fact_logits.detach(),
                    hidden=fact_hidden,
                    o_ctx=fact_sov,
                    cache=_cache,
                )
                hallu_tet = _tet(
                    logits=hallu_logits.detach(),
                    hidden=hallu_hidden,
                    o_ctx=hallu_sov,
                    cache=_cache,
                )

                # T shape: [1, T, K, 6] — columns: base, ont, jepa, csr, vritti, guna
                fact_T = fact_tet['T']      # [1, T, K, 6]
                hallu_T = hallu_tet['T']    # [1, T, K, 6]

                # Find which candidate is the actual next token (for continuation part)
                # We evaluate the last token of context and continuation tokens
                ctx_len = len(tokenizer(context, truncation=True, max_length=128)["input_ids"])

                # Average primitive scores over continuation tokens for the top candidate
                # (index 0 in the shortlist = highest base logit candidate)
                if fact_T.shape[1] > ctx_len:
                    # JEPA scores (column 2) — averaged over continuation positions
                    fact_jepa = fact_T[0, ctx_len:, 0, 2].mean().item()  # top candidate
                    hallu_jepa = hallu_T[0, ctx_len:, 0, 2].mean().item()
                    jepa_fact_scores.append(fact_jepa)
                    jepa_hallu_scores.append(hallu_jepa)

                    # Vritti scores (column 4) — but we need the distribution, not the scalar
                    # Use the vritti scorer directly for richer info
                    vritti_scorer = raw_model.conscious_gen.get('vritti_scorer', None)
                    if vritti_scorer is not None:
                        # Get context Vritti distribution for continuation tokens
                        fact_v_ctx = vritti_scorer.compute_context_repr(
                            fact_hidden[0, ctx_len:],
                            fact_sov[0, ctx_len:],
                        )  # [T_cont, 5]
                        hallu_v_ctx = vritti_scorer.compute_context_repr(
                            hallu_hidden[0, ctx_len:],
                            hallu_sov[0, ctx_len:],
                        )  # [T_cont, 5]

                        # Average over continuation tokens
                        # Vritti classes: [FACT=0, ERROR=1, IMAGINATION=2, VOID=3, MEMORY=4]
                        fact_v_mean = fact_v_ctx.mean(dim=0)   # [5]
                        hallu_v_mean = hallu_v_ctx.mean(dim=0)  # [5]

                        vritti_fact_on_fact.append(fact_v_mean[0].item())
                        vritti_fact_on_hallu.append(hallu_v_mean[0].item())
                        vritti_error_on_fact.append(fact_v_mean[1].item())
                        vritti_error_on_hallu.append(hallu_v_mean[1].item())

                    # Bliss scores via integrated scorer
                    if _bliss is not None and _kosha is not None:
                        # Compute Kosha weights
                        fact_alpha = _kosha(fact_hidden[0, ctx_len:], fact_sov[0, ctx_len:])
                        hallu_alpha = _kosha(hallu_hidden[0, ctx_len:], hallu_sov[0, ctx_len:])

                        # Bliss on the top candidate
                        fact_B = _bliss(fact_T[0, ctx_len:, 0:1, :], fact_alpha)
                        hallu_B = _bliss(hallu_T[0, ctx_len:, 0:1, :], hallu_alpha)

                        bliss_fact_scores.append(fact_B.mean().item())
                        bliss_hallu_scores.append(hallu_B.mean().item())

            # ── Aggregate metrics ────────────────────────────────────
            n = len(jepa_fact_scores)
            metrics["num_probes_evaluated"] = n

            if n > 0:
                # JEPA separation
                jepa_fact_mean = sum(jepa_fact_scores) / n
                jepa_hallu_mean = sum(jepa_hallu_scores) / n
                metrics["jepa_fact_mean"] = jepa_fact_mean
                metrics["jepa_hallu_mean"] = jepa_hallu_mean
                metrics["jepa_separation"] = jepa_fact_mean - jepa_hallu_mean
                # Binary accuracy: what fraction of probes has JEPA_fact > JEPA_hallu?
                jepa_correct = sum(
                    1 for f, h in zip(jepa_fact_scores, jepa_hallu_scores) if f > h
                )
                metrics["jepa_accuracy"] = jepa_correct / n

            if vritti_fact_on_fact:
                nv = len(vritti_fact_on_fact)
                metrics["vritti_P_FACT_on_fact"] = sum(vritti_fact_on_fact) / nv
                metrics["vritti_P_FACT_on_hallu"] = sum(vritti_fact_on_hallu) / nv
                metrics["vritti_P_ERROR_on_fact"] = sum(vritti_error_on_fact) / nv
                metrics["vritti_P_ERROR_on_hallu"] = sum(vritti_error_on_hallu) / nv
                # Vritti separation: P(FACT|fact) - P(FACT|hallu) should be positive
                metrics["vritti_fact_separation"] = (
                    sum(vritti_fact_on_fact) / nv - sum(vritti_fact_on_hallu) / nv
                )
                # Vritti accuracy: P(FACT|fact) > P(FACT|hallu)?
                vritti_correct = sum(
                    1 for f, h in zip(vritti_fact_on_fact, vritti_fact_on_hallu) if f > h
                )
                metrics["vritti_accuracy"] = vritti_correct / nv

            if bliss_fact_scores:
                nb = len(bliss_fact_scores)
                metrics["bliss_fact_mean"] = sum(bliss_fact_scores) / nb
                metrics["bliss_hallu_mean"] = sum(bliss_hallu_scores) / nb
                metrics["bliss_separation"] = (
                    sum(bliss_fact_scores) / nb - sum(bliss_hallu_scores) / nb
                )

            # Overall composite accuracy (JEPA + Vritti vote)
            if n > 0 and vritti_fact_on_fact:
                combined_correct = 0
                nmin = min(n, len(vritti_fact_on_fact))
                for i in range(nmin):
                    jepa_vote = jepa_fact_scores[i] > jepa_hallu_scores[i]
                    vritti_vote = vritti_fact_on_fact[i] > vritti_fact_on_hallu[i]
                    # Majority: either primitive agrees
                    if jepa_vote or vritti_vote:
                        combined_correct += 1
                metrics["combined_accuracy"] = combined_correct / nmin
                # Strict: both must agree
                strict_correct = sum(
                    1 for i in range(nmin)
                    if (jepa_fact_scores[i] > jepa_hallu_scores[i]
                        and vritti_fact_on_fact[i] > vritti_fact_on_hallu[i])
                )
                metrics["strict_accuracy"] = strict_correct / nmin

        except Exception as e:
            metrics["error"] = str(e)[:200]

        finally:
            if was_training:
                raw_model.train()

        self.history.append(metrics)
        return metrics

    def get_trend_summary(self, last_n: int = 5) -> Dict[str, str]:
        """Human-readable trend from recent evals."""
        summary: Dict[str, str] = {}
        if len(self.history) < 2:
            summary["status"] = "insufficient_data"
            return summary

        recent = [h for h in self.history[-last_n:] if "error" not in h]
        if not recent:
            summary["status"] = "all_recent_errored"
            return summary

        # JEPA accuracy trend
        jepa_accs = [h["jepa_accuracy"] for h in recent if "jepa_accuracy" in h]
        if jepa_accs:
            latest = jepa_accs[-1]
            if latest < 0.55:
                summary["jepa"] = f"RANDOM ({latest:.1%}) — not distinguishing facts"
            elif latest < 0.70:
                summary["jepa"] = f"WEAK ({latest:.1%}) — slight signal"
            elif latest < 0.85:
                summary["jepa"] = f"MODERATE ({latest:.1%}) — learning"
            else:
                summary["jepa"] = f"STRONG ({latest:.1%}) — reliably separating"

            # Trend direction
            if len(jepa_accs) >= 3:
                early = sum(jepa_accs[:len(jepa_accs)//2]) / max(len(jepa_accs)//2, 1)
                late = sum(jepa_accs[len(jepa_accs)//2:]) / max(len(jepa_accs) - len(jepa_accs)//2, 1)
                if late > early + 0.03:
                    summary["jepa"] += " (improving)"
                elif late < early - 0.03:
                    summary["jepa"] += " (degrading)"

        # Vritti accuracy trend
        vritti_accs = [h["vritti_accuracy"] for h in recent if "vritti_accuracy" in h]
        if vritti_accs:
            latest = vritti_accs[-1]
            if latest < 0.55:
                summary["vritti"] = f"RANDOM ({latest:.1%})"
            elif latest < 0.70:
                summary["vritti"] = f"WEAK ({latest:.1%})"
            elif latest < 0.85:
                summary["vritti"] = f"MODERATE ({latest:.1%})"
            else:
                summary["vritti"] = f"STRONG ({latest:.1%})"

        # Combined accuracy
        combined = [h["combined_accuracy"] for h in recent if "combined_accuracy" in h]
        if combined:
            summary["combined"] = f"{combined[-1]:.1%}"

        return summary

    def format_console_log(self, metrics: Dict[str, float]) -> str:
        """Format eval results as a concise console log."""
        parts = [f"  [FACTUAL-EVAL] Step {int(metrics.get('step', 0))}"]
        parts.append(f"probes={int(metrics.get('num_probes_evaluated', 0))}")

        if "error" in metrics:
            parts.append(f"ERROR: {metrics['error'][:80]}")
            return " | ".join(parts)

        if "jepa_accuracy" in metrics:
            parts.append(f"JEPA acc={metrics['jepa_accuracy']:.1%}")
            parts.append(f"sep={metrics['jepa_separation']:.4f}")
        if "vritti_accuracy" in metrics:
            parts.append(f"Vritti acc={metrics['vritti_accuracy']:.1%}")
            parts.append(
                f"P(FACT): fact={metrics['vritti_P_FACT_on_fact']:.3f}"
                f" hallu={metrics['vritti_P_FACT_on_hallu']:.3f}"
            )
        if "bliss_separation" in metrics:
            parts.append(f"Bliss sep={metrics['bliss_separation']:.4f}")
        if "combined_accuracy" in metrics:
            parts.append(f"combined={metrics['combined_accuracy']:.1%}")
        if "strict_accuracy" in metrics:
            parts.append(f"strict={metrics['strict_accuracy']:.1%}")

        return " | ".join(parts)
