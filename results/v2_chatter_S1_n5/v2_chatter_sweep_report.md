# Consumer V2 Chatter-Reduction Sweep

Scenario: `S1_normal_driving`  ·  N = 5  ·  V2 thresholds engage/disengage = 0.5/0.2  ·  T_engage/T_disengage = 3/5

## Chatter reduction

- Median V1 argmax-flip rate: **0.7739**
- Median V2 argmax-flip rate: **0.7739**
- Median per-seed reduction: **0.6%**
- Per-seed V2-wins-on-flip-rate: **4/5** (80.0%)
- Chatter-reduction gate: **FAIL** (requires median reduction ≥ 50% AND V2-win rate ≥ 70%)

## Rescue preservation

- V1 collisions: **0 / 5**
- V2 collisions: **0 / 5**
- V2 broke a V1 rescue (V1 nominal → V2 collision): **0**
- V2 fixed a V1 collision (V1 collision → V2 nominal): **0**
- McNemar one-sided p (V2 worse than V1): **1.0000**
- Rescue-preservation gate: **PASS** (requires V2 not introducing more collisions than it prevents AND p > 0.05 in the V2-worse direction)

## Promotion decision

**DO NOT PROMOTE**

At least one gate failed. V2 stays opt-in. Consider tuning the V2 thresholds, increasing N, or examining the failing gate's evidence in the per-seed JSON.
