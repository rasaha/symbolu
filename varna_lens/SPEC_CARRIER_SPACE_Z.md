# SPEC — The Acoustic State Space `Z` (carrier; foundational)

> **Status:** foundational specification. **Date:** 2026-06-25.
> **Scope:** defines the **carrier space `Z`** only. **No operators.** Composition, resonance, emergence,
> cancellation, attenuation, amplification are out of scope; every future operator must be defined *on this
> carrier* and respect the equivalence fixed here (§4). This document is representation-independent: the
> current JSON/Python is one *model* of the object defined below, not the object.

## 0. Critique of the guiding intuition

The intuition — *"define `Z` before any operator; this matters more than proposing operators"* — is correct
and is standard mathematical practice (vector spaces precede linear maps; manifolds precede connections).

One correction, which shapes everything: **defining the carrier is not defining a bare set.** A bare set is
vacuous and merely defers the real commitments. The content of a carrier lives in its **equivalence
relation** (when are two elements *the same*?) and its **admissibility** (what counts as an element at all?).
These two choices pre-determine the congruence and closure obligations of *every* future operator. So this
spec fixes, as primitives, a finite typed alphabet, an attribute map, an admissibility predicate, and a
**deterministic reading map** whose kernel *is* the equivalence relation. The metric is deliberately left
optional (§5): committing to a metric early silently pre-decides operator behavior.

## 1. Primitive data (the presentation of `Z`)

`Z` is **presented** by a tuple `𝒫 = (Σ, τ, A, λ, Adm, ρ)`. All six are finite/decidable data; any concrete
software (JSON table, tensor embedding, symbolic term) is a *model* of `𝒫` (§7–§8).

- **(D1) Typed alphabet.** A finite set `Σ` of **varṇa types** with a type function `τ : Σ → {C, V}`.
  Write `Σ_C = τ⁻¹(C)`, `Σ_V = τ⁻¹(V)`; both nonempty. (In the current model `|Σ| = 46`.)
- **(D2) Attribute set + lexicon map.** A finite set `A` of **pole-attributes** and a total map
  `λ : Σ → A × A`, `λ(x) = (β(x), ℓ(x))` = (binding-attribute, liberating-attribute) of `x`.
  `λ` is the *lexicon*; it is a **parameter** of the presentation, not part of its structure (§7, relabeling).
- **(D3) Strings.** `S = Σ*`, the set of finite sequences over `Σ` (order primitive; `ε` = empty string).
- **(D4) Admissibility.** A decidable predicate `Adm ⊆ S` of **well-formed acoustic strings**: `w ∈ Adm`
  iff `w` is parseable as a varṇa sequence and the reading `ρ` (D5) is total on `w` (every symbol in `Σ`;
  no undefined positions). `Adm` is a language over `Σ` (regular/decidable). `ε`-handling: see §3.
- **(D5) Reading map.** A **deterministic, total** map `ρ : Adm → R` into the *read-space* `R`. For
  `w = x₁…xₙ`,
  `ρ(w) = ( (x₁,s₁,a₁), …, (xₙ,sₙ,aₙ) ; e )`,
  where `sᵢ ∈ {+,−}` is the **polarity** assigned to position `i`, `aᵢ ∈ A` is the **selected attribute**
  (`aᵢ = ℓ(xᵢ)` if `sᵢ=+`, `aᵢ = β(xᵢ)` if `sᵢ=−`, with the V/C reading conventions), and
  `e ∈ ({+,−}×A) ∪ {⊥}` is the optional **whole-word essence**. `ρ` depends **only** on `w` (determinism)
  and is **position-respecting** (the `sᵢ` are a fixed function of the string and its positional structure).
  The carrier needs only that `ρ` *exists, is deterministic, total on `Adm`*; its internal rule (the
  vowel-attachment mechanism) is not part of `Z`'s identity — future operators may read it, `Z` does not.

## 2. Elements and coordinates (Q1, Q2)

**(Q1) What is an element of `Z`?** An **equivalence class of admissible ordered varṇa-strings, canonically
represented by its deterministic reading** — i.e., a *graded labeled sequence*, an element of a quotient of
the free monoid `Σ*`. Concretely:

