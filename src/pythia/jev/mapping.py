"""Pure conversions between Jev answers and Pythia values."""

from __future__ import annotations

from pythia.jev.core import Answer

STRENGTH_LEVELS = [
    "Mild: notices the bias and can set it aside when shown evidence",
    "Moderate: the bias shapes first reactions but can be argued down",
    "Strong: the bias usually wins over contrary evidence",
    "Rigid: the bias defines how this person sees every new fact",
]
STRENGTH_VALUES = [0.3, 0.5, 0.7, 0.85]

# Same relationship types the generator's LLM pass uses (models.Relationship.type).
RELATION_OPTIONS = {
    "none": "No meaningful relationship",
    "follows": "Takes cues from and tends to copy the other",
    "respects": "Values the other's judgment without copying it",
    "distrusts": "Discounts what the other says",
    "rivals": "Competes with the other and tends to take the opposite side",
}


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def strength_from_score(score: float) -> float:
    """Interpolate a continuous Score position onto STRENGTH_VALUES."""
    s = clamp(score, 0, len(STRENGTH_VALUES) - 1)
    i = min(int(s), len(STRENGTH_VALUES) - 2)
    f = s - i
    return STRENGTH_VALUES[i] + (STRENGTH_VALUES[i + 1] - STRENGTH_VALUES[i]) * f


def stance_from_score(score: float, n_levels: int) -> float:
    """Score position in [0, n-1] → stance in [0, 1], landing on bin midpoints."""
    return clamp((score + 0.5) / n_levels, 0.0, 1.0)


def stance_bin(v: float, n_levels: int = 5) -> int:
    return min(int(v * n_levels), n_levels - 1)


def ordinal_agree(a: float, b: float, n_levels: int = 5) -> bool:
    """Two stances agree when they fall in the same or adjacent spectrum bins."""
    return abs(stance_bin(a, n_levels) - stance_bin(b, n_levels)) <= 1


def prune_relationships(pairs: dict[tuple[str, str], Answer], k_max: int = 3) -> dict[str, list[tuple[str, str, float]]]:
    """Keep each agent's k_max strongest non-"none" relationships: source → [(target, type, weight)]."""
    by_source: dict[str, list[tuple[str, str, float]]] = {}
    for (src, tgt), ans in pairs.items():
        if ans.value == "none":
            continue
        weight = ans.probabilities.get(str(ans.value), ans.confidence)
        by_source.setdefault(src, []).append((tgt, str(ans.value), round(float(weight), 4)))
    return {src: sorted(rels, key=lambda r: -r[2])[:k_max] for src, rels in by_source.items()}
