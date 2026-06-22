# Answer Quality Rating — Rater Instructions

Thank you for helping. You will read a list of **questions**, each paired with **one answer**. Your job is
to judge **the answer** — how good it is for the person who asked. You don't need any special background:
judge it as a thoughtful everyday user would.

You'll get a file — `supervised_observation_packet.jsonl` or a spreadsheet — with one row per answer. Fill
in a label for each row. Keep each `item_id` exactly as given; don't edit the questions or answers.

---

## 7 rules to keep in mind
1. **Judge the answer as a user would receive it.** Would this be good for *you* if you'd asked the
   question?
2. **Don't try to guess which system produced the answer.** There's nothing hidden you're meant to figure
   out. Just rate quality.
3. **Don't reward an answer for mentioning "frames," "domains," or category labels.** Talking *about how it
   answers* is not the same as answering well — usually it's worse.
4. **Base your rating on usefulness, correctness, and whether it needs rewriting** — not on length, tone,
   or style.
5. **Use `rewrite_needed=yes` only when the answer should be rewritten before someone could use it.**
6. **Use `answer_acceptable=yes` only when the answer is usable as-is.**
7. **If you're uncertain, prefer the safer label** (the one that flags a possible problem) and explain
   briefly in `short_reason`.

---

## The labels (plain English)

**`rewrite_needed`** — `yes` / `no`
`yes` if a reasonable user would need this answer **rewritten before they could use it** (it's wrong,
misleading, off-topic, or too vague to act on). `no` if it's usable as it stands.

**`answer_acceptable`** — `yes` / `no`
`yes` if the answer is **usable as-is**. Judge this on its own merits — don't just flip your `rewrite_needed`
choice automatically.

**`primary_frame_correct`** — `yes` / `no`
`yes` if the answer addresses the **meaning the question was actually about**. `no` if it answers a
*different sense* of the question than the user intended.

**`rejected_domain_leak`** — `yes` / `no`
`yes` if the answer pulls in an **unrelated or wrong topic** that doesn't belong.

**`secondary_overpromoted`** — `yes` / `no`
`yes` if a **minor or side meaning** is treated as the **main** answer, crowding out what the user really
asked about.

**`generic_low_signal`** — `yes` / `no`
`yes` if the answer is **vague, padded, or mostly filler** — not necessarily wrong, but not actually
useful.

**`overconfident_or_overstated`** — `yes` / `no`
`yes` if it claims **more certainty or scope than warranted** (states guesses as facts, overgeneralizes).

**`frame_label_parroting`** — `yes` / `no`
`yes` if it **talks about "frames," "domains," or "categories"** instead of just answering naturally.

**`needs_clarification`** — `yes` / `no`
`yes` if the question is genuinely **ambiguous** and a good answer should have **asked a clarifying
question** instead of guessing.

**`clear_and_useful_1to5`** — number 1–5 (see scale below).

**`factual_or_grounded_1to5`** — number 1–5 (see scale below).

**`short_reason`** — one short phrase explaining your main call, especially on close calls
(e.g. *"answers the wrong meaning"*, *"correct but too vague to use"*). Optional but encouraged.

> For the yes/no labels use `yes` or `no`. For the two scales use a whole number 1–5. If you genuinely
> cannot judge a field, leave it blank (`null`).

---

## Scale definitions

**`clear_and_useful_1to5`**
```
1 = unclear or unusable
2 = mostly unclear / weak
3 = partially useful
4 = clear and mostly useful
5 = very clear and directly useful
```

**`factual_or_grounded_1to5`**
```
1 = likely false or unsupported
2 = weakly grounded
3 = partially grounded
4 = mostly grounded
5 = strongly grounded and reliable
```
(Use your general knowledge — you don't need to research. If you truly can't tell, pick 3 and note it.)

---

## Examples (generic — illustrative only)

**1. Good answer, no rewrite needed.**
*Q: "What does a paramedic do?"* → A clear, correct description of emergency medical care.
`rewrite_needed=no`, `answer_acceptable=yes`, `primary_frame_correct=yes`,
`clear_and_useful=5`, `factual_or_grounded=5`.

**2. Wrong frame / domain.**
*Q about a profession* → the answer talks about an unrelated meaning of the word (e.g. a brand or a fruit).
`primary_frame_correct=no`, `rejected_domain_leak=yes`, `rewrite_needed=yes`, `answer_acceptable=no`.

**3. Secondary meaning overpromoted.**
The question is mainly about meaning A, but the answer spends most of its effort on a minor meaning B and
treats B as the headline. `secondary_overpromoted=yes`, `primary_frame_correct=no` (or borderline),
`rewrite_needed=yes`.

**4. Generic low-signal answer.**
*"There are many factors to consider, and it depends on the context…"* with nothing specific.
`generic_low_signal=yes`, `clear_and_useful=2`, often `rewrite_needed=yes`.

**5. Frame-label parroting.**
*"The primary frame here is X and the secondary domain is Y, while Z is rejected…"* instead of just
answering the question. `frame_label_parroting=yes`, usually `clear_and_useful≤3`, often
`rewrite_needed=yes`.

**6. Overconfident, unsupported answer.**
States a specific claim as definite fact when it's doubtful or made up.
`overconfident_or_overstated=yes`, `factual_or_grounded=1–2`, `rewrite_needed=yes`.

**7. Needs clarification instead of an answer.**
The question is genuinely ambiguous (could mean two quite different things) and the answer just picks one
without flagging the ambiguity. `needs_clarification=yes`. Whether to also mark `rewrite_needed` depends on
whether the guessed answer is otherwise usable — note your reasoning in `short_reason`.

**8. Borderline / close call.**
Mostly fine but one part is shaky. Prefer the safer label (flag the problem) and explain in `short_reason`,
e.g. *"useful overall but one claim looks overstated."*

---

## Rater agreement plan
- Use **two raters** where possible, labeling the **same** rows.
- **Dual-rate at least 60 overlapping rows** so agreement can be measured.
- **Disagreements on `rewrite_needed`** will be resolved by a **named tie-breaker**, or by **majority** if
  three raters are used.
- **Do not discuss labels during independent labeling** — disagreement is useful data, not a problem to
  smooth over.

---

## Important — for the coordinator
```
Raters should receive ONLY the public packet/spreadsheet and this instruction document.
Do NOT share the private keymap, automated scores, audit findings, answer keys, arm labels,
or model metadata with raters.
```
There are intentionally **no** "Bhava / Guna / Vritti / Sattva / Rajas / Tamas" judgments here. Those are
not rater concepts; they are interpretive mappings applied later by the analyst, never asked of raters.

Thank you — your honest, end-user judgment is exactly what's needed.
