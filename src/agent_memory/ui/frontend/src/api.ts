// ──────────────────────────────────────────────────────────────────────────────
// TypeScript types — mirror interfaces.md §5 EXACTLY.
// `source_turn_ids` is removed everywhere; the dossier model uses `source_artifact_ids`.
// ──────────────────────────────────────────────────────────────────────────────

export type ArtifactKind = "pdf" | "image" | "docx" | "text" | "other";

export type Artifact = {
  artifact_id: number;
  client_id: string;
  advisor_id: string;
  kind: ArtifactKind;
  original_filename: string;
  volume_path: string;
  content_hash: string;
  summary?: string | null;
  extracted_text?: string | null;       // populated on detail route; null on list
  sensitivity_tags: string[];
  contributed_to_profile: boolean;
  ingested_at?: string | null;
};

export type RetrievedChunk = {
  chunk_id: number;
  artifact_id: number;
  chunk_index: number;
  content: string;
  score: number;
  created_at?: string | null;
};

export type ClientProfile = {
  client_id: string;
  risk_tolerance: string;
  investment_goals: string[];
  family_context: string;
  stated_preferences: string;
  summary: string;
  source_artifact_ids: number[];        // renamed from source_turn_ids
  distilled_at?: string | null;
};

// Ingest SSE (ADR-0010) — mirrors IngestStepEvent | IngestDoneEvent | IngestErrorEvent.
export type IngestEvent =
  | {
      type: "step";
      step: "saved" | "extracted" | "embedded" | "summarized" | "proposed";
      artifact_id?: number | null;
      chars?: number | null;
      chunks?: number | null;
      summary?: string | null;
      proposal_id?: string | null;
    }
  | { type: "done"; artifact_id: number; deduped: boolean }
  | { type: "error"; message: string };

// Chat SSE — token-oriented; retrieved_chunks replaces the old retrieved_turns.
export type StreamEvent =
  | { type: "retrieved"; chunks: RetrievedChunk[] }
  | { type: "token"; text: string }
  | {
      type: "done";
      response: string;
      agent_run_id?: string | null;
      retrieved_chunks: RetrievedChunk[];
    }
  | { type: "error"; message: string };

export type Proposal = {
  proposal_id: string;
  client_id: string;
  status: string;
  proposed_at: string;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  risk_tolerance: string;
  investment_goals: string[];
  family_context: string;
  stated_preferences: string;
  summary: string;
  source_artifact_ids: number[];        // renamed from source_turn_ids
};

// Field-level overrides for the Edit-then-Accept flow; omitted fields keep the proposed value.
export type ProposalEdits = {
  risk_tolerance?: string;
  investment_goals?: string[];
  family_context?: string;
  stated_preferences?: string;
  summary?: string;
};

export type ProfileEdits = {
  risk_tolerance: string;
  investment_goals: string[];
  family_context: string;
  stated_preferences: string;
  summary: string;
};

// ──────────────────────────────────────────────────────────────────────────────
// Shared helpers
// ──────────────────────────────────────────────────────────────────────────────

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

/**
 * Internal SSE parser reused by both chat stream and ingest stream.
 * Reads `data: <json>\n\n` frames from `res.body` and calls `onEvent` per frame.
 */
async function parseSSEStream<T>(
  res: Response,
  onEvent: (e: T) => void,
): Promise<void> {
  const reader = res.body?.getReader();
  if (!reader) {
    throw new Error("Streaming not supported by the browser");
  }
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      onEvent(JSON.parse(line.slice(6)) as T);
    }
  }
}

// ──────────────────────────────────────────────────────────────────────────────
// Client / advisor meta
// ──────────────────────────────────────────────────────────────────────────────

export type ClientInfo = { id: string; display_name: string };

export type Health = {
  status: string;
  lakebase_configured: boolean;
  databricks_app: boolean;
  uc_catalog?: string | null;
  uc_schema?: string | null;
  volume_name?: string | null;
  workspace_url?: string | null;
};

export function fetchHealth() {
  return json<Health>("/api/health");
}

export function fetchClients() {
  return json<ClientInfo[]>("/api/clients");
}

export function fetchAdvisors() {
  return json<string[]>("/api/advisors");
}

// ──────────────────────────────────────────────────────────────────────────────
// Artifact dossier (new in dossier model)
// ──────────────────────────────────────────────────────────────────────────────

/** GET /api/clients/{id}/artifacts — timeline, newest first */
export function fetchArtifacts(clientId: string): Promise<Artifact[]> {
  return json<Artifact[]>(`/api/clients/${encodeURIComponent(clientId)}/artifacts`);
}

