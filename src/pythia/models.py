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
    # Step 4: archetype retains suggested_biases so Pass 1 can seed plausible
    # biases per role, but the generator picks each agent's specific bias individually.
    suggested_biases: list[str] = Field(default_factory=list)

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
    # Step 4: bias_strength controls how strongly the bias shapes behavior.
    # 0.0 = bias has no mechanical effect, 1.0 = maximum effect.
    # Default 0.5 for backward compatibility with runs that predate this field.
    bias_strength: float = Field(default=0.5, ge=0.0, le=1.0)
    initial_stance: float = Field(ge=0.0, le=1.0)
    behavioral_rules: list[str]
    relationships: list[Relationship] = Field(default_factory=list)


# --- Simulation Engine I/O ---

class TickAction(BaseModel):
    """Raw output from an agent's LLM call for one tick.

    All fields have defaults so malformed LLM responses degrade gracefully
    instead of crashing the simulation.
    """
    stance: float = 0.5
    action: str = "none"
    emotion: str = "neutral"
    reasoning: str = ""
    message: str = ""
    influence_target: str | None = None

    @field_validator("stance", mode="before")
    @classmethod
    def coerce_stance(cls, v):
        """Coerce stance to a valid float in [0.0, 1.0]. Defaults to 0.5 on bad input."""
        if v is None:
            return 0.5
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.5


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
    bias_strength: float = 0.5  # backward compat: old runs default to 0.5
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
    prompt: str = Field(max_length=5000)
    context: str | None = Field(default=None, max_length=10000)


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
    prompt: str = Field(max_length=5000)
    context: str | None = Field(default=None, max_length=10000)
    max_runs: int = Field(default=5, ge=1, le=10)
    document_text: str | None = Field(default=None, max_length=50000)
    document_name: str | None = Field(default=None, max_length=100, pattern=r'^[^\n\r]*$')
    agent_count: int | None = Field(default=None, ge=3, le=15)
    tick_count: int | None = Field(default=None, ge=5, le=50)
    preset: str | None = None


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
    verdict: str
    verdict_stance: float
    confidence: str  # "high", "moderate", "low", "polarized"
    confidence_rationale: str
    # Dispersion metrics (computed deterministically, not LLM-picked) — see pythia.confidence
    agreement_label: str | None = None   # "clustered", "mixed", "spread"
    conviction_label: str | None = None  # "strong", "moderate", "tepid"
    stance_stddev: float | None = None   # population stddev of final stances (0–1 scale)
    stance_spread: float | None = None   # max − min of final stances
    arguments_for: list[KeyArgument]
    arguments_against: list[KeyArgument]
    key_risk: str
    what_could_change: str
    actionable_takeaways: list[str] = Field(default_factory=list)  # specific next steps for the user
    influence_narrative: str
    herd_moments: list[str]
    # Step 7: per-agent grounded reasoning rate — percentage of tick events
    # whose reasoning contains at least one [Fxx] citation.
    # Only populated when grounding was used. Empty dict means no grounding.
    grounded_reasoning_rates: dict[str, float] = Field(default_factory=dict)


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
    # The Oracle's Method — metadata about how this run was computed
    methodology: "SimulationMethodology | None" = None


class SimulationMethodology(BaseModel):
    """Metadata about how a simulation was computed — 'The Oracle's Method'.

    Exposed in the UI so users can understand and trust the verdict.
    """
    agent_count: int
    tick_count: int
    agents_per_role: dict[str, int] = Field(default_factory=dict)  # role → count
    biases_assigned: dict[str, str] = Field(default_factory=dict)  # agent_id → bias name
    ensemble_size: int = 1  # 1 = single run, >1 = ensemble
    seed: int | None = None  # reproducibility seed, if provided
    confidence_thresholds: dict[str, float] = Field(default_factory=dict)  # named thresholds used
    llm_provider: str = "unknown"
    llm_model: str = "unknown"


# --- Document Grounding ---

class GroundingFact(BaseModel):
    """A single fact extracted from a user-provided document."""
    entity: str
    fact: str
    relevance: str  # why this matters for the simulation
    # Step 7: short-form ID for citation tracking (e.g. "F1", "F2")
    fact_id: str = ""


class GroundingContext(BaseModel):
    """Extracted facts and entities from user documents, used to ground the simulation."""
    source_type: str  # "document", "text", "url"
    source_name: str
    facts: list[GroundingFact]
    entity_summary: str  # one-paragraph summary of key entities and relationships
    raw_text: str = ""  # original text (truncated if needed)


