"""BTRR implementation tests (stdlib only; no pytest/torch). Inadmissible fixtures only.

Run: python3 -m experiments.relational_reasoning_bounded_context.tests.test_btrr
No reserved scientific seed is used. Fixture seeds are 883000-883004 (inadmissible as evidence).
"""
from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys

from .. import (base_capability as bc, config, eval as ev, gates as G, generator as gen,
                metrics as M, output, schema_ext as S, serializer as SZ, shortcuts as SC,
                tokenizer as TK, verdict as V, execution as EX, replay as RP, manifest as MAN)

FIXT = 883000
SPLITS = gen.SPLITS


# ---------------- tokenizer ----------------
def test_tokenizer_frozen():
    assert len(TK.LEXEMES) == 80 and len(set(TK.LEXEMES)) == 80
    assert TK.LEXEME_START == 131
    ids = [TK.LEXEME_START + i for i in range(len(TK.LEXEMES))]
    assert ids[0] == 131 and ids[-1] == 210
    assert TK.VOCAB_SIZE == 211 == TK.BTRRTokenizer().vocab_size == config.VOCAB_SIZE

def test_tokenizer_roundtrip_and_ascii_fallback():
    t = TK.BTRRTokenizer()
    for s in ["ENT vendor Z9Q1AB amount 999999999", '{"answer":null,"reasoning_path":[],"evidence_ids":[],"status":"POLICY_NOT_APPLICABLE"}', "opaqueID_abc"]:
        assert t.round_trip(s) == s
    # opaque 6-char id stays char-level (no accidental lexeme collapse)
    assert all(i < 128 for i in t.encode("Q1W2E3"))

def test_status_output_representable():
    t = TK.BTRRTokenizer()
    for st in config.STATUS_VALUES:
        assert t.round_trip(f'"{st}"') == f'"{st}"'

def test_single_hop_tokenizer_untouched():
    p = pathlib.Path(__file__).resolve().parents[3] / "experiments/single_hop_typed_vs_prose/tokenizer.py"
    spec = importlib.util.spec_from_file_location("shtok", p)
    m = importlib.util.module_from_spec(spec); sys.modules["shtok"] = m; spec.loader.exec_module(m)
    assert len(m.LEXEMES) == 69                      # single-hop still 69 lexemes
    assert set(m.LEXEMES) != set(TK.LEXEMES)         # BTRR is a distinct inventory
    assert m.LexicalTokenizer().vocab_size == 200    # single-hop vocab unchanged


# ---------------- caps ----------------
def test_caps_reject_over_cap():
    tn = "TZZ1"
    def bad(fn):
        try:
            fn(); return False
        except S.SchemaError:
            return True
    assert bad(lambda: S.Entity("vendor", "E1", tn, (("a", "1"), ("b", "2"), ("c", "3"), ("d", "4"))))  # >3 attrs
    assert bad(lambda: S.Entity("vendor", "TOOLONGID", tn))                                             # id>6
    assert bad(lambda: S.Event("EV", "E1", "risk", 100, "HIGH", tn))                                    # seq>2 digits
    assert bad(lambda: S.Event("EV", "E1", "risk", 1, "1234567890", tn))                                # value>9
    assert bad(lambda: S.ReasoningQuery("apply_policy", "PATH_DISCOVERY", "R1", ("governed_by",)))       # discovery+chain
    assert bad(lambda: S.ReasoningQuery("resolve_path_target", "PATH_GIVEN", "R1", ()))                  # given+no chain

def test_caps_enforced_in_context():
    ents = tuple(S.Entity("vendor", f"E{i}", "TZZ1", (("amount", "5"),)) for i in range(13))            # 13 entities
    try:
        S.ReasoningContext("C1", "TZZ1", S.ReasoningQuery("resolve_attribute", "NOT_APPLICABLE", "E0"),
                           ents, (), (), (), (), S.Constraints(0, False, False),
                           S.ReasoningOutput("x", (), (), "SUPPORTED"))
        assert False, "expected cap rejection"
    except S.SchemaError:
        pass


