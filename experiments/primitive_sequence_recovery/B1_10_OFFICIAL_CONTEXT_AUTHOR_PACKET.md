# Context-Writing Task — Author Packet

*This packet contains everything you need. Please do not seek additional materials or context beyond what is written
here.*

## 1. Purpose

Your task is to write natural English example sentences for six target words. For each word you will write two short
sentences that illustrate two different inner states, described in Sections 3 and 4. Write as a careful, natural
writer would. There is no trick and no hidden right answer to reverse-engineer — just write clear, natural,
realistic sentences that fit the two described states.

## 2. Target words

Exactly these six, in this order:

1. pride
2. freedom
3. patience
4. courage
5. control
6. doubt

## 3. Condition A

> A state that depends on comparison, approval, possession, control, fear of loss, rivalry, outside results, or
> other people's reactions.

## 4. Condition B

> A state arising from inward steadiness, non-comparison, autonomy, non-grasping, clarity, self-possession, or
> action independent of approval or outcome.

## 5. Author instructions

For **each** of the six words, write:
- **one sentence expressing Condition A**, and
- **one sentence expressing Condition B**.

Rules for every sentence:
- **12–22 words.**
- **Natural English** — the kind of sentence a good writer would actually write.
- The **target word must appear naturally** in the sentence (not forced or shoehorned).
- Express **exactly one stable state** — the whole sentence sits in Condition A, or the whole sentence sits in
  Condition B.
- **No transformation** — a sentence must not begin in one state and resolve into the other. (Avoid "but",
  "however", "although", "even though", "yet", "despite" when they would flip the sentence into the other state.)
- **No moral caricatures** — write realistic people, not cartoons of virtue or vice.
- **Vary the settings** across the twelve sentences (different people, places, walks of life).
- **Vary the sentence structure** — do not reuse the same template.
- **No dialogue** (no quoted speech).
- **Do not explain any theory** — just write the sentences.
- **Do not use the words** "binding", "liberating", "source-condition", "self-grounded", or "other-conditioned"
  anywhere in your sentences.

## 6. Self-check

After writing each sentence, record four quick judgements:
- **intended class:** A or B
- **confidence:** high / medium / low
- **mixed-condition detected:** yes / no
- **naturalness:** natural / slightly forced / forced

If a sentence's **mixed-condition detected = yes**, or its **naturalness = forced**, **discard it and write a new
one.** Do not truncate or patch the sentence — replace it with a fresh sentence and re-run the self-check.

## 7. Blindness declaration

Please certify (by signing Section 9's attestation) that, before and during this task, you have **not** seen any of
the following:
- any per-word descriptive "packets" prepared for these words,
- any phonetic or letter-based mappings for these words,
- any previous set of context sentences written for these words,
- any audit, review, or commentary on such sentences,
- any previous evaluation results.

If you have seen any of the above, please stop and report it rather than continuing — someone who has not seen them
should author these sentences instead.

## 8. Output format

Return **exactly 12 sentences** — two per word, in the word order of Section 2 — using this exact layout:

```
pride
A: <your Condition A sentence>
   intended class: A | confidence: <high/medium/low> | mixed-condition detected: <yes/no> | naturalness: <natural/slightly forced/forced>
B: <your Condition B sentence>
   intended class: B | confidence: <high/medium/low> | mixed-condition detected: <yes/no> | naturalness: <natural/slightly forced/forced>

freedom
A: ...
B: ...

patience
A: ...
B: ...

courage
A: ...
B: ...

control
A: ...
B: ...

doubt
A: ...
B: ...
```

Return only the 12 sentences with their four self-check fields each, plus the completed provenance block (Section
9). No commentary, no explanations, no extra text.

## 9. Provenance metadata (fill in and return with your sentences)

```
author_identity:      <your name and role, OR: fresh isolated model session — model id + note "clean session">
date_utc:             <YYYY-MM-DDThh:mm:ssZ>
prompt_hash:          <sha256 of the exact text of this packet as delivered to you>
context_hash:         <sha256 of your final 12-sentence block, computed after you finish>
blindness_attestation: <"I certify I had not seen any of the materials listed in Section 7 before or during this
                        task, and I did not consult any outside material while writing.">
```

## 10. Explicit exclusion

There is **no hidden representation for you to optimize toward** — none has been disclosed to you, by design. Do
**not** try to guess, infer, or write toward any hidden scoring scheme, pattern, or system. Your only job is to
write natural sentences that honestly fit Condition A or Condition B as described in Sections 3 and 4. Sentences
that read as engineered toward an unseen target are worse, not better, for this task.
