"""Kitaru-backed SessionRecorder. The only module that imports kitaru.

The wrapper calls record_llm_call() synchronously from inside async LLM calls,
so nodes are buffered and ingested in batches when the session finishes.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Protocol

AGENT_NAME = "pythia-simulation"
_BATCH = 200


class KitaruSDK(Protocol):
    async def start_session(self, agent: str, inputs: dict, name: str, metadata: dict) -> str: ...
    async def ingest_llm_nodes(self, session_id: str, nodes: list[dict]) -> None: ...
    async def finish_session(self, session_id: str, outputs: dict, error: str | None) -> None: ...
    async def read_model_map(self) -> dict[str, str]: ...
    async def write_evaluations(self, session_id: str, values: dict[str, float]) -> None: ...


class KitaruRecorder:
    def __init__(self, agent_name: str = AGENT_NAME, sdk: KitaruSDK | None = None,
                 model_map: dict[str, str] | None = None):
        self.agent_name = agent_name
        self.sdk = sdk or RealKitaruSDK()
        self._explicit_map = model_map
        self._model_map: dict[str, str] = dict(model_map or {})
        self.session_id: str | None = None
        self._nodes: list[dict] = []

    async def start(self, inputs: dict, name: str, metadata: dict) -> str:
        if self._explicit_map is None:
            self._model_map = await self.sdk.read_model_map()
        self.session_id = await self.sdk.start_session(self.agent_name, inputs, name, metadata)
        self._nodes = []
        return self.session_id

    def record_llm_call(
        self, *, role: str, requested_model: str, model: str, provider: str,
        system: str | None, prompt: str, response: dict, latency_ms: int,
        started_at: datetime, ended_at: datetime,
    ) -> None:
        if self.session_id is None:
            raise RuntimeError("record_llm_call() before start(): call start() first")
        self._nodes.append({
            "external_id": f"llm-{len(self._nodes):04d}", "role": role,
            "requested_model": requested_model, "model": model, "provider": provider,
            "system": system, "prompt": prompt, "response": response, "latency_ms": latency_ms,
            "started_at": started_at, "ended_at": ended_at,
        })

    def model_for(self, requested_model: str) -> str | None:
        return self._model_map.get(requested_model)

    async def finish(self, outputs: dict, error: str | None = None) -> None:
        if self.session_id is None:
            raise RuntimeError("finish() called before start()")
        for i in range(0, len(self._nodes), _BATCH):
            await self.sdk.ingest_llm_nodes(self.session_id, self._nodes[i:i + _BATCH])
        await self.sdk.finish_session(self.session_id, outputs, error)
        self._nodes = []

    async def write_evaluations(self, session_id: str, values: dict[str, float]) -> None:
        await self.sdk.write_evaluations(session_id, values)


class RealKitaruSDK:
    """KitaruSDK over kitaru.client.KitaruClient (see docs/kitaru/api-notes.md)."""

    def __init__(self):
        try:
            from kitaru.client.client import KitaruClient
        except ImportError as exc:
            raise RuntimeError("Kitaru is not installed. Run: uv pip install -e '.[kitaru]'") from exc
        self._client = KitaruClient()
        self._agent_id: uuid.UUID | None = None
        self._version_id: uuid.UUID | None = None

    async def _agent(self, name: str) -> uuid.UUID:
        if self._agent_id is None:
            self._agent_id = (await self._client.get_agent(name)).id
            page = await self._client.api.agents.list_versions(self._agent_id)
            if page.items:
                self._version_id = max(page.items, key=lambda v: v.version).id
        return self._agent_id

    async def start_session(self, agent: str, inputs: dict, name: str, metadata: dict) -> str:
        from kitaru.api_models.v1.session import SessionCreateRequest, SessionOrigin, SessionStatus

        replaying = bool(os.environ.get("KITARU_REPLAY_ID"))
        # Inside a replay task the task-scoped token identifies the agent and may not list agents,
        # so agent and version are left to the server. Recorded sessions carry both, so they can be replayed.
        agent_id = None if replaying else await self._agent(agent)
        req = SessionCreateRequest(
            agent_id=agent_id,
            agent_version_id=None if replaying else self._version_id,
            origin=SessionOrigin.REPLAY if replaying else SessionOrigin.RECORDED,
            status=SessionStatus.IN_PROGRESS,
            name=name[:200],
            inputs=inputs,
            outputs=None,
            input_text_selector="/prompt",
            started_at=datetime.now(timezone.utc),
            metadata=metadata,
            framework="pythia-custom",
        )
        return str((await self._client.api.sessions.create(req)).id)

    async def ingest_llm_nodes(self, session_id: str, nodes: list[dict]) -> None:
        from kitaru.api_models.v1.session_node import (
            NodeStatus, NodeType, SessionNodeBatchRequest, SessionNodeCreateRequest,
        )

        batch = SessionNodeBatchRequest(nodes=[
            SessionNodeCreateRequest(
                external_id=n["external_id"],
                node_type=NodeType.LLM_CALL,
                name=f"{n['role']}: {n['model']}",
                status=NodeStatus.COMPLETED,
                started_at=n["started_at"],
                ended_at=n["ended_at"],
                system_prompt_selector="/system",
                input_text_selector="/prompt",
                inputs={"system": n["system"], "prompt": n["prompt"]},
                outputs=n["response"],
                requested_model=n["requested_model"],
                model=n["model"],
                model_provider=n["provider"],
                attributes={"latency_ms": n["latency_ms"]},
                metadata={"role": n["role"]},
            )
            for n in nodes
        ])
        await self._client.api.sessions.ingest_nodes(uuid.UUID(session_id), batch)

    async def finish_session(self, session_id: str, outputs: dict, error: str | None) -> None:
        from kitaru.api_models.v1.session import SessionStatus, SessionUpdateRequest

        await self._client.api.sessions.update(uuid.UUID(session_id), SessionUpdateRequest(
            status=SessionStatus.FAILED if error else SessionStatus.COMPLETED,
            outputs=outputs, error=error, ended_at=datetime.now(timezone.utc),
        ))

    async def read_model_map(self) -> dict[str, str]:
        rid = os.environ.get("KITARU_REPLAY_ID")
        if not rid:
            return {}
        replay = await self._client.get_replay(uuid.UUID(rid))
        model = replay.override.model if replay.override else None
        if isinstance(model, dict):
            return dict(model)
        if isinstance(model, str):
            raise RuntimeError(
                "Replay override replaces every model with one model; Pythia expects a map "
                "such as {'llama-3.1-8b-instant': 'gpt-4o-mini'} so only agent turns change."
            )
        return {}

    async def write_evaluations(self, session_id: str, values: dict[str, float]) -> None:
        from kitaru.api_models.v1.evaluation import EvaluationResult
        from kitaru.api_models.v1.session import SessionEvaluationsRequest

        await self._client.api.sessions.create_evaluations(uuid.UUID(session_id), SessionEvaluationsRequest(
            evaluations=[EvaluationResult(name=k, score=float(v)) for k, v in values.items()],
        ))

    async def close(self) -> None:
        await self._client.close()
