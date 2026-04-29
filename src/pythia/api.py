"""FastAPI server for Pythia."""

from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from pythia.config import (
    ANTHROPIC_API_KEY,
    GROQ_API_KEY,
    GROQ_FAST_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    RUNS_DIR,
)
from pythia.llm import build_llm_client
from pythia.models import BacktestRequest, EnsembleRequest, OracleRequest, SimulateRequest, SimulateRequestWithDocs
from pythia.oracle_loop import run_oracle_loop, stream_oracle_loop
from pythia.orchestrator import run_simulation, stream_simulation
from pythia.ensemble import run_ensemble, stream_ensemble
from pythia.backtest import run_backtest, run_batch_backtest, stream_backtest

logger = logging.getLogger(__name__)


def create_app(
    provider: str | None = None,
    ollama_url: str = OLLAMA_BASE_URL,
    model: str | None = None,
    runs_dir: str = RUNS_DIR,
) -> FastAPI:

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        print("\n  ┌─────────────────────────────────────┐")
        print("  │  Pythia ready → http://localhost    │")
        print("  └─────────────────────────────────────┘\n")
        yield

    app = FastAPI(
        title="Pythia",
        description="Opinion dynamics simulation engine",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    llm = build_llm_client(provider=provider, ollama_url=ollama_url, model=model)

    # The "fast LLM" is a cheap per-tick model used inside the simulation engine
    # while the main LLM is used for analyzer / generator / decision summary.
    # It ONLY makes sense when the effective provider is Groq — passing a Groq
    # model name to Anthropic/OpenAI would 404. Compute the effective provider
    # here so we don't rely on `provider is None` as a proxy for "Groq".
    effective_provider = provider or (
        "anthropic" if ANTHROPIC_API_KEY else
        "groq"      if GROQ_API_KEY else
        "openai"    if OPENAI_API_KEY else
        "ollama"
    )
    fast_llm = (
        build_llm_client(provider="groq", ollama_url=ollama_url, model=GROQ_FAST_MODEL)
        if effective_provider == "groq" and GROQ_API_KEY and not model
        else None
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        t0 = time.perf_counter()
        logger.info("Request %s %s", request.method, request.url.path)
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - t0) * 1000)
        logger.info(
            "Response %s %s status=%d latency_ms=%d",
            request.method, request.url.path, response.status_code, latency_ms,
        )
        return response

    @app.post("/api/simulate/stream")
    async def simulate_stream(request: SimulateRequestWithDocs):
        logger.info("Simulate stream request prompt=%r", request.prompt[:60])

        async def event_stream():
            try:
                async for event in stream_simulation(
                    prompt=request.prompt, context=request.context, llm=llm,
                    runs_dir=runs_dir, fast_llm=fast_llm,
                    document_text=request.document_text,
                    document_name=request.document_name,
                    agent_count=request.agent_count,
                    tick_count=request.tick_count,
                    preset=request.preset,
                ):
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as exc:
                logger.exception("Stream error: %s", exc)
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/simulate")
    async def simulate(request: SimulateRequestWithDocs) -> dict:
        logger.info("Simulate request prompt=%r", request.prompt[:60])
        result = await run_simulation(
            prompt=request.prompt,
            context=request.context,
            llm=llm,
            runs_dir=runs_dir,
            document_text=request.document_text,
            document_name=request.document_name,
            agent_count=request.agent_count,
            tick_count=request.tick_count,
            preset=request.preset,
        )
        return result.model_dump(mode="json")

    @app.post("/api/oracle")
    async def oracle(request: OracleRequest) -> dict:
        logger.info("Oracle request prompt=%r max_runs=%d", request.prompt[:60], request.max_runs)
        result = await run_oracle_loop(
            prompt=request.prompt,
            context=request.context,
            max_runs=request.max_runs,
            llm=llm,
            runs_dir=runs_dir,
            document_text=request.document_text,
            document_name=request.document_name,
            agent_count=request.agent_count,
            tick_count=request.tick_count,
            preset=request.preset,
        )
        return result.model_dump(mode="json")

    @app.post("/api/oracle/stream")
    async def oracle_stream(request: OracleRequest):
        logger.info(
            "Oracle stream request prompt=%r max_runs=%d",
            request.prompt[:60], request.max_runs,
        )

        async def event_stream():
            try:
                async for event in stream_oracle_loop(
                    prompt=request.prompt,
                    context=request.context,
                    max_runs=request.max_runs,
                    llm=llm,
                    runs_dir=runs_dir,
                    fast_llm=fast_llm,
                    document_text=request.document_text,
                    document_name=request.document_name,
                    agent_count=request.agent_count,
                    tick_count=request.tick_count,
                    preset=request.preset,
                ):
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as exc:
                logger.exception("Oracle stream error: %s", exc)
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/ensemble")
    async def ensemble(request: EnsembleRequest) -> dict:
        logger.info(
            "Ensemble request prompt=%r ensemble_size=%d",
            request.prompt[:60], request.ensemble_size,
        )
        result = await run_ensemble(
            prompt=request.prompt,
            context=request.context,
            ensemble_size=request.ensemble_size,
            llm=llm,
            runs_dir=runs_dir,
            document_text=request.document_text,
            document_name=request.document_name,
            agent_count=request.agent_count,
            tick_count=request.tick_count,
            preset=request.preset,
        )
        return result.model_dump(mode="json")

    @app.post("/api/ensemble/stream")
    async def ensemble_stream(request: EnsembleRequest):
        logger.info(
            "Ensemble stream request prompt=%r ensemble_size=%d",
            request.prompt[:60], request.ensemble_size,
        )

        async def event_stream():
            try:
                async for event in stream_ensemble(
                    prompt=request.prompt,
                    context=request.context,
                    ensemble_size=request.ensemble_size,
                    llm=llm,
                    runs_dir=runs_dir,
                    fast_llm=fast_llm,
                    document_text=request.document_text,
                    document_name=request.document_name,
                    agent_count=request.agent_count,
                    tick_count=request.tick_count,
                    preset=request.preset,
                ):
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as exc:
                logger.exception("Ensemble stream error: %s", exc)
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/backtest")
    async def backtest(request: BacktestRequest) -> dict:
        logger.info("Backtest request prompt=%r", request.prompt[:60])
        enriched, bt_result = await run_backtest(
            prompt=request.prompt,
            ground_truth=request.ground_truth_outcome,
            llm=llm,
            context=request.context,
            document_text=request.document_text,
            document_name=request.document_name,
            agent_count=request.agent_count,
            tick_count=request.tick_count,
            preset=request.preset,
            runs_dir=runs_dir,
        )
        return {
            "run": enriched.model_dump(mode="json"),
            "backtest": bt_result.model_dump(mode="json"),
        }

    @app.post("/api/backtest/stream")
    async def backtest_stream(request: BacktestRequest):
        logger.info("Backtest stream request prompt=%r", request.prompt[:60])

        async def event_stream():
            try:
                async for event in stream_backtest(
                    prompt=request.prompt,
                    ground_truth=request.ground_truth_outcome,
                    llm=llm,
                    context=request.context,
                    fast_llm=fast_llm,
                    document_text=request.document_text,
                    document_name=request.document_name,
                    agent_count=request.agent_count,
                    tick_count=request.tick_count,
                    preset=request.preset,
                    runs_dir=runs_dir,
                ):
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as exc:
                logger.exception("Backtest stream error: %s", exc)
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/backtest/batch")
    async def backtest_batch() -> dict:
        logger.info("Batch backtest request")
        report = await run_batch_backtest(llm=llm, runs_dir=runs_dir)
        return report.model_dump(mode="json")

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
