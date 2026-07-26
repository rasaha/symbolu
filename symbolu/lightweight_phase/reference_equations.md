# Lightweight Phase Attention — Frozen Reference Equations

**Status:** canonical research reference. Production implementations must prove
equivalence against *this* document, not the reverse.

Notation: `B` batch, `N` sequence length, `H` heads, `D` model dim, `Dh = D/H`
head dim, `t` a token position (`1..N`), `⊙` element-wise product, `Re(·)` real
part, `σ(·)` logistic sigmoid, `stopgrad(·)` gradient detachment.

All complex accumulation is performed in **float32** regardless of the input
dtype (bf16/fp16 inputs are up-cast for the scan, then down-cast on output).

---

## §1 Input normalization

```
x_n = LayerNorm(x)                      # x, x_n ∈ ℝ^{B×N×D}
```

LayerNorm has learnable affine (weight `γ`, bias `β`) and `eps = layernorm_eps`.

## §2 Key-side projections (write path)

```
φ_k_raw = W_φk · x_n                     # reshape → [B, N, H, Dh]
φ_k     = π · sin(φ_k_raw)               # if bounded_phase (canonical: True)
        = φ_k_raw                        # if not bounded_phase
a_k     = amp_floor + amp_scale · σ(W_ak · x_n)     # canonical: a_k = σ(W_ak · x_n)
v       = W_v · x_n                       # reshape → [B, N, H, Dh]
```

Complex key phasor (conjugate convention `-iφ`):

```
k_t = a_{k,t} · e^{-i φ_{k,t}}            # = polar(a_k, -φ_k)
```

## §3 Recurrent state (causal write)

Non-decay (canonical Stage 1, `decay_mode="none"`):

```
S_t = S_{t-1} + k_t ⊙ v_t                # S_0 = initial complex_memory (default 0)
    = S_0 + Σ_{τ≤t} k_τ ⊙ v_τ            # equivalently cumsum over τ
```

Optional decay (Stage 3, `γ ∈ (0, 1]`; per-head γ broadcasts over Dh):

```
S_t = γ · S_{t-1} + k_t ⊙ v_t
```

`S_t ∈ ℂ^{B×H×Dh}` at any single position — **independent of N**. The state is a
fixed-size complex tensor; this is the O(D) memory contract.

## §4 Query-side projections (read path)

```
φ_q_raw = W_φq · x_n                     # reshape → [B, N, H, Dh]
φ_q     = π · sin(φ_q_raw)   or   φ_q_raw
a_q     = amp_floor + amp_scale · σ(W_aq · x_n)     # canonical: a_q = σ(W_aq · x_n)
q_t     = a_{q,t} · e^{+i φ_{q,t}}        # = polar(a_q, +φ_q)
```

## §5 Readout and detached normalizer (FROZEN CONTRACT)

Unnormalized real readout:

```
n_t = Re( q_t ⊙ S_t )                    # [B, N, H, Dh]
```

Cumulative amplitude and **detached** denominator:

```
A_t = Σ_{τ≤t} a_{k,τ}                     # (or its EMA under decay), [B, N, H, Dh]
Z_t = stopgrad( max( a_{q,t} ⊙ A_t , ε ) )      # ε = denom_eps (default 0.1)
o_t = n_t / Z_t
```

**Why detached.** `∂(n/Z)/∂Z = -n/Z²` blows up when `Z` hits the `ε` floor,
which historically drove variance spikes back through `W_aq` and `cumsum(a_k)`.
Detaching `Z` preserves the exact forward normalization while routing amplitude
gradients only through the numerator. Detachment is a frozen part of the math,
selectable via `detach_denominator` (canonical: True) purely so tests can
measure the gradient it removes — never to weaken the default.

## §6 Output projection and residual

```
o        = reshape(o_t) → [B, N, D]
out      = Dropout( W_out · o ) · aux_scale
y        = out + x                        # residual on the ORIGINAL x (pre-norm block)
```

`aux_scale` is canonical `1.0`. Production `PhaseAttentionLayer` defaults it to
`0.1` for auxiliary-path integration; the equivalence harness sets it explicitly.

---

## §7 Fixed per-head phase offsets (compatibility note)

Production adds fixed buffers `off_q[h] = off_k[h] = 2πh/H` to `φ_q` and `φ_k`.
Because the same offset is added to *both* sides, it cancels in the phase
difference that drives the real readout:

```
Re( q_t ⊙ S_t ) involves e^{ i(φ_q + off_q) } · e^{ -i(φ_k + off_k) }
                       = e^{ i(φ_q - φ_k) } · e^{ i(off_q - off_k) }
                       = e^{ i(φ_q - φ_k) }          since off_q[h] = off_k[h].
```

Therefore fixed offsets do **not** change the output and do **not** by
themselves establish head specialization. The lightweight core omits them.
Head specialization is treated as an *empirical* property, never an
architectural guarantee.

---

## §8 Streaming equivalence (Stage 2)

The single-token recurrence of §3–§5 with carried state `(S, A, position)` is,
by construction, algebraically identical to the batched cumsum/EMA form. The
test suite verifies `max|batch − streamed| ≤ 1e-5` in float32.

## §9 Decay horizon (Stage 3, approximate)

For constant `γ < 1`, the effective memory horizon is approximately

```
H ≈ 1 / (1 − γ)          (approximation — geometric-weight 1/e-ish scale)
```

`γ = 1` recovers the non-decay core exactly.
