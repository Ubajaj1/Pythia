"""Shadow-mode statistics that decide when a Jev piece can move to primary.

The bars are necessary, not sufficient: disagreements still need review
(spec: docs/superpowers/specs/2026-09-23-jev-integration-design.md).
"""

from __future__ import annotations

import json
from pathlib import Path

from pythia.jev.core import threshold

AGREEMENT_BAR = 0.85
FALLBACK_BAR = 0.30


def piece_stats(records: list[dict], min_conf: float = 0.7) -> dict:
    n = len(records)
    if n == 0:
        return {"n": 0, "confident_share": 0.0, "agreement_at_conf": 0.0, "fallback_rate": 0.0}
    # Rows where the LLM was skipped (llm is None) have nothing to agree with.
    comparable = [r for r in records if r.get("llm") is not None and r["confidence"] >= min_conf]
    agree = sum(1 for r in comparable if r["agree"]) / len(comparable) if comparable else 0.0
    cut = threshold()
    return {
        "n": n,
        "confident_share": sum(1 for r in records if r["confidence"] >= min_conf) / n,
        "agreement_at_conf": agree,
        "fallback_rate": sum(1 for r in records if r["confidence"] < cut) / n,
    }


def ready_for_primary(stats: dict) -> bool:
    return stats["n"] > 0 and stats["agreement_at_conf"] >= AGREEMENT_BAR and stats["fallback_rate"] < FALLBACK_BAR


def disagreements(records: list[dict], piece: str, limit: int = 20) -> list[dict]:
    """The most confident disagreements first: the ones most worth a human look."""
    rows = [r for r in records if r["piece"] == piece and not r["agree"] and r.get("llm") is not None]
    return sorted(rows, key=lambda r: -r["confidence"])[:limit]


def save_shadow(runs_dir: str, records: list[dict], name: str) -> Path | None:
    """Write shadow records to <runs_dir>/<name>.jev.json (for results that are not saved whole)."""
    if not records:
        return None
    path = Path(runs_dir) / f"{name}.jev.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"jev_shadow": records}, indent=2, default=str))
    return path


def load_shadow(runs_dir: str) -> list[dict]:
    """All shadow records in runs_dir, each tagged with the file it came from."""
    records = []
    for f in sorted(Path(runs_dir).glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        for r in data.get("jev_shadow", []) if isinstance(data, dict) else []:
            records.append({**r, "run": f.stem})
    return records
