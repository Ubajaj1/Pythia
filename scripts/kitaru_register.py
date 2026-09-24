"""Register the pythia-simulation agent (once) with a run spec pointing at scripts/kitaru_agent.py."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from kitaru_common import REPO, load_env  # noqa: E402


async def main() -> None:
    from kitaru.api_models.v1.agent_version import RunSpec
    from kitaru.client.client import KitaruClient

    from pythia.kitaru_recorder import AGENT_NAME

    spec = RunSpec(
        command=f"{REPO / '.venv/bin/python'} {REPO / 'scripts/kitaru_agent.py'}",
        working_dir=str(REPO),
        timeout_seconds=1800,
    )
    async with KitaruClient() as client:
        try:
            agent = await client.get_agent(AGENT_NAME)
        except Exception:
            agent = None
        if agent is None:
            result = await client.register_agent(
                AGENT_NAME, spec,
                description="Pythia multi-agent opinion simulation (custom httpx LLM clients, no framework, no tools).",
                display_version="kitaru-exp-1",
            )
            print(f"registered agent={result.agent.id} version={result.version.version}")
        else:
            version = await client.register_agent_version(AGENT_NAME, spec, display_version="kitaru-exp-1")
            print(f"agent exists={agent.id}; new version={version.version}")


if __name__ == "__main__":
    load_env()
    asyncio.run(main())