# ---------------- zero-truncation ----------------
def _cap_saturated_input_string():
    ID = "Z" * 6; VAL = "9" * 9; SEQ = "9" * 2; NUM = "9" * 9
    rows = ["CTX " + ID,
            "QRY path_then_latest PATH_GIVEN " + ID + " approval_requirement vendor_risk risk "
            "governed_by approved_vendor supplies"]
    rows += ["ENT vendor " + ID + " amount " + VAL + " region " + VAL + " tier " + VAL for _ in range(12)]
    rows += ["REL " + ID + " governed_by " + ID for _ in range(20)]
    rows += ["EVT " + ID + " " + ID + " risk " + SEQ + " " + VAL for _ in range(48)]
    rows += ["POL " + ID + (" COND amount GT " + NUM) * 4 + " OUT VP_APPROVAL_REQUIRED" for _ in range(4)]
    rows += ["EVD " + ID + " supports " + ID for _ in range(16)]
    return "\n".join(rows) + "\n"

def test_zero_truncation_max_fixture_2901():
    t = TK.BTRRTokenizer()
    assert t.count(_cap_saturated_input_string(), add_bos=True) == 2901   # matches Amendment-002 proof
    assert 2901 <= config.INPUT_TOKEN_LIMIT == 3520
    assert config.MAX_SEQ_LEN == 3904 and config.OUTPUT_TOKEN_LIMIT == 384

def test_every_generated_episode_within_limits():
    for s in SPLITS:
        for ctx in gen.generate_split(s, FIXT, 6):
            r = SZ.assert_zero_truncation(ctx)
            assert r["input_tokens"] <= 3520 and r["output_tokens"] <= 384 and r["combined"] <= 3904
    for sub in bc.P0_SUBTASKS:
        for ctx in bc.generate_p0(sub, FIXT, 4):
            SZ.assert_zero_truncation(ctx)


# ---------------- parameters ----------------
def test_parameter_counts():
    from .. import model
    total, blocks = model.analytic_parameter_count()
    assert total == 394_752 and blocks == 131_392
    assert model.reasoning_block_delta_vs_original() == 0
    assert config.backbone_param_count(200, 1024)[1] == 131_392


# ---------------- no forbidden components ----------------
def test_no_forbidden_imports():
    # scan IMPORT lines only (preserved verdict strings like KDA_VALIDATION_BLOCKED are not imports)
    here = pathlib.Path(__file__).resolve().parents[1]
    banned = ("binding_slots", "bindingslots", "phase_transformer", "phaseattention", "ephemeral_table",
              "kda", "jepa", "graph_neural", "gnn", "retrieval_table", "pointer_head", "lightweight_phase")
    hits = []
    for py in here.glob("*.py"):
        for line in py.read_text().splitlines():
            s = line.strip()
            if s.startswith(("import ", "from ")):
                low = s.lower()
                for b in banned:
                    if b in low:
                        hits.append(f"{py.name}: {s}")
    assert not hits, hits
    # also assert the only cross-package import is the plain clean_softmax backbone
    model_src = (here / "model.py").read_text()
    assert "symbolu_neural.clean_softmax.backbone import BackboneConfig, SoftmaxTransformerLM" in model_src


# ---------------- oracle leakage / PATH_DISCOVERY hiding ----------------
def test_no_gold_in_visible_serialization():
    for s in ("R4", "R7", "R9", "R12"):
        for ctx in gen.generate_split(s, FIXT, 6):
            assert ctx.query.path_mode == "PATH_DISCOVERY" and ctx.query.relation_chain == ()
            qline = SZ.serialize_input(ctx).splitlines()[1]
            g = ctx.authoritative_output
            if g.answer:
                assert g.answer not in qline                       # outcome not leaked in query
            for p in ctx.policies:
                assert p.policy_id not in qline.split()            # target policy id not in query
            # forbidden keys never in visible payload
            S._assert_no_forbidden_keys(ctx.visible_canonical())

def test_visible_excludes_authoritative_output():
    ctx = gen.generate_episode("R9", FIXT, 0)
    vc = ctx.visible_canonical()
    assert "authoritative_output" not in vc and "relation_chain" not in vc["query"]


