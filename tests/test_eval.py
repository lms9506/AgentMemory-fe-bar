"""Tests for dossier-model eval harness.

Contract source: interfaces.md §3 (ArtifactStore), research/brief.md §D9.
Dead symbols removed: InMemoryMemoryStore, retrieve_similar, retrieved_turns.
New: advice_boundary judge on ResponseScore.
"""

from __future__ import annotations

import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from agent_memory.eval.response import (
    ResponseCase,
    ResponseScore,
    run_response_eval,
    score_response,
)
from agent_memory.eval.retrieval import (
    RetrievalCase,
    keyword_recall_score,
    run_retrieval_eval,
)
from agent_memory.memory.store import InMemoryArtifactStore

# ---------------------------------------------------------------------------
# keyword_recall_score (pure function — unchanged)
# ---------------------------------------------------------------------------

def test_recall_perfect():
    retrieved = ["I want retirement income.", "Tax-efficient municipal bonds."]
    gold = ["retirement", "bonds"]
    assert keyword_recall_score(retrieved, gold) == 1.0


def test_recall_partial():
    retrieved = ["I want retirement income."]
    gold = ["retirement", "equity"]
    score = keyword_recall_score(retrieved, gold)
    assert score == 0.5


def test_recall_miss():
    retrieved = ["General market commentary."]
    gold = ["retirement", "bonds"]
    assert keyword_recall_score(retrieved, gold) == 0.0


def test_recall_no_gold_keywords():
    assert keyword_recall_score(["anything"], []) == 1.0


def test_recall_case_insensitive():
    retrieved = ["Client prefers MUNICIPAL bonds."]
    gold = ["municipal"]
    assert keyword_recall_score(retrieved, gold) == 1.0


def test_recall_empty_retrieved_non_empty_gold():
    assert keyword_recall_score([], ["retirement"]) == 0.0


# ---------------------------------------------------------------------------
# run_retrieval_eval with InMemoryArtifactStore
# ---------------------------------------------------------------------------

def _seeded_store() -> InMemoryArtifactStore:
    """Return a store pre-loaded with known artifacts and chunks."""
    store = InMemoryArtifactStore()
    contents = [
        "I want steady retirement income from my portfolio.",
        "My risk tolerance is moderate, I prefer tax-efficient bonds.",
        "We should discuss estate planning for my children.",
    ]
    for i, text in enumerate(contents):
        store.ingest_artifact(
            client_id="client_0000",
            advisor_id="advisor_demo",
            kind="text",
            original_filename=f"note_{i}.txt",
            volume_path=f"/vol/client_0000/{i+1}.txt",
            content_hash=f"hash_{i}",
            extracted_text=text,
        )
        store.write_chunks(
            artifact_id=i + 1,
            client_id="client_0000",
            chunks=[text],
            embeddings=[[0.1 * (i + 1)] * 1024],
        )
    return store


def test_run_retrieval_eval_hit():
    store = _seeded_store()
    cases = [
        RetrievalCase(
            client_id="client_0000",
            query="retirement planning",
            gold_keywords=["retirement", "income"],
        )
    ]
    results = run_retrieval_eval(cases, store, top_k=5)
    assert len(results) == 1
    assert results[0].keyword_recall == 1.0


def test_run_retrieval_eval_miss():
    store = _seeded_store()
    cases = [
        RetrievalCase(
            client_id="client_0000",
            query="crypto speculation",
            gold_keywords=["bitcoin", "crypto"],
        )
    ]
    results = run_retrieval_eval(cases, store, top_k=5)
    assert results[0].keyword_recall == 0.0


def test_run_retrieval_eval_empty_client():
    store = InMemoryArtifactStore()
    cases = [
        RetrievalCase(
            client_id="client_unknown",
            query="retirement",
            gold_keywords=["retirement"],
        )
    ]
    results = run_retrieval_eval(cases, store, top_k=5)
    assert results[0].keyword_recall == 0.0
    assert results[0].retrieved_content == []


def test_run_retrieval_eval_uses_retrieve_chunks():
    """retrieval.py must call retrieve_chunks (not retrieve_similar) on ArtifactStore."""
    store = InMemoryArtifactStore()
    store.retrieve_chunks = lambda **kwargs: []  # type: ignore[assignment]

    cases = [RetrievalCase(client_id="c0", query="q", gold_keywords=["q"])]
    # If retrieve_similar is called instead, it would raise AttributeError on InMemoryArtifactStore
    results = run_retrieval_eval(cases, store, top_k=5)
    assert results[0].keyword_recall == 0.0


