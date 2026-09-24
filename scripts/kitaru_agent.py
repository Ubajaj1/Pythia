"""Replay entrypoint: a Kitaru worker runs this for each replayed session.

Reads the baseline session's inputs from KITARU_TASK_INPUTS; the recorder reads the
replay's model override via KITARU_REPLAY_ID. The new session is linked to the replay
by the server because it is created with the task-scoped token.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from kitaru_common import load_env, record_one  # noqa: E402


async def main() -> None:
    inputs = json.loads(os.environ["KITARU_TASK_INPUTS"])
    replay_id = os.environ.get("KITARU_REPLAY_ID", "")
    arm = os.environ.get("PYTHIA_REPLAY_ARM", "replay")
    row = await record_one(inputs["prompt"], int(inputs.get("repeat", 0)), arm,
                           extra_metadata={"replay_id": replay_id})
    print(json.dumps({"session_id": row["session_id"], "direction": row["metrics"]["direction"]}))


if __name__ == "__main__":
    load_env()
    from pythia.logger import setup_logging

    setup_logging(level="WARNING", log_dir="data/logs")
    asyncio.run(main())
