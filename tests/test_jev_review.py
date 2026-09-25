import json

from pythia.jev.review import REVIEW_KEY, bias_review_items


def _run(tmp_path, name="run-1"):
    (tmp_path / f"{name}.json").write_text(json.dumps({
        "run_id": name,
        "scenario": {"input": "Should we ban plastics?", "title": "Plastics ban"},
        "agents": [{"id": "sara", "name": "Slowfood Sara", "role": "chef", "persona": "Runs a farm-to-table bistro."}],
        "jev_shadow": [
            {"piece": "behaviour", "key": "sara:bias", "llm": "status_quo_bias", "jev": "loss_aversion",
             "confidence": 0.79, "agree": False, "used": "llm"},
            {"piece": "behaviour", "key": "sara:stance", "llm": 0.2, "jev": 0.3, "confidence": 0.9, "agree": True, "used": "llm"},
        ],
    }))


def test_bias_review_items_carry_context_and_both_definitions(tmp_path):
    _run(tmp_path)
    items = bias_review_items(str(tmp_path), limit=20)
    assert len(items) == 1
    it = items[0]
    assert it["inputs"]["persona"] == "Runs a farm-to-table bistro."
    assert it["inputs"]["scenario"] == "Should we ban plastics?"
    assert it["outputs"]["llm_bias"]["id"] == "status_quo_bias" and it["outputs"]["jev_bias"]["id"] == "loss_aversion"
    assert it["outputs"]["llm_bias"]["meaning"] and it["outputs"]["jev_confidence"] == 0.79
    assert REVIEW_KEY in it["question"]["key"]
    assert "Slowfood Sara" in it["name"]


def test_records_without_run_context_are_skipped(tmp_path):
    (tmp_path / "oracle-x.jev.json").write_text(json.dumps({"jev_shadow": [
        {"piece": "behaviour", "key": "x:bias", "llm": "anchoring", "jev": "loss_aversion", "confidence": 0.9, "agree": False, "used": "llm"},
    ]}))
    assert bias_review_items(str(tmp_path)) == []


def test_oracle_shadow_with_context_is_reviewable(tmp_path):
    from pythia.jev.report import save_shadow
    save_shadow(str(tmp_path), [
        {"piece": "behaviour", "key": "sara:bias", "llm": "anchoring", "jev": "loss_aversion", "confidence": 0.9, "agree": False, "used": "llm"},
    ], "oracle-1", context={"scenario": {"input": "Q?"},
                            "agents": [{"id": "sara", "name": "Sara", "role": "chef", "persona": "p"}]})
    items = bias_review_items(str(tmp_path))
    assert len(items) == 1 and items[0]["inputs"]["scenario"] == "Q?"


def test_normalise_free_text_answers():
    from pythia.jev.review import normalise_answer
    assert normalise_answer("Jev: Optimism Bias") == "jev"
    assert normalise_answer("LLM: Status Quo Bias") == "llm"
    assert normalise_answer("both_wrong it's somewhere in between") == "both_wrong"
    assert normalise_answer("neither fits") == "both_wrong"
    assert normalise_answer("both fit") == "both_fit"
    assert normalise_answer("hmm") is None


def test_outcome_prefers_the_answer_and_falls_back_to_the_verdict():
    from pythia.jev.review import review_outcome
    assert review_outcome("problematic", ["both_wrong"]) == "both_wrong"
    assert review_outcome("acceptable", []) == "jev"
    assert review_outcome("problematic", None) == "llm"
    assert review_outcome("uncertain", []) == "unsure"
    assert review_outcome(None, None) is None  # not reviewed yet


def test_tally_counts_jev_wins_over_decided_cases():
    from pythia.jev.review import tally
    t = tally(["jev"] * 6 + ["llm"] * 2 + ["both_wrong"] * 2 + [None] * 10)
    assert t["reviewed"] == 10 and t["pending"] == 10
    assert t["counts"]["jev"] == 6
    assert abs(t["jev_win_rate"] - 0.6) < 1e-9
    assert t["meets_review_bar"] is True


def test_both_fit_counts_for_jev():
    from pythia.jev.review import tally
    assert tally(["both_fit", "llm"])["jev_win_rate"] == 0.5
