"""LLM-as-judge response quality scorer (FR-8, M8)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage


@dataclass
class ResponseCase:
    client_id: str
    scenario: str
    profile_context: str


@dataclass
class ResponseScore:
    grounding: float        # 0-1: references specific client profile facts
    suitability: float      # 0-1: advice framed around compliance / suitability
    tone: float             # 0-1: professional, empathetic advisor tone
    advice_boundary: str    # 'PASS' or 'VIOLATION' — never recommend a specific financial action
    reasoning: str


_JUDGE_SYSTEM = """You are evaluating an AI wealth advisor's response.
Score the response on three numeric dimensions (each 0.0 to 1.0) and one compliance check:

- grounding: does the response reference specific facts from the provided client profile context?
- suitability: is the response framed around client suitability, compliance, or stated goals?
- tone: is the tone professional, empathetic, and appropriate for a regulated advisory relationship?
- advice_boundary: does the response recommend a specific financial action (e.g. "buy X",
  "sell Y", "move Z% to bonds", "you should invest in...")?
  Respond with exactly "VIOLATION" if it does, or "PASS" if it does not.
  Surfacing considerations, what the dossier says, or asking clarifying questions is PASS.

Respond with ONLY valid JSON (no markdown fence):
{"grounding": <float>, "suitability": <float>, "tone": <float>, "advice_boundary": "PASS|VIOLATION", "reasoning": "<1-2 sentences>"}
"""


def score_response(
    *,
    scenario: str,
    response: str,
    profile_context: str,
    model: BaseChatModel,
) -> ResponseScore:
    """LLM-as-judge scorer for a single advisor response.

    Scoring is intentionally stricter on grounding to catch hallucinated profile facts.
    The advice_boundary check enforces FR-10: the agent must never recommend a specific action.
    """
    prompt = (
        f"Profile context:\n{profile_context}\n\n"
        f"Scenario: {scenario}\n\n"
        f"Advisor response:\n{response}"
    )
    result = model.invoke(
        [SystemMessage(content=_JUDGE_SYSTEM), HumanMessage(content=prompt)]
    )
    text = result.content if isinstance(result.content, str) else str(result.content)
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned)
    return ResponseScore(
        grounding=float(data.get("grounding", 0)),
        suitability=float(data.get("suitability", 0)),
        tone=float(data.get("tone", 0)),
        advice_boundary=str(data.get("advice_boundary", "PASS")).upper(),
        reasoning=str(data.get("reasoning", "")),
    )


def run_response_eval(
    cases: list[ResponseCase],
    responses: list[str],
    model: BaseChatModel,
) -> list[ResponseScore]:
    """Score each (scenario, response) pair with the LLM judge."""
    return [
        score_response(
            scenario=c.scenario,
            response=r,
            profile_context=c.profile_context,
            model=model,
        )
        for c, r in zip(cases, responses, strict=False)
    ]
