from pythia.jev.core import Answer
from pythia.jev.mapping import (
    clamp, ordinal_agree, prune_relationships, stance_bin, stance_from_score, strength_from_score,
)


def test_strength_interpolates_between_levels():
    assert strength_from_score(0) == 0.3
    assert strength_from_score(3) == 0.85
    assert abs(strength_from_score(1.5) - 0.6) < 1e-9


def test_stance_from_score_uses_bin_midpoints():
    assert abs(stance_from_score(0, 5) - 0.1) < 1e-9
    assert abs(stance_from_score(4, 5) - 0.9) < 1e-9
    assert abs(stance_from_score(2.5, 5) - 0.6) < 1e-9


def test_clamp():
    assert clamp(0.9, 0.2, 0.4) == 0.4 and clamp(0.1, 0.2, 0.4) == 0.2


def test_ordinal_agree_allows_adjacent_bins():
    assert stance_bin(0.99) == 4
    assert ordinal_agree(0.25, 0.45)
    assert not ordinal_agree(0.1, 0.5)


def test_prune_relationships_keeps_top_three_non_none():
    pairs = {
        ("a", "b"): Answer("follows", 0.9, {"follows": 0.9}),
        ("a", "c"): Answer("distrusts", 0.7, {"distrusts": 0.7}),
        ("a", "d"): Answer("none", 0.9, {"none": 0.9}),
        ("a", "e"): Answer("respects", 0.6, {"respects": 0.6}),
        ("a", "f"): Answer("rivals", 0.5, {"rivals": 0.5}),
    }
    out = prune_relationships(pairs)
    assert [t for t, _, _ in out["a"]] == ["b", "c", "e"]
    assert out["a"][0] == ("b", "follows", 0.9)


def test_strength_agreement_needs_the_same_level():
    from pythia.jev.mapping import strength_agree, strength_level
    assert strength_level(0.72) == 2 and strength_level(0.49) == 1
    assert strength_agree(0.7, 0.71)
    assert not strength_agree(0.5, 0.7)  # moderate vs strong: adjacent is not agreement on a 4-level scale
