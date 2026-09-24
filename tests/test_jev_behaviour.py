"""Tests for Jev behaviour settings (fake Jev)."""

from pythia.jev.behaviour import apply_behaviour_judgement
from pythia.jev.core import Answer, start_shadow, stop_shadow
from pythia.models import Agent, AgentArchetype, Relationship, ScenarioBlueprint


def _bp():
    return ScenarioBlueprint(
        scenario_type="t", title="T", description="d", stance_spectrum=["vb", "b", "n", "bu", "vbu"],
        agent_archetypes=[AgentArchetype(role="trader", count=2, description="d", bias="anchoring", stance_range=(0.2, 0.6))],
        dynamics="x", tick_count=3,
    )


def _agents():
    return [
        Agent(id="a", name="A", role="trader", persona="p", bias="anchoring", bias_strength=0.5,
              initial_stance=0.3, behavioral_rules=["r"], archetype="trader",
              relationships=[Relationship(target="b", type="follows", weight=0.5)]),
        Agent(id="b", name="B", role="trader", persona="p", bias="anchoring", bias_strength=0.5,
              initial_stance=0.5, behavioral_rules=["r"], archetype="trader"),
    ]


class FakeJev:
    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    async def ask(self, state, questions):
        self.calls.append(questions)
        return {k: self.answers[k] for k in questions}


def _answers(conf=0.9):
    return {
        "a:bias": Answer("loss_aversion", conf, {"loss_aversion": conf}),
        "a:strength": Answer(3.0, conf, {}),
        "a:stance": Answer(0.0, conf, {}),
        "b:bias": Answer("anchoring", conf, {"anchoring": conf}),
        "b:strength": Answer(1.0, conf, {}),
        "b:stance": Answer(2.0, conf, {}),
        "rel:a->b": Answer("distrusts", conf, {"distrusts": conf}),
        "rel:b->a": Answer("none", conf, {"none": conf}),
    }


async def test_off_returns_agents_untouched():
    agents = _agents()
    out = await apply_behaviour_judgement(agents, _bp(), jev=FakeJev(_answers()), mode="off")
    assert out == agents


async def test_shadow_records_but_keeps_llm_values():
    records, token = start_shadow()
    try:
        out = await apply_behaviour_judgement(_agents(), _bp(), jev=FakeJev(_answers()), mode="shadow")
    finally:
        stop_shadow(token)
    assert out[0].bias == "anchoring" and out[0].initial_stance == 0.3
    bias_a = next(r for r in records if r["key"] == "a:bias")
    assert bias_a["llm"] == "anchoring" and bias_a["jev"] == "loss_aversion" and bias_a["agree"] is False
    assert all(r["used"] == "llm" for r in records)


async def test_primary_applies_confident_answers_and_clamps_stance():
    out = await apply_behaviour_judgement(_agents(), _bp(), jev=FakeJev(_answers()), mode="primary")
    a = out[0]
    assert a.bias == "loss_aversion"
    assert a.bias_strength == 0.85
    assert a.initial_stance == 0.2  # 0.1 clamped to archetype range (0.2, 0.6)
    assert [(r.target, r.type) for r in a.relationships] == [("b", "distrusts")]
    assert out[1].relationships == []


async def test_primary_keeps_llm_when_unsure():
    out = await apply_behaviour_judgement(_agents(), _bp(), jev=FakeJev(_answers(conf=0.2)), mode="primary")
    assert out[0].bias == "anchoring" and out[0].initial_stance == 0.3


async def test_jev_error_falls_back():
    class Boom:
        async def ask(self, state, questions):
            raise RuntimeError("down")
    agents = _agents()
    assert await apply_behaviour_judgement(agents, _bp(), jev=Boom(), mode="primary") == agents


async def test_primary_keeps_llm_relationships_when_unsure():
    answers = _answers()
    answers["rel:a->b"] = Answer("distrusts", 0.2, {"distrusts": 0.2})
    out = await apply_behaviour_judgement(_agents(), _bp(), jev=FakeJev(answers), mode="primary")
    assert [(r.target, r.type) for r in out[0].relationships] == [("b", "follows")]


async def test_relationships_are_recorded_per_pair():
    records, token = start_shadow()
    try:
        await apply_behaviour_judgement(_agents(), _bp(), jev=FakeJev(_answers()), mode="shadow")
    finally:
        stop_shadow(token)
    pairs = {r["key"]: r for r in records if r["key"].endswith(":relationship")}
    assert set(pairs) == {"a->b:relationship", "b->a:relationship"}
    assert pairs["a->b:relationship"]["llm"] == "follows" and pairs["a->b:relationship"]["jev"] == "distrusts"
    assert pairs["a->b:relationship"]["agree"] is False
    assert pairs["b->a:relationship"]["llm"] == "none" and pairs["b->a:relationship"]["agree"] is True
