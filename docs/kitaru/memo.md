# Kitaru feedback from building on Pythia

**From:** Utkarsh Bajaj · **Kitaru version:** 0.27.1, managed cloud · **Dates:** 2026-09-23 to 2026-09-25

## What we built

[Pythia](https://github.com/Ubajaj1/Pythia) simulates how a panel of LLM agents (investors, customers, regulators) reacts to a decision, tick by tick. It is a deliberately awkward fit for replay tools: no agent framework (its own httpx clients for OpenAI, Anthropic, Groq, Ollama), **no tool calls**, three model roles in one run (analysis, per-agent turns, judge), and highly stochastic multi-agent dynamics.

The integration:
- A ~120-line wrapper at Pythia's LLM-client boundary that records every call as an `llm_call` node and applies replay overrides. The engine was not changed.
- The agent registered with a run spec pointing at a small entrypoint script, and a local worker executing replays.
- 10 recorded sessions (5 prompts × 2), 50 LLM calls each.
- 20 native replays: 10 unchanged (to measure the noise floor) and 10 with agent turns swapped from `gpt-4.1-nano` to `gpt-4o-mini` via a model-map override.
- Scoring: Pythia's own metrics written as manual evaluations, plus Kitaru's built-in `kitaru/latency` and `kitaru/llm-call-signals`.
- One cross-provider replay: Groq `gpt-oss-20b` → OpenAI `gpt-4o-mini`.
- An investigation for human review of a second experiment (below): 20 sessions, one question each.

Total hands-on time: about a day for record and replay, including learning the SDK from source; under an hour for the investigation.

## Results

| | Recorded | Unchanged replay | Swap to gpt-4o-mini |
|---|---|---|---|
| Coherence (LLM judge) | 0.98 | 1.00 | 1.00 |
| Parse failures | 0 | 0 | 0 |
| Stance volatility per tick | 0.042 | 0.046 | 0.026 |
| Mean \|Δ final outcome\| vs its recording | n/a | **0.108** | **0.205** |

- **The override did exactly what it should.** In all 10 swap sessions, exactly the 40 agent-turn nodes show "requested `gpt-4.1-nano`, served `gpt-4o-mini`" and nothing else changed. The model-map form of `ReplayOverride.model` is what made this possible.
- **The swap roughly doubles how far outcomes move** compared with re-running unchanged (Welch t ≈ 2.3, n = 10 per arm). That's suggestive, not conclusive. `gpt-4o-mini` agents also move less per tick (volatility 0.026 vs 0.046).
- **The unchanged-replay arm was the most useful thing we measured.** A stochastic multi-agent system re-run unchanged still moves its outcome by about 0.11 on a 0–1 scale, and agreed on the final direction only 30% of the time. Without that noise floor we would have credited the model swap with differences that are just run-to-run variation.
- **Replays were fast and unattended** once working: about 32 s each, 4 concurrent, all 20 completed with no failures.

## Human review with investigations

Pythia now runs a second model (TypeSafe's Jev) in shadow next to its LLM for some judgement calls, such as which cognitive bias fits an agent's persona. We sent the 20 most confident disagreements to Kitaru as an investigation: one session per disagreement, holding the persona and both answers, each with the question "who is right?". The sessions weren't agent runs at all. We created them through the API under a separate agent, and investigations handled them unchanged.

Utkarsh reviewed 10: Jev was right in 6, the LLM in 2, neither in 2. The review also surfaced something the numbers hadn't: in the cases Jev lost, it was missing context the LLM had. That's a finding about our setup, and exactly what human review is for.

- **What worked:** hand-picking sessions and attaching a specific question to each; verdicts (acceptable, problematic, uncertain) that double as review progress; a review-page link returned when the investigation is created.
- **What didn't:** see friction #10 and #11.

## What worked

1. **Model-map overrides.** `{"gpt-4.1-nano": "gpt-4o-mini"}` swaps exactly one role in a multi-model agent, even across providers. For multi-model agents this is the killer feature, and it is buried in `replay_config.py`.
2. **Server-side replay linking.** A session created with the task-scoped token is attached to its replay automatically; our adapter needed no replay bookkeeping.
3. **Failure reporting.** A failed replay's `error` field includes the tail of our process's stderr. That turned two bugs into two-minute fixes.
4. **Readable SDK.** When docs ran out, the SDK source and request models were clear enough to build from directly.
5. **Built-in evaluators** (13 in the workspace) and a worker that started cleanly.
6. **Investigations over arbitrary sessions.** Review isn't limited to recorded agent runs, which made it easy to review a different kind of disagreement.

## Friction, ranked

| # | Severity | Issue | Suggested fix |
|---|---|---|---|
| 1 | Major | **No code example for a custom (non-framework) adapter.** The custom-adapter page gives principles and points to an agent skill and the PydanticAI adapter. We mapped the API by reading installed source (~20 min to start). | A 30-line "record and replay a custom agent" example: create session, ingest one LLM node, finish, read the override in a replay task. |
| 2 | Major | **Built-in evaluators fail with slightly older uv.** The worker runs evaluators with `--exclude-newer-package kitaru=0 days`. uv 0.8.8 has the flag but not relative durations; the preflight only checks the flag exists, so it passes and every evaluator exits 2. Since evaluators are mandatory, **every replay fails before the agent runs.** | Check uv's version (≥ 0.9) or trial-parse the value in preflight; or pass an absolute timestamp. |
| 3 | Major | **Sessions recorded without `agent_version_id` can't be replayed**, and nothing says so until replay time (422). | Default to the agent's latest version when recording, or warn / show "not replayable" in the UI. |
| 4 | Minor | **`evaluators` must be non-empty** for `client.replay`; learned from a pydantic error. | Default to a built-in set, or document the minimum. |
| 5 | Minor | **Task tokens can't list agents** (403). Correct least privilege, but the same adapter code works outside a replay and fails inside it, so custom adapters need two code paths. | Document which routes task tokens can call, or let `sessions.create` infer the agent from the token (it effectively does). |
| 6 | Minor | **Missing token data shows as cost 0 / tokens 0**, reading as "free" rather than "not reported". | Keep null as unknown through rollups and the UI. |
| 7 | Minor | **`kitaru doctor` reports `config: pass` / `credentials: pass` when neither file exists.** | Report missing files as missing. |
| 8 | Minor | **Async-only recording API.** Recording from inside an existing client wrapper means every custom adapter re-implements buffer-and-flush. | Ship a small `SessionRecorder` helper: buffer nodes, flush on finish, `model_for(requested_model)`. |
| 9 | Minor | **Contributor-only `AGENTS.md` files ship in the wheel.** Coding agents treat them as usage guidance. | Exclude them, or replace with an SDK-usage guide for agents. |
| 10 | Minor | **Investigation name rules surface only after its sessions exist.** Names may contain only letters, digits, `-` and `_` (422), but the field description doesn't say so. Sessions and the investigation are separate calls, so the sessions were already created and a naive retry would duplicate them. | State the rule in the field description, or accept free-text names alongside a slug. |
| 11 | Minor | **Investigation answers are free text.** Our question offered three answers, and they came back as "Jev: Optimism Bias", "both_wrong it's somewhere in between", and so on. Fine for one reviewer; a team tallying results would need to normalise them. | Optional answer choices per question, with an optional note. |
| 12 | Minor | **An expired login reads as `401: Missing bearer credential`.** A day after `kitaru login`, SDK calls failed with that message; logging in again fixed it. | Say the session expired and suggest `kitaru login`. |

## Product observations

- **Positioning.** The March launch posts describe durable execution (`@flow`, `@checkpoint`, `wait`); the current docs and SDK are replay-based evaluation. Both are valuable, but arriving from the launch post we initially looked for the wrong API. One sentence on the docs home ("Kitaru was durable execution; it is now X") would help.
- **Stochastic, tool-less agents.** The docs frame an unchanged replay as the faithful baseline, which holds when tool calls are answered from the recording. For agents whose variance comes from the model itself, one unchanged replay is one sample. First-class support would help: N unchanged replays per session, and experiment reports that compare against that spread.
- **Provider limits.** Replay-heavy workflows multiply provider load. Our first attempt on Groq's free tier (8k tokens/min) would have taken 7+ hours. Per-experiment pacing, and surfacing provider 429s in replay results, would help users see this coming.
- **Not evaluated:** self-hosted deployment, analyzers, insights, trace importers, experiments over cohorts (we drove replays individually).

## How it compares

We didn't benchmark alternatives, so this is positioning as we understand it:

- **Covered well elsewhere:** tracing, comparing experiments, and human review queues. LangSmith, Langfuse (open source, self-hostable), Braintrust and others do these well.
- **Where Kitaru is different: replay.** LangGraph can rewind to a checkpoint, but only inside LangGraph. LangSmith and Langfuse experiments re-run your code over a dataset with a harness you write. Kitaru makes "replay this recorded session with this override" one server-side operation: a worker re-runs the real agent, the result is linked to the original, and both are scored, whatever the framework.

For a tool-less agent like Pythia, a script plus a tracing tool would cover most of what we did, and we'd have written more glue. The case gets much stronger for agents that call tools, where serving tool results from the recording isolates the one change being tested. That was the one capability we couldn't exercise. A buyer's first question will be "why not LangSmith or Langfuse?", and the docs should answer it head-on.

## Would we keep using it?

**Yes, conditionally.** Once the four setup issues were fixed, the record → replay → compare loop answered a real question for Pythia ("can we use a cheaper model for agent turns?") in minutes, with evidence we trust because the noise-floor arm was cheap to run. Investigations then gave us a clean way to put a second experiment in front of a human reviewer. The condition: issues 1–3 above are the difference between "an afternoon" and "a day" for a custom agent, and #2 can silently break every replay for anyone on an older uv.
