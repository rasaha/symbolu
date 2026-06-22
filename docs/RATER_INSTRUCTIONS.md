# Answer Quality Rating — Instructions for Raters

Thank you for helping. You will read a series of **questions** and, for each one, **one answer**. Your job
is to judge **the answer** — how good it is for the person who asked. You do **not** need any special or
technical background; just judge as a thoughtful end user would.

You will be given a file (`supervised_observation_packet.jsonl`, or a spreadsheet
`supervised_observation_labels_template.csv`). Fill in a label for each row.

---

## Golden rules
1. **Judge the answer, not the system.** You are not grading a model, a method, or how the question was
   produced. Imagine *you* asked the question — is this answer good for you?
2. **Use only what you see.** Each row shows a `prompt` (the question), an `answer`, and a short
   `intended_task` reminder. There is nothing hidden you are "supposed to know." If the answer is unclear,
   that is itself information — mark it as such.
3. **There are no right/wrong "categories" to guess.** Do not try to infer what condition, version, or
   internal label produced the answer. Just rate quality.
4. **When unsure, use your judgment as the end user** and leave a short note in `short_reason`.

---

## The labels

### Primary label (the most important one)
- **`rewrite_needed`** — `yes` / `no`
  Mark **`yes`** if a reasonable user would need this answer **rewritten before they could use it** —
  because it is wrong, misleading, off-topic, or too vague to act on.
  Mark **`no`** if the answer is **usable as it stands**.

### Secondary labels
- **`answer_acceptable`** — `yes` / `no`
  Is the answer usable as-is? (This is close to the opposite of `rewrite_needed`, but judge it on its own —
  don't just flip your previous answer mechanically.)
- **`primary_frame_correct`** — `yes` / `no`
  Does the answer address the **meaning the question was actually about**? Mark **`no`** if it answers a
  *different sense* of the question than the user intended (e.g. answers about a fruit when the question
  was clearly about a profession).
- **`rejected_domain_leak`** — `yes` / `no`
  Does the answer drag in an **unrelated or wrong topic** that doesn't belong? Mark **`yes`** if it does.
- **`secondary_overpromoted`** — `yes` / `no`
  Does a **minor or side meaning** get treated as the **main** answer, pushing aside what the user really
  asked about? Mark **`yes`** if so.
- **`generic_low_signal`** — `yes` / `no`
  Is the answer **vague, padded, or mostly filler** — technically not wrong, but not actually useful? Mark
  **`yes`** if so.
- **`overconfident_or_overstated`** — `yes` / `no`
  Does it claim **more certainty or scope than it should** (states guesses as facts, overgeneralizes)?
- **`frame_label_parroting`** — `yes` / `no`
  Does it **talk about "frames," "domains," or "categories"** instead of simply answering the question in
  natural language? Mark **`yes`** if it describes *how it's answering* rather than just answering.
- **`needs_clarification`** — `yes` / `no`
  Is the question genuinely **ambiguous**, such that a good answer should have **asked a clarifying
  question** instead of guessing? Mark **`yes`** if the answer guessed when it should have asked.

### Rating scales (1 = very poor, 5 = excellent)
- **`clear_and_useful_1to5`** — How clear and useful is the answer to the person who asked?
- **`factual_or_grounded_1to5`** — How factually correct / well-grounded does it seem? (Use your general
  knowledge; you don't need to research. If you genuinely can't tell, pick the middle and note it.)

### Optional
- **`short_reason`** — one short phrase explaining your main label, especially if it was a close call.
  (e.g. *"answers about the wrong meaning"*, *"correct but too vague to use"*.)

---

## How to fill it in
- **JSONL file:** for each row, set the values inside `human_labels`. Use `"yes"` / `"no"` for the yes/no
  labels, a number **1–5** for the two scales, and text for `short_reason`. Leave anything you truly can't
  judge as `null`.
- **CSV file:** one row per `item_id`; put `yes`/`no`, a 1–5 number, or text in each column. Leave a cell
  blank only if you genuinely cannot judge it.
- **Keep the `item_id` exactly as given** — it's how your labels get matched back. Don't edit prompts or
  answers.

---

## A few worked cues
- A confident, on-topic, correct, easy-to-use answer → `rewrite_needed=no`, `answer_acceptable=yes`,
  high scales.
- An answer that's *about the wrong meaning* of the word/question → `primary_frame_correct=no`, almost
  always `rewrite_needed=yes`.
- An answer that's true but says nothing specific ("there are many factors to consider…") →
  `generic_low_signal=yes`, low `clear_and_useful`.
- An answer that keeps saying "the primary frame is… the secondary domain is…" instead of just answering →
  `frame_label_parroting=yes`.
- A reasonable answer to a genuinely ambiguous question that just *picked* one reading without flagging the
  ambiguity → consider `needs_clarification=yes`.

---

## Notes for the coordinator (not raters)
- Please use **two independent raters** where possible, labeling the **same** rows, so we can measure
  agreement. Raters should **not** discuss items while labeling — disagreement is useful data.
- Do **not** share the `..._private_keymap.json` file with raters. It is analyst-only.
- There are intentionally **no** "Bhava / Guna / Vritti / Sattva / Rajas / Tamas" judgments here. Those are
  not rater concepts; they are interpretive mappings the analyst may apply *after the fact*, never asked of
  raters.

Thank you — your honest, end-user judgment is exactly what's needed.
