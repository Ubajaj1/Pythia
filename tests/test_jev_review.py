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
