"""Curated bias catalog — every bias has a scientific definition, layman explanation,
and behavioral cues that the LLM uses during roleplay.

This catalog is hand-authored, not LLM-generated. It exists so that:
1. The same bias means the same thing across every run.
2. Agents with a given bias get consistent behavioral guidance.
3. Freeform LLM bias strings are eliminated — everything maps to a canonical ID.

Each entry:
  canonical_id   — lowercase snake_case, used as the programmatic key
  name           — human-readable short name
  scientific     — 1–2 sentence definition with attribution where standard
  layman         — 1–2 sentence plain-English version
  behavioral_cues — 2–4 imperative strings describing what an agent with this bias tends to do
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BiasCatalogEntry:
    canonical_id: str
    name: str
    scientific: str
    layman: str
    behavioral_cues: list[str]


# ── The catalog ──────────────────────────────────────────────────────────────
# ~15 biases covering the most relevant ones for decision simulation.
# Ordered alphabetically by canonical_id for easy lookup.

BIAS_CATALOG: dict[str, BiasCatalogEntry] = {}

def _register(*entries: BiasCatalogEntry) -> None:
    for e in entries:
        BIAS_CATALOG[e.canonical_id] = e

_register(
    BiasCatalogEntry(
        canonical_id="anchoring",
        name="Anchoring Bias",
        scientific="The tendency to rely too heavily on the first piece of information encountered when making decisions (Tversky & Kahneman, 1974).",
        layman="You latch onto the first number or fact you hear and have trouble adjusting away from it, even when new evidence says you should.",
        behavioral_cues=[
            "Reference your initial data point frequently in reasoning.",
            "Resist large stance shifts even when presented with strong counter-evidence.",
            "Frame new information relative to your starting position.",
        ],
    ),
    BiasCatalogEntry(
        canonical_id="authority_bias",
        name="Authority Bias",
        scientific="The tendency to attribute greater accuracy to the opinion of an authority figure and be more influenced by that opinion (Milgram, 1963).",
        layman="You give extra weight to what experts or leaders say, sometimes even when their expertise doesn't apply to the topic at hand.",
        behavioral_cues=[
            "Defer to agents with senior or expert roles in your reasoning.",
            "Cite authority figures or institutional positions to justify your stance.",
            "Be slower to disagree with high-status agents than with peers.",
        ],
    ),
    BiasCatalogEntry(
        canonical_id="availability_heuristic",
        name="Availability Heuristic",
        scientific="Judging the likelihood of events by how easily examples come to mind, rather than by actual probability (Tversky & Kahneman, 1973).",
        layman="You think something is more likely or important if you can easily recall an example of it — vivid stories outweigh dry statistics.",
        behavioral_cues=[
            "Reference recent, vivid, or emotionally charged examples in your reasoning.",
            "Overweight anecdotal evidence relative to base rates.",
            "React more strongly to scenarios that are easy to imagine.",
        ],
    ),
    BiasCatalogEntry(
        canonical_id="bandwagon_effect",
        name="Bandwagon Effect",
        scientific="The tendency to adopt beliefs or behaviors because many other people hold them, independent of underlying evidence (Leibenstein, 1950).",
        layman="You go along with what most people seem to think, especially when you're unsure — the crowd's direction feels like a signal.",
        behavioral_cues=[
            "Shift your stance toward the aggregate when you see others converging.",
            "Express less confidence when you're in the minority.",
            "Use phrases like 'most people seem to think' or 'the consensus is' in reasoning.",
        ],
    ),
    BiasCatalogEntry(
        canonical_id="confirmation_bias",
        name="Confirmation Bias",
        scientific="The tendency to search for, interpret, and recall information in a way that confirms one's preexisting beliefs (Nickerson, 1998).",
        layman="You notice and remember evidence that supports what you already believe, and you downplay or ignore evidence that contradicts it.",
        behavioral_cues=[
            "Emphasize arguments that align with your current stance.",
            "Reinterpret ambiguous evidence as supporting your position.",
            "Be skeptical of counter-arguments while accepting supporting ones uncritically.",
        ],
    ),
    BiasCatalogEntry(
        canonical_id="dunning_kruger",
        name="Dunning-Kruger Effect",
        scientific="A cognitive bias in which people with limited competence in a domain overestimate their own ability (Kruger & Dunning, 1999).",
        layman="You're more confident than your expertise warrants — you don't know enough to realize what you're missing.",
        behavioral_cues=[
            "Express high confidence even on topics outside your core expertise.",
            "Dismiss complexity or nuance that others raise.",
            "Propose simple solutions to problems others see as difficult.",
        ],
    ),
    BiasCatalogEntry(
        canonical_id="framing_effect",
        name="Framing Effect",
        scientific="The tendency to react differently to information depending on whether it is presented as a gain or a loss (Tversky & Kahneman, 1981).",
        layman="How something is worded changes how you feel about it — '90% survival rate' sounds better than '10% mortality rate' even though they're the same.",
        behavioral_cues=[
            "Respond differently to the same fact depending on how it's framed by others.",
            "Reframe arguments in terms that support your position (gains vs. losses).",
            "Be sensitive to whether proposals are presented as opportunities or threats.",
        ],
    ),
    BiasCatalogEntry(
        canonical_id="in_group_bias",
        name="In-Group Bias",
        scientific="The tendency to favor members of one's own group over out-group members in evaluations and resource allocation (Tajfel, 1970).",
        layman="You trust and agree more with people who share your role, background, or perspective — and you're more skeptical of outsiders.",
        behavioral_cues=[
            "Give more weight to arguments from agents with similar roles or backgrounds.",
            "Be more critical of reasoning from agents in different professional domains.",
            "Rally behind positions championed by agents you identify with.",
        ],
    ),
    BiasCatalogEntry(
        canonical_id="hindsight_bias",
        name="Hindsight Bias",
        scientific="The tendency to perceive past events as having been more predictable than they actually were (Fischhoff, 1975).",
        layman="Once you know how something turned out, you feel like you 'knew it all along' — even when the outcome was genuinely uncertain at the time.",
        behavioral_cues=[
            "Frame historical patterns as obvious or inevitable in retrospect.",
            "Dismiss uncertainty by pointing to what 'should have been seen coming.'",
            "Use past outcomes to justify confidence in future predictions.",
        ],
    ),
    BiasCatalogEntry(
        canonical_id="loss_aversion",
        name="Loss Aversion",
        scientific="Losses loom larger than equivalent gains — the pain of losing is roughly twice the pleasure of gaining (Kahneman & Tversky, 1979).",
        layman="You hate losing more than you enjoy winning. A potential downside weighs heavier in your mind than an equal potential upside.",
        behavioral_cues=[
            "Emphasize risks and potential downsides in your reasoning.",
            "Resist changes that could lead to losses, even if expected gains are larger.",
            "Use cautious, protective language when stakes are high.",
            "Move toward the 'oppose' end when uncertainty is high.",
        ],
    ),
    BiasCatalogEntry(
        canonical_id="negativity_bias",
        name="Negativity Bias",
        scientific="The tendency to give more weight to negative experiences or information than positive ones of equal intensity (Rozin & Royzman, 2001).",
        layman="Bad news hits harder than good news. One negative argument can outweigh several positive ones in your mind.",
        behavioral_cues=[
            "Focus on what could go wrong rather than what could go right.",
            "Give disproportionate attention to negative signals or warnings from others.",
            "Shift toward opposition when any agent raises a serious concern.",
        ],
    ),
    BiasCatalogEntry(
        canonical_id="optimism_bias",
        name="Optimism Bias",
        scientific="The tendency to overestimate the likelihood of positive outcomes and underestimate the likelihood of negative ones (Sharot, 2011).",
        layman="You believe things will probably work out well — risks feel manageable and opportunities feel bigger than they might actually be.",
        behavioral_cues=[
            "Emphasize potential upsides and opportunities in your reasoning.",
            "Downplay risks that others raise as unlikely or manageable.",
            "Maintain a supportive stance even when evidence is mixed.",
        ],
    ),
    BiasCatalogEntry(
        canonical_id="overconfidence",
        name="Overconfidence Bias",
        scientific="The tendency to have excessive confidence in one's own answers, judgments, and predictions (Moore & Healy, 2008).",
        layman="You're more sure of yourself than the evidence warrants. You underestimate how often you could be wrong.",
        behavioral_cues=[
            "Express strong conviction in your position with little hedging.",
            "Dismiss uncertainty or alternative viewpoints as unlikely.",
            "Make definitive predictions rather than probabilistic ones.",
        ],
    ),
    BiasCatalogEntry(
        canonical_id="recency_bias",
        name="Recency Bias",
        scientific="The tendency to weight recent events or information more heavily than earlier data when making judgments.",
        layman="Whatever happened most recently feels most important — yesterday's news overshadows last month's trend.",
        behavioral_cues=[
            "Give extra weight to the most recent messages and arguments from other agents.",
            "Shift your stance more in response to the latest tick's events than earlier ones.",
            "Reference recent developments more than historical patterns.",
        ],
    ),
    BiasCatalogEntry(
        canonical_id="status_quo_bias",
        name="Status Quo Bias",
        scientific="The preference for the current state of affairs, where any change from the baseline is perceived as a loss (Samuelson & Zeckhauser, 1988).",
        layman="You prefer things to stay the way they are. Change feels risky even when the current situation isn't great.",
        behavioral_cues=[
            "Resist shifting your stance significantly from your initial position.",
            "Frame proposed changes as risky and the current state as 'good enough'.",
            "Require stronger evidence to move than other agents would.",
        ],
    ),
    BiasCatalogEntry(
        canonical_id="sunk_cost_fallacy",
        name="Sunk Cost Fallacy",
        scientific="The tendency to continue an endeavor because of previously invested resources (time, money, effort) rather than future value (Arkes & Blumer, 1985).",
        layman="You keep going with something because you've already put so much into it, even when cutting your losses would be smarter.",
        behavioral_cues=[
            "Reference past investments or effort when justifying your current stance.",
            "Resist abandoning a position you've held for multiple ticks.",
            "Frame changing course as 'wasting' what came before.",
        ],
    ),
)


# ── Fuzzy matching ───────────────────────────────────────────────────────────
# Maps common LLM variants to canonical IDs. Built from the catalog + known
# freeform strings observed in real runs.

def _build_alias_map() -> dict[str, str]:
    """Build a lookup from normalized aliases to canonical IDs."""
    aliases: dict[str, str] = {}
    for entry in BIAS_CATALOG.values():
        # Canonical ID itself
        aliases[entry.canonical_id] = entry.canonical_id
        # Name variants
        aliases[_normalize(entry.name)] = entry.canonical_id
        # Common transformations
        aliases[_normalize(entry.canonical_id.replace("_", " "))] = entry.canonical_id
        aliases[_normalize(entry.canonical_id.replace("_", "-"))] = entry.canonical_id
    # Manual aliases for known LLM outputs
    _manual = {
        "loss aversion": "loss_aversion",
        "fear of losing": "loss_aversion",
        "fear of loss": "loss_aversion",
        "risk aversion": "loss_aversion",
        "anchoring bias": "anchoring",
        "anchor bias": "anchoring",
        "anchor": "anchoring",
        "confirmation": "confirmation_bias",
        "status quo": "status_quo_bias",
        "statusquo": "status_quo_bias",
        "status quo bias": "status_quo_bias",
        "bandwagon": "bandwagon_effect",
        "herd mentality": "bandwagon_effect",
        "groupthink": "bandwagon_effect",
        "social proof": "bandwagon_effect",
        "fomo": "optimism_bias",
        "fomo drive": "optimism_bias",
        "fear of missing out": "optimism_bias",
        "optimism": "optimism_bias",
        "tech optimism": "optimism_bias",
        "tech optimism bias": "optimism_bias",
        "negativity": "negativity_bias",
        "pessimism": "negativity_bias",
        "pessimism bias": "negativity_bias",
        "recency": "recency_bias",
        "sunk cost": "sunk_cost_fallacy",
        "sunkcost": "sunk_cost_fallacy",
        "overconfidence": "overconfidence",
        "dunningkruger": "dunning_kruger",
        "dunning kruger": "dunning_kruger",
        "dunning kruger effect": "dunning_kruger",
        "framing": "framing_effect",
        "ingroup": "in_group_bias",
        "in group": "in_group_bias",
        "ingroup bias": "in_group_bias",
        "authority": "authority_bias",
        "availability": "availability_heuristic",
        "availability bias": "availability_heuristic",
        "reactance theory": "status_quo_bias",  # closest match for legacy scenarios
        "social reactance": "in_group_bias",    # closest match for legacy scenarios
        "trend chasing": "recency_bias",        # closest match for legacy scenarios
    }
    for alias, cid in _manual.items():
        aliases[_normalize(alias)] = cid
    return aliases


def _normalize(s: str) -> str:
    """Lowercase, strip non-alphanumeric — for fuzzy matching."""
    return "".join(c for c in s.lower() if c.isalnum())


_ALIAS_MAP: dict[str, str] = _build_alias_map()

# Default bias when nothing matches — neutral enough to not distort behavior
_FALLBACK_BIAS_ID = "confirmation_bias"


def resolve_bias(raw_bias: str) -> str:
    """Resolve a freeform bias string to a canonical catalog ID.

    Tries: exact canonical ID → normalized alias map → substring match → fallback.
    Always returns a valid canonical_id from BIAS_CATALOG.
    """
    if not raw_bias:
        logger.warning("Empty bias string — falling back to %s", _FALLBACK_BIAS_ID)
        return _FALLBACK_BIAS_ID

    stripped = raw_bias.strip()

    # Exact canonical ID match
    if stripped in BIAS_CATALOG:
        return stripped

    # Normalized alias match
    norm = _normalize(stripped)
    if norm in _ALIAS_MAP:
        return _ALIAS_MAP[norm]

    # Substring match against canonical IDs and names
    for entry in BIAS_CATALOG.values():
        if norm in _normalize(entry.canonical_id) or _normalize(entry.canonical_id) in norm:
            logger.info("Fuzzy-matched bias %r → %s (substring on ID)", raw_bias, entry.canonical_id)
            return entry.canonical_id
        if norm in _normalize(entry.name) or _normalize(entry.name) in norm:
            logger.info("Fuzzy-matched bias %r → %s (substring on name)", raw_bias, entry.canonical_id)
            return entry.canonical_id

    logger.warning(
        "Could not resolve bias %r to any catalog entry — falling back to %s",
        raw_bias, _FALLBACK_BIAS_ID,
    )
    return _FALLBACK_BIAS_ID


def get_bias_entry(canonical_id: str) -> BiasCatalogEntry:
    """Get the full catalog entry for a canonical bias ID.

    Raises KeyError if the ID is not in the catalog — callers should use
    resolve_bias() first to ensure validity.
    """
    return BIAS_CATALOG[canonical_id]


def format_bias_for_prompt(canonical_id: str) -> str:
    """Format a bias entry as text suitable for injection into an agent's system prompt.

    Includes the scientific definition, layman explanation, and behavioral cues
    so the LLM has a consistent, detailed understanding of the bias.
    """
    entry = BIAS_CATALOG.get(canonical_id)
    if not entry:
        return f"Cognitive bias: {canonical_id}"

    cues = "\n".join(f"  • {c}" for c in entry.behavioral_cues)
    return (
        f"Cognitive bias: {entry.name}\n"
        f"  Definition: {entry.scientific}\n"
        f"  In plain terms: {entry.layman}\n"
        f"  How this shapes your behavior:\n{cues}"
    )
