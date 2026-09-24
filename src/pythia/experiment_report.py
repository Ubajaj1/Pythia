"""Aggregate experiment manifest rows into per-arm statistics and a markdown report."""

from __future__ import annotations

from statistics import mean, stdev

METRICS = ["coherence_rate", "parse_failure_rate", "target_validity_rate", "stance_volatility", "final_aggregate"]
ARM_ORDER = ["recorded", "baseline-replay", "swap-gpt4omini"]


def _value(row: dict, metric: str) -> float:
    return float(row["coherence_rate"] if metric == "coherence_rate" else row["metrics"][metric])


def summarize_arm(rows: list[dict]) -> dict[str, tuple[float, float]]:
    out = {}
    for m in METRICS:
        vals = [_value(r, m) for r in rows]
        out[m] = (mean(vals), stdev(vals) if len(vals) > 1 else 0.0)
    return out


def direction_agreement(a: list[dict], b: list[dict]) -> float:
    index = {(r["prompt"], r["repeat"]): r["metrics"]["direction"] for r in b}
    pairs = [(r["metrics"]["direction"], index[(r["prompt"], r["repeat"])]) for r in a if (r["prompt"], r["repeat"]) in index]
    if not pairs:
        return 0.0
    return sum(1 for x, y in pairs if x == y) / len(pairs)


def render_markdown(rows: list[dict]) -> str:
    by_arm = {arm: [r for r in rows if r["arm"] == arm] for arm in ARM_ORDER}
    lines = ["# Kitaru experiment results", "", "| Metric | " + " | ".join(ARM_ORDER) + " |", "|---|" + "---|" * len(ARM_ORDER)]
    stats = {arm: summarize_arm(rs) for arm, rs in by_arm.items() if rs}
    for m in METRICS:
        cells = [f"{stats[a][m][0]:.3f} ± {stats[a][m][1]:.3f}" if a in stats else "n/a" for a in ARM_ORDER]
        lines.append(f"| {m} | " + " | ".join(cells) + " |")
    lines += ["", "## Direction agreement with the recording", ""]
    rec = by_arm["recorded"]
    for arm in ARM_ORDER[1:]:
        if by_arm[arm] and rec:
            lines.append(f"- {arm}: {direction_agreement(rec, by_arm[arm]):.0%}")
    lines += ["", "Sessions per arm: " + ", ".join(f"{a}={len(by_arm[a])}" for a in ARM_ORDER)]
    return "\n".join(lines) + "\n"
