"""Jev core: question/answer types, per-piece modes, SDK adapter, shadow records."""

from __future__ import annotations

import logging
import os
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Literal, Protocol, Union

logger = logging.getLogger(__name__)

Mode = Literal["off", "shadow", "primary"]
_MODES = {"off", "shadow", "primary"}
JEV_MODEL = "jev-latest"


@dataclass(frozen=True)
class NoulQ:
    instructions: str
    true: str | None = None
    false: str | None = None


@dataclass(frozen=True)
class ChoiceQ:
    instructions: str
    options: dict[str, str]


@dataclass(frozen=True)
class ScoreQ:
    instructions: str
    levels: list[str]


Question = Union[NoulQ, ChoiceQ, ScoreQ]


@dataclass(frozen=True)
class Answer:
    value: float | str
    confidence: float
    probabilities: dict[str, float] = field(default_factory=dict)


class JevAsker(Protocol):
    async def ask(self, state: dict | str, questions: dict[str, Question]) -> dict[str, Answer]: ...


def jev_mode(piece: str) -> Mode:
    if not os.getenv("TYPESAFE_API_KEY"):
        return "off"
    raw = os.getenv(f"PYTHIA_JEV_{piece.upper()}", "off").strip().lower()
    if raw not in _MODES:
        logger.warning("Ignoring invalid PYTHIA_JEV_%s=%r (expected off|shadow|primary)", piece.upper(), raw)
        return "off"
    return raw  # type: ignore[return-value]


def threshold() -> float:
    return float(os.getenv("PYTHIA_JEV_THRESHOLD", "0.5"))


# ── shadow records ───────────────────────────────────────────────────────────
_shadow: ContextVar[list[dict] | None] = ContextVar("pythia_jev_shadow", default=None)


def start_shadow() -> tuple[list[dict], Token]:
    records: list[dict] = []
    return records, _shadow.set(records)


def stop_shadow(token: Token) -> None:
    try:
        _shadow.reset(token)
    except ValueError:
        # An async generator can be finalized in a different context than it started in.
        _shadow.set(None)


def record_shadow(piece: str, key: str, llm, jev, confidence: float, agree: bool, used: str) -> None:
    records = _shadow.get()
    if records is None:
        return
    records.append({"piece": piece, "key": key, "llm": llm, "jev": jev,
                    "confidence": round(float(confidence), 4), "agree": bool(agree), "used": used})


# ── SDK adapter ──────────────────────────────────────────────────────────────
def _convert(response, questions: dict[str, Question]) -> dict[str, Answer]:
    """Map SystemOneResponse.answers to our Answers.

    Noul answers carry only a probability, so confidence is its distance from a coin flip.
    """
    out: dict[str, Answer] = {}
    for key, q in questions.items():
        a = response.answers[key]
        if isinstance(q, NoulQ):
            p = float(a.noul)
            out[key] = Answer(p, abs(2 * p - 1), {"true": p, "false": 1 - p})
        elif isinstance(q, ChoiceQ):
            out[key] = Answer(a.choice, float(a.confidence), {str(k): float(v) for k, v in dict(a.probabilities).items()})
        else:
            out[key] = Answer(float(a.score), float(a.confidence), {str(k): float(v) for k, v in dict(a.probabilities).items()})
    return out


class SdkJev:
    """JevAsker backed by typesafe-sdk. The only place that imports it."""

    async def ask(self, state: dict | str, questions: dict[str, Question]) -> dict[str, Answer]:
        from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, NoulCriteria, Score

        sdk_qs = {}
        for key, q in questions.items():
            if isinstance(q, NoulQ):
                criteria = NoulCriteria(**{k: v for k, v in (("true", q.true), ("false", q.false)) if v})
                sdk_qs[key] = Noul(instructions=q.instructions, criteria=criteria or None)
            elif isinstance(q, ChoiceQ):
                sdk_qs[key] = Choice(instructions=q.instructions, criteria=q.options)
            else:
                sdk_qs[key] = Score(instructions=q.instructions, criteria=q.levels)

        async with AsyncTypeSafeClient() as client:
            response = await client.system_one(state=state, questions=sdk_qs, model=JEV_MODEL)

        usage = getattr(response, "usage", None)
        if usage is not None:
            from pythia.usage import record_usage
            record_usage(JEV_MODEL, int(usage.input_tokens or 0), int(usage.output_tokens or 0))
        return _convert(response, questions)


_client: JevAsker | None = None


def get_jev() -> JevAsker | None:
    global _client
    if not os.getenv("TYPESAFE_API_KEY"):
        return None
    if _client is None:
        _client = SdkJev()
    return _client
