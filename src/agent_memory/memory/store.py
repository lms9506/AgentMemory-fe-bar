"""Episodic + semantic memory backed by Lakebase."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Protocol

from pgvector.psycopg import Vector

from agent_memory.memory.connection import lakebase_connection
from agent_memory.memory.embeddings import embed_texts
from agent_memory.memory.models import ConversationTurnRecord, RetrievedTurn


class MemoryStore(Protocol):
    def next_turn_index(self, session_id: str) -> int: ...

    def append_turn(
        self,
        *,
        client_id: str,
        advisor_id: str,
        session_id: str,
        turn_index: int,
        role: str,
        content: str,
        source: str = "agent",
        agent_run_id: str | None = None,
        embed: bool = True,
    ) -> ConversationTurnRecord: ...

    def retrieve_similar(
        self,
        *,
        client_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievedTurn]: ...


class LakebaseMemoryStore:
    """Live memory store — requires schema from `databricks/lakebase_schema.sql`."""

    def next_turn_index(self, session_id: str) -> int:
        with lakebase_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(MAX(turn_index), -1) + 1
                FROM conversation_turns
                WHERE session_id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def append_turn(
        self,
        *,
        client_id: str,
        advisor_id: str,
        session_id: str,
        turn_index: int,
        role: str,
        content: str,
        source: str = "agent",
        agent_run_id: str | None = None,
        embed: bool = True,
    ) -> ConversationTurnRecord:
        with lakebase_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversation_turns
                    (client_id, advisor_id, session_id, turn_index, role, content, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING turn_id, ts
                """,
                (client_id, advisor_id, session_id, turn_index, role, content, source),
            )
            row = cur.fetchone()
            if row is None:
                msg = "INSERT into conversation_turns did not return a row"
                raise RuntimeError(msg)
            turn_id, ts = row

            if embed:
                vector = Vector(embed_texts([content])[0])
                cur.execute(
                    """
                    INSERT INTO turn_embeddings (turn_id, client_id, embedding)
                    VALUES (%s, %s, %s)
                    """,
                    (turn_id, client_id, vector),
                )

            cur.execute(
                """
                INSERT INTO audit_log (actor, actor_kind, action, target_ref, payload, agent_run_id)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                """,
                (
                    advisor_id if source == "human" else "wealth_advisor_agent",
                    "advisor" if source == "human" else "agent",
                    "append_turn",
                    f"client:{client_id}/session:{session_id}/turn:{turn_id}",
                    json.dumps(
                        {
                            "turn_id": turn_id,
                            "role": role,
                            "turn_index": turn_index,
                            "source": source,
                        }
                    ),
                    agent_run_id,
                ),
            )
            conn.commit()

        return ConversationTurnRecord(
            turn_id=int(turn_id),
            client_id=client_id,
            advisor_id=advisor_id,
            session_id=session_id,
            turn_index=turn_index,
            role=role,
            content=content,
            ts=ts,
        )

    def retrieve_similar(
        self,
        *,
        client_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievedTurn]:
        query_vector = Vector(embed_texts([query])[0])
        with lakebase_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.turn_id, t.content, t.role, t.ts,
                       1 - (e.embedding <=> %s) AS score
                FROM turn_embeddings e
                JOIN conversation_turns t ON t.turn_id = e.turn_id
                WHERE e.client_id = %s
                ORDER BY e.embedding <=> %s
                LIMIT %s
                """,
                (query_vector, client_id, query_vector, top_k),
            )
            rows = cur.fetchall()

        return [
            RetrievedTurn(
                turn_id=int(r[0]),
                content=r[1],
                role=r[2],
                score=float(r[4]),
                ts=r[3],
            )
            for r in rows
        ]


class InMemoryMemoryStore:
    """Test double — no Lakebase required."""

    def __init__(self) -> None:
        self._turns: list[ConversationTurnRecord] = []
        self._embeddings: dict[int, list[float]] = {}
        self._next_id = 1

    def next_turn_index(self, session_id: str) -> int:
        indices = [t.turn_index for t in self._turns if t.session_id == session_id]
        return (max(indices) + 1) if indices else 0

    def append_turn(
        self,
        *,
        client_id: str,
        advisor_id: str,
        session_id: str,
        turn_index: int,
        role: str,
        content: str,
        source: str = "agent",
        agent_run_id: str | None = None,
        embed: bool = True,
    ) -> ConversationTurnRecord:
        del source, agent_run_id, embed
        turn = ConversationTurnRecord(
            turn_id=self._next_id,
            client_id=client_id,
            advisor_id=advisor_id,
            session_id=session_id,
            turn_index=turn_index,
            role=role,
            content=content,
            ts=datetime.now(tz=UTC),
        )
        self._next_id += 1
        self._turns.append(turn)
        return turn

    def retrieve_similar(
        self,
        *,
        client_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievedTurn]:
        del query
        matches = [t for t in self._turns if t.client_id == client_id]
        return [
            RetrievedTurn(
                turn_id=t.turn_id,
                content=t.content,
                role=t.role,
                score=1.0,
                ts=t.ts,
            )
            for t in matches[:top_k]
        ]