> `Z := Adm / ≡`,  where  `w ≡ w'  :⇔  ρ(w) = ρ(w')`,  with canonical representative `ρ(w) ∈ R`.

So `Z ≅ ρ(Adm) ⊆ R`. Against the menu offered: **not** a single varṇa (too small for composition), **not**
a syllable (essence is whole-word), **not** a flat sequence (polarity/parse structure is intrinsic), **not**
a graph (over-rich), **not** a tensor (that is a *representation*, §7). The right object is an **ordered
sequence modulo reading-equivalence** — a labeled string / element of a quotient free monoid. Syllabic/CV
structure is **derived** (a function of the string), not primitive.

**(Q2) Coordinates — intrinsic vs. extrinsic.** Split each state into a **free part** and a **determined
part**. Only the free part carries degrees of freedom; everything else is a function of it.

| Coordinate | Status |
|---|---|
| atom sequence `x₁…xₙ` (which varṇas, in order) | **intrinsic, free** |
| length `n` | intrinsic (grading, §6) |
| polarity/sign pattern `s₁…sₙ` | **intrinsic, determined** (function of the string via `ρ`) |
| attribute string `a₁…aₙ` | intrinsic, determined |
| whole-word essence `e` | intrinsic, determined |
| aggregate valence (vote counts) | **derived projection** of `(s₁…sₙ,e)` — not a free axis |
| varga / place-of-articulation, elemental, guṇa, vṛtti-name, deva | **extrinsic** — a metadata fiber `M→Z` (§9), *not* part of identity |
| referential meaning, speaker, prosody, position in a larger utterance | **extrinsic** — context, never in `Z` |

The intrinsic coordinate system of one state is thus `(x_{1:n}, s_{1:n}, a_{1:n}, e)`, of which only
`x_{1:n}` is free; the rest is `ρ` applied to it.

## 3. Equivalence and canonical form (Q3)

- **Equality.** `[w] = [w']` in `Z` iff `ρ(w) = ρ(w')`. Two surface strings (e.g. spelling/romanization
  variants) that produce the identical reading are the **same state**.
- **`≡` is an equivalence relation** by construction (kernel of a function), hence reflexive, symmetric,
  transitive.
- **Canonical form.** Each class has the normal form `ρ(w) ∈ R`. Equality in `Z` = identity of normal forms.
  Since `ρ` is computable and `R` has decidable equality (finite tuples over `Σ×{+,−}×A`), **equality in `Z`
  is decidable** — the property every future operator needs to be checked for well-definedness (congruence).
- **Similarity ≠ equality.** Graded closeness is the *metric* (§5), a separate, optional structure. Equality
  is the quotient; similarity is distance.
- **Empty/identity element.** Reserve `𝟘 := ρ(ε)` (empty reading) as a distinguished **formal** element of
  the completion `Z⁰ = Z ∪ {𝟘}`, to host a future operator's identity *without asserting any operation now*.
  **Acoustic** states are the positive-length classes `Z⁺ = Z ∖ {𝟘}`; `Z⁺` is the object of interest.

## 4. The congruence obligation (what `Z` imposes on all future operators)

