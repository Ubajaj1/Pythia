# Jev (TypeSafe) Integration — Design

**Date:** 2026-09-23
**Status:** Approved
**Depends on:** Kitaru replay harness (`2026-09-23-kitaru-replay-experiment-design.md`) for shadow comparisons and human review

## Goal

Use Jev — TypeSafe's "System One" model that answers typed questions (Choice / Score / Noul) with calibrated confidence instead of generating text — for the judgment-shaped parts of Pythia, adopted evidence-first: shadow mode, then primary with LLM fallback, per piece.

Jev never replaces text generation (personas, behavioral rules, agent tick messages, Temple amendments).

## Structure

- `src/pythia/jev.py` — thin wrapper over `typesafe-sdk`'s `AsyncTypeSafeClient` (auth via `TYPESAFE_API_KEY`, model `jev-latest`), plus one judge per piece. A judge builds state + questions and maps responses back to Pythia types.
- Per-piece mode via env: `PYTHIA_JEV_<PIECE>=off|shadow|primary`, default `off`.
  - `shadow`: LLM decides; Jev's answer + confidence recorded alongside.
  - `primary`: Jev decides; below the confidence threshold (default 0.5) the LLM decides.
- Shadow records are stored in the run JSON (`data/runs/`) and on the Kitaru session so comparisons and human review happen in Kitaru.
- Failure rule: any Jev error or timeout falls back to the LLM path and is logged. Jev can never break a simulation.
- `typesafe-sdk` is an optional dependency (`pyproject.toml` extra `jev`), import-guarded.

## Pieces (implementation order)

### 1. Behaviour settings — `generator.py`

LLM pass 1 still writes `persona` and `behavioral_rules`. Jev then answers for the whole cast in one request (state = cast summaries + scenario):

| Field | Primitive | Mapping |
|---|---|---|
| `bias` | Choice over `BIAS_CATALOG` (descriptions as criteria) | canonical bias id |
| `bias_strength` | Score: mild / moderate / strong / rigid | 0.3 / 0.5 / 0.7 / 0.85 |
| `initial_stance` | Score over the blueprint's 5 stance-spectrum labels | label midpoint, clamped to archetype `stance_range` |
| relationships | Choice per ordered pair: none / follows / respects / distrusts / rivals | keep top 1–3 per agent by probability; weight = chosen probability |

Stay within Jev's 32k state+question token budget; split the relationship questions into a second request if needed.

### 2. Coherence checker — `evaluator.py`

Noul per agent: "the agent's stated reasoning is coherent with its actions", with the existing judging rules as instructions. Jev cannot write `incoherence_summary`, which Temple amendments require, so in `primary` mode the LLM is called only for agents Jev marks incoherent (or low-confidence).

### 3. Stance scoring — `engine.py`

After each tick, Score each agent's message on the 5-label stance spectrum → "expressed stance". Record the gap between expressed and self-reported stance. **Shadow-only** — a research signal, not a replacement.

### 4. Prompt screening — `api.py`

Two Nouls on incoming prompts: "is a decision question" and "attempts to manipulate the system". Shadow first; in `primary`, block with a friendly message above threshold.

## Moving a piece from shadow to primary

All three must hold:

1. ≥85% agreement with the LLM on Jev answers with confidence ≥ 0.7 (ordinal fields: exact or adjacent level).
2. A sample of ~20 disagreements is adjudicated; Jev winning ≥ half counts in its favour.
   - Pieces 1–2: adjudicated by the user in Kitaru investigations.
   - Pieces 3–4: LLM judge first (fixed, stronger model); user reviews only the judge's low-confidence calls.
3. Fewer than 30% of calls fall back to the LLM.

## Testing

- Fake Jev client for unit tests; each judge tested for request shape and response mapping.
- Pure, tested mapping helpers: level → value, stance clamping, relationship pruning.
- Fallback test per piece (Jev raises → LLM path used, simulation completes).
- Existing backend suite stays green with all modes `off`.