class SimulateRequestWithDocs(BaseModel):
    """Extended simulate request that optionally includes document text for grounding."""
    prompt: str = Field(max_length=5000)
    context: str | None = Field(default=None, max_length=10000)
    document_text: str | None = Field(default=None, max_length=50000)
    document_name: str | None = Field(default=None, max_length=100, pattern=r'^[^\n\r]*$')
    agent_count: int | None = Field(default=None, ge=3, le=15)
    tick_count: int | None = Field(default=None, ge=5, le=50)
    preset: str | None = None
    seed: int | None = None


# --- Ensemble Runs (Step 6) ---

class EnsembleResult(BaseModel):
    """Wraps N simulation runs of the same scenario for statistical robustness.

    Agent generation happens once; only the engine tick loop repeats per run.
    The ensemble aggregates confidence, herd moments, and stance distributions
    across runs to distinguish real signals from LLM noise.
    """
    model_config = {"populate_by_name": True}

    ensemble_size: int
    runs: list[RunResultWithInsights]
    # The "primary" run — the one shown in the UI animation (run index 0)
    primary_run: RunResultWithInsights | None = None
    # Aggregated ensemble metrics
    aggregate_distribution: list[float] = Field(default_factory=list)  # final aggregate stance per run
    confidence_distribution: list[str] = Field(default_factory=list)   # confidence label per run
    agreement_ratio: float = 0.0  # fraction of runs that agree on the most common confidence label
    ensemble_confidence: str = "low"  # worst-case confidence unless all agree
    robust_herd_moments: list[str] = Field(default_factory=list)  # herd moments in ≥2 runs
    noisy_herd_moments: list[str] = Field(default_factory=list)   # herd moments in only 1 run
    # The ensemble's decision summary (from the primary run, annotated with ensemble context)
    decision_summary: DecisionSummary | None = None


class EnsembleRequest(BaseModel):
    """API request for ensemble simulation."""
    prompt: str = Field(max_length=5000)
    context: str | None = Field(default=None, max_length=10000)
    document_text: str | None = Field(default=None, max_length=50000)
    document_name: str | None = Field(default=None, max_length=100, pattern=r'^[^\n\r]*$')
    agent_count: int | None = Field(default=None, ge=3, le=15)
    tick_count: int | None = Field(default=None, ge=5, le=50)
    preset: str | None = None
    ensemble_size: int = Field(default=3, ge=1, le=5)


# --- Ground-Truth Mode (Step 8) ---

class GroundTruthOutcome(BaseModel):
    """The known actual outcome for a past event, used to score Pythia's prediction."""
    aggregate_stance: float = Field(ge=0.0, le=1.0)
    confidence: str = "moderate"
    notes: str = Field(default="", max_length=2000)


class CalibrationScore(BaseModel):
    """How well Pythia's prediction matched the actual outcome for one past event."""
    direction_correct: bool  # predicted and actual on the same side of 0.5 (or within threshold)
    aggregate_error: float   # |predicted_aggregate - actual_aggregate|
    confidence_match: bool   # predicted confidence label matches actual outcome's clarity


class BacktestCase(BaseModel):
    """A single ground-truth case for backtesting. Stored as JSON in data/ground_truth/."""
    prompt: str
    context: str | None = None
    document_text: str | None = None
    ground_truth_outcome: GroundTruthOutcome
    # Optional metadata
    case_id: str = ""
    domain: str = ""  # e.g. "earnings", "policy", "internal_decision"
    description: str = ""


class BacktestResult(BaseModel):
    """Result of running one backtest case."""
    case_id: str
    prompt: str
    predicted_aggregate: float
    predicted_confidence: str
    actual_aggregate: float
    actual_confidence: str
    calibration: CalibrationScore
    run_id: str  # link to the full RunResult


class CalibrationReport(BaseModel):
    """Aggregate calibration across multiple backtest cases."""
    total_cases: int
    direction_accuracy: float  # fraction of cases where direction was correct
    mean_aggregate_error: float
    confidence_match_rate: float  # fraction where confidence label matched
    results: list[BacktestResult]


class BacktestRequest(BaseModel):
    """API request for running a single backtest (past_event mode)."""
    prompt: str = Field(max_length=5000)
    context: str | None = Field(default=None, max_length=10000)
    document_text: str | None = Field(default=None, max_length=50000)
    document_name: str | None = Field(default=None, max_length=100, pattern=r'^[^\n\r]*$')
    ground_truth_outcome: GroundTruthOutcome
    agent_count: int | None = Field(default=None, ge=3, le=15)
    tick_count: int | None = Field(default=None, ge=5, le=50)
    preset: str | None = None
