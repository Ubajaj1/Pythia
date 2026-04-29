"""Simulation Engine — tick-by-tick opinion dynamics loop."""

from __future__ import annotations

import asyncio
import json
import logging

from pythia.biases import format_bias_for_prompt
from pythia.bias_mechanics import apply_bias
from pythia.llm import LLMClient
from pythia.models import (
    Agent,
    InfluenceGraph,
    ScenarioBlueprint,
    TickAction,
    TickEvent,
    TickRecord,
)

logger = logging.getLogger(__name__)


class AgentMemory:
    """Stores an agent's full tick history for prompt inclusion.

    `full_history` is preserved intact for run JSON export and the influence
    graph. `for_prompt()` returns a pivot-preserving compressed view once
    history grows beyond the threshold — keeping the anchor (tick 1), pivot
    moments where stance moved meaningfully, and the last few ticks.
    """

    # When history has this many or fewer ticks, return everything.
    # Above this, pivot-preserving compression kicks in.
    COMPRESSION_THRESHOLD = 4

    # Number of most-recent ticks always kept verbatim.
    RECENT_WINDOW = 3

    # Minimum stance delta (vs. last kept tick) to count as a pivot.
    # 0.10 catches real directional shifts while ignoring small drift
    # during a sustained trend (e.g. repeated "strengthen support" ticks).
    PIVOT_DELTA = 0.10

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.full_history: list[dict] = []

    def record(self, tick_event: dict) -> None:
        self.full_history.append(tick_event)

    def for_prompt(self) -> list[dict]:
        """Return a prompt-friendly view of history.

        Short runs get the full history. Longer runs get:
          1. The anchor tick (tick 1) — the agent's starting position.
          2. Any middle tick that represents a stance pivot (>= PIVOT_DELTA).
          3. The last RECENT_WINDOW ticks — immediate context.

        Full history is untouched; only the prompt view is compressed.
        """
        if len(self.full_history) <= self.COMPRESSION_THRESHOLD:
            return list(self.full_history)

        anchor = [self.full_history[0]]
        recent = self.full_history[-self.RECENT_WINDOW:]
        middle = self.full_history[1:-self.RECENT_WINDOW]

        # Walk the middle, keeping only ticks that pivoted vs. the last kept stance.
        prev_stance = anchor[0]["stance"]
        pivots: list[dict] = []
        for tick in middle:
            if abs(tick["stance"] - prev_stance) >= self.PIVOT_DELTA:
                pivots.append(tick)
                prev_stance = tick["stance"]

        return anchor + pivots + recent


AGENT_SYSTEM_TEMPLATE = """\
You are {name}, {persona}.

Your behavioral rules:
{rules}

{bias_description}"""

AGENT_PROMPT_TEMPLATE = """\
Scenario: {title} — {description}
Dynamics: {dynamics}
Stance spectrum: {spectrum}
{grounding}
Current world state:
- Aggregate sentiment: {aggregate_stance} ({aggregate_label})
- Other agents:
{other_agents}

Messages directed at you:
{messages}

Your history:
{history}

---

Valid influence_target values (use EXACTLY one of these IDs, or null if broadcasting to no one specific):
{valid_targets}

Respond with ONLY this JSON (no other text):
{{"stance": <float 0.0-1.0>, "action": "<what you do>", "emotion": "<how you feel>", "reasoning": "<why in one sentence>", "message": "<what you say to others>", "influence_target": "<one of the IDs above, or null>"}}"""


def _stance_to_label(stance: float, spectrum: list[str]) -> str:
    """Map a 0.0-1.0 stance to one of 5 spectrum labels."""
    idx = min(int(stance * len(spectrum)), len(spectrum) - 1)
    return spectrum[idx]


def _format_rules(rules: list[str]) -> str:
    return "\n".join(f"- {r}" for r in rules)


