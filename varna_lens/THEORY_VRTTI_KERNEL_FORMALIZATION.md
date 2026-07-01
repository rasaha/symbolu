# Research Note — A Vṛtti as a Markov Transition Kernel (with the Deterministic Operator as its Point-Mass Limit)

**Status:** Mathematical classification only. No implementation, no code, no experiments, no pre-registration change. Existing mathematics only. Not an evaluation of Symbol-U's truth. Stage A not modified.

**Scope:** Documents two candidate mathematical types for a vṛtti — **(B) Markov transition kernel** (general) and **(A) deterministic operator** — and their relationship. Starts from first principles; does not assume novelty.

---

## 0. Executive summary

Taking the six frozen stated properties of a vṛtti — *propensity, state-transforming, compositional, order-sensitive, finite/discrete, interpretable* — the object that satisfies **all six simultaneously and most generally** is a **Markov transition kernel** `K_σ : X ⇝ X`. Under this frame:

- **Kernel composition** (Chapman–Kolmogorov) is associative and non-commutative, and reproduces exactly the ordered "driver/passenger" composition the theory describes.
- **Deterministic operators are precisely the point-mass (Dirac) kernels** `K(·|x)=δ_{T(x)}`; deterministic-operator models — including the SO(4) **Stage-A** construction — are therefore a **strict subclass** (zero-conditional-entropy limit) of the stochastic formulation.
- The kernel frame is the categorical morphism-space `Stoch` (Kleisli category of the Giry monad); deterministic maps are its point-mass subcategory. This resolves the earlier "which category?" question concretely.

**However** (§10): the six stated properties do **not by themselves force stochasticity**. Only "propensity" hints at it, and "propensity" is ambiguous between a *probabilistic* disposition (⇒ kernel) and a *deterministic* tendency (⇒ operator). By parsimony, the extra stochastic structure is **surplus until a stated property requires representing dispersion/ambiguity** (e.g. graded meaning, polysemy, context-dependent uncertainty), which is not among the current six.

**Recommendation (§ end):** adopt the Markov kernel as the **canonical *frame* (superclass)**, because it loses nothing and makes the deterministic case a *provable special case*; but **do not assert a vṛtti is stochastic.** Keep "conditional entropy > 0 vs = 0" as the single open modeling parameter, to be decided only by whether the theory needs meaning-dispersion.

---

## 1. Do the properties imply a Markov kernel?

Map each property to a formal requirement:

| stated property | formal requirement |
|---|---|
| propensity | a **disposition** ⇒ (Popper) a probability object |
| state-transforming | acts on a state `x ∈ X` |
| compositional | closed under a composition operator |
| order-sensitive | composition **non-commutative** |
| finite/discrete | the **index set** Σ is finite (|Σ| kernels); the state space need not be |
| interpretable | each object carries a semantic label |

A *disposition that transforms a state* = a conditional law over next-states given the current state = **a Markov kernel** `K(·|x) ∈ 𝒫(X)`, measurable in `x`. Composition + order-sensitivity = **kernel composition, non-commutative**. So the properties **naturally** imply a kernel.

**Uniqueness (honest):** *not* unique. The kernel is the **most general** object meeting all six *under the probabilistic reading of "propensity."* A **deterministic operator** meets all six except that reading (it is a point-mass kernel). Unconditional distributions fail *state-transforming* and *order-sensitivity*; energy functionals fail *order-sensitivity* (they add commutatively); vectors/latent-states fail *state-transforming*. So the kernel is uniquely the **maximal** consistent type, but the deterministic operator is an equally consistent **sub-type** — the fork is entirely the stochastic-vs-deterministic reading of P1 (see §10).

---

## 2. Existing mathematics of transition kernels — genuine vs superficial

