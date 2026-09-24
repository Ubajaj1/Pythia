"""Render docs/kitaru/results.md from the experiment manifest."""

import json
from pathlib import Path

from pythia.experiment_report import render_markdown

rows = [json.loads(line) for line in Path("data/kitaru/cohort.jsonl").read_text().splitlines() if line.strip()]
Path("docs/kitaru/results.md").write_text(render_markdown(rows))
print(Path("docs/kitaru/results.md").read_text())
