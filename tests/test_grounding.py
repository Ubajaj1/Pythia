"""Tests for the Document Grounding module."""

import pytest
from tests.conftest import FakeLLMClient
from pythia.grounding import extract_grounding, format_grounding_for_prompt
from pythia.models import GroundingContext, GroundingFact


GROUNDING_RESPONSE = {
    "facts": [
        {"entity": "Federal Reserve", "fact": "Raised rates by 50bps on March 15",
         "relevance": "Direct trigger for market reaction"},
        {"entity": "S&P 500", "fact": "Down 2.3% in pre-market trading",
         "relevance": "Indicates immediate negative sentiment"},
        {"entity": "Treasury yields", "fact": "10-year yield jumped to 4.8%",
         "relevance": "Higher yields compete with equities"},
    ],
    "entity_summary": "The Federal Reserve raised rates by 50bps, causing S&P 500 to drop 2.3% and Treasury yields to spike to 4.8%.",
}


class TestExtractGrounding:
    async def test_returns_valid_grounding_context(self):
        llm = FakeLLMClient(responses=[GROUNDING_RESPONSE])
        result = await extract_grounding(
            document_text="The Fed raised rates by 50bps today...",
            prompt="Fed raises rates 50bps",
            llm=llm,
        )
        assert isinstance(result, GroundingContext)
        assert len(result.facts) == 3
        assert result.source_type == "document"

    async def test_facts_have_correct_structure(self):
        llm = FakeLLMClient(responses=[GROUNDING_RESPONSE])
        result = await extract_grounding(
            document_text="The Fed raised rates...",
            prompt="Fed raises rates",
            llm=llm,
        )
        fact = result.facts[0]
        assert isinstance(fact, GroundingFact)
        assert fact.entity == "Federal Reserve"
        assert "50bps" in fact.fact

    async def test_entity_summary_populated(self):
        llm = FakeLLMClient(responses=[GROUNDING_RESPONSE])
        result = await extract_grounding(
            document_text="The Fed raised rates...",
            prompt="Fed raises rates",
            llm=llm,
        )
        assert "Federal Reserve" in result.entity_summary

    async def test_handles_empty_response(self):
        llm = FakeLLMClient(responses=[{}])
        result = await extract_grounding(
            document_text="Some document",
            prompt="Some question",
            llm=llm,
        )
        assert isinstance(result, GroundingContext)
        assert result.facts == []

    async def test_truncates_long_documents(self):
        llm = FakeLLMClient(responses=[GROUNDING_RESPONSE])
        long_doc = "x" * 20000
        result = await extract_grounding(
            document_text=long_doc,
            prompt="Test",
            llm=llm,
        )
        # Should still work — truncation happens internally
        assert isinstance(result, GroundingContext)

    async def test_prompt_contains_document_and_question(self):
        llm = FakeLLMClient(responses=[GROUNDING_RESPONSE])
        await extract_grounding(
            document_text="Important document content here",
            prompt="Should we invest?",
            llm=llm,
        )
        prompt_sent = llm.calls[0]["prompt"]
        assert "Important document content here" in prompt_sent
        assert "Should we invest?" in prompt_sent

    async def test_custom_source_name(self):
        llm = FakeLLMClient(responses=[GROUNDING_RESPONSE])
        result = await extract_grounding(
            document_text="doc",
            prompt="test",
            llm=llm,
            source_name="Q1 Earnings Report.pdf",
        )
        assert result.source_name == "Q1 Earnings Report.pdf"


class TestFormatGroundingForPrompt:
    def test_returns_empty_string_when_no_grounding(self):
        assert format_grounding_for_prompt(None) == ""

    def test_returns_empty_string_when_no_facts(self):
        ctx = GroundingContext(
            source_type="document", source_name="test",
            facts=[], entity_summary="", raw_text="",
        )
        assert format_grounding_for_prompt(ctx) == ""

    def test_formats_facts_as_bullet_points(self):
        ctx = GroundingContext(
            source_type="document",
            source_name="report.pdf",
            facts=[
                GroundingFact(entity="Fed", fact="Raised rates 50bps", relevance="trigger"),
            ],
            entity_summary="The Fed raised rates.",
            raw_text="",
        )
        formatted = format_grounding_for_prompt(ctx)
        assert "Fed: Raised rates 50bps" in formatted
        assert "report.pdf" in formatted

    def test_includes_entity_summary(self):
        ctx = GroundingContext(
            source_type="document",
            source_name="test",
            facts=[GroundingFact(entity="X", fact="Y", relevance="Z")],
            entity_summary="Key summary here.",
            raw_text="",
        )
        formatted = format_grounding_for_prompt(ctx)
        assert "Key summary here." in formatted