/** GET /api/artifacts/{id} — detail; includes extracted_text + summary */
export function fetchArtifact(artifactId: number): Promise<Artifact> {
  return json<Artifact>(`/api/artifacts/${artifactId}`);
}

/** /api/artifacts/{id}/raw — raw bytes via UC Volume; returned as a URL for <a href> / download */
export function rawArtifactUrl(artifactId: number): string {
  return `/api/artifacts/${artifactId}/raw`;
}

/**
 * POST /api/clients/{id}/artifacts/ingest — multipart/form-data.
 * Parses the SSE stream (`data: <json>\n\n`) and calls `onEvent` per IngestEvent.
 * Note: Content-Type is NOT set manually so the browser sets the multipart boundary.
 */
export async function ingestArtifact(
  clientId: string,
  file: File,
  advisorId: string,
  onEvent: (e: IngestEvent) => void,
): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  form.append("advisor_id", advisorId);
  const res = await fetch(
    `/api/clients/${encodeURIComponent(clientId)}/artifacts/ingest`,
    { method: "POST", body: form },
  );
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  await parseSSEStream<IngestEvent>(res, onEvent);
}

// ──────────────────────────────────────────────────────────────────────────────
// Distillation
// ──────────────────────────────────────────────────────────────────────────────

export function triggerDistill() {
  return json<{ status: string; run_id?: number | null; message?: string }>(
    "/api/distill",
    { method: "POST" },
  );
}

export type DistillRunStatus = {
  run_id: number;
  life_cycle_state: string;
  result_state: string | null;
  finished: boolean;
};

export function fetchDistillStatus(runId: number) {
  return json<DistillRunStatus>(`/api/distill/${runId}`);
}

// ──────────────────────────────────────────────────────────────────────────────
// Profile
// ──────────────────────────────────────────────────────────────────────────────

export function fetchProfile(clientId: string) {
  return json<ClientProfile | null>(`/api/clients/${encodeURIComponent(clientId)}/profile`);
}

export type ProfileEditsPayload = ProfileEdits & { edited_by: string };

export function saveProfileEdit(clientId: string, editedBy: string, edits: ProfileEdits) {
  return json<{ status: string; client_id: string; delta_version?: number | null }>(
    `/api/clients/${encodeURIComponent(clientId)}/profile`,
    { method: "PUT", body: JSON.stringify({ edited_by: editedBy, ...edits }) },
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// Proposals (HITL review)
// ──────────────────────────────────────────────────────────────────────────────

export function fetchProposals(clientId: string, status = "pending") {
  const q = new URLSearchParams({ status });
  if (clientId) q.set("client_id", clientId);
  return json<Proposal[]>(`/api/proposals?${q}`);
}

export function acceptProposal(
  proposalId: string,
  reviewedBy: string,
  edits?: ProposalEdits,
) {
  return json<{ status: string; proposal_id: string; delta_version?: number | null }>(
    `/api/proposals/${encodeURIComponent(proposalId)}/accept`,
    { method: "POST", body: JSON.stringify({ reviewed_by: reviewedBy, ...edits }) },
  );
}

export function rejectProposal(proposalId: string, reviewedBy: string) {
  return json<{ status: string; proposal_id: string }>(
    `/api/proposals/${encodeURIComponent(proposalId)}/reject`,
    { method: "POST", body: JSON.stringify({ reviewed_by: reviewedBy }) },
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// Chat stream (session_id removed; retrieved_chunks replaces retrieved_turns)
// ──────────────────────────────────────────────────────────────────────────────

export async function sendChatStream(
  body: {
    client_id: string;
    advisor_id: string;
    message: string;
    // NO session_id (dossier model)
  },
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  await parseSSEStream<StreamEvent>(res, onEvent);
}

// ──────────────────────────────────────────────────────────────────────────────
// Managed memory search (NEW — one allowed addition per task brief)
// GET /api/managed-memory/search?client_id=&query=&top_k=
// ──────────────────────────────────────────────────────────────────────────────

export type ManagedMemoryHit = {
  id: string;
  content: string;
  score: number;
  source?: string | null;
};

export type ManagedMemorySearchResult = {
  enabled: boolean;
  hits: ManagedMemoryHit[];
};

export function searchManagedMemory(
  clientId: string,
  query: string,
  topK = 3,
): Promise<ManagedMemorySearchResult> {
  const q = new URLSearchParams({
    client_id: clientId,
    query,
    top_k: String(topK),
  });
  return json<ManagedMemorySearchResult>(`/api/managed-memory/search?${q}`);
}

// ──────────────────────────────────────────────────────────────────────────────
// Utilities
// ──────────────────────────────────────────────────────────────────────────────

export function formatTs(ts: string | null | undefined): string {
  if (!ts) return "";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  const diffMs = Date.now() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr} hr ago`;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}
