"""Replay recorded sessions through Kitaru (native path): unchanged, and with the tick model swapped.

A local worker (`kitaru worker start`) runs scripts/kitaru_agent.py for each replay; that script
records the result session and appends its row to data/kitaru/cohort.jsonl.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from kitaru_common import MANIFEST, SWAP_MAP, load_env  # noqa: E402

ARMS = {"baseline-replay": None, "swap-gpt4omini": SWAP_MAP}


def sessions_for(arm: str) -> list[dict]:
    rows = [json.loads(line) for line in MANIFEST.read_text().splitlines() if line.strip()]
    return [r for r in rows if r["arm"] == arm]


async def latest_version_id(client) -> uuid.UUID:
    """Sessions recorded before a version was attached need the version passed explicitly."""
    from pythia.kitaru_recorder import AGENT_NAME

    agent = await client.get_agent(AGENT_NAME)
    page = await client.api.agents.list_versions(agent.id)
    return max(page.items, key=lambda v: v.version).id


async def replay_one(client, session_id: str, model_map: dict | None, timeout: float, version_id: uuid.UUID) -> dict:
    from kitaru.api_models.v1.plugin import EvaluatorConfig
    from kitaru.api_models.v1.replay_config import ReplayOverride

    # Kitaru requires at least one evaluator per replay; use two built-ins that compare arms.
    evaluators = [EvaluatorConfig(evaluator="kitaru/latency"), EvaluatorConfig(evaluator="kitaru/llm-call-signals")]
    override = ReplayOverride(model=dict(model_map)) if model_map else None
    t0 = time.time()
    replay = await client.replay(uuid.UUID(session_id), evaluators=evaluators, agent_version_id=version_id,
                                  override=override, wait=True, timeout=timeout)
    return {"replay_id": str(replay.id), "status": str(replay.status), "error": replay.error,
            "result_session_id": str(replay.result_session_id) if replay.result_session_id else None,
            "seconds": round(time.time() - t0)}


async def main(source_arm: str, arms: list[str], limit: int | None, concurrency: int, timeout: float) -> None:
    from kitaru.client.client import KitaruClient

    baselines = sessions_for(source_arm)[:limit] if limit else sessions_for(source_arm)
    sem = asyncio.Semaphore(concurrency)
    log = MANIFEST.parent / "replays.jsonl"

    async with KitaruClient() as client:
        version_id = await latest_version_id(client)

        async def run(arm: str, row: dict) -> None:
            async with sem:
                out = await replay_one(client, row["session_id"], ARMS[arm], timeout, version_id)
                out |= {"arm": arm, "baseline_session_id": row["session_id"], "prompt": row["prompt"], "repeat": row["repeat"]}
                with log.open("a") as fh:
                    fh.write(json.dumps(out) + "\n")
                print(f"{arm} {out['status']} {out['seconds']}s baseline={row['session_id'][:8]} result={out['result_session_id']} {out['error'] or ''}", flush=True)

        await asyncio.gather(*(run(arm, row) for arm in arms for row in baselines))


if __name__ == "__main__":
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-arm", default="recorded")
    ap.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=1800)
    ap.add_argument("--swap-from", default=None, help="Tick model to swap for gpt-4o-mini (default: the cohort's tick model)")
    args = ap.parse_args()
    if args.swap_from:
        ARMS["swap-gpt4omini"] = {args.swap_from: "gpt-4o-mini"}
    asyncio.run(main(args.source_arm, args.arms, args.limit, args.concurrency, args.timeout))
