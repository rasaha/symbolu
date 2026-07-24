"""Phase 8 tests: classifier entry point, complexity budget, accuracy, 0 unsafe, replay determinism."""
from minimal_evidence_policy import classifier, dataset as d, schema as s, modifiers, replay


def test_classifier_never_raises():
    assert classifier.classify({"artifact_id": "x"}).final_obligation in s.LEVELS


def test_within_complexity_budget():
    c = modifiers.COMPLEXITY
    assert c["policy_logic_rules"] <= c["budget_primary_rules"]
    assert c["learned_model"] is False
    assert c["obligation_outcomes"] == 6


def test_held_out_zero_unsafe_assignments():
    held = d.load_partition("HELD_OUT_NATURAL")
    unsafe = sum(classifier.classify(it).final_obligation in it.get("unsafe_obligations", []) for it in held)
    assert unsafe == 0


def test_adversarial_never_weaker_than_gold():
    adv = d.load_partition("ADVERSARIAL_INVARIANTS")
    weaker = sum(s.RANK[classifier.classify(it).final_obligation] < s.RANK[it["gold_obligation"]] for it in adv)
    assert weaker == 0


def test_replay_deterministic():
    assert replay.replay_stable(d.load_partition("HELD_OUT_NATURAL")[:40]) is True
