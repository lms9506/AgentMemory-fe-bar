"""Smoke tests for the Lakebase hydration job (ADR-0019).

Exercises `hydrate()` with the store, embeddings, and warehouse fetch mocked, so
it runs offline. Verifies: dedup skip, per-client upsert, chunk/embed/write, and a
job-attributed audit row per new artifact.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent_memory.jobs import hydrate_entry


class _FakeStore:
    def __init__(self, existing_hashes=()):
        self.existing = set(existing_hashes)
        self.clients: list[tuple[str, str]] = []
        self.ingested: list[dict] = []
        self.audits: list[dict] = []
        self.chunk_calls: list[dict] = []
        self._next_id = 100

    def upsert_client(self, client_id, display_name):
        self.clients.append((client_id, display_name))

    def find_by_hash(self, *, client_id, content_hash):
        return object() if content_hash in self.existing else None

    def ingest_artifact(self, **kw):
        self._next_id += 1
        self.ingested.append(kw)
        return SimpleNamespace(artifact_id=self._next_id)

    def write_chunks(self, *, artifact_id, client_id, chunks, embeddings):
        self.chunk_calls.append({"artifact_id": artifact_id, "n": len(chunks)})
        return len(chunks)

    def write_audit(self, **kw):
        self.audits.append(kw)


_SILVER_ROWS = [
    ["client_1000", "note.txt", "text", "hashA", "/Volumes/x/_landing/client_1000/note.txt", "some text here", "a summary"],
    ["client_1000", "stmt.pdf", "pdf", "hashB", "/Volumes/x/_landing/client_1000/stmt.pdf", "more text", "b summary"],
    ["client_0000", "scan.jpg", "image", "hashC", "/Volumes/x/_landing/client_0000/scan.jpg", "ocr text", "c summary"],
]


@pytest.fixture
def _patched(monkeypatch):
    store = _FakeStore()
    monkeypatch.setattr(hydrate_entry, "establish_runtime_auth", lambda cfg: None)
    monkeypatch.setattr(hydrate_entry, "LakebaseArtifactStore", lambda: store)
    monkeypatch.setattr(hydrate_entry, "fetch_sql", lambda sql, settings=None: list(_SILVER_ROWS))
    monkeypatch.setattr(hydrate_entry, "embed_texts", lambda chunks, settings=None: [[0.0] * 8 for _ in chunks])
    return store


def _settings():
    return SimpleNamespace(
        uc_catalog="cat", uc_schema="sch", chunk_tokens=512, chunk_overlap_tokens=50,
        auth_diagnostics=lambda: "",
    )


def test_hydrate_ingests_all_new_rows(_patched):
    counts = hydrate_entry.hydrate(settings=_settings())
    assert counts["seen"] == 3
    assert counts["ingested"] == 3
    assert counts["deduped"] == 0
    # Two distinct clients registered exactly once each.
    assert {c[0] for c in _patched.clients} == {"client_1000", "client_0000"}
    assert len(_patched.clients) == 2
    # One job-attributed audit row per ingested artifact.
    assert len(_patched.audits) == 3
    assert all(a["actor_kind"] == "job" for a in _patched.audits)
    assert all(a["action"] == "bulk_onboard_artifact" for a in _patched.audits)


def test_hydrate_skips_deduped(monkeypatch):
    store = _FakeStore(existing_hashes={"hashB"})
    monkeypatch.setattr(hydrate_entry, "establish_runtime_auth", lambda cfg: None)
    monkeypatch.setattr(hydrate_entry, "LakebaseArtifactStore", lambda: store)
    monkeypatch.setattr(hydrate_entry, "fetch_sql", lambda sql, settings=None: list(_SILVER_ROWS))
    monkeypatch.setattr(hydrate_entry, "embed_texts", lambda chunks, settings=None: [[0.0] * 8 for _ in chunks])

    counts = hydrate_entry.hydrate(settings=_settings())
    assert counts["deduped"] == 1
    assert counts["ingested"] == 2
    assert len(store.ingested) == 2


def test_hydrate_display_name_is_prettified():
    assert hydrate_entry._pretty_display_name("client_1000") == "Client 1000"
    assert hydrate_entry._pretty_display_name("client_0000") == "Client 0000"