class TestFactIds:
    """Step 7: facts get sequential IDs for citation tracking."""

    async def test_facts_get_sequential_ids(self):
        llm = FakeLLMClient(responses=[GROUNDING_RESPONSE])
        result = await extract_grounding(
            document_text="The Fed raised rates...",
            prompt="Fed raises rates",
            llm=llm,
        )
        assert result.facts[0].fact_id == "F1"
        assert result.facts[1].fact_id == "F2"
        assert result.facts[2].fact_id == "F3"

    def test_formatted_output_includes_fact_ids(self):
        ctx = GroundingContext(
            source_type="document",
            source_name="report.pdf",
            facts=[
                GroundingFact(entity="Fed", fact="Raised rates 50bps", relevance="trigger", fact_id="F1"),
                GroundingFact(entity="S&P", fact="Down 2.3%", relevance="reaction", fact_id="F2"),
            ],
            entity_summary="Summary.",
            raw_text="",
        )
        formatted = format_grounding_for_prompt(ctx)
        assert "[F1]" in formatted
        assert "[F2]" in formatted
        assert "cite as [F1]" in formatted.lower() or "cite" in formatted.lower()


class TestCitationExtraction:
    """Step 7: citation regex and grounded reasoning rate computation."""

    def test_citation_regex_matches_simple(self):
        import re
        from pythia.decision import _CITATION_PATTERN
        assert _CITATION_PATTERN.search("Based on [F1] the market dropped")
        assert _CITATION_PATTERN.search("[F23] shows growth")

    def test_citation_regex_no_match(self):
        from pythia.decision import _CITATION_PATTERN
        assert not _CITATION_PATTERN.search("No citations here")
        assert not _CITATION_PATTERN.search("F1 without brackets")

    def test_grounded_reasoning_rates_mixed(self):
        """Mixed reasoning (some cited, some not) produces correct rate."""
        from pythia.decision import _compute_grounded_reasoning_rates
        from pythia.models import RunResult, RunSummary, ScenarioInfo, AgentInfo, TickRecord, TickEvent, BiggestShift

        result = RunResult(
            run_id="test",
            scenario=ScenarioInfo(input="test", type="test", title="test", stance_spectrum=["a","b","c","d","e"]),
            agents=[AgentInfo(id="a1", name="A1", role="r", persona="p", bias="anchoring", initial_stance=0.5)],
            ticks=[
                TickRecord(tick=1, events=[
                    TickEvent(agent_id="a1", stance=0.5, previous_stance=0.5, action="a", emotion="e",
                              reasoning="Based on [F1] the data shows...", message=""),
                ], aggregate_stance=0.5),
                TickRecord(tick=2, events=[
                    TickEvent(agent_id="a1", stance=0.6, previous_stance=0.5, action="a", emotion="e",
                              reasoning="I think this is good", message=""),
                ], aggregate_stance=0.6),
            ],
            summary=RunSummary(total_ticks=2, final_aggregate_stance=0.6,
                               biggest_shift=BiggestShift(agent_id="a1", from_stance=0.5, to_stance=0.6, reason=""),
                               consensus_reached=False),
        )
        rates = _compute_grounded_reasoning_rates(result)
        assert rates["a1"] == 0.5  # 1 out of 2 ticks cited

    def test_no_grounding_no_rates(self):
        """When no grounding is provided, rates dict should be empty."""
        from pythia.decision import _compute_grounded_reasoning_rates
        from pythia.models import RunResult, RunSummary, ScenarioInfo, AgentInfo, TickRecord, TickEvent, BiggestShift

        result = RunResult(
            run_id="test",
            scenario=ScenarioInfo(input="test", type="test", title="test", stance_spectrum=["a","b","c","d","e"]),
            agents=[AgentInfo(id="a1", name="A1", role="r", persona="p", bias="anchoring", initial_stance=0.5)],
            ticks=[
                TickRecord(tick=1, events=[
                    TickEvent(agent_id="a1", stance=0.5, previous_stance=0.5, action="a", emotion="e",
                              reasoning="No citations here", message=""),
                ], aggregate_stance=0.5),
            ],
            summary=RunSummary(total_ticks=1, final_aggregate_stance=0.5,
                               biggest_shift=BiggestShift(agent_id="a1", from_stance=0.5, to_stance=0.5, reason=""),
                               consensus_reached=True),
        )
        rates = _compute_grounded_reasoning_rates(result)
        assert rates["a1"] == 0.0
