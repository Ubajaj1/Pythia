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
    decision_summary: "DecisionSummary | None" = None
    influence_graph: "InfluenceGraph | None" = None


class OracleRequest(BaseModel):
    prompt: str
    context: str | None = None
    max_runs: int = Field(default=5, ge=1, le=10)
    document_text: str | None = None
    document_name: str | None = None


# --- Influence Graph ---

class InfluenceEdge(BaseModel):
    """A single influence event between two agents at a specific tick."""
    source_id: str
    target_id: str
    tick: int
    message: str
    source_stance_before: float
    target_stance_before: float
    target_stance_after: float
    influence_delta: float  # how much the target shifted (can be 0 if no effect yet)
    edge_type: str = "message"  # message, herd_pressure, contrarian_reaction


class InfluenceNode(BaseModel):
    """Snapshot of an agent at a specific tick within the influence graph."""
    agent_id: str
    tick: int
    stance: float
    action: str
    reasoning: str
    emotion: str


class InfluenceGraph(BaseModel):
    """Living graph of causal influence chains across a simulation run."""
    nodes: list[InfluenceNode] = Field(default_factory=list)
    edges: list[InfluenceEdge] = Field(default_factory=list)

    def add_tick_state(self, agent_id: str, tick: int, stance: float,
                       action: str, reasoning: str, emotion: str) -> None:
        self.nodes.append(InfluenceNode(
            agent_id=agent_id, tick=tick, stance=stance,
            action=action, reasoning=reasoning, emotion=emotion,
        ))

    def add_influence(self, source_id: str, target_id: str, tick: int,
                      message: str, source_stance: float,
                      target_stance_before: float, target_stance_after: float,
                      edge_type: str = "message") -> None:
        self.edges.append(InfluenceEdge(
            source_id=source_id, target_id=target_id, tick=tick,
            message=message, source_stance_before=source_stance,
            target_stance_before=target_stance_before,
            target_stance_after=target_stance_after,
            influence_delta=round(target_stance_after - target_stance_before, 4),
            edge_type=edge_type,
        ))

    def get_agent_trajectory(self, agent_id: str) -> list[InfluenceNode]:
        return [n for n in self.nodes if n.agent_id == agent_id]

    def get_influences_on(self, agent_id: str) -> list[InfluenceEdge]:
        return [e for e in self.edges if e.target_id == agent_id]

    def get_influences_by(self, agent_id: str) -> list[InfluenceEdge]:
        return [e for e in self.edges if e.source_id == agent_id]

    def get_strongest_influence_chains(self, top_n: int = 5) -> list[InfluenceEdge]:
        """Return the edges with the largest absolute influence delta."""
        sorted_edges = sorted(self.edges, key=lambda e: abs(e.influence_delta), reverse=True)
        return sorted_edges[:top_n]

    def get_herd_moments(self, agents_count: int, threshold: float = 0.6) -> list[int]:
        """Find ticks where a majority of agents shifted in the same direction."""
        tick_deltas: dict[int, list[float]] = {}
        prev_stances: dict[str, float] = {}
        for node in sorted(self.nodes, key=lambda n: (n.tick, n.agent_id)):
            if node.agent_id in prev_stances:
                delta = node.stance - prev_stances[node.agent_id]
                tick_deltas.setdefault(node.tick, []).append(delta)
            prev_stances[node.agent_id] = node.stance

        herd_ticks = []
        for tick, deltas in tick_deltas.items():
            if not deltas:
                continue
            positive = sum(1 for d in deltas if d > 0.01)
            negative = sum(1 for d in deltas if d < -0.01)
            if positive / len(deltas) >= threshold or negative / len(deltas) >= threshold:
                herd_ticks.append(tick)
        return herd_ticks


# --- Decision Summary ---

class KeyArgument(BaseModel):
    agent_name: str
    agent_role: str
    position: str
    reasoning: str


class DecisionSummary(BaseModel):
    """Human-readable interpretation of what the simulation means for the user's decision."""
    verdict: str  # e.g. "The panel leans toward raising a Series A"
    verdict_stance: float  # 0.0-1.0 final aggregate mapped to spectrum
    confidence: str  # "high", "moderate", "low", "polarized"
    confidence_rationale: str  # why this confidence level
    arguments_for: list[KeyArgument]  # strongest arguments toward high end of spectrum
    arguments_against: list[KeyArgument]  # strongest arguments toward low end
    key_risk: str  # the most important risk or dissenting insight
    what_could_change: str  # conditions that would flip the outcome
    influence_narrative: str  # plain English: who influenced whom and why
    herd_moments: list[str]  # descriptions of moments where group dynamics dominated


# --- Extended Run Result ---

class RunResultWithInsights(BaseModel):
    """RunResult enriched with influence graph and decision summary."""
    model_config = {"populate_by_name": True}

    run_id: str
    scenario: ScenarioInfo
    agents: list[AgentInfo]
    ticks: list[TickRecord]
    summary: RunSummary
    influence_graph: InfluenceGraph
    decision_summary: DecisionSummary | None = None


# --- Document Grounding ---

class GroundingFact(BaseModel):
    """A single fact extracted from a user-provided document."""
    entity: str
    fact: str
    relevance: str  # why this matters for the simulation


class GroundingContext(BaseModel):
    """Extracted facts and entities from user documents, used to ground the simulation."""
    source_type: str  # "document", "text", "url"
    source_name: str
    facts: list[GroundingFact]
    entity_summary: str  # one-paragraph summary of key entities and relationships
    raw_text: str = ""  # original text (truncated if needed)


class SimulateRequestWithDocs(BaseModel):
    """Extended simulate request that optionally includes document text for grounding."""
    prompt: str
    context: str | None = None
    document_text: str | None = None  # raw text from uploaded document
    document_name: str | None = None
