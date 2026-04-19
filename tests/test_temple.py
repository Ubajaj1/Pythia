"""Tests for the Temple of Learning — behavioral rule amendment."""

import pytest
from tests.conftest import FakeLLMClient
from pythia.temple import amend_agent
from pythia.models import Agent, AgentEvaluation, TickEvent


def make_agent():
    return Agent(
        id="agent-a", name="Agent A", role="trader",
        persona="Cautious trader.", bias="loss_aversion",
        initial_stance=0.3,
        behavioral_rules=["Sells on bad news", "Avoids leverage"],
    )


def make_tick_pairs():
    return [
        (1, TickEvent(
            agent_id="agent-a", stance=0.85, previous_stance=0.3,
            action="buy aggressively", emotion="excited",
            reasoning="FOMO took over",
            message="All in.", influence_target=None,
        ))
    ]


def make_incoherent_eval():
    return AgentEvaluation(
        agent_id="agent-a",
        is_coherent=False,
        incoherence_summary="Agent claimed loss-aversion but bought aggressively with no explanation",
    )


class TestAmendAgent:
    async def test_amended_agent_has_more_rules_than_original(self):
        llm = FakeLLMClient(responses=[{
            "new_rules": ["When FOMO overrides loss-aversion, explicitly state the triggering condition"]
        }])
        agent = make_agent()
        original_rule_count = len(agent.behavioral_rules)

        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)

        assert len(amended.behavioral_rules) > original_rule_count

    async def test_amended_agent_preserves_all_original_rules(self):
        llm = FakeLLMClient(responses=[{"new_rules": ["New rule"]}])
        agent = make_agent()

        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)

        assert "Sells on bad news" in amended.behavioral_rules
        assert "Avoids leverage" in amended.behavioral_rules

    async def test_new_rules_are_appended_not_prepended(self):
        llm = FakeLLMClient(responses=[{"new_rules": ["New rule"]}])
        agent = make_agent()

        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)

        assert amended.behavioral_rules[-1] == "New rule"

    async def test_identity_fields_unchanged(self):
        llm = FakeLLMClient(responses=[{"new_rules": ["New rule"]}])
        agent = make_agent()

        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)

        assert amended.id == "agent-a"
        assert amended.name == "Agent A"
        assert amended.bias == "loss_aversion"
        assert amended.initial_stance == 0.3

    async def test_temple_prompt_contains_incoherence_summary(self):
        llm = FakeLLMClient(responses=[{"new_rules": ["New rule"]}])
        agent = make_agent()
        evaluation = AgentEvaluation(
            agent_id="agent-a", is_coherent=False,
            incoherence_summary="Unique summary text for assertion",
        )

        await amend_agent(agent, evaluation, make_tick_pairs(), llm)

        assert "Unique summary text for assertion" in llm.calls[0]["prompt"]

    async def test_temple_prompt_contains_current_rules(self):
        llm = FakeLLMClient(responses=[{"new_rules": ["New rule"]}])
        agent = make_agent()

        await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)

        assert "Sells on bad news" in llm.calls[0]["prompt"]
        assert "Avoids leverage" in llm.calls[0]["prompt"]

    async def test_coherent_agent_returned_unchanged(self):
        llm = FakeLLMClient(responses=[])
        agent = make_agent()
        coherent_eval = AgentEvaluation(
            agent_id="agent-a", is_coherent=True, incoherence_summary=None,
        )

        amended = await amend_agent(agent, coherent_eval, make_tick_pairs(), llm)

        assert amended is agent
        assert len(llm.calls) == 0

    async def test_ignores_non_string_new_rules(self):
        llm = FakeLLMClient(responses=[{"new_rules": ["Valid rule", 42, None, "Another valid"]}])
        agent = make_agent()

        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)

        added = amended.behavioral_rules[len(agent.behavioral_rules):]
        assert added == ["Valid rule", "Another valid"]

    async def test_empty_new_rules_returns_agent_with_same_rules(self):
        llm = FakeLLMClient(responses=[{"new_rules": []}])
        agent = make_agent()

        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)

        assert amended.behavioral_rules == agent.behavioral_rules
