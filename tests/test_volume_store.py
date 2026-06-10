"""Tests for memory/volume_store.py — NEW module (D2, ADR-0013).

Contract source: interfaces.md §3 (volume_store.py functions).
WorkspaceClient calls are monkeypatched; tests run offline.
"""

from __future__ import annotations

import hashlib
import io
from unittest.mock import MagicMock

from agent_memory.memory.volume_store import (
    build_volume_path,
    content_hash,
    download_raw,
    ext_for,
    upload_raw,
)

# ---------------------------------------------------------------------------
# content_hash — stable SHA-256 (contract test + property)
# ---------------------------------------------------------------------------

def test_content_hash_returns_hex_string():
    h = content_hash(b"hello")
    assert isinstance(h, str)
    assert len(h) == 64  # SHA-256 hex = 64 chars
    assert all(c in "0123456789abcdef" for c in h)


def test_content_hash_matches_hashlib():
    raw = b"test bytes for hashing"
    expected = hashlib.sha256(raw).hexdigest()
    assert content_hash(raw) == expected


def test_content_hash_stable_same_input():
    raw = b"deterministic"
    assert content_hash(raw) == content_hash(raw)


def test_content_hash_different_inputs_differ():
    assert content_hash(b"aaa") != content_hash(b"bbb")


def test_content_hash_empty_bytes():
    h = content_hash(b"")
    expected = hashlib.sha256(b"").hexdigest()
    assert h == expected


def test_content_hash_large_bytes():
    raw = b"x" * 10_000_000
    h = content_hash(raw)
    assert len(h) == 64


# ---------------------------------------------------------------------------
# build_volume_path — format contract
# ---------------------------------------------------------------------------

def _settings(catalog: str = "mycat", schema: str = "myschema", volume_name: str = "dossier_raw"):
    from agent_memory.config import Settings

    return Settings(
        databricks_host="https://host.databricks.com",
        databricks_token="tok",
        databricks_profile=None,
        fm_api_endpoint="x",
        fm_api_embedding_endpoint="y",
        mlflow_experiment_name="/test",
        uc_catalog=catalog,
        uc_schema=schema,
        lakebase_database=None,
        lakebase_conninfo=None,
        databricks_client_id=None,
        databricks_client_secret=None,
        volume_name=volume_name,
    )


def test_build_volume_path_format():
    """/Volumes/{catalog}/{schema}/{volume_name}/{client_id}/{artifact_id}.{ext}"""
    s = _settings(catalog="agent_memory_dev", schema="wealth_advisor", volume_name="dossier_raw")
    path = build_volume_path(
        client_id="client_0000",
        artifact_id=42,
        ext="pdf",
        settings=s,
    )
    assert path == "/Volumes/agent_memory_dev/wealth_advisor/dossier_raw/client_0000/42.pdf"


def test_build_volume_path_different_catalog():
    s = _settings(catalog="prod", schema="fin", volume_name="dossier_raw")
    path = build_volume_path(client_id="c1", artifact_id=7, ext="txt", settings=s)
    assert path.startswith("/Volumes/prod/fin/dossier_raw/")
    assert path.endswith("/7.txt")


def test_build_volume_path_client_id_in_path():
    s = _settings()
    path = build_volume_path(client_id="client_0123", artifact_id=1, ext="docx", settings=s)
    assert "client_0123" in path


def test_build_volume_path_artifact_id_in_path():
    s = _settings()
    path = build_volume_path(client_id="c0", artifact_id=999, ext="pdf", settings=s)
    assert "999" in path
    assert path.endswith("999.pdf")


def test_build_volume_path_ext_without_dot():
    """ext parameter must NOT include a leading dot."""
    s = _settings()
    path = build_volume_path(client_id="c0", artifact_id=1, ext="pdf", settings=s)
    # Should not have double dot
    assert ".." not in path


def test_build_volume_path_uses_volume_name_from_settings():
    s = _settings(volume_name="custom_volume")
    path = build_volume_path(client_id="c0", artifact_id=1, ext="txt", settings=s)
    assert "custom_volume" in path


# ---------------------------------------------------------------------------
# ext_for — kind/filename mapping
# ---------------------------------------------------------------------------

def test_ext_for_kind_pdf():
    assert ext_for(kind="pdf", original_filename="report.pdf") == "pdf"


def test_ext_for_kind_text():
    assert ext_for(kind="text", original_filename="note.txt") == "txt"


def test_ext_for_kind_docx():
    assert ext_for(kind="docx", original_filename="doc.docx") in ("docx", "doc")


def test_ext_for_kind_image_png():
    assert ext_for(kind="image", original_filename="scan.png") == "png"


