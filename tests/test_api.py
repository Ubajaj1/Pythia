"""Tests for the FastAPI server."""

import json
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from pythia.api import create_app
from pythia.models import (
    RunResult, RunSummary, ScenarioInfo, AgentInfo,
    BiggestShift, TickRecord, TickEvent,
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