def _format_history(memory: AgentMemory) -> str:
    entries = memory.for_prompt()
    if not entries:
        return "(no history yet — this is tick 1)"
    total_ticks = len(memory.full_history)
    is_compressed = len(entries) < total_ticks
    lines = []
    if is_compressed:
        lines.append(
            f"(showing key moments from your {total_ticks}-tick history: "
            "anchor, pivots, and recent context)"
        )
    for e in entries:
        lines.append(
            f"Tick {e['tick']}: stance={e['stance']}, action={e['action']}, "
            f"emotion={e['emotion']}, reasoning=\"{e['reasoning']}\""
        )
    return "\n".join(lines)


# ── Relationship attention weights ────────────────────────────────────────────
# These are relative, not absolute. They determine how prominently each other
# agent is described in the prompt. Higher = more detail and attention cues.
# "none" agents still appear (the agent should know they exist) but minimally.
RELATIONSHIP_ATTENTION_WEIGHTS: dict[str, float] = {
    "follows": 1.0,    # actively tracks this agent's views
    "respects": 1.0,   # values this agent's opinion highly
    "distrusts": 0.8,  # pays attention but with skepticism
    "rivals": 0.7,     # contrarian attention — watches to oppose
    "none": 0.3,       # aware but not particularly attentive
}

# Prompt framing per relationship type — injected into the agent's world view
_RELATIONSHIP_FRAMING: dict[str, str] = {
    "follows": "You tend to pay close attention to {name}'s views.",
    "respects": "You hold {name}'s judgment in high regard.",
    "distrusts": "You view {name}'s arguments with skepticism.",
    "rivals": "You often position yourself against {name}.",
}


def _format_other_agents(
    agent_id: str, current_stances: dict[str, dict], agents: list[Agent]
) -> str:
    """Render other agents for the prompt, weighted and annotated by relationship.

    Agents with relationships (follows, respects, distrusts, rivals) get prominent
    descriptions with attention cues. Agents with no relationship get minimal
    descriptions — just name + stance.
    """
    # Build relationship lookup for this agent
    this_agent = next((a for a in agents if a.id == agent_id), None)
    rel_map: dict[str, tuple[str, float]] = {}  # target_id → (type, weight)
    if this_agent:
        for rel in this_agent.relationships:
            rel_map[rel.target] = (rel.type, rel.weight)

    # Sort: related agents first (by attention weight desc), then unrelated
    def sort_key(a: Agent) -> tuple[float, str]:
        if a.id in rel_map:
            rel_type, _ = rel_map[a.id]
            return (-RELATIONSHIP_ATTENTION_WEIGHTS.get(rel_type, 0.3), a.name)
        return (-RELATIONSHIP_ATTENTION_WEIGHTS["none"], a.name)

    lines = []
    for a in sorted((a for a in agents if a.id != agent_id), key=sort_key):
        state = current_stances.get(a.id, {})
        stance = state.get("stance", a.initial_stance)
        action = state.get("action", "none yet")

        if a.id in rel_map:
            rel_type, rel_weight = rel_map[a.id]
            framing = _RELATIONSHIP_FRAMING.get(rel_type, "")
            framing_text = framing.format(name=a.name) if framing else ""
            lines.append(
                f'  - "{a.id}" / {a.name} ({a.role}): stance={stance:.2f}, last action={action}'
                f"  [{rel_type}, strength {rel_weight:.1f}] {framing_text}"
            )
        else:
            # Minimal description for unrelated agents
            lines.append(f'  - "{a.id}" / {a.name} ({a.role}): stance={stance:.2f}')

    return "\n".join(lines) if lines else "  (none)"


def _get_messages_for_agent(
    agent_id: str, recent_messages: list[dict], agents: list[Agent]
) -> str:
    """Format messages directed at this agent, tagged with relationship context."""
    msgs = [m for m in recent_messages if m.get("to") == agent_id]
    if not msgs:
        return "(no messages)"

    # Build relationship lookup for the receiving agent
    this_agent = next((a for a in agents if a.id == agent_id), None)
    rel_map: dict[str, str] = {}  # source_id → relationship type
    if this_agent:
        for rel in this_agent.relationships:
            rel_map[rel.target] = rel.type

    lines = []
    for m in msgs:
        source_id = m["from"]
        rel_type = rel_map.get(source_id, "")
        rel_tag = f" [{rel_type}]" if rel_type else ""
        lines.append(
            f"  - {m['from_name']}{rel_tag} (tick {m['tick']}): \"{m['message']}\""
        )
    return "\n".join(lines)


