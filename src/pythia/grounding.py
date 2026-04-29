"""Document grounding — extracts facts and entities from user-provided text to anchor simulations."""

from __future__ import annotations

import logging

from pythia.llm import LLMClient
from pythia.models import GroundingContext, GroundingFact

logger = logging.getLogger(__name__)

GROUNDING_SYSTEM = """\
You are Pythia's Document Grounding Engine. Given a document or text, extract the key facts,
entities, and relationships that are relevant to a simulation about the user's decision.

Your output MUST be a JSON object with:
- facts: array of objects, each with:
    - entity: string — the person, organization, metric, or concept
    - fact: string — one concrete, specific fact about this entity
    - relevance: string — why this matters for simulating the decision
- entity_summary: string — one paragraph summarizing the key entities and their relationships

Extract 5-15 facts. Focus on:
- Named entities (people, companies, institutions)
- Quantitative data (numbers, percentages, dates)
- Relationships between entities (who influences whom, dependencies)
- Stated positions or opinions
- Risks, constraints, or conditions

Do NOT invent facts. Only extract what is explicitly stated in the document."""


async def extract_grounding(
    document_text: str,
    prompt: str,
    llm: LLMClient,
    source_name: str = "uploaded document",
) -> GroundingContext:
    """Extract grounding facts from document text. Returns GroundingContext."""
    # Truncate very long documents to avoid blowing context windows
    max_chars = 12000
    truncated = document_text[:max_chars]
    if len(document_text) > max_chars:
        truncated += f"\n\n[... truncated, {len(document_text) - max_chars} chars omitted ...]"
        logger.warning(
            "Document truncated from %d to %d chars for grounding extraction",
            len(document_text), max_chars,
        )

    user_prompt = (
        f"User's decision/question: {prompt}\n\n"
        f"Document to extract facts from:\n---\n{truncated}\n---"
    )

    logger.info(
        "Grounding extraction started source=%r prompt=%r doc_chars=%d",
        source_name, prompt[:60], len(document_text),
    )

    raw = await llm.generate(prompt=user_prompt, system=GROUNDING_SYSTEM)

    facts_data = raw.get("facts", [])
    facts = []
    for i, f in enumerate(facts_data, start=1):
        if isinstance(f, dict) and "entity" in f and "fact" in f:
            facts.append(GroundingFact(
                entity=str(f["entity"]),
                fact=str(f["fact"]),
                relevance=str(f.get("relevance", "")),
                fact_id=f"F{i}",
            ))

    entity_summary = str(raw.get("entity_summary", ""))

    logger.info(
        "Grounding extraction complete facts=%d entities_summary_chars=%d",
        len(facts), len(entity_summary),
    )

    return GroundingContext(
        source_type="document",
        source_name=source_name,
        facts=facts,
        entity_summary=entity_summary,
        raw_text=truncated,
    )


def format_grounding_for_prompt(grounding: GroundingContext | None) -> str:
    """Format grounding context as a string to inject into LLM prompts.

    Returns empty string if no grounding is available — simulation works without it.
    Facts are labeled with IDs (e.g. [F1], [F2]) so agents can cite them.
    """
    if grounding is None or not grounding.facts:
        return ""

    lines = [
        f"\n--- Grounding Data (from: {grounding.source_name}) ---",
        grounding.entity_summary,
        "",
        "Key facts (cite as [F1], [F2], etc. when referencing in your reasoning):",
    ]
    for f in grounding.facts:
        fid = f.fact_id or "F?"
        lines.append(f"  [{fid}] {f.entity}: {f.fact}")
    lines.append("--- End Grounding Data ---\n")
    return "\n".join(lines)
