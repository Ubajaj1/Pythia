"""Summarize Jev shadow records across saved runs and export disagreements for review.

Writes docs/jev/shadow-report.md and data/jev/disagreements-<piece>.jsonl.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pythia.config import RUNS_DIR  # noqa: E402
from pythia.jev.report import disagreements, load_shadow, piece_stats, ready_for_primary  # noqa: E402

PIECES = ["behaviour", "coherence", "stance"]
SCREENING_LOG = Path("data/jev/screening.jsonl")

records = load_shadow(RUNS_DIR)
lines = [
    "# Jev shadow report", "",
    f"{len(records)} shadow records from {len({r['run'] for r in records})} saved runs.", "",
    "| Piece | Records | Confident share | Agreement at ≥0.7 | Fallback rate | Meets bars |",
    "|---|---|---|---|---|---|",
]
Path("data/jev").mkdir(parents=True, exist_ok=True)
for piece in PIECES:
    rows = [r for r in records if r["piece"] == piece]
    s = piece_stats(rows)
    lines.append(f"| {piece} | {s['n']} | {s['confident_share']:.0%} | {s['agreement_at_conf']:.0%} "
                 f"| {s['fallback_rate']:.0%} | {'yes' if ready_for_primary(s) else 'no'} |")
    with open(f"data/jev/disagreements-{piece}.jsonl", "w") as fh:
        for r in disagreements(rows, piece):
            fh.write(json.dumps(r, default=str) + "\n")

screened = [json.loads(line) for line in SCREENING_LOG.read_text().splitlines() if line.strip()] if SCREENING_LOG.exists() else []
lines += [
    "",
    f"Screening (logged separately in {SCREENING_LOG}): {len(screened)} prompts, "
    f"{sum(1 for r in screened if r['would_block'])} would have been blocked.",
    "",
    "Meeting the bars is necessary, not sufficient: review the exported disagreements "
    "(data/jev/disagreements-*.jsonl) before switching a piece to primary.",
]
Path("docs/jev").mkdir(parents=True, exist_ok=True)
Path("docs/jev/shadow-report.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
