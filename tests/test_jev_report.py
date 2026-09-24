from pythia.jev.report import disagreements, piece_stats, ready_for_primary


def _r(agree, conf, llm=True):
    return {"piece": "coherence", "key": "k", "llm": llm, "jev": True, "confidence": conf, "agree": agree, "used": "llm"}


def test_stats_only_count_confident_rows_for_agreement():
    rows = [_r(True, 0.9)] * 9 + [_r(False, 0.9)] + [_r(False, 0.2)] * 2
    s = piece_stats(rows)
    assert s["n"] == 12
    assert abs(s["agreement_at_conf"] - 0.9) < 1e-9
    assert abs(s["fallback_rate"] - 2 / 12) < 1e-9


def test_rows_without_llm_value_are_ignored_for_agreement():
    rows = [_r(True, 0.9)] * 3 + [_r(True, 0.9, llm=None)]
    assert piece_stats(rows)["agreement_at_conf"] == 1.0


def test_ready_for_primary():
    assert ready_for_primary({"agreement_at_conf": 0.9, "fallback_rate": 0.1, "n": 50})
    assert not ready_for_primary({"agreement_at_conf": 0.8, "fallback_rate": 0.1, "n": 50})
    assert not ready_for_primary({"agreement_at_conf": 0.9, "fallback_rate": 0.4, "n": 50})
    assert not ready_for_primary({"agreement_at_conf": 1.0, "fallback_rate": 0.0, "n": 0})


def test_disagreements_sorted_by_confidence():
    rows = [_r(False, 0.6), _r(False, 0.95), _r(True, 0.99)]
    out = disagreements(rows, "coherence")
    assert [r["confidence"] for r in out] == [0.95, 0.6]


def test_save_and_load_shadow(tmp_path):
    import json
    from pythia.jev.report import load_shadow, save_shadow

    assert save_shadow(str(tmp_path), [], "oracle-x") is None  # nothing to save, no file
    save_shadow(str(tmp_path), [_r(True, 0.9)], "oracle-x")
    # A run file saved by the orchestrator carries its own jev_shadow list.
    (tmp_path / "run-1.json").write_text(json.dumps({"run_id": "run-1", "jev_shadow": [_r(False, 0.8)]}))
    (tmp_path / "run-2.json").write_text(json.dumps({"run_id": "run-2"}))
    rows = load_shadow(str(tmp_path))
    assert sorted(r["run"] for r in rows) == ["oracle-x.jev", "run-1"]
