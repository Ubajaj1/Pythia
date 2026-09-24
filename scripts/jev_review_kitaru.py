"""Send the top Jev-vs-LLM bias disagreements to Kitaru as an investigation for human review.

Each disagreement becomes a small session (scenario, persona, both answers with their
meanings) under the `pythia-jev-review` agent, kept apart from simulation sessions.
The investigation asks one question per session: jev, llm, or both_wrong.

    .venv/bin/python scripts/jev_review_kitaru.py [--limit 20]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from kitaru_common import load_env  # noqa: E402

REVIEW_AGENT = "pythia-jev-review"


async def review_agent_id(client):
    from kitaru.api_models.v1.agent import AgentCreateRequest
    from kitaru.client.exceptions import APIError

    try:
        return (await client.get_agent(REVIEW_AGENT)).id
    except APIError as exc:
        if exc.status_code != 404:
            raise
    agent = await client.api.agents.create(AgentCreateRequest(
        name=REVIEW_AGENT, description="Human review of Jev vs LLM disagreements in Pythia (not replayable).",
    ))
    return agent.id


async def existing_sessions(client, agent_id) -> dict[tuple[str, str], object]:
    """Review sessions already sent, keyed by (run, shadow key), so reruns don't duplicate them."""
    from kitaru.api_models.v1.filter import FilterCondition, FilterOp
    from kitaru.api_models.v1.session import SessionListParams

    params = SessionListParams(
        size=1000, include_payloads=True,
        filter=FilterCondition(field="agent_id", op=FilterOp.EQ, value=str(agent_id)),
    )
    page = await client.api.sessions.list(params)
    return {(s.metadata.get("run"), s.metadata.get("key")): s.id for s in page.items if s.metadata}


async def main(limit: int) -> None:
    from kitaru.api_models.v1.investigation import (
        InvestigationCreateRequest, InvestigationSessionInput, InvestigationSessionQuestion,
    )
    from kitaru.api_models.v1.session import SessionCreateRequest, SessionOrigin, SessionStatus
    from kitaru.client.client import KitaruClient
    from kitaru.client.dashboard_urls import get_investigation_review_url

    from pythia.config import RUNS_DIR
    from pythia.jev.review import bias_review_items

    items = bias_review_items(RUNS_DIR, limit=limit)
    if not items:
        print("No bias disagreements with saved run context.")
        return

    async with KitaruClient() as client:
        agent_id = await review_agent_id(client)
        sent = await existing_sessions(client, agent_id)
        now = datetime.now(timezone.utc)
        links = []
        for it in items:
            session_id = sent.get((it["metadata"]["run"], it["metadata"]["key"]))
            if session_id is None:
                session_id = (await client.api.sessions.create(SessionCreateRequest(
                    agent_id=agent_id, origin=SessionOrigin.RECORDED, status=SessionStatus.COMPLETED,
                    name=it["name"][:200], inputs=it["inputs"], outputs=it["outputs"], metadata=it["metadata"],
                    input_text_selector="/persona", started_at=now, ended_at=now, framework="pythia-jev-review",
                ))).id
            links.append(InvestigationSessionInput(
                session_id=session_id, questions=[InvestigationSessionQuestion(**it["question"])],
            ))
        investigation = await client.api.investigations.create(InvestigationCreateRequest(
            agent_id=agent_id,
            name=f"jev-vs-llm-bias-{now:%Y-%m-%d-%H%M}",  # letters, digits, - and _ only
            description=("Top bias disagreements from the shadow batch, most confident Jev answers first. "
                         "For each persona, answer jev, llm, or both_wrong; set the verdict to acceptable "
                         "when Jev's pick is at least as good."),
            sessions=links,
        ))
        url = get_investigation_review_url(await client.api.info.get(), client.api.base_url,
                                           agent_id=agent_id, investigation_id=investigation.id)
    print(f"Created investigation {investigation.id} with {len(links)} sessions.")
    print(f"Review: {url or '(no dashboard link; open Investigations in the Kitaru dashboard)'}")


if __name__ == "__main__":
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    asyncio.run(main(ap.parse_args().limit))
