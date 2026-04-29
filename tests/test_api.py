"""Tests for the FastAPI server."""

import json
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from pythia.api import create_app
from pythia.models import (
    RunResult, RunSummary, ScenarioInfo, AgentInfo,
    BiggestShift, TickRecord, TickEvent,
    AgentEvaluation, OracleRunRecord, OracleLoopResult,
)


def make_mock_result() -> RunResult:
    return RunResult(
        run_id="run_test_001",
        scenario=ScenarioInfo(
            input="Test prompt", type="market_event",
            title="Test", stance_spectrum=["vb", "b", "n", "bu", "vbu"],
        ),
        agents=[
            AgentInfo(id="a1", name="Agent 1", role="trader", persona="p", bias="b", initial_stance=0.3),
        ],
        ticks=[
            TickRecord(tick=1, events=[
                TickEvent(agent_id="a1", stance=0.35, previous_stance=0.3,
                          action="hold", emotion="calm", reasoning="r", message="m"),
            ], aggregate_stance=0.35),
        ],
        summary=RunSummary(
            total_ticks=1, final_aggregate_stance=0.35,
            biggest_shift=BiggestShift(agent_id="a1", from_stance=0.3, to_stance=0.35, reason="r"),
            consensus_reached=True,
        ),
    )


class TestSimulateEndpoint:
    @pytest.fixture
    def app(self):
        return create_app(ollama_url="http://fake:11434", model="test")

    async def test_simulate_returns_run_result(self, app):
        mock_result = make_mock_result()
        with patch("pythia.api.run_simulation", new_callable=AsyncMock, return_value=mock_result):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/simulate", json={"prompt": "Test prompt"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == "run_test_001"
        assert data["scenario"]["title"] == "Test"

    async def test_simulate_requires_prompt(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/simulate", json={})
        assert resp.status_code == 422


class TestRunsEndpoints:
    async def test_get_runs_returns_list(self, tmp_path):
        # Write a fake run file
        run_data = make_mock_result().model_dump()
        (tmp_path / "run_test_001.json").write_text(json.dumps(run_data))

        app = create_app(ollama_url="http://fake:11434", model="test", runs_dir=str(tmp_path))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["run_id"] == "run_test_001"

    async def test_get_run_by_id(self, tmp_path):
        run_data = make_mock_result().model_dump()
        (tmp_path / "run_test_001.json").write_text(json.dumps(run_data))

        app = create_app(ollama_url="http://fake:11434", model="test", runs_dir=str(tmp_path))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/runs/run_test_001")
        assert resp.status_code == 200
        assert resp.json()["run_id"] == "run_test_001"

    async def test_get_nonexistent_run_returns_404(self, tmp_path):
        app = create_app(ollama_url="http://fake:11434", model="test", runs_dir=str(tmp_path))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/runs/nonexistent")
        assert resp.status_code == 404


def make_mock_oracle_result() -> OracleLoopResult:
    run_result = make_mock_result()
    run_record = OracleRunRecord(
        run_number=1,
        result=run_result,
        evaluations=[
            AgentEvaluation(agent_id="a1", is_coherent=True, incoherence_summary=None),
        ],
        coherence_score=1.0,
        amended_agent_ids=[],
    )
    return OracleLoopResult(
        prompt="Test prompt",
        runs=[run_record],
        coherence_history=[1.0],
    )


class TestOracleEndpoint:
    @pytest.fixture
    def app(self):
        return create_app(ollama_url="http://fake:11434", model="test")

    async def test_oracle_returns_oracle_loop_result(self, app):
        mock_result = make_mock_oracle_result()
        with patch("pythia.api.run_oracle_loop", new_callable=AsyncMock, return_value=mock_result):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/oracle",
                    json={"prompt": "Test prompt", "max_runs": 3},
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["prompt"] == "Test prompt"
        assert len(data["runs"]) == 1
        assert data["coherence_history"] == [1.0]

    async def test_oracle_requires_prompt(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/oracle", json={})
        assert resp.status_code == 422

    async def test_oracle_max_runs_validated(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/oracle", json={"prompt": "test", "max_runs": 0})
        assert resp.status_code == 422


class TestFastLLMProvisioning:
    """Regression: fast_llm must only spin up when the effective provider is Groq.

    Previously, if the user had both ANTHROPIC_API_KEY and GROQ_API_KEY set,
    the app would auto-detect Anthropic as the main provider but then build a
    fast_llm that re-detected Anthropic and handed it a Groq model name,
    producing 404s against api.anthropic.com/v1/messages.
    """

    async def test_fast_llm_built_only_for_groq(self, monkeypatch):
        """Explicit provider=groq path gets a fast_llm."""
        from pythia import api as api_module
        calls: list[dict] = []

        def fake_build(provider=None, ollama_url=None, model=None):
            calls.append({"provider": provider, "model": model})
            return object()

        monkeypatch.setattr(api_module, "build_llm_client", fake_build)
        monkeypatch.setattr(api_module, "GROQ_API_KEY", "groq-key")
        monkeypatch.setattr(api_module, "ANTHROPIC_API_KEY", "")
        monkeypatch.setattr(api_module, "OPENAI_API_KEY", "")

        api_module.create_app(provider="groq")

        # Two builds expected: main llm + fast_llm
        assert len(calls) == 2
        assert calls[1]["provider"] == "groq"
        # Fast model must be a Groq model name
        assert "llama" in (calls[1]["model"] or "").lower()

    async def test_fast_llm_not_built_when_anthropic_auto_detected(self, monkeypatch):
        """Regression for 404: with ANTHROPIC_API_KEY set and provider=None,
        we must NOT build a fast_llm using a Groq model."""
        from pythia import api as api_module
        calls: list[dict] = []

        def fake_build(provider=None, ollama_url=None, model=None):
            calls.append({"provider": provider, "model": model})
            return object()

        monkeypatch.setattr(api_module, "build_llm_client", fake_build)
        monkeypatch.setattr(api_module, "GROQ_API_KEY", "groq-key")       # both keys set
        monkeypatch.setattr(api_module, "ANTHROPIC_API_KEY", "anth-key")  # both keys set
        monkeypatch.setattr(api_module, "OPENAI_API_KEY", "")

        api_module.create_app()  # provider=None — auto-detect

        # Only one build expected: the main llm. No fast_llm.
        assert len(calls) == 1, (
            f"Expected no fast_llm when Anthropic is auto-detected, got: {calls}"
        )

    async def test_fast_llm_not_built_when_user_specifies_model(self, monkeypatch):
        """If the user explicitly sets a model, don't override with Groq fast model."""
        from pythia import api as api_module
        calls: list[dict] = []

        def fake_build(provider=None, ollama_url=None, model=None):
            calls.append({"provider": provider, "model": model})
            return object()

        monkeypatch.setattr(api_module, "build_llm_client", fake_build)
        monkeypatch.setattr(api_module, "GROQ_API_KEY", "groq-key")
        monkeypatch.setattr(api_module, "ANTHROPIC_API_KEY", "")
        monkeypatch.setattr(api_module, "OPENAI_API_KEY", "")

        api_module.create_app(provider="groq", model="llama-3.3-70b-versatile")

        assert len(calls) == 1
        assert calls[0]["model"] == "llama-3.3-70b-versatile"
