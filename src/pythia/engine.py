"""Simulation Engine — tick-by-tick opinion dynamics loop."""

from __future__ import annotations

import asyncio
import json
import logging

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
    """Stores an agent's full tick history for prompt inclusion."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.full_history: list[dict] = []

    def record(self, tick_event: dict) -> None:
        self.full_history.append(tick_event)

    def for_prompt(self) -> list[dict]:
        return self.full_history


AGENT_SYSTEM_TEMPLATE = """\
You are {name}, {persona}.

Your behavioral rules:
{rules}

Your cognitive bias: {bias}"""

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

Respond with ONLY this JSON (no other text):
{{"stance": <float 0.0-1.0>, "action": "<what you do>", "emotion": "<how you feel>", "reasoning": "<why in one sentence>", "message": "<what you say to others>", "influence_target": "<agent-id or null>"}}"""


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
    lines = []
    for e in entries:
        lines.append(
            f"Tick {e['tick']}: stance={e['stance']}, action={e['action']}, "
            f"emotion={e['emotion']}, reasoning=\"{e['reasoning']}\""
        )
    return "\n".join(lines)


def _format_other_agents(
    agent_id: str, current_stances: dict[str, dict], agents: list[Agent]
) -> str:
    lines = []
    for a in agents:
        if a.id == agent_id:
            continue
        state = current_stances.get(a.id, {})
        stance = state.get("stance", a.initial_stance)
        action = state.get("action", "none yet")
        lines.append(f"  - {a.name} ({a.role}): stance={stance:.2f}, last action={action}")
    return "\n".join(lines) if lines else "  (none)"


def _get_messages_for_agent(agent_id: str, recent_messages: list[dict]) -> str:
    msgs = [m for m in recent_messages if m.get("to") == agent_id]
    if not msgs:
        return "(no messages)"
    return "\n".join(
        f"  - {m['from_name']} (tick {m['tick']}): \"{m['message']}\""
        for m in msgs
    )


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
        self.memories: dict[str, AgentMemory] = {
            a.id: AgentMemory(a.id) for a in agents
        }
        self.current_stances: dict[str, dict] = {
            a.id: {"stance": a.initial_stance, "action": "none", "emotion": "neutral"}
            for a in agents
        }
        self.recent_messages: list[dict] = []
        self._agent_map: dict[str, Agent] = {a.id: a for a in agents}
        self._llm_semaphore = asyncio.Semaphore(3)
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
            bias=agent.bias,
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
            messages=_get_messages_for_agent(agent.id, self.recent_messages),
            history=_format_history(self.memories[agent.id]),
        )

        logger.debug(
            "Agent tick prompt agent=%s tick=%d\n--- SYSTEM ---\n%s\n--- PROMPT ---\n%s",
            agent.name, tick_num, system, prompt,
        )

        async with self._llm_semaphore:
            raw = await self.llm.generate(prompt=prompt, system=system)
        action = TickAction.model_validate(raw)

        delta = action.stance - previous_stance
        logger.info(
            "Agent tick agent=%-20s tick=%d stance=%.2f→%.2f(%+.2f) action=%r emotion=%r",
            agent.name, tick_num, previous_stance, action.stance, delta,
            action.action, action.emotion,
        )
        logger.debug(
            "Agent reasoning agent=%s tick=%d reasoning=%r message=%r target=%s",
            agent.name, tick_num, action.reasoning, action.message, action.influence_target,
        )

        return TickEvent(
            agent_id=agent.id,
            stance=action.stance,
            previous_stance=previous_stance,
            action=action.action,
            emotion=action.emotion,
            reasoning=action.reasoning,
            message=action.message,
            influence_target=action.influence_target,
        )

    def _compute_aggregate(self) -> float:
        """Equal-weight average of all agent stances."""
        stances = [s["stance"] for s in self.current_stances.values()]
        return sum(stances) / len(stances)