def test_ext_for_kind_image_jpg():
    assert ext_for(kind="image", original_filename="scan.jpg") == "jpg"


def test_ext_for_kind_image_jpeg():
    assert ext_for(kind="image", original_filename="scan.jpeg") == "jpeg"


def test_ext_for_kind_image_tiff():
    assert ext_for(kind="image", original_filename="scan.tiff") in ("tiff", "tif")


def test_ext_for_kind_other_falls_back_to_filename():
    ext = ext_for(kind="other", original_filename="file.xyz")
    assert ext == "xyz"


def test_ext_for_returns_lowercase():
    ext = ext_for(kind="pdf", original_filename="REPORT.PDF")
    assert ext == ext.lower()


def test_ext_for_no_extension_filename():
    """filename without extension must not raise; falls back gracefully."""
    ext = ext_for(kind="text", original_filename="notextfile")
    assert isinstance(ext, str)


# ---------------------------------------------------------------------------
# upload_raw — WorkspaceClient.files.upload called correctly
# ---------------------------------------------------------------------------

def test_upload_raw_calls_wc_files_upload(monkeypatch):
    mock_wc = MagicMock()
    monkeypatch.setattr(
        "agent_memory.memory.volume_store.get_workspace_client",
        lambda _settings: mock_wc,
    )

    s = _settings()
    upload_raw(volume_path="/Volumes/cat/sch/vol/c0/1.pdf", raw_bytes=b"pdf data", settings=s)

    mock_wc.files.upload.assert_called_once()
    call_args = mock_wc.files.upload.call_args
    # First positional arg must be the volume_path
    assert call_args.args[0] == "/Volumes/cat/sch/vol/c0/1.pdf" or (
        call_args.kwargs.get("file_path") == "/Volumes/cat/sch/vol/c0/1.pdf"
    )


def test_upload_raw_passes_bytesio(monkeypatch):
    mock_wc = MagicMock()
    monkeypatch.setattr(
        "agent_memory.memory.volume_store.get_workspace_client",
        lambda _settings: mock_wc,
    )

    s = _settings()
    upload_raw(volume_path="/vol/c0/1.txt", raw_bytes=b"hello", settings=s)

    call_args = mock_wc.files.upload.call_args
    # The second arg must be a file-like object (BytesIO)
    positional = call_args.args
    keyword = call_args.kwargs
    content_arg = positional[1] if len(positional) > 1 else keyword.get("contents")
    assert hasattr(content_arg, "read")


def test_upload_raw_overwrite_is_false(monkeypatch):
    """Uploads must be immutable — overwrite=False (ADR-0013)."""
    mock_wc = MagicMock()
    monkeypatch.setattr(
        "agent_memory.memory.volume_store.get_workspace_client",
        lambda _settings: mock_wc,
    )

    s = _settings()
    upload_raw(volume_path="/vol/c0/1.pdf", raw_bytes=b"data", settings=s)

    call_kwargs = mock_wc.files.upload.call_args.kwargs
    # overwrite must be False (default) or explicitly False
    overwrite = call_kwargs.get("overwrite", False)
    assert overwrite is False


# ---------------------------------------------------------------------------
# download_raw — WorkspaceClient.files.download called correctly
# ---------------------------------------------------------------------------

def test_download_raw_calls_wc_files_download(monkeypatch):
    fake_content = io.BytesIO(b"raw bytes")
    mock_wc = MagicMock()
    mock_wc.files.download.return_value = MagicMock(contents=fake_content)
    monkeypatch.setattr(
        "agent_memory.memory.volume_store.get_workspace_client",
        lambda _settings: mock_wc,
    )

    s = _settings()
    download_raw(volume_path="/Volumes/cat/sch/vol/c0/1.pdf", settings=s)

    mock_wc.files.download.assert_called_once()
    call_args = mock_wc.files.download.call_args
    path_arg = call_args.args[0] if call_args.args else call_args.kwargs.get("file_path") or call_args.kwargs.get("path")
    assert path_arg == "/Volumes/cat/sch/vol/c0/1.pdf"


def test_download_raw_returns_binary_io(monkeypatch):
    fake_content = io.BytesIO(b"raw bytes")
    mock_wc = MagicMock()
    mock_wc.files.download.return_value = MagicMock(contents=fake_content)
    monkeypatch.setattr(
        "agent_memory.memory.volume_store.get_workspace_client",
        lambda _settings: mock_wc,
    )

    s = _settings()
    result = download_raw(volume_path="/vol/c0/1.pdf", settings=s)

    assert hasattr(result, "read")
    assert result.read() == b"raw bytes"
