"""Episodic + semantic memory backed by Lakebase — dossier model (D1)."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from typing import Protocol

# `Vector` moved between pgvector releases: older versions expose it at
# `pgvector.psycopg`, newer ones (e.g. the Databricks Serverless build) only at the
# top-level `pgvector`. Import from whichever this environment provides.
try:
    from pgvector.psycopg import Vector
except ImportError:  # pragma: no cover - version-dependent import path
    from pgvector import Vector

from agent_memory.memory.connection import lakebase_connection
from agent_memory.memory.embeddings import embed_texts
from agent_memory.memory.lakebase_ddl import (
    ensure_artifact_chunks,
    ensure_artifacts,
    ensure_audit_log,
    ensure_clients_table,
)
from agent_memory.memory.models import ArtifactKind, ArtifactRecord, RetrievedChunk


class ArtifactStore(Protocol):
    def ingest_artifact(
        self,
        *,
        client_id: str,
        advisor_id: str,
        kind: ArtifactKind,
        original_filename: str,
        volume_path: str,
        content_hash: str,
        extracted_text: str | None = None,
        summary: str | None = None,
        sensitivity_tags: list[str] | None = None,
        agent_run_id: str | None = None,
    ) -> ArtifactRecord:
        """INSERT an artifacts row + append an 'ingest_artifact' audit row. Does NOT
        write chunks (see write_chunks) and does NOT upload bytes (see volume_store)."""
        ...

    def update_artifact_text(
        self, *, artifact_id: int, extracted_text: str, summary: str | None = None
    ) -> None:
        """Patch extracted_text/summary after extraction/summarize nodes run."""
        ...

    def update_volume_path(self, *, artifact_id: int, volume_path: str) -> None:
        """Persist the UC Volume path after the raw bytes are uploaded (ADR-0013).

        raw_save inserts the row to mint artifact_id (the path embeds it), uploads
        the bytes, then calls this to record where they landed — keeping the
        provenance chain (field → artifact → volume_path → raw bytes) intact.
        """
        ...

    def backdate_artifact(self, *, artifact_id: int, ingested_at: datetime) -> None:
        """Override an artifact's ingested_at (and its chunks' created_at).

        Seed-only (ADR-0015): production ingest always stamps "now"; the demo seed
        backdates artifacts so the dossier timeline reads as a real history.
        """
        ...

    def write_chunks(
        self,
        *,
        artifact_id: int,
        client_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> int:
        """Insert artifact_chunks rows (chunk_index = 0..n-1). Returns count written."""
        ...

    def retrieve_chunks(
        self, *, client_id: str, query: str, top_k: int = 5
    ) -> list[RetrievedChunk]:
        """Semantic recall scoped to client_id (cosine over artifact_chunks)."""
        ...

    def get_artifact(self, artifact_id: int) -> ArtifactRecord | None: ...

    def list_artifacts(
        self, *, client_id: str, limit: int = 200
    ) -> list[ArtifactRecord]:
        """Dossier timeline, newest first (ingested_at DESC)."""
        ...

    def find_by_hash(
        self, *, client_id: str, content_hash: str
    ) -> ArtifactRecord | None:
        """Dedup check (ADR-0013); returns the existing record on a hit."""
        ...

    def list_clients(self) -> list[tuple[str, str]]:
        """[(client_id, display_name)] from artifacts JOIN clients, ordered by name."""
        ...

    def list_advisors(self) -> list[str]:
        """DISTINCT advisor_id from artifacts."""
        ...

    def upsert_client(self, client_id: str, display_name: str) -> None: ...

    def write_audit(
        self,
        *,
        actor: str,
        actor_kind: str,        # 'agent' | 'advisor' | 'job'
        action: str,
        target_ref: str,
        payload: dict,
        agent_run_id: str | None = None,
    ) -> None:
        """Append-only audit_log row. Used by ingest + any LTM write."""
        ...


class LakebaseArtifactStore:
    """Live artifact store — requires schema from `databricks/lakebase_schema.sql`."""

    def ingest_artifact(
        self,
        *,
        client_id: str,
        advisor_id: str,
        kind: ArtifactKind,
        original_filename: str,
        volume_path: str,
        content_hash: str,
        extracted_text: str | None = None,
        summary: str | None = None,
        sensitivity_tags: list[str] | None = None,
        agent_run_id: str | None = None,
    ) -> ArtifactRecord:
        # P2 ordering note: the ingest pipeline does INSERT (here) → Volume upload →
        # UPDATE (volume_path patch).  If the process dies between INSERT and Volume
        # upload the row exists with an empty/placeholder volume_path.  The unique index
        # on (client_id, content_hash) prevents a second attempt from creating a
        # duplicate row — a UniqueViolation on retry is caught below and treated as a
        # dedup hit so callers can recover cleanly.
        tags = sensitivity_tags or []
        with lakebase_connection() as conn, conn.cursor() as cur:
            ensure_artifacts(cur)
            ensure_audit_log(cur)
            try:
                cur.execute(
                    """
                    INSERT INTO artifacts
                        (client_id, advisor_id, kind, original_filename, volume_path,
                         content_hash, extracted_text, summary, sensitivity_tags)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING artifact_id, ingested_at
                    """,
                    (
                        client_id,
                        advisor_id,
                        kind,
                        original_filename,
                        volume_path,
                        content_hash,
                        extracted_text,
                        summary,
                        tags,
                    ),
                )
                row = cur.fetchone()
            except Exception as exc:
                # Catch unique-violation on (client_id, content_hash) index.
                # psycopg raises psycopg.errors.UniqueViolation (a subclass of
                # DatabaseError); we check by pgcode '23505' to avoid importing the
                # errors submodule conditionally.
                pgcode = getattr(exc, "pgcode", None) or getattr(
                    getattr(exc, "diag", None), "sqlstate", None
                )
                if pgcode == "23505":
                    # Dedup race: another concurrent ingest inserted the same hash
                    # between our find_by_hash check and this INSERT.  Roll back and
                    # re-fetch the existing row so the caller gets a valid record.
                    conn.rollback()
                    cur.execute(
                        """
                        SELECT artifact_id, client_id, advisor_id, kind,
                               original_filename, volume_path, content_hash,
                               extracted_text, summary, sensitivity_tags, ingested_at
                        FROM artifacts
                        WHERE client_id = %s AND content_hash = %s
                        LIMIT 1
                        """,
                        (client_id, content_hash),
                    )
                    existing = cur.fetchone()
                    if existing:
                        return _row_to_artifact(existing)
                raise
            if row is None:
                msg = "INSERT into artifacts did not return a row"
                raise RuntimeError(msg)
            artifact_id, ingested_at = row

            cur.execute(
                """
                INSERT INTO audit_log
                    (actor, actor_kind, action, target_ref, payload, agent_run_id)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                """,
                (
                    advisor_id,
                    "advisor",
                    "ingest_artifact",
                    f"client:{client_id}/artifact:{artifact_id}",
                    json.dumps(
                        {
                            "artifact_id": int(artifact_id),
                            "kind": kind,
                            "filename": original_filename,
                            "volume_path": volume_path,
                            "content_hash": content_hash,
                        }
                    ),
                    agent_run_id,
                ),
            )
            conn.commit()

        return ArtifactRecord(
            artifact_id=int(artifact_id),
            client_id=client_id,
            advisor_id=advisor_id,
            kind=kind,
            original_filename=original_filename,
            volume_path=volume_path,
            content_hash=content_hash,
            extracted_text=extracted_text,
            summary=summary,
            sensitivity_tags=tags,
            ingested_at=ingested_at,
        )

    def update_artifact_text(
        self, *, artifact_id: int, extracted_text: str, summary: str | None = None
    ) -> None:
        with lakebase_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE artifacts
                SET extracted_text = %s,
                    summary = COALESCE(%s, summary)
                WHERE artifact_id = %s
                """,
                (extracted_text, summary, artifact_id),
            )
            conn.commit()

    def update_volume_path(self, *, artifact_id: int, volume_path: str) -> None:
        with lakebase_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE artifacts SET volume_path = %s WHERE artifact_id = %s",
                (volume_path, artifact_id),
            )
            conn.commit()

    def backdate_artifact(self, *, artifact_id: int, ingested_at: datetime) -> None:
        with lakebase_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE artifacts SET ingested_at = %s WHERE artifact_id = %s",
                (ingested_at, artifact_id),
            )
            cur.execute(
                "UPDATE artifact_chunks SET created_at = %s WHERE artifact_id = %s",
                (ingested_at, artifact_id),
            )
            conn.commit()

    def write_chunks(
        self,
        *,
        artifact_id: int,
        client_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> int:
        if not chunks:
            return 0
        with lakebase_connection() as conn, conn.cursor() as cur:
            ensure_artifact_chunks(cur)
            for chunk_index, (content, embedding) in enumerate(
                zip(chunks, embeddings, strict=True)
            ):
                vector = Vector(embedding)
                cur.execute(
                    """
                    INSERT INTO artifact_chunks
                        (artifact_id, client_id, chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (artifact_id, client_id, chunk_index, content, vector),
                )
            conn.commit()
        return len(chunks)

    def retrieve_chunks(
        self, *, client_id: str, query: str, top_k: int = 5
    ) -> list[RetrievedChunk]:
        query_vector = Vector(embed_texts([query])[0])
        with lakebase_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT chunk_id, artifact_id, chunk_index, content,
                       1 - (embedding <=> %s) AS score, created_at
                FROM artifact_chunks
                WHERE client_id = %s
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (query_vector, client_id, query_vector, top_k),
            )
            rows = cur.fetchall()

        return [
            RetrievedChunk(
                chunk_id=int(r[0]),
                artifact_id=int(r[1]),
                chunk_index=int(r[2]),
                content=str(r[3]),
                score=float(r[4]),
                created_at=r[5],
            )
            for r in rows
        ]

    def get_artifact(self, artifact_id: int) -> ArtifactRecord | None:
        with lakebase_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT artifact_id, client_id, advisor_id, kind, original_filename,
                       volume_path, content_hash, extracted_text, summary,
                       sensitivity_tags, ingested_at
                FROM artifacts
                WHERE artifact_id = %s
                """,
                (artifact_id,),
            )
            row = cur.fetchone()
        return _row_to_artifact(row) if row else None

    def list_artifacts(self, *, client_id: str, limit: int = 200) -> list[ArtifactRecord]:
        with lakebase_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT artifact_id, client_id, advisor_id, kind, original_filename,
                       volume_path, content_hash, extracted_text, summary,
                       sensitivity_tags, ingested_at
                FROM artifacts
                WHERE client_id = %s
                ORDER BY ingested_at DESC
                LIMIT %s
                """,
                (client_id, limit),
            )
            rows = cur.fetchall()
        return [_row_to_artifact(r) for r in rows]

    def find_by_hash(
        self, *, client_id: str, content_hash: str
    ) -> ArtifactRecord | None:
        with lakebase_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT artifact_id, client_id, advisor_id, kind, original_filename,
                       volume_path, content_hash, extracted_text, summary,
                       sensitivity_tags, ingested_at
                FROM artifacts
                WHERE client_id = %s AND content_hash = %s
                LIMIT 1
                """,
                (client_id, content_hash),
            )
            row = cur.fetchone()
        return _row_to_artifact(row) if row else None

    def list_clients(self) -> list[tuple[str, str]]:
        """Return [(client_id, display_name)] from artifacts JOIN clients, ordered by name."""
        with lakebase_connection() as conn, conn.cursor() as cur:
            ensure_clients_table(cur)
            conn.commit()
            cur.execute(
                """
                SELECT DISTINCT a.client_id,
                       COALESCE(c.display_name, a.client_id) AS display_name
                FROM artifacts a
                LEFT JOIN clients c USING (client_id)
                ORDER BY display_name
                """
            )
            return [(r[0], r[1]) for r in cur.fetchall()]

    def list_advisors(self) -> list[str]:
        with lakebase_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT advisor_id FROM artifacts ORDER BY advisor_id"
            )
            return [r[0] for r in cur.fetchall()]

    def upsert_client(self, client_id: str, display_name: str) -> None:
        with lakebase_connection() as conn, conn.cursor() as cur:
            ensure_clients_table(cur)
            cur.execute(
                """
                INSERT INTO clients (client_id, display_name)
                VALUES (%s, %s)
                ON CONFLICT (client_id) DO UPDATE SET display_name = EXCLUDED.display_name
                """,
                (client_id, display_name),
            )
            conn.commit()

    def write_audit(
        self,
        *,
        actor: str,
        actor_kind: str,
        action: str,
        target_ref: str,
        payload: dict,
        agent_run_id: str | None = None,
    ) -> None:
        with lakebase_connection() as conn, conn.cursor() as cur:
            ensure_audit_log(cur)
            cur.execute(
                """
                INSERT INTO audit_log
                    (actor, actor_kind, action, target_ref, payload, agent_run_id)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                """,
                (
                    actor,
                    actor_kind,
                    action,
                    target_ref,
                    json.dumps(payload),
                    agent_run_id,
                ),
            )
            conn.commit()