This is the foundational payload. Because `Z = Adm/≡`, **any future operator must be well-defined on
classes**: if `w ≡ u` and `w' ≡ u'` then the operator's output on `(w,w')` and `(u,u')` must be `≡`. I.e.,
operators must factor through `ρ` (the reading), never depend on surface spelling. `Z` fixes this obligation
in advance; an operator that violates it is not an operator on `Z` at all.

## 5. Metric (Q4) — optional, not canonical

`Z` does **not** require a metric (groups, monoids have none). A metric is *layered, optional* structure,
and there is **no single canonical choice** — different tasks/operators may need different ones. An admissible
(pseudo)metric `d` on `Z` must be **well-defined on classes**: `d([w],[w']) = 0 ⇔ [w]=[w']`. Candidate
families, kept explicitly separate:

- **phonological** — edit distance over `Σ` (substitution costs from articulatory features); preserves "sounds alike".
- **structural** — distance over sign-pattern / parse skeleton; preserves "same shape".
- **functional** — distance over attribute-strings `a_{1:n}` and essence `e`; preserves "same reading-content".
- **operator-behavioral** — deferred (no operators yet).

These need **not** coincide. *What a metric should preserve* is itself an empirical/modeling question,
answered later by homomorphism/leverage tests — **not** fixed here. The only axiomatic requirement is
compatibility with `≡` (above). No metric is asserted as part of `Z`.

## 6. Closure / admissibility (Q5)

The closure boundary is a property of the carrier, independent of operators. `c ∈ R` is a **valid acoustic
state** iff `c` is the reading of an admissible string:

> `c ∈ Z  ⇔  ∃ w ∈ Adm. ρ(w) = c`.

So a future `compose(a,b) = c` yields a valid state **iff its underlying string is admissible** (parseable
over `Σ`, total reading) — i.e. `c ∈ ρ(Adm)`. A result that is "merely another word" but contains non-varṇa
atoms, an unparseable cluster, or an undefined reading is **not** in `Z`; an operation producing it is
**not internal**, and either the operation or `Adm` must be revised. Because `Adm` is decidable and `ρ`
total on it, **membership in `Z` is decidable** and **graded**:

> `Z⁺ = ⊔_{n≥1} Z_n`,  with each `Z_n = ρ(Adm ∩ Σ^n)` **finite** (since `Σ, A` finite).

`Z` is therefore a countable, decidable, length-graded combinatorial set — supporting induction on `n`.

## 7. Representation independence (Q6)

Drop the JSON entirely; what survives is exactly the presentation `𝒫 = (Σ, τ, A, λ, Adm, ρ)` as **abstract
data**: a finite typed alphabet, a finite attribute set, a fixed labeling map, a decidable admissibility
language, and a deterministic position-respecting reading. JSON records, tensor embeddings, and symbolic
terms are **models** of `𝒫`; `Z` is the quotient they all present. Two models that preserve `𝒫` as a typed
structure yield **isomorphic** `Z`.

Two invariance facts pin down what is *structure* vs. *gauge*:

- **Content is gauge (relabeling-invariance).** Let `π : A → A` be a bijection and replace `λ` by `π∘λ`.
  The induced map on `Z` (carry every selected attribute `aᵢ ↦ π(aᵢ)`) is an **isomorphism**. Hence the
  *values* in `A` (the specific binding/liberating glosses) are **not** structural — only the *pattern* of
  which-pole-where is. This is the project's relabeling theorem, here as a property of the carrier itself.
- **Implementation is gauge.** Float coordinates, key strings, file formats added by a model are
  non-canonical; the **invariants** any faithful model must preserve are exactly
  `(x_{1:n}, s_{1:n}, a_{1:n}, e, n)` and the equivalence `≡`.

## 8. Category-theoretic formulation (Q7)

Let **TypedAlph** be the category of finite typed alphabets `(Σ, τ)` (morphisms: type-preserving maps).
Let `(-)*` be the free-monoid (list) monad. The carrier is built in three moves:

1. **Free structure:** `Σ ↦ Σ*` — the free monoid on the typed alphabet (order, the only primitive
   structure). *No operation on `Z` is asserted; we use `Σ*` only as the set of generators.*
2. **Restriction:** to the admissible sublanguage `Adm ⊆ Σ*` (a decidable subobject).
3. **Quotient by the reading:** `Z = Adm / ker(ρ)`, with `ρ` the deterministic reading; `Z ≅ ρ(Adm)`.

So **`Z` is a finitely-presented, typed, sequential object: a quotient of the free monoid on the varṇa
alphabet by the reading-congruence, restricted to a regular admissibility language.** The assignment
`𝒫 ↦ Z` is **functorial**, and concrete representations are functors **out** of this presentation:

- `Z` in **Set** (symbolic normal forms `ρ(w)`),
- `Z` in **Vect** (a tensor/embedding model — a faithful linear representation),
- `Z` in a **JSON schema** (the current implementation),

connected by natural isomorphisms on the invariants of §7. The **Cayley analogy** is exact: as every group
embeds faithfully into a permutation group (one representation among many of one abstract group), the
abstract `Z` admits many faithful representations (symbolic, vector, JSON), all isomorphic as carriers
because they preserve `𝒫`. The abstract object is the **presented quotient**, not any of its models.

## 9. Minimal axioms (Q8) — the definition of `Z`

The smallest consistent set that defines the carrier, analogous to the vector-space axioms before linear
algebra. Given primitives `𝒫 = (Σ, τ, A, λ, Adm, ρ)` (§1):

- **(A1 Functionality / determinism.)** `ρ : Adm → R` is total and well-defined: `w = w' ⇒ ρ(w) = ρ(w')`.
  States are attributes *of* admissible strings.
- **(A2 Carrier.)** `Z := Adm / ≡`, where `w ≡ w' :⇔ ρ(w) = ρ(w')`; canonical representative `ρ(w)`.
- **(A3 Equivalence & decidable equality.)** `≡` is an equivalence relation and equality of normal forms in
  `R` is decidable; hence equality in `Z` is decidable.
- **(A4 Invariants.)** The maps `[w] ↦ x_{1:n}`, `↦ s_{1:n}`, `↦ a_{1:n}`, `↦ e`, `↦ n` are well-defined on
  `Z` (the intrinsic coordinates).
- **(A5 Admissibility / closure boundary.)** `c ∈ Z ⇔ ∃ w∈Adm. ρ(w)=c`; membership decidable. Defines what
  counts as a valid state, hence internality for any future operation.
- **(A6 Grading / finiteness.)** `Z⁺ = ⊔_{n≥1} Z_n` with each `Z_n` finite; `Z` countable and decidable;
  induction on `n` available.
- **(A7 Representation independence.)** `Z` depends only on `𝒫` up to isomorphism; bijective relabeling of
  `A` (`λ ↦ π∘λ`) induces an isomorphism of `Z` (content is gauge); implementation details are gauge.
- **(A8 Firewall / no extrinsic content.)** `Z` carries no semantic, referential, or truth-bearing field.
  Interpretive metadata (varga, elemental, guṇa, vṛtti-name, deva) form a separate fiber `M → Z` (a
  decoration over states); `[w] = [w']` in `Z` regardless of `M`. Equality and structure of `Z` never depend
  on metadata.
- **(A9 Reserved unit.)** `𝟘 := ρ(ε)` exists in the completion `Z⁰ = Z⁺ ∪ {𝟘}` as a distinguished formal
  element, reserved to host a future identity; it is **not** an acoustic state and asserts **no** operation.

These nine axioms define `Z` completely and assert no operator. They are mutually consistent (the current
model satisfies all of them) and minimal (dropping any one either makes equality undecidable, the closure
boundary undefined, the object representation-dependent, or the firewall breachable).

## 10. What this licenses, and the obligations it transmits

`Z` is now a decidable, graded, finitely-presented, representation-independent carrier with a fixed
congruence. Any future operator `f` on `Z` must satisfy, **by inheritance from this spec**:

1. **Congruence (A2–A3):** `f` factors through `ρ` — depends on readings, never on surface spelling.
2. **Closure (A5):** `f`'s outputs lie in `Z` (admissible underlying strings), or `f` is not internal.
3. **Relabeling-equivariance (A7):** `f` commutes with bijective relabeling of `A`, *unless* `f` is
   explicitly defined to use attribute *values* — in which case that dependence must be declared and tested
   (it would be the first non-gauge use of content, and carries the burden of proof).
4. **Firewall (A8):** `f` introduces no semantic/truth field; metadata stays in the fiber.

## 11. Firewalls (binding)

- `Z` is a **formal carrier**, not a meaning space. Nothing here claims sound determines meaning.
- `Z` carries **no truth/evidence field**; it may not ground factual claims (the C×R×S firewall holds at the
  carrier level via A8).
- This document defines **only the carrier**. It asserts **no** operator, metric, or algebra. Composition and
  all other operators remain hypotheses to be tested on top of this object (see `PREREG_ACOUSTIC_ALGEBRA.md`),
  each bound by the obligations of §10.
