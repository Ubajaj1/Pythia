# Graph Memory & Self-Healing — Design Note

> Date: 2026-04-05
> Status: Future reference (Phase 2+)
> Context: Captured during Phase 1 brainstorming to guide future architecture decisions

---

## Graph Memory

Three levels, each plugging into a different spot in the pipeline.

### Level 1 — Ingestion Layer (before Scenario Analyzer)

Web search + GraphRAG pipeline. Sits upstream of everything:

```
User Input → [Graph Memory: extract entities + relationships from documents]
                    ↓
            Enriched Input → Scenario Analyzer → ...
```

GraphRAG takes user input + retrieved documents, extracts entities (Fed, Treasury, retail investors, tech sector) and their relationships (Fed → influences → Treasury yields). This enriched graph replaces the LLM having to invent the world from scratch — the Scenario Analyzer gets real entities to build archetypes from.

**Phase:** 1.5 (between Phase 1 and 2)
**Plugs into:** Upstream of `analyzer.py`
**Tech candidates:** Microsoft GraphRAG, or lighter LLM-based entity extraction

### Level 2 — Agent Memory During Simulation

Replace the flat-list `AgentMemory` with graph-based memory so agents reason about relationships between events, not just sequence:

```
AgentMemory (current): [tick1, tick2, tick3, ...]
AgentMemory (graph):   tick1 --caused--> tick2 --contradicts--> tick3
                       "Ivan's hold" --influenced--> "my shift to bullish"
```

Plugs in at `AgentMemory.for_prompt()` — the interface stays the same, but the prompt gets richer context.

**Phase:** 2
**Plugs into:** `engine.py` → `AgentMemory` class (seam already exists via `for_prompt()`)
**Tech candidates:** Zep Cloud (listed in PLAN.md tech stack)

### Level 3 — Cross-Simulation Research DAG

A persistent graph that survives across runs. Example: "In the last market simulation, herd behavior triggered at tick 7 when aggregate hit 0.3" becomes a node that seeds hypotheses in the next simulation.

**Phase:** 5 (Hyperspace-inspired)
**Plugs into:** New standalone subsystem, reads/writes `data/` directory
**Tech candidates:** Hyperspace-inspired Research DAG

---

## Self-Healing (Temple of Learning)

A loop around the simulation engine, not inside it. After a run completes, failing agents get their behavioral rules rewritten and re-enter the next run.

### Architecture

```
                    ┌────────────────────────────────────┐
                    │                                    │
User Input → Analyzer → Generator → Engine → Run JSON   │
                                       │                 │
                                       ▼                 │
                                  Evaluator              │
                                  (compare to            │
                                   ground truth)         │
                                       │                 │
                                       ▼                 │
                              ┌─── Pass? ───┐            │
                              │ Yes         │ No         │
                              ▼             ▼            │
                           Done        Temple of         │
                                       Learning          │
                                       (rewrite          │
                                       behavioral_rules) │
                                           │             │
                                           └─────────────┘
                                       Re-run with amended agents
```

### Integration Points (seams already exist in Phase 1)

1. **`behavioral_rules` on each Agent** — these are the "scrolls." The Temple rewrites them. The field already exists in `models.py`.

2. **`RunResult.summary`** — the Evaluator compares `final_aggregate_stance` and per-agent stances to ground truth. Ground truth data lives in `data/ground_truth/`.

3. **`generate_agents()` is skippable for re-runs** — pass amended agents directly back into the engine instead of regenerating from scratch.

### Temple Implementation (v1 — simple LLM rewrite)

One LLM call per failing agent:

> "This agent predicted X, reality was Y. Here are their current behavioral rules. Rewrite the rules to correct this failure."

Input: agent's `behavioral_rules` + their prediction trajectory + ground truth
Output: new `behavioral_rules` list

This is where Cognee would fit as a more sophisticated skill amendment framework, but v1 is just a targeted LLM call.

### New Components Needed

| Component | File | Responsibility |
|-----------|------|---------------|
| Evaluator | `src/pythia/evaluator.py` | Compare run results to ground truth, identify failing agents |
| Temple | `src/pythia/temple.py` | Rewrite behavioral_rules for failing agents via LLM |
| Ground truth loader | `src/pythia/ground_truth.py` | Load/manage ground truth data from `data/ground_truth/` |
| Run loop | `src/pythia/oracle_loop.py` | Orchestrate: run → evaluate → amend → re-run (N iterations) |

**Phase:** 2
**Tech candidates:** Cognee for skill amendment, or plain LLM calls for v1

---

## Phase Roadmap Summary

| Feature | Phase | Plugs into |
|---------|-------|------------|
| GraphRAG ingestion | 1.5 | Upstream of Scenario Analyzer |
| Graph agent memory (Zep) | 2 | `AgentMemory.for_prompt()` |
| Temple / self-healing | 2 | Loop around Engine, rewrites `behavioral_rules` |
| Cross-sim Research DAG | 5 | New persistent subsystem |
