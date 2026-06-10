"""FastAPI route tests — dossier model.

Contract source: interfaces.md §4 (FastAPI models) + §4 route list.
Dead routes tested as 404. New routes tested happy path + edge cases.
Dead symbols removed: ConversationTurnRecord, session_id on chat body, retrieved_turns.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agent_memory.memory.models import ArtifactRecord
from agent_memory.memory.profile_models import DistilledClientProfile
from agent_memory.ui.server import create_app

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with (
        patch("agent_memory.ui.server.ensure_databricks_auth", return_value=True),
        TestClient(create_app()) as test_client,
    ):
        yield test_client


def _artifact_record(artifact_id: int = 1, client_id: str = "c1") -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=artifact_id,
        client_id=client_id,
        advisor_id="a1",
        kind="text",
        original_filename="note.txt",
        volume_path=f"/vol/{client_id}/{artifact_id}.txt",
        content_hash=f"hash{artifact_id}",
        extracted_text="Some extracted text.",
        summary="A summary.",
        sensitivity_tags=[],
        ingested_at=datetime.now(tz=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Health — unchanged
# ---------------------------------------------------------------------------

def test_health(client: TestClient) -> None:
    with patch("agent_memory.ui.server.Settings") as mock_settings:
        s = mock_settings.from_env.return_value
        s.lakebase_configured = True
        s.uc_catalog = "cat"
        s.uc_schema = "sch"
        s.volume_name = "dossier_raw"
        s.databricks_host = "https://example.cloud.databricks.com"
        res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["volume_name"] == "dossier_raw"
    assert body["workspace_url"] == "https://example.cloud.databricks.com"


# ---------------------------------------------------------------------------
# REMOVED routes return 404
# ---------------------------------------------------------------------------

def test_transcript_route_removed(client: TestClient) -> None:
    res = client.get("/api/sessions/s1/transcript", params={"client_id": "c1"})
    assert res.status_code == 404


def test_sessions_route_removed(client: TestClient) -> None:
    res = client.get("/api/clients/c1/sessions")
    assert res.status_code == 404


def test_memory_human_route_removed(client: TestClient) -> None:
    res = client.post("/api/memory/human", json={"client_id": "c1", "content": "test"})
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/clients/{client_id}/artifacts (NEW)
# ---------------------------------------------------------------------------

def test_list_artifacts_happy_path(client: TestClient) -> None:
    mock_store = MagicMock()
    mock_store.list_artifacts.return_value = [_artifact_record(1, "c1"), _artifact_record(2, "c1")]
    mock_profile = MagicMock()
    mock_profile.get_profile.return_value = DistilledClientProfile(
        client_id="c1",
        source_artifact_ids=[1],
    )
    with (
        patch("agent_memory.ui.server.LakebaseArtifactStore", return_value=mock_store),
        patch("agent_memory.ui.server.DeltaProfileStore", return_value=mock_profile),
    ):
        res = client.get("/api/clients/c1/artifacts")

    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    assert data[0]["artifact_id"] == 1
    assert data[0]["client_id"] == "c1"


def test_list_artifacts_response_has_no_extracted_text(client: TestClient) -> None:
    """Timeline view must NOT include extracted_text (it's large)."""
    mock_store = MagicMock()
    mock_store.list_artifacts.return_value = [_artifact_record(1, "c1")]
    mock_profile = MagicMock()
    mock_profile.get_profile.return_value = None
    with (
        patch("agent_memory.ui.server.LakebaseArtifactStore", return_value=mock_store),
        patch("agent_memory.ui.server.DeltaProfileStore", return_value=mock_profile),
    ):
        res = client.get("/api/clients/c1/artifacts")

    data = res.json()
    assert len(data) >= 1
    # extracted_text must be null/omitted on the list route
    assert data[0].get("extracted_text") is None


def test_list_artifacts_contributed_to_profile_flag(client: TestClient) -> None:
    """artifact_id ∈ profile.source_artifact_ids → contributed_to_profile=True."""
    mock_store = MagicMock()
    mock_store.list_artifacts.return_value = [
        _artifact_record(10, "c1"),
        _artifact_record(20, "c1"),
    ]
    mock_profile = MagicMock()
    mock_profile.get_profile.return_value = DistilledClientProfile(
        client_id="c1",
        source_artifact_ids=[10],  # only artifact 10 contributed
    )
    with (
        patch("agent_memory.ui.server.LakebaseArtifactStore", return_value=mock_store),
        patch("agent_memory.ui.server.DeltaProfileStore", return_value=mock_profile),
    ):
        res = client.get("/api/clients/c1/artifacts")

    data = res.json()
    by_id = {item["artifact_id"]: item for item in data}
    assert by_id[10]["contributed_to_profile"] is True
    assert by_id[20]["contributed_to_profile"] is False


def test_list_artifacts_no_profile_all_false(client: TestClient) -> None:
    mock_store = MagicMock()
    mock_store.list_artifacts.return_value = [_artifact_record(1, "c1")]
    mock_profile = MagicMock()
    mock_profile.get_profile.return_value = None
    with (
        patch("agent_memory.ui.server.LakebaseArtifactStore", return_value=mock_store),
        patch("agent_memory.ui.server.DeltaProfileStore", return_value=mock_profile),
    ):
        res = client.get("/api/clients/c1/artifacts")

    data = res.json()
    assert data[0]["contributed_to_profile"] is False


# ---------------------------------------------------------------------------
# GET /api/artifacts/{artifact_id} (NEW — detail)
# ---------------------------------------------------------------------------

def test_get_artifact_detail_happy_path(client: TestClient) -> None:
    mock_store = MagicMock()
    mock_store.get_artifact.return_value = _artifact_record(5, "c1")
    with patch("agent_memory.ui.server.LakebaseArtifactStore", return_value=mock_store):
        res = client.get("/api/artifacts/5")

    assert res.status_code == 200
    body = res.json()
    assert body["artifact_id"] == 5
    assert body["extracted_text"] == "Some extracted text."
    assert body["summary"] == "A summary."
    assert "volume_path" in body


def test_get_artifact_detail_not_found(client: TestClient) -> None:
    mock_store = MagicMock()
    mock_store.get_artifact.return_value = None
    with patch("agent_memory.ui.server.LakebaseArtifactStore", return_value=mock_store):
        res = client.get("/api/artifacts/9999")
    assert res.status_code == 404


def test_get_artifact_detail_lakebase_error(client: TestClient) -> None:
    mock_store = MagicMock()
    mock_store.get_artifact.side_effect = RuntimeError("Lakebase credential refresh failed")
    with patch("agent_memory.ui.server.LakebaseArtifactStore", return_value=mock_store):
        res = client.get("/api/artifacts/1")
    assert res.status_code == 503


# ---------------------------------------------------------------------------
# GET /api/artifacts/{artifact_id}/raw (NEW — provenance download)
# ---------------------------------------------------------------------------

def test_get_artifact_raw_happy_path(client: TestClient) -> None:
    mock_store = MagicMock()
    mock_store.get_artifact.return_value = _artifact_record(3, "c1")

    raw_data = b"PDF bytes here"

    with (
        patch("agent_memory.ui.server.LakebaseArtifactStore", return_value=mock_store),
        patch("agent_memory.memory.volume_store.download_raw", return_value=BytesIO(raw_data)),
    ):
        res = client.get("/api/artifacts/3/raw")

    assert res.status_code == 200
    assert res.content == raw_data


def test_get_artifact_raw_not_found(client: TestClient) -> None:
    mock_store = MagicMock()
    mock_store.get_artifact.return_value = None
    with patch("agent_memory.ui.server.LakebaseArtifactStore", return_value=mock_store):
        res = client.get("/api/artifacts/9999/raw")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/clients/{client_id}/artifacts/ingest (NEW)
# ---------------------------------------------------------------------------

def test_ingest_artifact_25mb_cap_rejected(client: TestClient) -> None:
    """Files over 25 MB must be rejected with HTTP 413 (ADR-0011)."""
    oversized_bytes = b"x" * (25 * 1024 * 1024 + 1)
    res = client.post(
        "/api/clients/c1/artifacts/ingest",
        data={"advisor_id": "a1"},
        files={"file": ("big.pdf", BytesIO(oversized_bytes), "application/pdf")},
    )
    assert res.status_code == 413


def test_ingest_artifact_happy_path_sse(client: TestClient) -> None:
    """SSE response must have content-type text/event-stream and contain data: frames."""
    small_bytes = b"Hello, this is a small note."

    def fake_ingest_events(**kwargs):
        yield 'data: {"type": "step", "step": "saved", "artifact_id": 1}\n\n'
        yield 'data: {"type": "done", "artifact_id": 1, "deduped": false}\n\n'

    with patch("agent_memory.ui.server.stream_ingest_events", side_effect=fake_ingest_events):
        res = client.post(
            "/api/clients/c1/artifacts/ingest",
            data={"advisor_id": "a1"},
            files={"file": ("note.txt", BytesIO(small_bytes), "text/plain")},
        )

    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")
    assert "data:" in res.text


def test_ingest_artifact_missing_advisor_id_rejected(client: TestClient) -> None:
    small_bytes = b"data"
    res = client.post(
        "/api/clients/c1/artifacts/ingest",
        files={"file": ("note.txt", BytesIO(small_bytes), "text/plain")},
        # advisor_id intentionally omitted
    )
    assert res.status_code in (400, 422)


# ---------------------------------------------------------------------------
# POST /api/chat — no session_id, uses retrieved_chunks
# ---------------------------------------------------------------------------

def test_chat_no_session_id_required(client: TestClient) -> None:
    with patch("agent_memory.ui.server.run_turn_with_state") as mock_run:
        mock_run.return_value = {
            "response": "Here is guidance.",
            "retrieved_chunks": [],
            "agent_run_id": "run-1",
        }
        res = client.post(
            "/api/chat",
            json={
                "client_id": "c1",
                "advisor_id": "a1",
                "message": "What is my risk tolerance?",
                # NO session_id
            },
        )
    assert res.status_code == 200
    body = res.json()
    assert body["response"] == "Here is guidance."


def test_chat_response_has_retrieved_chunks_not_turns(client: TestClient) -> None:
    with patch("agent_memory.ui.server.run_turn_with_state") as mock_run:
        mock_run.return_value = {
            "response": "Guidance.",
            "retrieved_chunks": [
                {
                    "chunk_id": 1,
                    "artifact_id": 10,
                    "chunk_index": 0,
                    "content": "retirement income",
                    "score": 0.88,
                    "created_at": "2026-01-01T00:00:00+00:00",
                }
            ],
            "agent_run_id": "run-2",
        }
        res = client.post(
            "/api/chat",
            json={"client_id": "c1", "advisor_id": "a1", "message": "Tell me about retirement"},
        )
    assert res.status_code == 200
    body = res.json()
    assert "retrieved_chunks" in body
    assert "retrieved_turns" not in body
    assert body["retrieved_chunks"][0]["score"] == 0.88


def test_chat_request_rejects_session_id(client: TestClient) -> None:
    """ChatRequest must NOT accept session_id — it's a dead symbol."""
    from agent_memory.ui.schemas import ChatRequest

    req = ChatRequest(client_id="c1", advisor_id="a1", message="hello")
    assert not hasattr(req, "session_id")


# ---------------------------------------------------------------------------
# POST /api/chat/stream — retrieved_chunks in SSE
# ---------------------------------------------------------------------------

def test_chat_stream_sse_uses_retrieved_chunks(client: TestClient) -> None:
    def fake_events():
        yield {"type": "retrieved", "chunks": []}
        yield {"type": "token", "text": "Hi"}
        yield {"type": "done", "response": "Hi", "agent_run_id": "r1", "retrieved_chunks": []}

    with patch("agent_memory.ui.server.stream_advisor_events", return_value=fake_events()):
        res = client.post(
            "/api/chat/stream",
            json={"client_id": "c1", "advisor_id": "a1", "message": "Hello"},
        )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")
    assert "data:" in res.text
    # Must not contain retrieved_turns anywhere in the SSE stream
    assert "retrieved_turns" not in res.text


# ---------------------------------------------------------------------------
# ArtifactOut schema (contract tests — interfaces.md §4)
# ---------------------------------------------------------------------------

def test_artifact_out_schema_fields():
    from agent_memory.ui.schemas import ArtifactOut

    a = ArtifactOut(
        artifact_id=1,
        client_id="c0",
        advisor_id="a0",
        kind="pdf",
        original_filename="doc.pdf",
        volume_path="/vol/c0/1.pdf",
        content_hash="deadbeef",
    )
    assert a.artifact_id == 1
    assert a.contributed_to_profile is False
    assert isinstance(a.sensitivity_tags, list)
    assert a.summary is None
    assert a.extracted_text is None


def test_artifact_out_schema_contributed_to_profile_default():
    from agent_memory.ui.schemas import ArtifactOut

    a = ArtifactOut(
        artifact_id=2,
        client_id="c0",
        advisor_id="a0",
        kind="text",
        original_filename="n.txt",
        volume_path="/vol/c0/2.txt",
        content_hash="abc",
    )
    assert a.contributed_to_profile is False


def test_retrieved_chunk_out_schema_fields():
    from agent_memory.ui.schemas import RetrievedChunkOut

    c = RetrievedChunkOut(
        chunk_id=1,
        artifact_id=10,
        chunk_index=0,
        content="retirement income",
        score=0.9,
    )
    assert c.chunk_id == 1
    assert c.artifact_id == 10
    assert c.score == 0.9
    assert c.created_at is None


def test_chat_request_no_session_id_field():
    from agent_memory.ui.schemas import ChatRequest

    r = ChatRequest(client_id="c0", advisor_id="a0", message="hello")
    d = r.model_dump()
    assert "session_id" not in d


def test_chat_response_no_retrieved_turns_field():
    from agent_memory.ui.schemas import ChatResponse

    r = ChatResponse(response="ok")
    d = r.model_dump()
    assert "retrieved_turns" not in d
    assert "retrieved_chunks" in d


def test_client_profile_out_schema_source_artifact_ids():
    from agent_memory.ui.schemas import ClientProfileOut

    p = ClientProfileOut(
        client_id="c0",
        risk_tolerance="moderate",
        source_artifact_ids=[1, 2],
    )
    assert p.source_artifact_ids == [1, 2]
    assert not hasattr(p, "source_turn_ids")


# ---------------------------------------------------------------------------
# Existing kept routes still work
# ---------------------------------------------------------------------------

def test_profile_missing(client: TestClient) -> None:
    mock_profile = MagicMock()
    mock_profile.get_profile.return_value = None
    with patch("agent_memory.ui.server.DeltaProfileStore", return_value=mock_profile):
        res = client.get("/api/clients/c1/profile")
    assert res.status_code == 200
    assert res.json() is None


def test_profile_found_source_artifact_ids(client: TestClient) -> None:
    mock_profile = MagicMock()
    mock_profile.get_profile.return_value = DistilledClientProfile(
        client_id="c1",
        risk_tolerance="moderate",
        investment_goals=["retirement"],
        summary="Stable income focus",
        source_artifact_ids=[3, 4],
    )
    with patch("agent_memory.ui.server.DeltaProfileStore", return_value=mock_profile):
        res = client.get("/api/clients/c1/profile")
    body = res.json()
    assert body["risk_tolerance"] == "moderate"
    assert "source_artifact_ids" in body
    assert "source_turn_ids" not in body
    assert body["source_artifact_ids"] == [3, 4]


def test_root_without_ui_build() -> None:
    with (
        patch("agent_memory.ui.server.ensure_databricks_auth", return_value=True),
        patch("agent_memory.ui.server._resolve_static_dir", return_value=None),
        TestClient(create_app()) as test_client,
    ):
        res = test_client.get("/")
    assert res.status_code == 503
    assert "build_frontend" in res.json()["detail"]


def test_profile_warehouse_unavailable(client: TestClient) -> None:
    mock_profile = MagicMock()
    mock_profile.get_profile.side_effect = RuntimeError(
        "No RUNNING SQL warehouse found. Set DATABRICKS_SQL_WAREHOUSE_ID"
    )
    with patch("agent_memory.ui.server.DeltaProfileStore", return_value=mock_profile):
        res = client.get("/api/clients/c1/profile")
    assert res.status_code == 503
