"""One-shot seed for Smart Advise on Azure workspace adb-984752964297111.

Populates Lakebase (clients, artifacts, artifact_chunks) + UC Volume raw bytes +
Delta client_profile. Uses real GTE-large embeddings via FMAPI so retrieval works.
Idempotent: safe to re-run (uses content_hash uniqueness + INSERT ... ON CONFLICT).

Requires PATH to have `databricks` and `psql`. Auth: profile adb-984752964297111.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Import personas.py directly (bypassing the package __init__.py which pulls pydantic).
import importlib.util as _iu
_spec = _iu.spec_from_file_location(
    "smart_advise_personas",
    REPO_ROOT / "src" / "agent_memory" / "synthetic" / "personas.py",
)
_mod = _iu.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["smart_advise_personas"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
PERSONAS = _mod.PERSONAS

PROFILE = "adb-984752964297111"
LAKEBASE_INSTANCE = "smart-advise"
PGHOST = "ep-royal-tree-e108d0tb.database.eastus2.azuredatabricks.net"
PGDB = "databricks_postgres"
PGUSER = "michael.egli@databricks.com"
UC_CATALOG = "michael_egli"
UC_SCHEMA = "smart_advise"
VOLUME = "smart_advise_raw"
WAREHOUSE_ID = "148ccb90800933a1"
EMBED_ENDPOINT = "databricks-gte-large-en"


def db_token() -> str:
    r = subprocess.run(
        ["databricks", "database", "generate-database-credential", "-p", PROFILE,
         "--json", json.dumps({"instance_names": [LAKEBASE_INSTANCE]})],
        capture_output=True, text=True, check=True,
    )
    return json.loads(r.stdout)["token"]


def embed(texts: list[str]) -> list[list[float]]:
    """Batch embed via FMAPI GTE-large-en. Returns 1024-d vectors."""
    if not texts:
        return []
    payload = json.dumps({"input": texts})
    r = subprocess.run(
        ["databricks", "serving-endpoints", "query", EMBED_ENDPOINT,
         "-p", PROFILE, "--json", payload],
        capture_output=True, text=True, check=True,
    )
    resp = json.loads(r.stdout)
    return [item["embedding"] for item in resp["data"]]


def sql_exec(pgpass: str, stmts: list[str]) -> None:
    env = os.environ | {
        "PGHOST": PGHOST, "PGDATABASE": PGDB, "PGUSER": PGUSER,
        "PGPASSWORD": pgpass, "PGSSLMODE": "require", "PGPORT": "5432",
    }
    body = "\n".join(stmts)
    r = subprocess.run(["psql", "-v", "ON_ERROR_STOP=1", "-q"],
                       input=body, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        print("SQL FAILED:", r.stderr[-2000:], file=sys.stderr)
        sys.exit(1)


_MKDIR_DONE: set[str] = set()


def upload_volume(client_id: str, artifact_id: int, content: bytes, ext: str) -> str:
    """Upload bytes to /Volumes/.../smart_advise_raw/{client_id}/{artifact_id}.{ext}."""
    vpath = f"/Volumes/{UC_CATALOG}/{UC_SCHEMA}/{VOLUME}/{client_id}/{artifact_id}.{ext}"
    client_dir = f"/Volumes/{UC_CATALOG}/{UC_SCHEMA}/{VOLUME}/{client_id}"
    if client_id not in _MKDIR_DONE:
        subprocess.run(["databricks", "fs", "mkdirs", f"dbfs:{client_dir}", "-p", PROFILE],
                       capture_output=True, text=True)
        _MKDIR_DONE.add(client_id)
    tmp = Path(f"/tmp/seed_{client_id}_{artifact_id}.{ext}")
    tmp.write_bytes(content)
    r = subprocess.run(["databricks", "fs", "cp", "--overwrite", str(tmp),
                        f"dbfs:{vpath}", "-p", PROFILE],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  UPLOAD FAILED: {r.stderr[:500]}", file=sys.stderr)
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"volume upload failed: {vpath}")
    tmp.unlink(missing_ok=True)
    return vpath


def chunk_text(text: str, tokens: int = 200) -> list[str]:
    """Simple sentence-ish chunking; not tokenizer-perfect but fine for demo."""
    words = text.split()
    step = max(30, tokens)
    return [" ".join(words[i:i + step]) for i in range(0, len(words), step)] or [text]


def sql_lit(s: str) -> str:
    """Postgres string literal quoting."""
    return "'" + s.replace("'", "''") + "'"


def sql_array(items: list[str]) -> str:
    return "ARRAY[" + ",".join(sql_lit(x) for x in items) + "]::TEXT[]"


def sql_vec(vec: list[float]) -> str:
    return "'[" + ",".join(f"{x:.6f}" for x in vec) + "]'"


def main() -> None:
    print("Fetching Lakebase token…")
    pgpass = db_token()

    now = datetime.now(timezone.utc)

    for persona in PERSONAS:
        print(f"\n=== {persona.client_id} — {persona.display_name} ===")

        # Client row
        sql_exec(pgpass, [
            f"""INSERT INTO clients (client_id, display_name)
                VALUES ({sql_lit(persona.client_id)}, {sql_lit(persona.display_name)})
                ON CONFLICT (client_id) DO UPDATE SET display_name = EXCLUDED.display_name;"""
        ])

        # Embed all artifact contents in one batch
        contents = [a.content for a in persona.artifacts]
        print(f"  embedding {len(contents)} artifacts…")
        embeddings_top = embed(contents)  # one vector per artifact (top-level summary embed)

        for art, vec in zip(persona.artifacts, embeddings_top):
            ext = {"text": "txt", "handwritten": "png", "pdf": "pdf", "scan": "jpg"}[art.fmt]
            kind = {"text": "text", "handwritten": "image", "pdf": "pdf", "scan": "image"}[art.fmt]
            # Binary artifacts (pdf/handwritten/scan) — use pre-rendered fixtures so downloaded
            # files are real (openable in Preview). Text artifacts encode the plain content.
            if art.fmt == "text":
                body_bytes = art.content.encode("utf-8")
            else:
                fixture = REPO_ROOT / "data" / "synthetic" / "fixtures" / persona.client_id / art.filename(persona.client_id)
                if not fixture.exists():
                    print(f"  ! missing fixture, falling back to text bytes: {fixture}", file=sys.stderr)
                    body_bytes = art.content.encode("utf-8")
                else:
                    body_bytes = fixture.read_bytes()
            content_hash = hashlib.sha256(body_bytes).hexdigest()
            ingested_at = now - timedelta(days=art.days_ago)

            # Insert artifact and get artifact_id
            r = subprocess.run(
                ["psql", "-v", "ON_ERROR_STOP=1", "-t", "-A", "-c", f"""