def _row_to_artifact(row: tuple) -> ArtifactRecord:
    (
        artifact_id,
        client_id,
        advisor_id,
        kind,
        original_filename,
        volume_path,
        content_hash,
        extracted_text,
        summary,
        sensitivity_tags,
        ingested_at,
    ) = row
    return ArtifactRecord(
        artifact_id=int(artifact_id),
        client_id=str(client_id),
        advisor_id=str(advisor_id),
        kind=str(kind),  # type: ignore[arg-type]
        original_filename=str(original_filename),
        volume_path=str(volume_path),
        content_hash=str(content_hash),
        extracted_text=str(extracted_text) if extracted_text is not None else None,
        summary=str(summary) if summary is not None else None,
        sensitivity_tags=list(sensitivity_tags) if sensitivity_tags else [],
        ingested_at=ingested_at if isinstance(ingested_at, datetime) else datetime.now(tz=timezone.utc),
    )


class InMemoryArtifactStore:
    """Test double — no Lakebase required."""

    def __init__(self) -> None:
        self._artifacts: list[ArtifactRecord] = []
        self._chunks: list[tuple[int, int, int, str, list[float], datetime]] = []
        self._audit_events: list[dict] = []
        self._next_artifact_id = 1
        self._next_chunk_id = 1
        self._clients: dict[str, str] = {}

    def ingest_artifact(
        self,
        *,
        client_id: str,
        advisor_id: str,
        kind: ArtifactKind,
        original_filename: str,
        volume_path: str,
        content_hash: str,
        extracted_text: str | None = None,
        summary: str | None = None,
        sensitivity_tags: list[str] | None = None,
        agent_run_id: str | None = None,
    ) -> ArtifactRecord:
        artifact = ArtifactRecord(
            artifact_id=self._next_artifact_id,
            client_id=client_id,
            advisor_id=advisor_id,
            kind=kind,
            original_filename=original_filename,
            volume_path=volume_path,
            content_hash=content_hash,
            extracted_text=extracted_text,
            summary=summary,
            sensitivity_tags=sensitivity_tags or [],
            ingested_at=datetime.now(tz=timezone.utc),
        )
        self._next_artifact_id += 1
        self._artifacts.append(artifact)
        self._audit_events.append(
            {
                "action": "ingest_artifact",
                "artifact_id": artifact.artifact_id,
                "kind": kind,
                "filename": original_filename,
                "volume_path": volume_path,
                "content_hash": content_hash,
                "agent_run_id": agent_run_id,
            }
        )
        return artifact

    def update_artifact_text(
        self, *, artifact_id: int, extracted_text: str, summary: str | None = None
    ) -> None:
        updated = []
        for a in self._artifacts:
            if a.artifact_id == artifact_id:
                a = ArtifactRecord(
                    artifact_id=a.artifact_id,
                    client_id=a.client_id,
                    advisor_id=a.advisor_id,
                    kind=a.kind,
                    original_filename=a.original_filename,
                    volume_path=a.volume_path,
                    content_hash=a.content_hash,
                    extracted_text=extracted_text,
                    summary=summary if summary is not None else a.summary,
                    sensitivity_tags=a.sensitivity_tags,
                    ingested_at=a.ingested_at,
                )
            updated.append(a)
        self._artifacts = updated

    def update_volume_path(self, *, artifact_id: int, volume_path: str) -> None:
        self._artifacts = [
            replace(a, volume_path=volume_path) if a.artifact_id == artifact_id else a
            for a in self._artifacts
        ]

    def backdate_artifact(self, *, artifact_id: int, ingested_at: datetime) -> None:
        self._artifacts = [
            replace(a, ingested_at=ingested_at) if a.artifact_id == artifact_id else a
            for a in self._artifacts
        ]
        self._chunks = [
            (cid, aid, idx, content, emb, ingested_at if aid == artifact_id else created)
            for (cid, aid, idx, content, emb, created) in self._chunks
        ]

    def write_chunks(
        self,
        *,
        artifact_id: int,
        client_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> int:
        now = datetime.now(tz=timezone.utc)
        for chunk_index, (content, embedding) in enumerate(
            zip(chunks, embeddings, strict=True)
        ):
            self._chunks.append(
                (self._next_chunk_id, artifact_id, chunk_index, content, embedding, now)
            )
            self._next_chunk_id += 1
        return len(chunks)

    def retrieve_chunks(
        self, *, client_id: str, query: str, top_k: int = 5
    ) -> list[RetrievedChunk]:
        del query
        # Return chunks belonging to this client's artifacts, score=1.0.
        client_artifact_ids = {
            a.artifact_id for a in self._artifacts if a.client_id == client_id
        }
        result = []
        for chunk_id, artifact_id, chunk_index, content, _emb, created_at in self._chunks:
            if artifact_id in client_artifact_ids:
                result.append(
                    RetrievedChunk(
                        chunk_id=chunk_id,
                        artifact_id=artifact_id,
                        chunk_index=chunk_index,
                        content=content,
                        score=1.0,
                        created_at=created_at,
                    )
                )
        return result[:top_k]

    def get_artifact(self, artifact_id: int) -> ArtifactRecord | None:
        for a in self._artifacts:
            if a.artifact_id == artifact_id:
                return a
        return None

    def list_artifacts(self, *, client_id: str, limit: int = 200) -> list[ArtifactRecord]:
        matches = [a for a in self._artifacts if a.client_id == client_id]
        matches.sort(key=lambda a: a.ingested_at, reverse=True)
        return matches[:limit]

    def find_by_hash(
        self, *, client_id: str, content_hash: str
    ) -> ArtifactRecord | None:
        for a in self._artifacts:
            if a.client_id == client_id and a.content_hash == content_hash:
                return a
        return None

    def list_clients(self) -> list[tuple[str, str]]:
        seen: dict[str, str] = {}
        for a in self._artifacts:
            if a.client_id not in seen:
                seen[a.client_id] = self._clients.get(a.client_id, a.client_id)
        return sorted(seen.items(), key=lambda x: x[1])

    def list_advisors(self) -> list[str]:
        return sorted({a.advisor_id for a in self._artifacts})

    def upsert_client(self, client_id: str, display_name: str) -> None:
        self._clients[client_id] = display_name

    def write_audit(
        self,
        *,
        actor: str,
        actor_kind: str,
        action: str,
        target_ref: str,
        payload: dict,
        agent_run_id: str | None = None,
    ) -> None:
        self._audit_events.append(
            {
                "actor": actor,
                "actor_kind": actor_kind,
                "action": action,
                "target_ref": target_ref,
                "payload": payload,
                "agent_run_id": agent_run_id,
            }
        )
