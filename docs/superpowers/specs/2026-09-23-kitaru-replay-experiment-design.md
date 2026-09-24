# Kitaru Replay Experiment — Design

**Date:** 2026-09-23
**Status:** Approved
**Deadline:** Feedback to Kitaru CTO by end of week (Fri 2026-09-25)
**Branch:** `exp/kitaru-replay`

## Goal

Produce evidence-based feedback on Kitaru's current product (record → replay → evaluate) for its CTO, by integrating it with Pythia as a real, non-framework, custom agent and running one model-swap experiment end to end.

Out of scope: Kitaru's earlier durable-execution API (`@flow`/`@checkpoint`/`wait`), self-hosted deployment (we use managed cloud; the memo notes this path was skipped).

## Integration

- New module `src/pythia/recording.py` with `RecordingLLMClient`, a wrapper implementing the existing `LLMClient` protocol (`llm.py`). It delegates to an inner client and records each `generate()` call as an LLM-call session node, tagged with a client `role`: `main` (analyze, generate), `tick` (agent turns), `judge` (coherence evaluation). Roles replace per-stage tags because one client serves several stages; the override only ever targets `tick`, so nothing is lost. The Kitaru SDK lives only in `src/pythia/kitaru_recorder.py`.
- Session boundary: one simulation run = one Kitaru session, agent identity `pythia-simulation`.
- Replay overrides apply only to the `fast_llm` client (agent ticks). Analyze/generate stay on the recorded model so the model swap is the only variable.
- Engine, orchestrator, and API code paths are unchanged when Kitaru is disabled.
- Dependency is optional: `pyproject.toml` extra `kitaru`; import guarded so the default install is unaffected.
- Credentials come from `.env` (user-supplied); nothing is hard-coded or logged.

## Cohort

- 5 prompts from the README "Try it" table × 2 seeds = 10 sessions.
- Simulation size ≈ 5 agents × 8 ticks (~50 LLM calls per session).
- Recorded with Groq: 70B for analyze/generate, `llama-3.1-8b-instant` for ticks.
- Cohort frozen once recorded.

## Experiment

1. **Noise floor** — unchanged replay of the cohort (ticks on 8B). Quantifies run-to-run variance in a stochastic multi-agent system and directly tests Kitaru's "faithful replay" claim.
2. **Model swap** — replay with ticks overridden to OpenAI `gpt-4o-mini` (tests cross-provider override, not just model name). Compare against the noise floor, not against the original recording alone.

Optional third arm (only if the first two go smoothly): Groq 70B for ticks.

## Evaluators

| Kind | Evaluator | Source |
|---|---|---|
| Deterministic | Parse-failure rate (tick fallback `"Failed to parse response"`) | tick events |
| Deterministic | Influence-target validity rate | tick events |
| Deterministic | Stance volatility (mean abs tick-to-tick delta) | tick events |
| Deterministic | Cost / tokens / latency | Kitaru session rollups |
| Judge | Coherence — reuse `EVAL_PROMPT` from `evaluator.py`, fixed judge model Groq 70B (neither arm grades itself) | per agent |
| Outcome | Verdict direction agreement vs. baseline | final aggregate stance |

## Friction log

`docs/kitaru/friction-log.md` — timestamped entries whenever something breaks, docs don't answer the question, or a workaround is needed. Each entry: what we tried, what happened, time lost, severity (blocker / major / minor), suggested fix. The memo is built from this log.

## Deliverables

1. Memo (shareable doc): what we built, results (metrics, cost, time), what worked, friction ranked by severity with fix suggestions, product-level observations (positioning shift from durable execution to replay-eval; custom-adapter story for non-framework agents; replay semantics for tool-less stochastic agents).
2. Short cover message pointing to the memo.

## Schedule

| Day | Work | Gate |
|---|---|---|
| Wed 09-23 | Install, cloud login, adapter, record ONE session | No recording by EOD → memo pivots to setup friction + reduced scope |
| Thu 09-24 | Record cohort, build evaluators, run noise-floor + swap replays | |
| Fri 09-25 | Analysis, memo, cover message | Send |

## Risks

- Custom-adapter docs defer to the `kitaru-adapter-builder` skill instead of code examples; we use the skill (part of the product experience) and log the result.
- Replay model may assume deterministic tool-call answering; Pythia has no tools and is stochastic. A mismatch is a finding, not a failure.
- Provider rate limits during replay (Groq 70B judge at 30 RPM): judge calls ≈ 10 sessions × 2 arms × 5 agents = 100, within limits if paced.

## Testing

- Unit tests for `RecordingLLMClient` with a fake inner client and a fake Kitaru recorder: delegation, stage tagging, override routing to `fast_llm` only, no-op when disabled.
- Existing 307 backend tests must stay green.