INSERT INTO artifacts (client_id, advisor_id, kind, original_filename, volume_path,
                       content_hash, extracted_text, summary, sensitivity_tags, ingested_at)
VALUES ({sql_lit(persona.client_id)},
        {sql_lit('advisor_demo_01')},
        {sql_lit(kind)},
        {sql_lit(art.filename(persona.client_id))},
        '__PENDING__',
        {sql_lit(content_hash)},
        {sql_lit(art.content)},
        {sql_lit(art.content[:280])},
        {sql_array([art.category, art.fmt])},
        {sql_lit(ingested_at.isoformat())})
ON CONFLICT (client_id, content_hash) DO UPDATE
  SET summary = EXCLUDED.summary, extracted_text = EXCLUDED.extracted_text
RETURNING artifact_id;
"""],
                env=os.environ | {"PGHOST": PGHOST, "PGDATABASE": PGDB, "PGUSER": PGUSER,
                                  "PGPASSWORD": pgpass, "PGSSLMODE": "require", "PGPORT": "5432"},
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                print("INSERT artifact FAILED:", r.stderr[-1000:])
                sys.exit(1)
            # -t -A prints RETURNING then a status line like "INSERT 0 1"; take first int line
            first_line = r.stdout.strip().splitlines()[0].strip()
            artifact_id = int(first_line)

            # Upload to volume, then update the row with the real path
            volume_path = upload_volume(persona.client_id, artifact_id, body_bytes, ext)
            sql_exec(pgpass, [
                f"UPDATE artifacts SET volume_path = {sql_lit(volume_path)} WHERE artifact_id = {artifact_id};"
            ])

            # Chunk + embed chunks
            chunks = chunk_text(art.content, tokens=200)
            chunk_embeds = embed(chunks) if len(chunks) > 1 else [vec]
            for idx, (ctxt, cvec) in enumerate(zip(chunks, chunk_embeds)):
                sql_exec(pgpass, [f"""
INSERT INTO artifact_chunks (artifact_id, client_id, chunk_index, content, embedding)
VALUES ({artifact_id}, {sql_lit(persona.client_id)}, {idx}, {sql_lit(ctxt)}, {sql_vec(cvec)});
"""])
            print(f"  · artifact_id={artifact_id} chunks={len(chunks)} slug={art.slug}")

    # One Delta client_profile row for the first persona so the profile panel isn't empty.
    p = PERSONAS[0]
    profile_stmt = f"""
INSERT INTO {UC_CATALOG}.{UC_SCHEMA}.client_profile
  (client_id, risk_tolerance, investment_goals, family_context, stated_preferences,
   summary, source_artifact_ids, distilled_at, updated_at)
VALUES
  ('{p.client_id}', 'conservative',
   ARRAY('retirement at 62', 'tax-efficient growth', 'ESG alignment'),
   'Single professional; supports younger sibling.',
   'Prefers ESG-aligned funds; wary of concentrated single-stock positions.',
   'Long-time client with a conservative-leaning profile centered on retirement funding and ESG-aligned diversification.',
   ARRAY(1L, 2L, 3L),
   current_timestamp(), current_timestamp())
"""
    r = subprocess.run(
        ["databricks", "api", "post", "/api/2.0/sql/statements", "-p", PROFILE,
         "--json", json.dumps({"statement": profile_stmt, "warehouse_id": WAREHOUSE_ID,
                                "wait_timeout": "30s"})],
        capture_output=True, text=True, check=True,
    )
    d = json.loads(r.stdout)
    state = d.get("status", {}).get("state")
    print(f"\nDelta client_profile insert: {state}")
    if state == "FAILED":
        print("  err:", d.get("status", {}).get("error", {}).get("message"))

    print("\n=== Row counts ===")
    for tbl in ("clients", "artifacts", "artifact_chunks"):
        r = subprocess.run(
            ["psql", "-t", "-A", "-c", f"SELECT COUNT(*) FROM {tbl};"],
            env=os.environ | {"PGHOST": PGHOST, "PGDATABASE": PGDB, "PGUSER": PGUSER,
                              "PGPASSWORD": pgpass, "PGSSLMODE": "require", "PGPORT": "5432"},
            capture_output=True, text=True,
        )
        print(f"  {tbl}: {r.stdout.strip()}")


if __name__ == "__main__":
    main()
