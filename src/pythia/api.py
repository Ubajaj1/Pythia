"""FastAPI server for Pythia."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pythia.config import OLLAMA_BASE_URL, OLLAMA_MODEL, RUNS_DIR
from pythia.llm import OllamaClient
from pythia.models import SimulateRequest
from pythia.orchestrator import run_simulation


def create_app(
    ollama_url: str = OLLAMA_BASE_URL,
    model: str = OLLAMA_MODEL,
    runs_dir: str = RUNS_DIR,
) -> FastAPI:
    app = FastAPI(title="Pythia", description="Opinion dynamics simulation engine")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    llm = OllamaClient(base_url=ollama_url, model=model)

    @app.post("/api/simulate")
    async def simulate(request: SimulateRequest) -> dict:
        result = await run_simulation(
            prompt=request.prompt,
            context=request.context,
            llm=llm,
            runs_dir=runs_dir,
        )
        return result.model_dump()

    @app.get("/api/runs")
    async def list_runs() -> list[dict]:
        runs_path = Path(runs_dir)
        if not runs_path.exists():
            return []
        runs = []
        for f in sorted(runs_path.glob("run_*.json"), reverse=True):
            data = json.loads(f.read_text())
            runs.append({
                "run_id": data.get("run_id", f.stem),
                "title": data.get("scenario", {}).get("title", "Unknown"),
                "type": data.get("scenario", {}).get("type", "unknown"),
            })
        return runs

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str) -> dict:
        run_file = Path(runs_dir) / f"{run_id}.json"
        if not run_file.exists():
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        return json.loads(run_file.read_text())

    return app