| body of math | relation |
|---|---|
| **Markov / transfer (Perron–Frobenius) & Koopman operators** | **genuine, central.** A kernel induces a linear operator on measures `p ↦ Kp` and dually on functions. Kernel composition = operator composition. This is the *linear-operator view of kernels* and is exactly the bridge to the operator/monoid picture. |
| **stochastic matrices** | **genuine** — the finite-state special case (`X` finite ⇒ `K_σ` a row-stochastic matrix). |
| **probabilistic automata / weighted FSTs** | **genuine, closest classical object.** Σ = input alphabet, each σ ↦ an input-driven stochastic transition, a word = input sequence. A vṛtti-word model *is* an input-driven Markov chain / PFA. |
| **hidden Markov models / IO-HMM** | **genuine** — Markov transitions + an **emission** map; supplies the readout (§7) and the "one state, several emissions = boundaries" structure. |
| **stochastic state-space models** | **genuine** — continuous-state version. |
| **stochastic differential equations** | genuine but the **continuous-time limit** (Fokker–Planck); a vṛtti sequence is discrete steps, so this is a limit, not the base object. |
| **diffusion models** | **partial** — composes transition kernels to generate, but indexed by **time/noise schedule**, not by a **symbol alphabet**. Structurally analogous, differently indexed. |
| **Bayesian state transitions / filtering** | **genuine** — prediction (kernel push-forward) + observation update. |
| **probabilistic programming** | **superficial as a *type*** — a *framework* that can *express* kernels; not itself the mathematical object. |

---

## 3. AI architectures already using transition kernels

| architecture | state space `X` | transition kernel | composition | readout | training |
|---|---|---|---|---|---|
| HMM / IO-HMM | finite symbolic | (input-dependent) stochastic matrix | forward algorithm / Chapman–Kolmogorov | emission distribution | EM (Baum–Welch) / gradient |
| Linear-Gaussian SSM (Kalman) | `ℝ^d` | linear-Gaussian kernel | Kalman prediction | linear-Gaussian emission | EM / gradient |
| Deep SSM (S4/Mamba) | `ℝ^d` | **deterministic** `A(x)` (point-mass limit) | scan / convolution | linear head | backprop |
| Diffusion models | data space | Gaussian transition kernels | over time steps | denoised sample / score | score matching |
| Deep Kalman / VRNN / SRNN | latent `ℝ^d` (stochastic) | learned stochastic kernel | sequential | decoder | variational (ELBO) |
| Probabilistic automata / WFST | finite | per-symbol stochastic transitions | product over the (log/prob) semiring | final weights | forward–backward |

**Closest to the vṛtti setup:** an **input-driven latent stochastic state-space model** (deep Kalman filter / IO-HMM / variational RNN): each symbol σ parameterizes a transition kernel on a latent state; meaning is emitted from the state; trained by variational inference. (Note S4/Mamba are the *deterministic-transition* members — already the point-mass limit.)

---

## 4. Composition of three vṛttis `K_c K_b K_a`

Kernel composition:
$$(K_b \circ K_a)(dx''\mid x) \;=\; \int_X K_b(dx''\mid x')\,K_a(dx'\mid x).$$

- **Associativity:** `(K_c∘K_b)∘K_a = K_c∘(K_b∘K_a)` — integration associates. ⇒ sub-words compose consistently; the kernels form a **monoid under composition** (a transition monoid), i.e. `L^*: Σ^* →` Markov-operators is a **monoid homomorphism**.
- **Non-commutativity:** `K_b∘K_a ≠ K_a∘K_b` in general (equality only when they share structure, e.g. a common eigenbasis / simultaneous diagonalisation). ⇒ order matters.
- **Chapman–Kolmogorov** *is* the composition rule; nothing extra is imposed.
- **Order emerges naturally:** applying `K_a` first (to `x`), then `K_b`, then `K_c`, maps the word's symbol order onto composition order. "Driver/passenger" = which kernel acts first vs last.

So the theory's *compositional* and *order-sensitive* properties are **exactly** the algebra of kernel composition — no additional machinery is needed to obtain sequential composition.

---

## 5. Relation to deterministic operators (point-mass kernels)

