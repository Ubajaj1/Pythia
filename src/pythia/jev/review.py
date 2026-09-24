"""Human review of Jev vs LLM disagreements: build self-contained review items.

Each item carries what a reviewer needs to judge (scenario, persona, both answers
with their meanings) so it can be shown anywhere: a table, or a Kitaru session.
"""

from __future__ import annotations

import json
from pathlib import Path

from pythia.biases import BIAS_CATALOG
from pythia.jev.report import disagreements, field_of, load_shadow

REVIEW_KEY = "who_is_right"
ANSWERS = ("jev", "llm", "both_wrong")


def _bias(cid: str) -> dict:
    entry = BIAS_CATALOG.get(cid)
    return {"id": cid, "name": entry.name if entry else cid, "meaning": entry.layman if entry else ""}


def bias_review_items(runs_dir: str, limit: int = 20) -> list[dict]:
    """The most confident bias disagreements that have their run's scenario and cast saved."""
    records = [r for r in load_shadow(runs_dir) if field_of(r) == "bias"]
    items = []
    for r in disagreements(records, "behaviour", limit=len(records)):
        path = Path(runs_dir) / f"{r['run']}.json"
        run = json.loads(path.read_text()) if path.exists() else {}
        agent_id = r["key"].split(":")[0]
        agent = next((a for a in run.get("agents", []) if a["id"] == agent_id), None)
        if agent is None:
            continue  # no persona to judge against (e.g. oracle-loop shadow files)
        llm, jev = _bias(r["llm"]), _bias(r["jev"])
        items.append({
            "name": f"Bias: {agent['name']} ({agent['role']}): {llm['name']} vs {jev['name']}",
            "inputs": {
                "scenario": run["scenario"]["input"],
                "agent": f"{agent['name']} ({agent['role']})",
                "persona": agent["persona"],
            },
            "outputs": {"llm_bias": llm, "jev_bias": jev, "jev_confidence": r["confidence"]},
            "metadata": {"run": r["run"], "key": r["key"], "field": "bias"},
            "question": {
                "key": REVIEW_KEY,
                "question": (f"Which bias fits this persona better? LLM: {llm['name']}. "
                             f"Jev: {jev['name']} (confidence {r['confidence']:.2f}). "
                             f"Answer {', '.join(ANSWERS)}."),
            },
        })
        if len(items) == limit:
            break
    return items
