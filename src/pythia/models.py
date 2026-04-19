"""Pydantic models for all Pythia data structures."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


# --- Scenario Analyzer output ---

class AgentArchetype(BaseModel):
    role: str
    count: int = Field(ge=1)
    description: str
    bias: str
    stance_range: tuple[float, float]

    @field_validator("stance_range")
    @classmethod
    def validate_stance_range(cls, v: tuple[float, float]) -> tuple[float, float]:
        low, high = v
        if not (0.0 <= low <= 1.0 and 0.0 <= high <= 1.0):
            raise ValueError("stance_range values must be between 0.0 and 1.0")
        if low >= high:
            raise ValueError("stance_range low must be less than high")
        return v


class ScenarioBlueprint(BaseModel):
    scenario_type: str
    title: str
    description: str
    stance_spectrum: list[str]
    agent_archetypes: list[AgentArchetype]
    dynamics: str
    tick_count: int = Field(default=20, ge=1)

    @field_validator("stance_spectrum")
    @classmethod
    def validate_spectrum_length(cls, v: list[str]) -> list[str]:
        if len(v) != 5:
            raise ValueError("stance_spectrum must have exactly 5 labels")
        return v


# --- Agent Generator output ---

class Relationship(BaseModel):
    target: str
    type: str  # follows, distrusts, rivals, respects
    weight: float = Field(ge=0.0, le=1.0)


class Agent(BaseModel):
    id: str
    name: str
    role: str
    persona: str
    bias: str
    initial_stance: float = Field(ge=0.0, le=1.0)
    behavioral_rules: list[str]
    relationships: list[Relationship] = Field(default_factory=list)


# --- Simulation Engine I/O ---

class TickAction(BaseModel):
    """Raw output from an agent's LLM call for one tick."""
    stance: float
    action: str
    emotion: str
    reasoning: str
    message: str
    influence_target: str | None = None

    @field_validator("stance")
    @classmethod
    def clamp_stance(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class TickEvent(BaseModel):
    """One agent's contribution to a tick, enriched with context."""
    agent_id: str
    stance: float
    previous_stance: float
    action: str
    emotion: str
    reasoning: str
    message: str
    influence_target: str | None = None


class TickRecord(BaseModel):
    """All events for a single tick."""
    tick: int
    events: list[TickEvent]
    aggregate_stance: float


# --- Run output ---

class BiggestShift(BaseModel):
    agent_id: str
    from_stance: float = Field(serialization_alias="from")
    to_stance: float = Field(serialization_alias="to")
    reason: str


class RunSummary(BaseModel):
    total_ticks: int
    final_aggregate_stance: float
    biggest_shift: BiggestShift
    consensus_reached: bool


class ScenarioInfo(BaseModel):
    input: str
    type: str
    title: str
    stance_spectrum: list[str]


class AgentInfo(BaseModel):
    id: str
    name: str
    role: str
    persona: str
    bias: str
    initial_stance: float


class RunResult(BaseModel):
    model_config = {"populate_by_name": True}

    run_id: str
    scenario: ScenarioInfo
    agents: list[AgentInfo]
    ticks: list[TickRecord]
    summary: RunSummary


# --- API request ---

class SimulateRequest(BaseModel):
    prompt: str
    context: str | None = None


# --- Oracle Loop ---

class AgentEvaluation(BaseModel):
    agent_id: str
    is_coherent: bool
    incoherence_summary: str | None = None


class OracleRunRecord(BaseModel):
    run_number: int
    result: RunResult
    evaluations: list[AgentEvaluation]
    coherence_score: float
    amended_agent_ids: list[str]


class OracleLoopResult(BaseModel):
    prompt: str
    runs: list[OracleRunRecord]
    coherence_history: list[float]


class OracleRequest(BaseModel):
    prompt: str
    context: str | None = None
    max_runs: int = Field(default=5, ge=1, le=10)
