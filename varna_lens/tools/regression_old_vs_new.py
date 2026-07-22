#!/usr/bin/env python3
"""Old-vs-new varṇa-mapping regression for the PSE Varṇa Tool.

Runs the same corpus through the deterministic engine + renderer under:
  * OLD mapping  = varna_lens/lexicon_authoritative.json   (comparison artifact only)
  * NEW mapping  = varna_lens/lexicon_b1_12.json           (B1.12 frozen substrate; default runtime)

and writes an objective diff to varna_lens/mapping/MIGRATION_OLD_VS_NEW_REPORT.md.
Changed outputs are recorded, NOT judged as better. No LLM. Deterministic.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VL = _HERE.parent
_REPO = _VL.parent
DUMP = _HERE / "_regression_dump.py"
OLD = _VL / "lexicon_authoritative.json"
NEW = _VL / "lexicon_b1_12.json"
REPORT = _VL / "mapping" / "MIGRATION_OLD_VS_NEW_REPORT.md"


def run(mapping: Path):
    env = dict(os.environ, VARNA_LENS_MAPPING=str(mapping))
    r = subprocess.run([sys.executable, str(DUMP)], capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise SystemExit(f"dump failed for {mapping}:\n{r.stderr}")
    return json.loads(r.stdout)


def main():
    old = {p["word"]: p for p in run(OLD)["profiles"]}
    new = {p["word"]: p for p in run(NEW)["profiles"]}
    words = list(old)

    FIELDS_STRUCT = ["valence", "trajectory_roles", "controlling_element", "tone",
                     "reflection_essence_line", "honesty_ok"]
    FIELDS_DRIVE = ["essence_short"]

    struct_changed, drive_changed, new_abstentions = [], [], []
    for w in words:
        o, n = old[w], new[w]
        for f in FIELDS_STRUCT:
            if o.get(f) != n.get(f):
                struct_changed.append((w, f, o.get(f), n.get(f)))
        for f in FIELDS_DRIVE:
            if o.get(f) != n.get(f):
                drive_changed.append(w)
        if n.get("unmapped_varnas") and not o.get("unmapped_varnas"):
            new_abstentions.append((w, n["unmapped_varnas"]))

    L = []
    L.append("# PSE Varṇa Tool — Old vs New Mapping Regression\n")
    L.append("`GENERATED — varna_lens/tools/regression_old_vs_new.py` · deterministic · no LLM\n")
    L.append(f"- **OLD**: `{OLD.relative_to(_REPO)}` (retained as comparison artifact only)")
    L.append(f"- **NEW**: `{NEW.relative_to(_REPO)}` (B1.12 frozen substrate → default runtime)")
    L.append(f"- Corpus: {len(words)} words (English hybrid/g2p + IAST Sanskrit)\n")

    L.append("## Summary\n")
    L.append(f"- Drive/gloss (`essence_short`) changed: **{len(drive_changed)}/{len(words)}** words "
             f"(expected — this IS the mapping-source swap).")
    L.append(f"- Structural fields changed (valence, trajectory roles, controlling element, tone, "
             f"deterministic reflection, honesty): **{len(struct_changed)}** field-diffs.")
    L.append(f"- New abstentions (varṇa unmapped in B1.12, e.g. `ksha`): **{len(new_abstentions)}** words.")
    L.append(f"- Honesty violations introduced: "
             f"**{sum(1 for w in words if new[w].get('honesty_ok') is False)}**.\n")

    abst_words = {w for w, _ in new_abstentions}
    L.append("## Structural changes (should be minimal — architecture is unchanged)\n")
    if struct_changed:
        non_abst = [(w, f, ov, nv) for (w, f, ov, nv) in struct_changed if w not in abst_words]
        L.append(f"All {len(struct_changed)} structural field-diffs are confined to **"
                 f"{len({w for w, *_ in struct_changed})} word(s)**, "
                 f"of which **{len(non_abst)}** are NOT explained by a new abstention.\n")
        L.append("| word | field | abstention-driven? | old | new |")
        L.append("|---|---|:--:|---|---|")
        for w, f, ov, nv in struct_changed:
            drv = "yes (ksha)" if w in abst_words else "**NO**"
            L.append(f"| {w} | {f} | {drv} | `{str(ov)[:48]}` | `{str(nv)[:48]}` |")
        L.append("")
        L.append("*Every diff above is downstream of the single `ksha` (क्ष) abstention — v3 has no "
                 "compound kṣa row (it decomposes क्ष → k + ṣ), so words containing क्ष lose that beat, "
                 "which shifts their derived roles/element/tone. No structural change occurs on any word "
                 "whose varṇas are all mapped: the trajectory/renderer architecture is untouched.*"
                 if not non_abst else
                 "*Diffs marked **NO** are NOT abstention-driven and warrant inspection.*")
    else:
        L.append("**None.** Every structural field (valence, trajectory roles, controlling element, tone, "
                 "deterministic reflection, honesty_ok) is byte-identical old→new. Only the varṇa→drive "
                 "gloss payload changed, confirming the swap is isolated to the symbolic substrate.")
    L.append("")

    L.append("## New abstentions (explicit, surfaced — never silent)\n")
    if new_abstentions:
        for w, u in new_abstentions:
            L.append(f"- `{w}`: varṇa(s) {u} have no B1.12 mapping → engine emits '(no lexicon entry)'.")
    else:
        L.append("None in this corpus.")
    L.append("")

    L.append("## Drive/gloss changes (per word) — recorded, not judged\n")
    L.append("| word | old essence_short | new essence_short |")
    L.append("|---|---|---|")
    for w in words:
        if w in drive_changed:
            L.append(f"| {w} | `{str(old[w].get('essence_short'))[:70]}` "
                     f"| `{str(new[w].get('essence_short'))[:70]}` |")
    L.append("")
    L.append("*Old glosses are short two-pole labels (e.g. `Hope`/`Detach`); new glosses are the B1.12 "
             "binding/liberating vṛtti prose (verbatim). `_short()` truncates each at the first `(`.*\n")

    REPORT.write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {REPORT.relative_to(_REPO)}")
    print(f"  drive-changed words: {len(drive_changed)}/{len(words)}")
    print(f"  structural field-diffs: {len(struct_changed)}")
    print(f"  new abstentions: {len(new_abstentions)}")
    print(f"  honesty violations introduced: "
          f"{sum(1 for w in words if new[w].get('honesty_ok') is False)}")


if __name__ == "__main__":
    main()