# ---------------- generators: invariants ----------------
def test_generator_validity_and_invariants():
    for s in SPLITS:
        for ctx in gen.generate_split(s, FIXT, 8):
            ctx.validate()                                          # FK + tenant purity + caps
            ids = {e.entity_id for e in ctx.entities}
            for r in ctx.relations:
                assert r.source_entity_id in ids and r.target_entity_id in ids
            for e in (*ctx.entities, *ctx.relations, *ctx.events, *ctx.policies, *ctx.evidence):
                assert e.tenant_id == ctx.tenant_id                 # tenant purity

def test_absence_genuinely_unanswerable():
    for s in ("R10", "R11"):
        for ctx in gen.generate_split(s, FIXT, 6):
            assert ctx.authoritative_output.status == "INSUFFICIENT_EVIDENCE"
            assert ctx.authoritative_output.answer is None
    # R10 authorized-absence: no relation originates from the root (required fact absent)
    for ctx in gen.generate_split("R10", FIXT, 6):
        assert all(r.source_entity_id != ctx.query.root_entity_id for r in ctx.relations)
    # R11 insufficient-evidence: the root path exists but no applicable policy supports a conclusion
    for ctx in gen.generate_split("R11", FIXT, 6):
        assert any(r.source_entity_id == ctx.query.root_entity_id for r in ctx.relations)

def test_latest_by_sequence_not_position():
    for ctx in gen.generate_split("R5", FIXT, 6):
        target = ctx.query.root_entity_id
        tev = [e for e in ctx.events if e.entity_id == target]
        latest = max(tev, key=lambda e: e.sequence)
        assert ctx.authoritative_output.reasoning_path[-1] == f"Event:{latest.event_id}"

def test_no_policy_id_to_outcome_leakage():
    pairs = {}
    for ctx in gen.generate_split("R9", FIXT, 24):
        for p in ctx.policies:
            pairs.setdefault(p.outcome, set()).add(p.policy_id)
    # the applicable outcome must not map to a single fixed policy id
    assert all(len(v) > 1 for k, v in pairs.items() if k == "VP_APPROVAL_REQUIRED")

def test_disjoint_identity_pools():
    train = {e.entity_id for c in gen.generate_split("R9", FIXT, 6, role="train") for e in c.entities}
    final = {e.entity_id for c in gen.generate_split("R9", FIXT, 6, role="final") for e in c.entities}
    assert train and final and not (train & final)

def test_replay_deterministic():
    rep = RP.replay_report(SPLITS, FIXT, 3)
    assert all(rep.values()), rep


# ---------------- metrics / gates / verdict ----------------
def test_metrics_perfect_on_gold():
    cohort = [(c, output.serialize_output(c.authoritative_output))
              for s in SPLITS for c in gen.generate_split(s, FIXT, 4)]
    m = M.compute(cohort)
    assert m["structured_output_validity"] == 1.0
    assert m["final_answer_accuracy"] == 1.0
    assert m["hallucinated_entity"] == 0.0 and m["hallucinated_evidence"] == 0.0
    assert m["abstention_accuracy"] == 1.0 and m["false_abstention_on_answerable"] == 0.0

def test_metrics_penalize_invalid():
    cohort = [(c, "not json") for c in gen.generate_split("R9", FIXT, 5)]
    m = M.compute(cohort)
    assert m["structured_output_validity"] == 0.0 and m["final_answer_accuracy"] == 0.0

def test_gate_thresholds_match_amendment_json():
    import json
    p = pathlib.Path(__file__).resolve().parents[3] / "docs/research/hybrid_llm/benchmarks/BOUNDED_TYPED_RELATIONAL_REASONING_PROTOCOL_AMENDMENT_002.json"
    j = json.load(open(p))
    assert config.INPUT_TOKEN_LIMIT == j["context_sizing"]["input_token_limit"]["a002"]
    assert config.MAX_SEQ_LEN == j["context_sizing"]["max_seq_len"]["a002"]

