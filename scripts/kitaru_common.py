"""Shared pieces for the Kitaru experiment scripts: .env loading and recording one simulation."""

from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "data" / "kitaru" / "cohort.jsonl"
AGENT_COUNT, TICK_COUNT = 5, 8


def load_env(path: Path = REPO / ".env") -> None:
    """Minimal .env loader (KEY=VALUE lines); never overrides variables already set."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


async def record_one(prompt: str, repeat: int, arm: str, model_map: dict[str, str] | None = None,
                     extra_metadata: dict | None = None) -> dict:
    """Run one simulation with Groq main/tick/judge clients, recorded as one Kitaru session."""
    from pythia.config import GROQ_FAST_MODEL, GROQ_MODEL
    from pythia.experiment import run_experiment_once
    from pythia.kitaru_recorder import KitaruRecorder
    from pythia.llm import build_llm_client
    from pythia.recording import RecordingLLMClient

    recorder = KitaruRecorder(model_map=model_map)
    main = RecordingLLMClient(build_llm_client(provider="groq", model=GROQ_MODEL), "main", recorder)
    tick = RecordingLLMClient(build_llm_client(provider="groq", model=GROQ_FAST_MODEL), "tick", recorder)
    judge = RecordingLLMClient(build_llm_client(provider="groq", model=GROQ_MODEL), "judge", recorder)
    inputs = {"prompt": prompt, "agent_count": AGENT_COUNT, "tick_count": TICK_COUNT, "repeat": repeat}
    metadata = {"arm": arm, "repeat": str(repeat), **(extra_metadata or {})}
    session_id = await recorder.start(inputs, name=prompt, metadata=metadata)
    try:
        run = await run_experiment_once(prompt, main, tick, judge, agent_count=AGENT_COUNT, tick_count=TICK_COUNT)
    except Exception as exc:
        await recorder.finish({}, error=f"{type(exc).__name__}: {exc}"[:500])
        raise
    finally:
        for c in (main, tick, judge):
            await c.close()
    await recorder.finish({"final_aggregate": run.metrics["final_aggregate"], "direction": run.metrics["direction"],
                           "run_id": run.result.run_id})
    numeric = {k: float(v) for k, v in run.metrics.items() if isinstance(v, (int, float))}
    await recorder.write_evaluations(session_id, {**numeric, "coherence_rate": run.coherence_rate})
    row = {"session_id": session_id, "prompt": prompt, "repeat": repeat, "arm": arm,
           "metrics": run.metrics, "coherence_rate": run.coherence_rate, **(extra_metadata or {})}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("a") as fh:
        fh.write(json.dumps(row) + "\n")
    return row
