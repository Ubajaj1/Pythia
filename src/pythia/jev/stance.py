"""Jev expressed-stance scoring: where does what an agent says place it? Shadow only.

The gap between this and the agent's self-reported stance is a research signal
(does the agent talk the way it votes?), never a replacement for the stance.
"""

from __future__ import annotations

import logging

from pythia.jev.core import JevAsker, ScoreQ, get_jev, jev_mode, record_shadow
from pythia.jev.mapping import ordinal_agree, stance_from_score
from pythia.models import ScenarioBlueprint, TickRecord

logger = logging.getLogger(__name__)
PIECE = "stance"


async def record_expressed_stances(
    tick: TickRecord, blueprint: ScenarioBlueprint,
    jev: JevAsker | None = None, mode: str | None = None,
) -> None:
    mode = mode or jev_mode(PIECE)
    if mode == "off":
        return
    jev = jev or get_jev()
    if jev is None:
        return
    spoken = [e for e in tick.events if e.message.strip()]
    if not spoken:
        return
    state = {"scenario": f"{blueprint.title}. {blueprint.description}",
             "messages": {e.agent_id: e.message for e in spoken}}
    questions = {
        e.agent_id: ScoreQ(f"Judging only by the message from {e.agent_id}, where does its author stand?",
                           blueprint.stance_spectrum)
        for e in spoken
    }
    try:
        answers = await jev.ask(state, questions)
    except Exception:
        logger.exception("Jev stance scoring failed tick=%d", tick.tick)
        return
    n = len(blueprint.stance_spectrum)
    for e in spoken:
        a = answers[e.agent_id]
        expressed = round(stance_from_score(float(a.value), n), 4)
        record_shadow(PIECE, f"{tick.tick}:{e.agent_id}", e.stance, expressed, a.confidence,
                      ordinal_agree(expressed, e.stance, n), "llm")