def test_run_retrieval_eval_scoped_to_client():
    """Chunks from a different client must not influence retrieval for client_0000."""
    store = InMemoryArtifactStore()
    store.ingest_artifact(
        client_id="client_0001",
        advisor_id="a",
        kind="text",
        original_filename="n.txt",
        volume_path="/vol/c1/1.txt",
        content_hash="xyz",
        extracted_text="bitcoin speculation",
    )
    store.write_chunks(
        artifact_id=1,
        client_id="client_0001",
        chunks=["bitcoin speculation"],
        embeddings=[[0.9] * 1024],
    )
    cases = [
        RetrievalCase(
            client_id="client_0000",
            query="bitcoin",
            gold_keywords=["bitcoin"],
        )
    ]
    results = run_retrieval_eval(cases, store, top_k=5)
    assert results[0].keyword_recall == 0.0


# ---------------------------------------------------------------------------
# score_response (LLM-as-judge) — existing fields
# ---------------------------------------------------------------------------

def _judge_model(grounding: float, suitability: float, tone: float, advice_boundary: str = "PASS") -> FakeListChatModel:
    payload = {
        "grounding": grounding,
        "suitability": suitability,
        "tone": tone,
        "advice_boundary": advice_boundary,
        "reasoning": "Response references client's retirement goals and appropriate risk framing.",
    }
    return FakeListChatModel(responses=[json.dumps(payload)])


def test_score_response_parses_json():
    model = _judge_model(grounding=0.9, suitability=0.8, tone=0.95)
    score = score_response(
        scenario="How should I rebalance?",
        response="Given your moderate risk and retirement focus, I suggest...",
        profile_context="Moderate risk, retirement income goal.",
        model=model,
    )
    assert isinstance(score, ResponseScore)
    assert score.grounding == pytest.approx(0.9)
    assert score.suitability == pytest.approx(0.8)
    assert score.tone == pytest.approx(0.95)
    assert "retirement" in score.reasoning


def test_run_response_eval_batch():
    model = FakeListChatModel(
        responses=[
            json.dumps({"grounding": 0.8, "suitability": 0.7, "tone": 0.9, "advice_boundary": "PASS", "reasoning": "ok"}),
            json.dumps({"grounding": 0.6, "suitability": 0.5, "tone": 0.8, "advice_boundary": "VIOLATION", "reasoning": "fair"}),
        ]
    )
    cases = [
        ResponseCase(client_id="c0", scenario="Q1", profile_context="profile1"),
        ResponseCase(client_id="c1", scenario="Q2", profile_context="profile2"),
    ]
    scores = run_response_eval(cases, ["response1", "response2"], model=model)
    assert len(scores) == 2
    assert scores[0].grounding == pytest.approx(0.8)
    assert scores[1].tone == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# advice_boundary judge (NEW — D9, interfaces.md §7)
# ---------------------------------------------------------------------------

def test_response_score_has_advice_boundary_field():
    """ResponseScore must have advice_boundary: 'PASS' | 'VIOLATION'."""
    model = _judge_model(grounding=0.9, suitability=0.8, tone=0.9, advice_boundary="PASS")
    score = score_response(
        scenario="Should I buy bonds?",
        response="Here are some considerations around fixed income allocation.",
        profile_context="Moderate risk",
        model=model,
    )
    assert hasattr(score, "advice_boundary")
    assert score.advice_boundary in ("PASS", "VIOLATION")


def test_response_score_advice_boundary_pass():
    model = _judge_model(grounding=0.9, suitability=0.9, tone=0.9, advice_boundary="PASS")
    score = score_response(
        scenario="What should I consider for retirement?",
        response="Considerations include your time horizon, risk tolerance, and tax efficiency.",
        profile_context="Moderate risk, retirement focus",
        model=model,
    )
    assert score.advice_boundary == "PASS"


def test_response_score_advice_boundary_violation():
    model = _judge_model(grounding=0.7, suitability=0.6, tone=0.7, advice_boundary="VIOLATION")
    score = score_response(
        scenario="What should I buy?",
        response="You should buy Apple stock immediately.",
        profile_context="Moderate risk",
        model=model,
    )
    assert score.advice_boundary == "VIOLATION"


def test_advice_boundary_judge_batch():
    """Batch eval must propagate advice_boundary per case."""
    model = FakeListChatModel(
        responses=[
            json.dumps({"grounding": 0.9, "suitability": 0.9, "tone": 0.9, "advice_boundary": "PASS", "reasoning": "ok"}),
            json.dumps({"grounding": 0.5, "suitability": 0.4, "tone": 0.6, "advice_boundary": "VIOLATION", "reasoning": "recommends specific stock"}),
        ]
    )
    cases = [
        ResponseCase(client_id="c0", scenario="Q1", profile_context="p1"),
        ResponseCase(client_id="c1", scenario="Q2", profile_context="p2"),
    ]
    scores = run_response_eval(cases, ["r1", "r2"], model=model)
    assert scores[0].advice_boundary == "PASS"
    assert scores[1].advice_boundary == "VIOLATION"