def test_verdict_precedence():
    # protocol invalid dominates everything
    assert V.decide(protocol_valid=False, base_capability_established=True, shortcut_detected=True,
                    resource_ok=True, gates={}, discovery_ok=True,
                    composite_ok=True)["primary_verdict"] == "PROTOCOL_VIOLATED"
    # base capability before shortcut
    r = V.decide(protocol_valid=True, base_capability_established=False, shortcut_detected=True,
                 resource_ok=True, gates={}, discovery_ok=True, composite_ok=True)
    assert r["primary_verdict"] == "RELATIONAL_REASONING_BLOCKED_BY_BASE_CAPABILITY"
    assert "BASE_COPY_SELECTION_CAPABILITY_NOT_ESTABLISHED" in r["co_emitted"]
    # temporal failure surfaces
    gm = {"latest_event": {"pass": False}}
    assert V.decide(protocol_valid=True, base_capability_established=True, shortcut_detected=False,
                    resource_ok=True, gates=gm, discovery_ok=True,
                    composite_ok=True)["primary_verdict"] == "TEMPORAL_REASONING_FAILED"
    # preserved invariants always co-emitted, forbidden never emitted
    ok = V.decide(protocol_valid=True, base_capability_established=True, shortcut_detected=False,
                  resource_ok=True, gates={"x": {"pass": True}}, discovery_ok=True, composite_ok=True)
    assert set(config.PRESERVED_VERDICTS) <= set(ok["preserved"])
    assert ok["primary_verdict"] not in config.FORBIDDEN_VERDICTS


# ---------------- base capability + single checkpoint ----------------
def test_p0_gate_and_block():
    good = {k: 0.99 for k in bc.P0_SUBTASKS}
    assert bc.p0_gate(good)["established"]
    bad = dict(good); bad["B4"] = 0.90
    assert not bc.p0_gate(bad)["established"]

def test_single_checkpoint_identity_and_admissibility():
    class FakeCkpt:
        def __init__(self, blob, mutate=False): self.blob = blob; self.mutate = mutate; self.n = 0
        def digest(self):
            self.n += 1
            b = self.blob + (str(self.n).encode() if self.mutate else b"")
            return hashlib.sha256(b).hexdigest()
    # stable checkpoint, P0 established -> admissible
    res = ev.run_single_checkpoint(FakeCkpt(b"m"), lambda c: {"established": True},
                                   lambda c: {"r": "ok"})
    assert res["reasoning_admissible"] and "admissibility_stamp" not in res
    # P0 not established -> NON_ADMISSIBLE stamp
    res2 = ev.run_single_checkpoint(FakeCkpt(b"m"), lambda c: {"established": False},
                                    lambda c: {"r": "ok"})
    assert res2["admissibility_stamp"] == ev.NON_ADMISSIBLE
    # mutated checkpoint -> identity error
    try:
        ev.run_single_checkpoint(FakeCkpt(b"m", mutate=True), lambda c: {"established": True},
                                 lambda c: {"r": "ok"})
        assert False
    except ev.CheckpointIdentityError:
        pass


# ---------------- length shortcut control ----------------
def test_length_shortcut_control_length_preserving():
    mixed = (gen.generate_split("R9", FIXT, 12) + gen.generate_split("R10", FIXT, 12)
             + gen.generate_split("R11", FIXT, 12))
    r = SC.length_shortcut_control(mixed)
    assert r["applicable"] and r["length_preserving"], r   # answerable/absent length ranges overlap


# ---------------- seed guard / execution lock ----------------
def test_seed_guard_fail_closed():
    for reserved in (8100, 8101, 8102, 8103, 81600, 81604):
        try:
            EX.guard_seed(reserved); assert False, f"seed {reserved} should fail closed"
        except EX.ExecutionNotAuthorized:
            pass
    for reserved in (8100, 81600):
        try:
            EX.require_unit_fixture(reserved); assert False
        except EX.ExecutionNotAuthorized:
            pass
    assert EX.require_unit_fixture(883000) == 883000
    assert EX.guard_seed(883000).authorized

def test_execution_authorization_unsigned():
    p = pathlib.Path(__file__).resolve().parents[1] / "EXECUTION_AUTHORIZATION.md"
    txt = p.read_text()
    assert "BTRR_EXECUTION_NOT_AUTHORIZED" in txt and txt.count("not issued") >= 3

def test_manifest_provenance_chain():
    man = MAN.build_manifest()
    assert man["provenance"]["amendment_002"] == "a84cc8eef848e7081764deb894593f7b270f32ba"
    assert man["execution"] == "BTRR_EXECUTION_NOT_AUTHORIZED"
    assert "config.py" in man["source_hashes"]


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1; print(f"PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1; print(f"FAIL {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{passed} passed, {failed} failed, {len(tests)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
