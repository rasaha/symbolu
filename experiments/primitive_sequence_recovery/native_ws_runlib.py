"""Shared library for the native Sanskrit word-specificity evaluator run (v2 packet freeze).

Reused by the preflight, presentation-order builder, evaluator collector, and tests. Implements ONLY:
  * loading the frozen evaluator-facing trials + protocol (NEVER the answer key);
  * rendering the literal frozen prompt for a trial;
  * strict parsing of the {"choice":"W#"} response;
  * the frozen collection policy (temperature 0, one retry, timeout/invalid rules);
  * atomic incremental JSONL evidence writing + resume.

NO scoring, NO accuracy, NO answer-key access, NO model import at module load. Structure, not validated meaning.
"""
from __future__ import annotations
import hashlib
import json
import os
import pathlib
import tempfile
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

HERE = pathlib.Path(__file__).resolve().parent
V2 = HERE / "native_word_specificity_packets_v2"
TRIALS_PATH = V2 / "evaluator_facing" / "trials.json"          # the ONLY packet input a collector may read
PROTOCOL_PATH = V2 / "evaluator_protocol.json"
FREEZE_INDEX_PATH = V2 / "packet_freeze_index.json"
# NOTE: the internal answer key path is deliberately NOT defined here so no collector can import it.

VALID_LABELS = ("W1", "W2", "W3", "W4", "W5", "W6")


# ---------------------------------------------------------------------------------------------------
# frozen inputs
# ---------------------------------------------------------------------------------------------------
def load_protocol() -> Dict:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def load_trials() -> List[Dict]:
    return json.loads(TRIALS_PATH.read_text(encoding="utf-8"))["trials"]


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def load_manifest(path: str | pathlib.Path) -> Dict:
    p = pathlib.Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except Exception as e:                                  # noqa: BLE001
            raise RuntimeError("PyYAML is required to read a .yaml manifest (`pip install pyyaml`), "
                               "or use the .json manifest template instead") from e
        return yaml.safe_load(text)
    return json.loads(text)


# ---------------------------------------------------------------------------------------------------
# literal prompt rendering (exactly per evaluator_protocol.json)
# ---------------------------------------------------------------------------------------------------
def render_description_block(trial: Dict) -> str:
    if "packet" in trial:                                       # semantic arms T/X/S/R/G
        blocks = [f"toward: {f['binding']}\naway: {f['liberating']}" for f in trial["packet"]]
        return "\n\n".join(blocks)
    md = trial["packet_metadata_only"]                         # feature-only arm F
    return f"structure only: {md['n_features']} feature(s), length band {md['length_band']}"


def render_candidates_block(trial: Dict) -> str:
    return "\n".join(f"{c['label']}: {c['gloss']}" for c in trial["candidates"])


def render_prompt(trial: Dict, protocol: Dict) -> str:
    # targeted substitution (NOT str.format): the template contains a literal {"choice": "W3"} example that
    # str.format would misread as a field. Replace only the two named placeholders.
    return (protocol["literal_prompt_template"]
            .replace("{description_block}", render_description_block(trial))
            .replace("{candidates_block}", render_candidates_block(trial)))


# ---------------------------------------------------------------------------------------------------
# strict response parsing
# ---------------------------------------------------------------------------------------------------
def parse_choice(raw: Optional[str]) -> Optional[str]:
    """Strict: raw must be a JSON object whose ONLY key is 'choice' mapping to one of W1..W6. Else None."""
    if raw is None:
        return None
    try:
        obj = json.loads(raw.strip())
    except Exception:                                          # noqa: BLE001
        return None
    if not isinstance(obj, dict) or set(obj.keys()) != {"choice"}:
        return None
    c = obj["choice"]
    return c if isinstance(c, str) and c in VALID_LABELS else None


# ---------------------------------------------------------------------------------------------------
# frozen collection policy (temperature 0, ONE retry, timeout/invalid rules)
# ---------------------------------------------------------------------------------------------------
@dataclass
class TrialRecord:
    trial_id: str
    evaluator_id: str
    model_id: str
    model_revision: Optional[str]
    prompt_sha256: str
    status: str                 # answered | invalid | missing
    parsed_choice: Optional[str]
    attempts: int
    raw_responses: List[Optional[str]]
    errors: List[Optional[str]]
    latency_s: float

    def to_json(self) -> Dict:
        return self.__dict__.copy()


def _call_with_timeout(fn: Callable[[], str], timeout_s: int) -> Tuple[Optional[str], Optional[str]]:
    """Run fn() with a wall-clock timeout in a worker thread. Returns (text, error). On timeout returns
    (None, 'timeout'). NOTE: a Transformers generate() cannot be truly cancelled — the worker may keep
    running to completion; on a dedicated pod with small max_tokens this is negligible. For strict
    timeouts, use the vLLM/openai_compat_local backend (HTTP has a real socket timeout)."""
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        try:
            return fut.result(timeout=timeout_s), None
        except concurrent.futures.TimeoutError:
            return None, "timeout"
        except Exception as e:                                 # noqa: BLE001
            return None, f"{type(e).__name__}: {e}"


def collect_one(adapter, trial: Dict, protocol: Dict, evaluator_id: str, model_id: str,
                model_revision: Optional[str], settings, timeout_s: int = 60, sleep=time.sleep) -> TrialRecord:
    """Apply the frozen policy to a single trial: at most 2 attempts (1 retry), identical prompt at
    temperature 0. NEVER reads any answer key. Classifies status; never edits output."""
    prompt = render_prompt(trial, protocol)
    prompt_h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    raws: List[Optional[str]] = []
    errs: List[Optional[str]] = []
    t0 = time.time()
    parsed = None
    last_was_timeout_or_error = False
    for attempt in range(2):                                    # attempt 0 + at most one retry
        text, err = _call_with_timeout(lambda: adapter.generate(prompt, settings), timeout_s)
        raws.append(text)
        errs.append(err)
        if err is not None:
            last_was_timeout_or_error = True
        else:
            last_was_timeout_or_error = False
            parsed = parse_choice(text)
            if parsed is not None:
                break
        if attempt == 0:
            sleep(0)                                            # identical retry, temperature unchanged
    latency = round(time.time() - t0, 4)
    if parsed is not None:
        status = "answered"
    elif last_was_timeout_or_error or all(e is not None for e in errs):
        status = "missing"                                     # timeout/error dominated
    else:
        status = "invalid"                                     # got text, never parseable
    return TrialRecord(trial_id=trial["trial_id"], evaluator_id=evaluator_id, model_id=model_id,
                       model_revision=model_revision, prompt_sha256=prompt_h, status=status,
                       parsed_choice=parsed, attempts=len(raws), raw_responses=raws, errors=errs,
                       latency_s=latency)


# ---------------------------------------------------------------------------------------------------
# atomic incremental evidence I/O + resume
# ---------------------------------------------------------------------------------------------------
def append_jsonl_atomic(path: pathlib.Path, record: Dict) -> None:
    """Append one record as a line, flushing + fsync so a pod interruption cannot leave a half record
    lost. A single small append is atomic on POSIX; we fsync to force it to disk."""
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def read_completed_trial_ids(path: pathlib.Path) -> set:
    """Trial IDs already collected (resume). Tolerates a trailing partial line from an interrupted write."""
    done = set()
    if not path.exists():
        return done
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:                                  # noqa: BLE001
                continue                                       # skip a torn final line
            if "trial_id" in rec:
                done.add(rec["trial_id"])
    return done


def write_json_atomic(path: pathlib.Path, obj: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