Let `K(x'\mid x) = δ(x' - T(x))`. Then
$$(K_b\circ K_a)(x''\mid x)=\int \delta(x''-T_b(x'))\,\delta(x'-T_a(x))\,dx' = \delta\big(x'' - (T_b\circ T_a)(x)\big).$$

So **composition of point-mass kernels = composition of the deterministic maps.** Therefore:

- **Deterministic operators are exactly the Dirac (zero-conditional-entropy) kernels.**
- **Deterministic-operator models are a strict subclass** of the stochastic formulation — the sub-monoid of kernels with `H(K(·|x)) = 0` for all `x`.
- Consequently *any* deterministic operator result is recoverable as the point-mass limit; the stochastic model can only add (dispersion), never lose, deterministic expressivity.

---

## 6. Minimal latent state `X`

The kernel acts on `X`; the evolving ensemble object is a distribution `p_t ∈ 𝒫(X)` with `p_{t+1}=K_{σ_t}p_t`. Candidate base spaces:

| `X` | kernel form | assessment |
|---|---|---|
| **finite symbolic set** | stochastic matrix | **minimal & most interpretable** — states = named categories; `p_t` on a simplex. Best fit to *finite/discrete* + *interpretable*. |
| Euclidean `ℝ^d` | e.g. Gaussian | richer; links to Kalman/SSM; less interpretable |
| manifold (e.g. `S³`) | e.g. heat kernel | needed only if geometric constraints are posited (this is Stage-A's carrier) |
| probability simplex as `X` | info-geometric | states *are* distributions; elegant but adds an inference layer |
| graph | structured kernel | only if states carry relational structure |

**Minimal:** a **finite symbolic `X`** (⇒ stochastic-matrix kernels, `p_t` on a simplex) is the smallest choice consistent with *finite/discrete* + *interpretable*. Euclidean/manifold are richer instances requiring extra assumptions.

---

## 7. Readout

Given `p_T` after the word:

| readout | property | note |
|---|---|---|
| **emission distribution** `∫ e(·|x)p_T(dx)` (HMM-style) | principled; order-sensitive | matches *"one state, several emission maps = boundaries"*; the natural primary readout |
| **expectation** `E_{p_T}[φ]` | differentiable vector | practical default; smooth |
| **MAP** `argmax p_T` | interpretable, discrete | non-differentiable |
| **stationary distribution** | **order-insensitive** | *discards order → contradicts P3*; usable only as a "gist," not primary |
| **entropy / functionals** | scalar summary | uncertainty of meaning |
| **learned latent head** | flexible | least interpretable |

Recommended primary: **emission/observation readout** (HMM-style), because it is order-preserving and directly models "boundaries" as distinct emission maps on one shared state. Stationary-distribution readout is explicitly *inconsistent* with the order-sensitivity property.

---

## 8. Does this reproduce Stage A?

Stage A: `M_σ = exp(Σ_j f_{σ,j} G_j) ∈ SO(4)`, word = ordered product acting on `ℝ⁴/S³`.

- **In kernel terms:** SO(4) maps are deterministic, measure-preserving, orthogonal ⇒ **point-mass kernels** `K_σ(·|x)=δ_{M_σ x}`.
- **What survives:** ordered (non-commutative) composition; the operator-monoid / homomorphism structure; the manifold carrier `S³`; input-indexed generators; the Lie parameterization.
- **What disappears (present in kernels, absent in Stage A):** stochasticity (conditional entropy = 0), representation of *uncertainty/ambiguity of meaning*, *non-invertible* transformations (SO(4) is invertible), and *dissipative/contractive* dynamics (orthogonal maps preserve norm; general kernels can contract toward a stationary law).
- **What becomes a limit:** Stage A **is** the (deterministic ∩ measure-preserving ∩ orthogonal ∩ Lie-parameterized) special case.

So the kernel formulation **strictly generalizes Stage A**, and it makes explicit *what Stage A discarded* (dispersion, contraction, non-invertibility) — which is informative regardless of whether those features are needed.

---

## 9. Strengths and weaknesses (no advocacy)

| axis | kernel formulation |
|---|---|
| elegance | high — unifies distribution + operator; special cases fall out cleanly |
| expressive power | high — strictly generalizes deterministic operators; can encode ambiguity, contraction, non-invertibility |
| identifiability | **worse** — more parameters; latent + stochastic models are notoriously under-identified (HMM/SSM symmetries) |
| interpretability | mixed — stochastic matrix over a finite symbolic `X` is interpretable; high-dim continuous kernels are not |
| computational cost | **higher** — composition = integration; latent filtering/variational inference vs a plain matmul |
| trainability | **harder** — variational/EM, higher-variance gradients, vs backprop for deterministic operators |
| existing precedent | strong — HMM, SSM, diffusion, deep Kalman filters all train at scale |
| LLM compatibility | **partial** — mainstream LLMs are deterministic; Mamba/S4 are the closest and are *deterministic-transition*; stochastic-latent sequence models are off the mainstream path |

---

## 10. Failure modes (attempt to falsify)

- **Does "propensity" necessarily imply probability?** **No.** Popper's *propensity* is probabilistic, but ordinary "propensity/tendency" can be a *deterministic characteristic disposition* (always manifests the same way). The probabilistic reading is a **choice**, not forced by the word.
- **Could "propensity" be a deterministic tendency?** Yes — then the point-mass kernel (= operator) suffices and the stochastic apparatus adds nothing observable.
- **Are kernels unnecessary machinery?** Possibly. If the theory never *uses* uncertainty/dispersion, then a kernel and its mean/mode map are empirically indistinguishable, making the stochastic surplus **unfalsifiable**.
- **Richer than needed?** Given only the six stated properties — **yes.** None of the six *requires* representing dispersion; only "propensity" hints at it, ambiguously.
- **Simpler formulation for the same properties?** **Yes** — the deterministic operator (point-mass kernel) satisfies all six except the (possibly unintended) probabilistic reading of P1. By Occam, it is the simpler adequate model.

**Net:** the six properties **do not justify** *asserting* stochasticity. The kernel is the correct *generalization*, but its extra structure is warranted only if a **seventh property** requiring dispersion (graded/ambiguous/context-uncertain meaning) is added.

---

## Unresolved assumptions

1. **Stochastic vs deterministic ("is `H(K(·|x)) > 0`?").** The single open modeling parameter; everything else is downstream. Resolvable only by whether the theory needs meaning-dispersion — a property not currently stated.
2. **Base state space `X`** (finite-symbolic minimal vs Euclidean/manifold richer).
3. **Kernel family** (arbitrary vs Gaussian vs stochastic-matrix vs orthogonal-deterministic).
4. **Readout** (emission vs expectation vs MAP), and whether "boundaries" = distinct emission maps.
5. **Carrier / composition base point** and whether composition is a strict monoid homomorphism.

## Recommendation

Adopt the **Markov transition kernel as the canonical *frame* (superclass)** for a vṛtti, **but not as an assertion of stochasticity.** Rationale:

- It **loses nothing**: deterministic operators (and Stage A) are the provable point-mass sub-case, recoverable exactly.
- It **makes the real question explicit and testable-by-definition**: "is conditional entropy zero?" — i.e., is a vṛtti a deterministic operator or a genuinely dispersive kernel?
- It **matches the user's strategy** (start general; collapse if warranted) while **respecting parsimony** (do not claim the stochastic structure until a stated property uses it).

Concretely: **treat a vṛtti as `K_σ` with the deterministic operator as the default *instance* (zero conditional entropy) until a stated property requires dispersion.** The kernel is the canonical *frame*; the deterministic operator is the canonical *first instance*. It should **remain a frame-with-open-parameter, not a finished ontology**, until assumption (1) above is committed.

> structure, not validated meaning.
