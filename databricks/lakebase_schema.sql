-- Lakebase (Postgres) schema for live agent memory.
-- See docs/architecture.md §1 for the full design.

CREATE EXTENSION IF NOT EXISTS vector;

-- Episodic memory — append-only conversation log.
CREATE TABLE IF NOT EXISTS conversation_turns (
    turn_id      BIGSERIAL PRIMARY KEY,
    client_id    TEXT      NOT NULL,
    advisor_id   TEXT      NOT NULL,
    session_id   TEXT      NOT NULL,
    turn_index   INT       NOT NULL,
    role         TEXT      NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content      TEXT      NOT NULL,
    source       TEXT      NOT NULL DEFAULT 'agent' CHECK (source IN ('agent', 'human')),
    ts           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_turns_client_ts ON conversation_turns (client_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_turns_session   ON conversation_turns (session_id, turn_index);

-- Semantic memory — embeddings for similarity recall.
CREATE TABLE IF NOT EXISTS turn_embeddings (
    turn_id     BIGINT PRIMARY KEY REFERENCES conversation_turns(turn_id) ON DELETE CASCADE,
    client_id   TEXT   NOT NULL,
    embedding   VECTOR(1024) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_turn_emb_client ON turn_embeddings (client_id);
CREATE INDEX IF NOT EXISTS idx_turn_emb_ann    ON turn_embeddings USING hnsw (embedding vector_cosine_ops);

-- Audit log — every memory-write event, including HITL edits.
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
