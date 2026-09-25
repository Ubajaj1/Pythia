"""Read a Jev review investigation back from Kitaru and tally who was right.

Answers are free text in Kitaru, so they are normalised (pythia.jev.review.normalise_answer);
a session with only a verdict counts as acceptable -> Jev, problematic -> LLM, uncertain -> unsure.
Writes docs/jev/bias-review.md.

    .venv/bin/python scripts/jev_review_tally.py [--investigation <uuid>]   # default: the latest one
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from jev_review_kitaru import REVIEW_AGENT  # noqa: E402
from kitaru_common import load_env  # noqa: E402

OUT = Path("docs/jev/bias-review.md")


async def main(investigation: str | None) -> None:
    from kitaru.client.client import KitaruClient

    from pythia.jev.review import review_outcome, tally

    async with KitaruClient() as client:
        if investigation:
            inv = await client.api.investigations.get(uuid.UUID(investigation))
        else:
            agent_id = (await client.get_agent(REVIEW_AGENT)).id
            invs = [i async for i in client.api.investigations.iter() if i.agent_id == agent_id]
            inv = max(invs, key=lambda i: str(i.id))  # uuid7 ids sort by creation time
        links = [s async for s in client.api.investigations.iter_sessions(inv.id)]
        link_ids = {s.id for s in links}
        answers: dict = {}
        async for a in client.api.annotations.iter():
            if a.investigation_session_id in link_ids:
                answers.setdefault(a.investigation_session_id, []).append(a.value)
        names = {s.id: (await client.api.sessions.get(s.session_id)).name for s in links}

    rows, outcomes = [], []
    for s in sorted(links, key=lambda s: s.position):
        outcome = review_outcome(s.verdict, answers.get(s.id))
        outcomes.append(outcome)
        note = "; ".join(str(v) for v in answers.get(s.id, []))
        rows.append(f"| {s.position + 1} | {names[s.id]} | {s.verdict or ''} | {note} | {outcome or 'not reviewed'} |")

    t = tally(outcomes)
    c = t["counts"]
    lines = [
        f"# Jev bias review: `{inv.name}`", "",
        f"Reviewed {t['reviewed']} of {t['reviewed'] + t['pending']}. "
        f"Jev right {c['jev']}, both fit {c['both_fit']}, LLM right {c['llm']}, "
        f"both wrong {c['both_wrong']}, unsure {c['unsure']}.", "",
        f"**Jev win rate: {t['jev_win_rate']:.0%}** (Jev right or both fit, over reviewed). "
        f"Review bar (≥ 50%): {'met' if t['meets_review_bar'] else 'not met'}.", "",
        "| # | Disagreement | Verdict | Answer | Outcome |", "|---|---|---|---|---|", *rows,
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:6]))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--investigation", default=None)
    asyncio.run(main(ap.parse_args().investigation))
