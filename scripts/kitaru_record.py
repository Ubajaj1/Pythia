"""Record the cohort: 5 README prompts x N repeats with baseline models, one Kitaru session each."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from kitaru_common import load_env, record_one  # noqa: E402


async def main(arm: str, repeats: int, limit: int | None) -> None:
    from pythia.experiment import README_PROMPTS

    prompts = README_PROMPTS[:limit] if limit else README_PROMPTS
    for prompt in prompts:
        for repeat in range(repeats):
            row = await record_one(prompt, repeat, arm)
            print(f"{arm} repeat={repeat} session={row['session_id']} "
                  f"coherence={row['coherence_rate']:.2f} dir={row['metrics']['direction']} :: {prompt[:50]}", flush=True)


if __name__ == "__main__":
    load_env()
    from pythia.logger import setup_logging

    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="recorded")
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--limit", type=int, default=None, help="Only the first N prompts (smoke tests)")
    args = ap.parse_args()
    setup_logging(level="WARNING", log_dir="data/logs")
    asyncio.run(main(args.arm, args.repeats, args.limit))
