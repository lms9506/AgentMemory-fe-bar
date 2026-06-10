"""Retrieval recall eval — keyword-based recall@k scoring (FR-8, M8)."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_memory.memory.store import ArtifactStore


@dataclass
class RetrievalCase:
    client_id: str
    query: str
    gold_keywords: list[str] = field(default_factory=list)


@dataclass
class RetrievalResult:
    case: RetrievalCase
    retrieved_content: list[str]
    keyword_recall: float


def keyword_recall_score(retrieved_content: list[str], gold_keywords: list[str]) -> float:
    """Fraction of gold keywords present in any retrieved chunk's content.

    Uses keyword containment rather than chunk-ID matching so the eval can run
    against a live workspace without pre-labelled chunk IDs.
    """
    if not gold_keywords:
        return 1.0
    blob = " ".join(c.lower() for c in retrieved_content)
    hits = sum(1 for kw in gold_keywords if kw.lower() in blob)
    return hits / len(gold_keywords)


def run_retrieval_eval(
    cases: list[RetrievalCase],
    store: ArtifactStore,
    *,
    top_k: int = 5,
) -> list[RetrievalResult]:
    """Retrieve top-k chunks per case and score keyword recall."""
    results = []
    for case in cases:
        retrieved = store.retrieve_chunks(
            client_id=case.client_id,
            query=case.query,
            top_k=top_k,
        )
        content = [c.content for c in retrieved]
        score = keyword_recall_score(content, case.gold_keywords)
        results.append(
            RetrievalResult(case=case, retrieved_content=content, keyword_recall=score)
        )
    return results