def _normalize_id(s: str) -> str:
    """Lowercase, strip non-alphanumeric — used for fuzzy ID matching."""
    return "".join(c for c in s.lower() if c.isalnum())


def _resolve_influence_target(
    raw_target: str | None, agents: list[Agent], self_id: str
) -> str | None:
    """Resolve an LLM-provided influence_target to a valid agent ID.

    Handles common LLM malformations:
    - Literal string "null" / "none" / "" → None
    - Comma-separated multi-target strings → None (engine only supports one target)
    - Exact ID match → use as-is
    - Fuzzy match against ID, name, or normalized variants (e.g. "CodeCrusher",
      "vincent_bugbuster", "VINCENT BUGBUSTER" all map to the right agent)
    - Self-reference → None (can't influence yourself)
    - No match → None
    """
    if raw_target is None:
        return None
    raw = str(raw_target).strip()
    if not raw or raw.lower() in ("null", "none", "n/a", "nobody", "no one"):
        return None

    # Reject multi-target strings — "Alex, Maya" and "Alex and Maya" are
    # ambiguous and the engine only supports one target per message.
    # Split on commas or " and " and if there are 2+ non-trivial parts, bail.
    if "," in raw or " and " in raw.lower():
        return None

    # Exact ID match
    for a in agents:
        if a.id == raw:
            return None if a.id == self_id else a.id

    # Fuzzy match: normalize and compare against IDs and names
    norm_raw = _normalize_id(raw)
    if not norm_raw:
        return None

    for a in agents:
        if _normalize_id(a.id) == norm_raw or _normalize_id(a.name) == norm_raw:
            return None if a.id == self_id else a.id

    # Substring match as last resort — but only if it's unambiguous.
    # If the raw string substring-matches multiple agents, return None rather
    # than picking one arbitrarily.
    substring_matches = []
    for a in agents:
        norm_id = _normalize_id(a.id)
        norm_name = _normalize_id(a.name)
        if norm_raw in norm_id or norm_raw in norm_name or norm_id in norm_raw or norm_name in norm_raw:
            substring_matches.append(a)

    if len(substring_matches) == 1:
        matched = substring_matches[0]
        return None if matched.id == self_id else matched.id

    return None


def _format_valid_targets(agents: list[Agent], self_id: str) -> str:
    """Render the roster of valid influence_target IDs for the prompt."""
    lines = []
    for a in agents:
        if a.id == self_id:
            continue
        lines.append(f'  - "{a.id}"  ({a.name})')
    return "\n".join(lines) if lines else "  (no other agents)"


