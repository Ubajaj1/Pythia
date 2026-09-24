from pythia.experiment_report import direction_agreement, render_markdown, summarize_arm


def _row(arm, prompt, repeat, coh, direction, agg=0.3):
    return {"arm": arm, "prompt": prompt, "repeat": repeat, "coherence_rate": coh,
            "metrics": {"parse_failure_rate": 0.0, "target_validity_rate": 1.0,
                        "stance_volatility": 0.05, "final_aggregate": agg, "direction": direction}}


def test_summarize_arm_mean_and_stdev():
    s = summarize_arm([_row("x", "p", 0, 0.6, "sell"), _row("x", "p", 1, 1.0, "sell")])
    mean, sd = s["coherence_rate"]
    assert abs(mean - 0.8) < 1e-9 and abs(sd - 0.2828427) < 1e-6


def test_direction_agreement_pairs_by_prompt_and_repeat():
    a = [_row("a", "p", 0, 1, "sell"), _row("a", "q", 0, 1, "buy")]
    b = [_row("b", "q", 0, 1, "buy"), _row("b", "p", 0, 1, "neutral")]
    assert direction_agreement(a, b) == 0.5


def test_render_markdown_has_all_arms():
    rows = [_row(arm, "p", 0, 0.8, "sell") for arm in ("recorded", "baseline-replay", "swap-gpt4omini")]
    md = render_markdown(rows)
    for arm in ("recorded", "baseline-replay", "swap-gpt4omini"):
        assert arm in md
    assert "Direction agreement" in md
