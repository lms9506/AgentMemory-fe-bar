-- Lakebase (Postgres) schema for live agent memory — dossier model (D1).
-- See docs/architecture.md for the full design.

CREATE EXTENSION IF NOT EXISTS vector;

-- Dossier model supersedes the turn/session model.
DROP TABLE IF EXISTS turn_embeddings CASCADE;
DROP TABLE IF EXISTS conversation_turns CASCADE;

-- Episodic memory — append-only dossier of dated artifacts.
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id      BIGSERIAL    PRIMARY KEY,
    client_id        TEXT         NOT NULL,
    advisor_id       TEXT         NOT NULL,
    kind             TEXT         NOT NULL CHECK (kind IN ('pdf','image','docx','text','other')),
    original_filename TEXT        NOT NULL,
    volume_path      TEXT         NOT NULL,
    content_hash     TEXT         NOT NULL,        -- SHA-256 hex; dedup key
    extracted_text   TEXT,
    summary          TEXT,
    sensitivity_tags TEXT[]       NOT NULL DEFAULT '{}',
    ingested_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_artifacts_hash   ON artifacts (client_id, content_hash);
CREATE INDEX        IF NOT EXISTS idx_artifacts_client ON artifacts (client_id, ingested_at DESC);

-- Semantic memory — chunk embeddings for similarity recall.
CREATE TABLE IF NOT EXISTS artifact_chunks (
    chunk_id    BIGSERIAL    PRIMARY KEY,
    artifact_id BIGINT       NOT NULL REFERENCES artifacts(artifact_id) ON DELETE CASCADE,
    client_id   TEXT         NOT NULL,
    chunk_index INT          NOT NULL,
    content     TEXT         NOT NULL,
    embedding   VECTOR(1024) NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chunks_artifact ON artifact_chunks (artifact_id);
CREATE INDEX IF NOT EXISTS idx_chunks_client   ON artifact_chunks (client_id);
CREATE INDEX IF NOT EXISTS idx_chunks_ann      ON artifact_chunks
    USING hnsw (embedding vector_cosine_ops);

-- Audit log — UNCHANGED in shape (append-only). Carries over verbatim.
CREATE TABLE IF NOT EXISTS audit_log (
    event_id    BIGSERIAL PRIMARY KEY,
    actor       TEXT      NOT NULL,
    actor_kind  TEXT      NOT NULL CHECK (actor_kind IN ('agent', 'advisor', 'job')),
    action      TEXT      NOT NULL,
    target_ref  TEXT      NOT NULL,
    payload     JSONB     NOT NULL,
    agent_run_id TEXT,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_log (target_ref, ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor  ON audit_log (actor, ts DESC);

-- Append-only protection on audit_log: no UPDATE / DELETE in app code.
-- (Permissions enforced at the role level — see DAB setup.)

-- Profile proposals — column renamed source_turn_ids -> source_artifact_ids (type unchanged).
CREATE TABLE IF NOT EXISTS profile_proposals (
    proposal_id  TEXT        PRIMARY KEY,
    client_id    TEXT        NOT NULL,
    proposed_profile JSONB   NOT NULL,
    source_artifact_ids BIGINT[] NOT NULL DEFAULT '{}',
    status       TEXT        NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending', 'accepted', 'rejected', 'superseded')),
    proposed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at  TIMESTAMPTZ,
    reviewed_by  TEXT,
    run_id       TEXT
);
CREATE INDEX IF NOT EXISTS idx_proposals_client_status ON profile_proposals (client_id, status);

-- Client registry — UNCHANGED.
CREATE TABLE IF NOT EXISTS clients (
    client_id    TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