class SimulationEngine:
    """Runs the perceive → reason → act loop for all agents over N ticks."""

    def __init__(
        self,
        blueprint: ScenarioBlueprint,
        agents: list[Agent],
        llm: LLMClient,
        grounding_context: str = "",
    ):
        self.blueprint = blueprint
        self.agents = agents
        self.llm = llm
        self.grounding_context = grounding_context

        # Defensive check — the generator deduplicates IDs, but a caller
        # constructing agents by hand (tests, scripts) could still pass
        # colliding IDs. current_stances is a dict keyed by id, so
        # collisions silently drop agents from the aggregate.
        ids_seen: dict[str, int] = {}
        for a in agents:
            ids_seen[a.id] = ids_seen.get(a.id, 0) + 1
        dupes = [aid for aid, c in ids_seen.items() if c > 1]
        if dupes:
            raise ValueError(
                f"SimulationEngine received agents with duplicate IDs: {dupes}. "
                "Each agent.id must be unique — the engine stores state keyed by "
                "id and colliding agents would be silently dropped from the aggregate."
            )

        self.memories: dict[str, AgentMemory] = {
            a.id: AgentMemory(a.id) for a in agents
        }
        self.current_stances: dict[str, dict] = {
            a.id: {"stance": a.initial_stance, "action": "none", "emotion": "neutral"}
            for a in agents
        }
        self.recent_messages: list[dict] = []
        self._agent_map: dict[str, Agent] = {a.id: a for a in agents}
        self.influence_graph = InfluenceGraph()

    async def run_stream(self):
        """Async generator — yields each TickRecord as it completes."""
        logger.info(
            "Simulation started scenario=%r agents=%d ticks=%d",
            self.blueprint.title, len(self.agents), self.blueprint.tick_count,
        )
        logger.debug("Agents: %s", ", ".join(f"{a.name}({a.initial_stance:.2f})" for a in self.agents))
        for tick_num in range(1, self.blueprint.tick_count + 1):
            tick_record = await self._run_tick(tick_num)
            yield tick_record
        logger.info("Simulation complete scenario=%r", self.blueprint.title)

    async def run(self) -> list[TickRecord]:
        """Run the full simulation and return all tick records."""
        tick_records = []
        async for tick_record in self.run_stream():
            tick_records.append(tick_record)
        return tick_records

    async def _run_tick(self, tick_num: int) -> TickRecord:
        """Run a single tick: all agents reason in parallel, update influence graph."""
        aggregate = self._compute_aggregate()
        logger.info(
            "Tick %d/%d aggregate_stance=%.3f (%s)",
            tick_num, self.blueprint.tick_count, aggregate,
            _stance_to_label(aggregate, self.blueprint.stance_spectrum),
        )

        # Snapshot pre-tick stances for influence tracking
        pre_tick_stances = {aid: s["stance"] for aid, s in self.current_stances.items()}

        tasks = [
            self._run_agent_tick(agent, tick_num, aggregate)
            for agent in self.agents
        ]
        events = await asyncio.gather(*tasks)

        new_messages: list[dict] = []
        for event in events:
            # Record node in influence graph
            self.influence_graph.add_tick_state(
                agent_id=event.agent_id, tick=tick_num,
                stance=event.stance, action=event.action,
                reasoning=event.reasoning, emotion=event.emotion,
            )

            self.current_stances[event.agent_id] = {
                "stance": event.stance,
                "action": event.action,
                "emotion": event.emotion,
            }
            self.memories[event.agent_id].record({
                "tick": tick_num,
                "stance": event.stance,
                "action": event.action,
                "emotion": event.emotion,
                "reasoning": event.reasoning,
            })
            if event.influence_target and event.influence_target in self._agent_map:
                new_messages.append({
                    "from": event.agent_id,
                    "from_name": self._agent_map[event.agent_id].name,
                    "to": event.influence_target,
                    "tick": tick_num,
                    "message": event.message,
                })

        # Record influence edges: for each message, track the target's stance change
        for msg in new_messages:
            target_id = msg["to"]
            source_id = msg["from"]
            target_event = next((e for e in events if e.agent_id == target_id), None)
            if target_event:
                self.influence_graph.add_influence(
                    source_id=source_id,
                    target_id=target_id,
                    tick=tick_num,
                    message=msg["message"],
                    source_stance=pre_tick_stances.get(source_id, 0.5),
                    target_stance_before=pre_tick_stances.get(target_id, 0.5),
                    target_stance_after=target_event.stance,
                    edge_type="message",
                )

        # Detect herd pressure: if aggregate shifted significantly, record implicit influence
        new_aggregate = self._compute_aggregate()
        agg_shift = abs(new_aggregate - aggregate)
        if agg_shift > 0.03 and tick_num > 1:
            for event in events:
                agent_delta = event.stance - pre_tick_stances.get(event.agent_id, 0.5)
                # Agent moved in same direction as aggregate — herd pressure
                if (agent_delta > 0.02 and new_aggregate > aggregate) or \
                   (agent_delta < -0.02 and new_aggregate < aggregate):
                    if not event.influence_target:  # no explicit message, so this is herd
                        self.influence_graph.add_influence(
                            source_id="__aggregate__",
                            target_id=event.agent_id,
                            tick=tick_num,
                            message=f"Aggregate shifted to {new_aggregate:.2f}",
                            source_stance=aggregate,
                            target_stance_before=pre_tick_stances.get(event.agent_id, 0.5),
                            target_stance_after=event.stance,
                            edge_type="herd_pressure",
                        )

        self.recent_messages = new_messages

        return TickRecord(
            tick=tick_num,
            events=list(events),
            aggregate_stance=round(new_aggregate, 4),
        )

    async def _run_agent_tick(
        self, agent: Agent, tick_num: int, aggregate: float
    ) -> TickEvent:
        """Build prompt for one agent, call LLM, validate and return TickEvent."""
        previous_stance = self.current_stances[agent.id]["stance"]

        system = AGENT_SYSTEM_TEMPLATE.format(
            name=agent.name,
            persona=agent.persona,
            rules=_format_rules(agent.behavioral_rules),
            bias_description=format_bias_for_prompt(agent.bias),
        )

        prompt = AGENT_PROMPT_TEMPLATE.format(
            title=self.blueprint.title,
            description=self.blueprint.description,
            dynamics=self.blueprint.dynamics,
            spectrum=json.dumps(self.blueprint.stance_spectrum),
            grounding=self.grounding_context if self.grounding_context else "",
            aggregate_stance=f"{aggregate:.2f}",
            aggregate_label=_stance_to_label(aggregate, self.blueprint.stance_spectrum),
            other_agents=_format_other_agents(agent.id, self.current_stances, self.agents),
            messages=_get_messages_for_agent(agent.id, self.recent_messages, self.agents),
            history=_format_history(self.memories[agent.id]),
            valid_targets=_format_valid_targets(self.agents, agent.id),
        )

        logger.debug(
            "Agent tick prompt agent=%s tick=%d\n--- SYSTEM ---\n%s\n--- PROMPT ---\n%s",
            agent.name, tick_num, system, prompt,
        )

        raw = await self.llm.generate(prompt=prompt, system=system)
        try:
            action = TickAction.model_validate(raw)
        except Exception as exc:
            logger.warning(
                "Agent tick parse failed agent=%s tick=%d error=%s raw=%r — using neutral fallback",
                agent.name, tick_num, exc, raw,
            )
            action = TickAction(stance=previous_stance, action="none",
                                emotion="confused", reasoning="Failed to parse response",
                                message="")

        # Resolve fuzzy/malformed influence_target values to real agent IDs
        resolved_target = _resolve_influence_target(
            action.influence_target, self.agents, agent.id,
        )
        if action.influence_target and resolved_target != action.influence_target:
            logger.debug(
                "Resolved influence_target agent=%s raw=%r → %r",
                agent.name, action.influence_target, resolved_target,
            )

        # Apply mechanical bias correction (Step 5)
        corrected_stance = apply_bias(
            bias_id=agent.bias,
            bias_strength=getattr(agent, 'bias_strength', 0.5),
            proposed_stance=action.stance,
            previous_stance=previous_stance,
            initial_stance=agent.initial_stance,
            aggregate_stance=aggregate,
        )
        if abs(corrected_stance - action.stance) > 0.001:
            logger.debug(
                "Bias correction agent=%s bias=%s proposed=%.3f → corrected=%.3f",
                agent.name, agent.bias, action.stance, corrected_stance,
            )

        delta = corrected_stance - previous_stance
        logger.info(
            "Agent tick agent=%-20s tick=%d stance=%.2f→%.2f(%+.2f) action=%r emotion=%r",
            agent.name, tick_num, previous_stance, corrected_stance, delta,
            action.action, action.emotion,
        )
        logger.debug(
            "Agent reasoning agent=%s tick=%d reasoning=%r message=%r target=%s",
            agent.name, tick_num, action.reasoning, action.message, resolved_target,
        )

        return TickEvent(
            agent_id=agent.id,
            stance=corrected_stance,
            previous_stance=previous_stance,
            action=action.action,
            emotion=action.emotion,
            reasoning=action.reasoning,
            message=action.message,
            influence_target=resolved_target,
        )

    def _compute_aggregate(self) -> float:
        """Equal-weight average of all agent stances."""
        stances = [s["stance"] for s in self.current_stances.values()]
        return sum(stances) / len(stances)
