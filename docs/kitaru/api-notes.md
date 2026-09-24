# Kitaru API notes (spike, 2026-09-23)

Kitaru version: 0.27.1 (`kitaru[cli,worker,mcp]`), Python 3.12 virtualenv.

Source: read from the installed package (`kitaru/client/`, `kitaru/api_models/v1/`, `kitaru/worker/`, `kitaru/server/application/services/`), because the public custom-adapter docs have no code sample.

## SDK mapping table

The SDK is **async only** (`kitaru.client.client.KitaruClient`, which wraps `KitaruAPIClient`; there is also a `sync_client.py`). `KitaruClient()` with no arguments resolves the server and credentials from `kitaru login` or from `KITARU_API_URL` + `KITARU_API_TOKEN` (the worker sets both for task processes).

| Capability | Exact call | Sync or async | Notes |
|---|---|---|---|
| register agent | `await client.register_agent(name, RunSpec(command=..., working_dir=..., env=...))` → `AgentRegistrationResult(agent, version)`; later versions: `await client.register_agent_version(agent_name_or_id, run_spec)` | async | `kitaru.api_models.v1.agent_version.RunSpec`. The run spec's shell command is what a worker executes during replay. |
| start_session | `await client.api.sessions.create(SessionCreateRequest(agent_id=..., origin=SessionOrigin.RECORDED, status=SessionStatus.IN_PROGRESS, name=..., inputs=..., outputs=None, started_at=..., metadata={...}, framework="pythia-custom"))` → `SessionResponse` (`.id`) | async | `kitaru.api_models.v1.session`. Inside a replay task, a created session is auto-linked to the replay as its result session (`SessionService`, `replay.link_result_session`); `agent_id` can be omitted there because the task token scopes it. |
| record_llm_call | `await client.api.sessions.ingest_nodes(session_id, SessionNodeBatchRequest(nodes=[SessionNodeCreateRequest(external_id, node_type=NodeType.LLM_CALL, name, status=NodeStatus.COMPLETED, started_at, ended_at, inputs, outputs, requested_model, model, model_provider, tokens=TokenUsage(input_tokens, output_tokens), attributes={}, metadata={"role": ...})]))` | async | `kitaru.api_models.v1.session_node`. Batched; an existing `external_id` is replaced whole. `system_prompt_selector` / `input_text_selector` are JSON pointers into `inputs` for UI display. |
| finish_session | `await client.api.sessions.update(session_id, SessionUpdateRequest(status=SessionStatus.COMPLETED, outputs=..., ended_at=...))` | async | `status=FAILED` + `error=` on failure. |
| read_override | In a replay process: `rid = os.environ["KITARU_REPLAY_ID"]`; `replay = await client.get_replay(uuid.UUID(rid))`; `replay.override` is a `ReplayOverride` with `model: str \| dict[str, str] \| None`, `system_prompt`, `prompt`, `model_params` | async | The session's original inputs arrive as JSON in `KITARU_TASK_INPUTS`. `model` may be a **map from old model to new model**, which targets exactly the tick calls. |
| write_evaluation | `await client.api.sessions.create_evaluations(session_id, SessionEvaluationsRequest(evaluations=[EvaluationResult(...)]))` | async | Manual evaluations; 409 if a name already exists on that session. Registered evaluators (`kitaru evaluator`) can also run server-side on replay results. Exact `EvaluationResult` fields: see `kitaru/api_models/v1/evaluation.py` (read in Task 5). |
| trigger replay | `await client.replay(baseline_session_id, override=ReplayOverride(model={"llama-3.1-8b-instant": "gpt-4o-mini"}))`, then `await client.wait_for_replay(replay_id)` | async | Creates a job that a worker picks up. Experiments over a cohort: `client.run_experiment(...)` / `wait_for_experiment_run(...)`. |

## Replay entrypoint

1. Register agent `pythia-simulation` with `RunSpec(command=".venv/bin/python scripts/kitaru_agent.py", working_dir=<repo path>)`.
2. Run a worker locally: `kitaru worker start` (foreground; drains on SIGINT). Workers execute tasks in our environment; the managed server only coordinates.
3. For each replay, the worker runs the command with `KITARU_TASK_INPUTS` (the baseline session's inputs, JSON, if ≤ the env-size limit), `KITARU_REPLAY_ID`, `KITARU_API_URL`, `KITARU_API_TOKEN` (task-scoped), and `KITARU_TASK_ID`.
4. `scripts/kitaru_agent.py` reads the inputs, fetches the replay's override, builds clients with the model map applied, runs the simulation, and records the result session, which the server links to the replay.

## Can replay swap only the tick model?

**Yes.** `ReplayOverride.model` accepts a map from old to new model. Pythia's tick role is the only one on `llama-3.1-8b-instant` (main and judge use `llama-3.3-70b-versatile`), so `{"llama-3.1-8b-instant": "gpt-4o-mini"}` swaps agent turns only. The mapping is applied by our wrapper (the runtime declares `RuntimeCapabilities.overrides=True`); Kitaru does not intercept HTTP.

## Decision: replay path

**Path A (native).** Kitaru replays recorded sessions through a registered agent command, and our wrapper applies the override. Consequence for the plan:

- The SDK is async, so `KitaruSDK` / `KitaruRecorder` become async: `start()` and `finish()` are awaited; `record_llm_call()` stays synchronous for the wrapper and **buffers** nodes, which `finish()` ingests in one batch.
- The override is a model map, not a role map: `KitaruRecorder.override_for(role)` is replaced by `model_for(requested_model) -> str | None`, and `RecordingLLMClient` asks for the override by its inner client's model name. The factory still turns `"gpt-4o-mini"` into a client (provider inferred: `gpt-*` → openai, `llama-*` → groq, `claude-*` → anthropic).
- New file `scripts/kitaru_agent.py` (the replay entrypoint), and a one-time `scripts/kitaru_register.py` for the agent registration.
- Task 6 triggers replays with `client.replay(...)` per recorded session (two arms: no override, and the model map), instead of Path B's local re-runs.
