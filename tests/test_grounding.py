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
