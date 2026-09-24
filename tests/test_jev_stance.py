from pythia.jev.core import Answer, start_shadow, stop_shadow
from pythia.jev.stance import record_expressed_stances
from pythia.models import AgentArchetype, ScenarioBlueprint, TickEvent, TickRecord


def _bp():
    return ScenarioBlueprint(scenario_type="t", title="T", description="d", stance_spectrum=["vb", "b", "n", "bu", "vbu"],
                             agent_archetypes=[AgentArchetype(role="r", count=1, description="d", bias="anchoring", stance_range=(0.1, 0.9))],
                             dynamics="x", tick_count=1)


def _tick():
    def ev(a, s, m):
        return TickEvent(agent_id=a, stance=s, previous_stance=s, action="x", emotion="y", reasoning="z", message=m)
    return TickRecord(tick=3, aggregate_stance=0.5, events=[ev("a", 0.2, "Sell now."), ev("b", 0.8, "")])


class FakeJev:
    def __init__(self):
        self.questions = None

    async def ask(self, state, questions):
        self.questions = questions
        return {k: Answer(4.0, 0.9, {}) for k in questions}


async def test_scores_only_agents_with_messages():
    jev = FakeJev()
    records, token = start_shadow()
    try:
        await record_expressed_stances(_tick(), _bp(), jev=jev, mode="shadow")
    finally:
        stop_shadow(token)
    assert list(jev.questions) == ["a"]
    r = records[0]
    assert r["key"] == "3:a" and r["llm"] == 0.2 and abs(r["jev"] - 0.9) < 1e-9 and r["agree"] is False and r["used"] == "llm"


async def test_off_does_nothing():
    jev = FakeJev()
    await record_expressed_stances(_tick(), _bp(), jev=jev, mode="off")
    assert jev.questions is None


async def test_jev_error_is_swallowed():
    class Boom:
        async def ask(self, state, questions):
            raise RuntimeError("down")
    await record_expressed_stances(_tick(), _bp(), jev=Boom(), mode="shadow")
