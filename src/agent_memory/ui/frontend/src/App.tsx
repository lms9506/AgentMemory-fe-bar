import {
  DragEvent,
  Fragment,
  FormEvent,
  KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import ReactMarkdown from "react-markdown";
import {
  Artifact,
  ClientInfo,
  ClientProfile,
  Health,
  IngestEvent,
  Proposal,
  ProposalEdits,
  ProfileEdits,
  RetrievedChunk,
  acceptProposal,
  fetchAdvisors,
  fetchArtifact,
  fetchArtifacts,
  fetchClients,
  fetchHealth,
  fetchProfile,
  fetchDistillStatus,
  fetchProposals,
  formatTs,
  ingestArtifact,
  rawArtifactUrl,
  rejectProposal,
  saveProfileEdit,
  sendChatStream,
  triggerDistill,
} from "./api";

const DEFAULT_ADVISOR = "advisor_demo_01";

// Per-kind glyph for the dossier timeline (kept as emoji to avoid an icon dep).
const KIND_ICON: Record<string, string> = {
  text: "📝",
  pdf: "📄",
  image: "🖼️",
  docx: "📃",
  other: "📎",
};

// The ordered steps in an ingest pipeline run.
const INGEST_STEPS = ["saved", "extracted", "embedded", "summarized", "proposed"] as const;
type IngestStep = (typeof INGEST_STEPS)[number];

type IngestProgress =
  | { phase: "idle" }
  | { phase: "running"; completedSteps: Set<IngestStep>; currentStep: IngestStep | null; detail: string | null }
  | { phase: "done"; artifactId: number; deduped: boolean }
  | { phase: "error"; message: string };

export default function App() {
  const [clientId, setClientId] = useState("");
  const [advisorId, setAdvisorId] = useState(DEFAULT_ADVISOR);
  const [clients, setClients] = useState<ClientInfo[]>([]);
  const [advisors, setAdvisors] = useState<string[]>([]);
  const [distilling, setDistilling] = useState(false);
  const [distillMsg, setDistillMsg] = useState<string | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [ingestProgress, setIngestProgress] = useState<IngestProgress>({ phase: "idle" });
  const [dragOver, setDragOver] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [storage, setStorage] = useState<Health | null>(null);
  const [provenanceArtifact, setProvenanceArtifact] = useState<Artifact | null>(null);
  const [provenanceLoading, setProvenanceLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [retrieved, setRetrieved] = useState<RetrievedChunk[]>([]);
  const [profile, setProfile] = useState<ClientProfile | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [editingProfile, setEditingProfile] = useState(false);
  const [chatMessages, setChatMessages] = useState<Array<{ role: "user" | "assistant"; text: string }>>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [streamingReply, setStreamingReply] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load client and advisor lists once on mount
  useEffect(() => {
    fetchClients()
      .then((cs) => {
        setClients(cs);
        if (cs.length > 0 && !clientId) setClientId(cs[0].id);
      })
      .catch(() => {});
    fetchAdvisors()
      .then((as) => {
        setAdvisors(as);
        if (as.length > 0 && !as.includes(DEFAULT_ADVISOR)) setAdvisorId(as[0]);
      })
      .catch(() => {});
    fetchHealth().then(setStorage).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const refreshContext = useCallback(async () => {
    if (!clientId) return;
    setError(null);
    try {
      // Profile + proposals are best-effort: the distilled profile is read from
      // Delta via a SQL warehouse, so a warehouse hiccup must not blank the whole
      // dossier (timeline + retrieval come from Lakebase and always load).
      const [arts, prof, props] = await Promise.all([
        fetchArtifacts(clientId),
        fetchProfile(clientId).catch(() => null),
        fetchProposals(clientId).catch(() => [] as Proposal[]),
      ]);
      setArtifacts(arts);
      setProfile(prof);
      setProposals(props);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [clientId]);

  useEffect(() => {
    void refreshContext();
  }, [refreshContext]);

  function handleClientChange(newClient: string) {
    setClientId(newClient);
    setArtifacts([]);
    setRetrieved([]);
    setProfile(null);
    setProposals([]);
    setEditingProfile(false);
    setChatMessages([]);
    setStreamingReply(null);
    setIngestProgress({ phase: "idle" });
    setProvenanceArtifact(null);
  }

  function handleAdvisorChange(newAdvisor: string) {
    setAdvisorId(newAdvisor);
    setRetrieved([]);
    setStreamingReply(null);
  }

  // ─── Ingest ─────────────────────────────────────────────────────────────────

  async function runIngest(file: File) {
    if (!clientId) return;
    setIngestProgress({
      phase: "running",
      completedSteps: new Set(),
      currentStep: "saved",
      detail: null,
    });
    setError(null);
    try {
      await ingestArtifact(clientId, file, advisorId, (e: IngestEvent) => {
        if (e.type === "step") {
          setIngestProgress((prev) => {
            if (prev.phase !== "running") return prev;
            const completedSteps = new Set(prev.completedSteps);
            completedSteps.add(e.step);
            // Determine next expected step
            const idx = INGEST_STEPS.indexOf(e.step);
            const nextStep =
              idx >= 0 && idx < INGEST_STEPS.length - 1
                ? INGEST_STEPS[idx + 1]
                : null;
            // Capture human-readable detail for this step
            let detail: string | null = null;
            if (e.step === "extracted" && e.chars != null)
              detail = `${e.chars.toLocaleString()} chars extracted`;
            if (e.step === "embedded" && e.chunks != null)
              detail = `${e.chunks} chunks embedded`;
            if (e.step === "summarized" && e.summary)
              detail = e.summary.slice(0, 120) + (e.summary.length > 120 ? "…" : "");
            if (e.step === "proposed" && e.proposal_id)
              detail = `Proposal ${e.proposal_id.slice(0, 8)}…`;
            return { phase: "running", completedSteps, currentStep: nextStep, detail };
          });
        } else if (e.type === "done") {
          setIngestProgress({ phase: "done", artifactId: e.artifact_id, deduped: e.deduped });
          void refreshContext();
        } else if (e.type === "error") {
          setIngestProgress({ phase: "error", message: e.message });
        }
      });
    } catch (err) {
      setIngestProgress({
        phase: "error",
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }

  function handleFileDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) void runIngest(file);
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) void runIngest(file);
    // Reset so the same file can be re-uploaded if needed
    e.target.value = "";
  }

  // A typed note is just a text artifact — wrap it as a .txt File and run it
  // through the same ingest pipeline (kind='text' skips ai_parse_document).
  function runIngestText() {
    const text = noteText.trim();
    if (!clientId || !text) return;
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const file = new File([text], `typed_note_${stamp}.txt`, { type: "text/plain" });
    void runIngest(file);
    setNoteText("");
  }

  // ─── Provenance ─────────────────────────────────────────────────────────────

  async function loadProvenance(artifactId: number) {
    setProvenanceLoading(true);
    setProvenanceArtifact(null);
    try {
      const art = await fetchArtifact(artifactId);
      setProvenanceArtifact(art);
    } catch {
      // Non-fatal; surface nothing rather than crashing the profile panel
    } finally {
      setProvenanceLoading(false);
    }
  }

  // ─── Chat ────────────────────────────────────────────────────────────────────

  async function onChat(e: FormEvent) {
    e.preventDefault();
    if (!message.trim() || !clientId) return;
    const userText = message.trim();
    setBusy(true);
    setStreamingReply("");
    setError(null);
    setMessage("");
    setChatMessages((prev) => [...prev, { role: "user", text: userText }]);
    try {
      let finalResponse = "";
      await sendChatStream(
        { client_id: clientId, advisor_id: advisorId, message: userText },
        (event) => {
          if (event.type === "retrieved") {
            setRetrieved(event.chunks);
          } else if (event.type === "token") {
            setStreamingReply((prev) => (prev ?? "") + event.text);
            finalResponse += event.text;
          } else if (event.type === "done") {
            setRetrieved(event.retrieved_chunks);
            finalResponse = event.response;
            setStreamingReply(event.response);
          } else if (event.type === "error") {
            setError(event.message);
          }
        },
      );
      setChatMessages((prev) => [...prev, { role: "assistant", text: finalResponse }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
      setStreamingReply(null);
    }
  }

  // ─── Proposals ───────────────────────────────────────────────────────────────

  async function onProposalAccept(proposalId: string, edits?: ProposalEdits) {
    setBusy(true);
    setError(null);
    try {
      await acceptProposal(proposalId, advisorId, edits);
      // The accepted profile IS the proposal (plus any edits), so reflect it
      // immediately rather than re-reading it back through the Delta/SQL-warehouse
      // path — that round-trip is slow and is what made the panel need a refresh.
      const p = proposals.find((x) => x.proposal_id === proposalId);
      if (p) {
        setProfile({
          client_id: p.client_id,
          risk_tolerance: edits?.risk_tolerance ?? p.risk_tolerance,
          investment_goals: edits?.investment_goals ?? p.investment_goals,
          family_context: edits?.family_context ?? p.family_context,
          stated_preferences: edits?.stated_preferences ?? p.stated_preferences,
          summary: edits?.summary ?? p.summary,
          source_artifact_ids: p.source_artifact_ids,
          distilled_at: new Date().toISOString(),
        });
      }
      setProposals((prev) => prev.filter((x) => x.proposal_id !== proposalId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onProposalReject(proposalId: string) {
    setBusy(true);
    setError(null);
    try {
      await rejectProposal(proposalId, advisorId);
      // Reject doesn't touch the profile — just drop it from the pending list
      // (no slow Delta/warehouse re-read needed).
      setProposals((prev) => prev.filter((x) => x.proposal_id !== proposalId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  // ─── Manual profile edit ─────────────────────────────────────────────────────

  async function onProfileSave(edits: ProfileEdits) {
    if (!clientId) return;
    setBusy(true);
    setError(null);
    try {
      await saveProfileEdit(clientId, advisorId, edits);
      setEditingProfile(false);
      await refreshContext();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  // ─── Distillation trigger ────────────────────────────────────────────────────

  async function onTriggerDistill() {
    if (!clientId) return;
    setDistilling(true);
    setDistillMsg(null);
    const beforeIds = new Set(proposals.map((p) => p.proposal_id));
    try {
      const res = await triggerDistill();
      if (res.status !== "triggered") {
        setDistillMsg(`Error: ${res.message}`);
        return;
      }
      const runId = res.run_id ?? null;
      for (let attempt = 0; attempt < 40; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        const latest = await fetchProposals(clientId).catch(() => [] as Proposal[]);
        if (latest.some((p) => !beforeIds.has(p.proposal_id))) {
          setProposals(latest);
          return;
        }
        if (runId !== null) {
          const run = await fetchDistillStatus(runId).catch(() => null);
          if (run?.finished) {
            setDistillMsg(
              "No new artifacts since the last proposal — nothing to distill for this client.",
            );
            return;
          }
        }
      }
      setDistillMsg("Distillation is taking longer than usual — it'll appear shortly.");
    } catch (e) {
      setDistillMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setDistilling(false);
    }
  }

  // ─── Render ──────────────────────────────────────────────────────────────────

  return (
    <>
      <header className="app-header">
        <h1>AI Wealth Advisor — Client Dossier</h1>
        <p>
          Dossier timeline, retrieval inspector, distilled profile, proposal review — considerations
          only, not financial advice.
        </p>
      </header>

      <div className="context-bar">
        <label>
          Client
          <select
            value={clientId}
            onChange={(e) => handleClientChange(e.target.value)}
            aria-label="Client ID"
            className="context-select"
            disabled={clients.length === 0}
          >
            {clients.length === 0 ? (
              <option value="">Loading…</option>
            ) : (
              clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.display_name}
                </option>
              ))
            )}
          </select>
        </label>

        <label>
          Advisor
          <select
            value={advisorId}
            onChange={(e) => handleAdvisorChange(e.target.value)}
            aria-label="Advisor ID"
            className="context-select"
          >
            {advisors.length === 0 ? (
              <option value={DEFAULT_ADVISOR}>{DEFAULT_ADVISOR}</option>
            ) : (
              advisors.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))
            )}
          </select>
        </label>
      </div>

      {error && <p className="error error-bar">{error}</p>}

      <div className="panels">
        {/* ── Panel 1: Dossier timeline + upload ────────────────────────────── */}
        <section className="panel span-2">
          <h2>Dossier timeline</h2>
          <div className="panel-body">
            {/* Drag-and-drop upload box with click fallback */}
            <div
              className={`upload-zone${dragOver ? " drag-over" : ""}${!clientId ? " disabled" : ""}`}
              role="button"
              aria-label="Upload dossier artifact — drag a file here or click to select"
              tabIndex={clientId ? 0 : -1}
              onDragOver={(e) => { e.preventDefault(); if (clientId) setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={clientId ? handleFileDrop : undefined}
              onClick={() => { if (clientId) fileInputRef.current?.click(); }}
              onKeyDown={(e) => {
                if (clientId && (e.key === "Enter" || e.key === " ")) {
                  e.preventDefault();
                  fileInputRef.current?.click();
                }
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif,.docx,.doc,.txt"
                aria-label="Select file to ingest"
                style={{ display: "none" }}
                onChange={handleFileSelect}
                disabled={!clientId}
              />
              {clientId ? (
                <span>Drop a file here, or click to select (PDF, image, DOCX, text)</span>
              ) : (
                <span>Select a client to upload artifacts</span>
              )}
            </div>

            {/* Type a note directly — ingested as a text artifact */}
            <div className="note-entry">
              <textarea
                className="note-input"
                rows={3}
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                disabled={!clientId || ingestProgress.phase === "running"}
                aria-label="Type a note to add to the dossier"
                placeholder={
                  clientId
                    ? "…or type a note (meeting takeaway, idea) to add to the dossier"
                    : "Select a client to add a note"
                }
              />
              <button
                type="button"
                className="secondary"
                onClick={runIngestText}
                disabled={!clientId || !noteText.trim() || ingestProgress.phase === "running"}
              >
                Add note
              </button>
            </div>

            {/* SSE ingest progress */}
            {ingestProgress.phase !== "idle" && (
              <IngestProgressView progress={ingestProgress} />
            )}

            {/* Timeline list */}
            {artifacts.length === 0 ? (
              <p className="empty">
                {clientId
                  ? "No artifacts in dossier yet — upload the first one above."
                  : "Select a client to view the dossier."}
              </p>
            ) : (
              <ul className="artifact-list" aria-label="Dossier artifacts">
                {artifacts.map((a) => (
                  <li key={a.artifact_id} className="artifact-row">
                    <div className="artifact-head">
                      <span
                        className={`artifact-kind kind-${a.kind}`}
                        aria-label={`Kind: ${a.kind}`}
                      >
                        <span aria-hidden="true">{KIND_ICON[a.kind] ?? "📎"}</span> {a.kind}
                      </span>
                      <span className="artifact-filename" title={a.original_filename}>
                        {a.original_filename}
                      </span>
                      <span className="artifact-ts">{formatTs(a.ingested_at)}</span>
                    </div>
                    {a.summary && <p className="artifact-summary">{a.summary}</p>}
                    <div className="artifact-foot">
                      <a
                        className="artifact-link"
                        href={rawArtifactUrl(a.artifact_id)}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Original ↗
                      </a>
                      {a.contributed_to_profile && (
                        <span
                          className="badge badge-profile"
                          title="Used in the current profile distillation"
                        >
                          ✓ in profile
                        </span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {/* Subtle pointer to where the dossier data physically lives. */}
            {storage && artifacts.length > 0 && (
              <p className="storage-note">
                Stored in —{" "}
                {storage.workspace_url && storage.uc_catalog ? (
                  <a
                    href={`${storage.workspace_url}/explore/data/volumes/${storage.uc_catalog}/${storage.uc_schema}/${storage.volume_name}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    UC Volume <code>{storage.volume_name}</code> ↗
                  </a>
                ) : (
                  <span>
                    UC Volume <code>{storage.volume_name ?? "dossier_raw"}</code>
                  </span>
                )}{" "}
                (originals) · Lakebase <code>artifacts</code>, <code>artifact_chunks</code>{" "}
                (transcripts &amp; summaries)
              </p>
            )}
          </div>
        </section>

        {/* ── Panel 2: Advisor chat ───────────────────────────────────────────── */}
        <section className="panel span-2">
          <h2>Advisor brainstorm — considerations, not advice</h2>
          <div className="panel-body">
            {chatMessages.length === 0 && !streamingReply ? (
              <p className="empty">
                {clientId
                  ? "Ask a question about this client's dossier."
                  : "Select a client to begin."}
              </p>
            ) : (
              chatMessages.map((m, idx) => (
                <div key={idx} className={`turn ${m.role}`}>
                  <div className="turn-meta">{m.role}</div>
                  {m.role === "assistant" ? (
                    <div className="md">
                      <ReactMarkdown>{m.text}</ReactMarkdown>
                    </div>
                  ) : (
                    <div>{m.text}</div>
                  )}
                </div>
              ))
            )}
            {streamingReply !== null && (
              <div className="turn assistant">
                <div className="turn-meta">
                  assistant · streaming…
                  {busy && <span className="spinner" aria-label="Loading" />}
                </div>
                <div className="md">
                  <ReactMarkdown>{streamingReply}</ReactMarkdown>
                </div>
              </div>
            )}
          </div>
          <form className="chat-compose" onSubmit={onChat}>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e: KeyboardEvent<HTMLTextAreaElement>) => {
                if (e.key === "Enter" && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
                  e.preventDefault();
                  if (!busy && message.trim() && clientId) {
                    void onChat(e as unknown as FormEvent);
                  }
                }
              }}
              placeholder={clientId ? "Ask about the client's goals, circumstances, history…" : "Select a client first"}
              aria-label="Chat message"
              disabled={busy || !clientId}
            />
            <button type="submit" disabled={busy || !message.trim() || !clientId}>
              Send
            </button>
          </form>
        </section>

        {/* ── Panel 3: Retrieval inspector ───────────────────────────────────── */}
        <section className="panel">
          <h2>Retrieved chunks (last query)</h2>
          <div className="panel-body">
            {retrieved.length === 0 ? (
              <p className="empty">Send a message to see semantic recall scores.</p>
            ) : (
              retrieved.map((r) => (
                <div key={r.chunk_id} className="retrieval-item">
                  <div className="turn-meta">
                    chunk {r.chunk_index} · artifact {r.artifact_id} ·{" "}
                    <span className="score">score {r.score.toFixed(3)}</span>
                  </div>
                  <div>{r.content}</div>
                </div>
              ))
            )}
          </div>
        </section>

        {/* ── Panel 4: Distilled profile + provenance ─────────────────────────── */}
        <section className="panel">
          <h2>
            Distilled client profile (Delta)
            {clientId && !editingProfile && (
              <button
                type="button"
                className="ghost distill-btn"
                disabled={busy}
                onClick={() => setEditingProfile(true)}
                aria-label="Edit profile manually"
              >
                Edit profile
              </button>
            )}
          </h2>
          <div className="panel-body">
            {editingProfile ? (
              <ProfileEditPanel
                profile={profile}
                disabled={busy}
                onSave={(edits) => void onProfileSave(edits)}
                onCancel={() => setEditingProfile(false)}
              />
            ) : !profile ? (
              <p className="empty">
                No profile in UC yet — click "Edit profile", "Trigger distillation", or wait for
                the nightly job.
              </p>
            ) : (
              <>
                <dl className="profile-dl">
                  <dt>Risk tolerance</dt>
                  <dd>{profile.risk_tolerance}</dd>
                  <dt>Goals</dt>
                  <dd>{profile.investment_goals.join(", ") || "—"}</dd>
                  <dt>Family context</dt>
                  <dd>{profile.family_context || "—"}</dd>
                  <dt>Preferences</dt>
                  <dd>{profile.stated_preferences || "—"}</dd>
                  <dt>Summary</dt>
                  <dd>{profile.summary || "—"}</dd>
                  <dt>Distilled at</dt>
                  <dd>{formatTs(profile.distilled_at) || "—"}</dd>
                  {profile.source_artifact_ids.length > 0 && (
                    <>
                      <dt>Source artifacts</dt>
                      <dd>
                        <div className="provenance-badges">
                          {profile.source_artifact_ids.map((aid) => (
                            <button
                              key={aid}
                              type="button"
                              className="badge badge-artifact"
                              aria-label={`View provenance for artifact ${aid}`}
                              onClick={() => void loadProvenance(aid)}
                            >
                              #{aid}
                            </button>
                          ))}
                        </div>
                      </dd>
                    </>
                  )}
                </dl>

                {/* Provenance drawer */}
                {provenanceLoading && (
                  <p className="empty">
                    Loading provenance… <span className="spinner" aria-label="Loading" />
                  </p>
                )}
                {provenanceArtifact && (
                  <ProvenanceCard
                    artifact={provenanceArtifact}
                    onClose={() => setProvenanceArtifact(null)}
                  />
                )}
              </>
            )}
          </div>
        </section>

        {/* ── Panel 5: Pending proposals ─────────────────────────────────────── */}
        <section className="panel span-2">
          <h2>
            Pending memory proposals (human-in-the-loop)
            <button
              type="button"
              className="ghost distill-btn"
              disabled={distilling || !clientId}
              onClick={() => void onTriggerDistill()}
              aria-label="Trigger distillation job"
            >
              {distilling ? "Generating…" : "Trigger distillation"}
            </button>
          </h2>
          {distillMsg && <p className="distill-msg">{distillMsg}</p>}
          <div className="panel-body">
            <p className="memory-edit-hint">
              The nightly distillation job proposes profile updates from recent artifacts.
              <strong> Accept</strong> commits to the Delta profile,{" "}
              <strong> Edit</strong> lets you correct fields before committing, and{" "}
              <strong> Cancel</strong> rejects the proposal. Every outcome writes an audit row.
            </p>
            {proposals.length === 0 ? (
              <p className="empty">
                {clientId
                  ? "No pending proposals for this client."
                  : "Select a client to review proposals."}
              </p>
            ) : (
              proposals.map((p) => (
                <ProposalCard
                  key={p.proposal_id}
                  proposal={p}
                  current={profile}
                  disabled={busy}
                  onAccept={(edits) => void onProposalAccept(p.proposal_id, edits)}
                  onReject={() => void onProposalReject(p.proposal_id)}
                />
              ))
            )}
          </div>
        </section>
      </div>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// IngestProgressView — checklist of SSE ingest steps with live spinner
// ─────────────────────────────────────────────────────────────────────────────

function IngestProgressView({ progress }: { progress: IngestProgress }) {
  if (progress.phase === "idle") return null;

  if (progress.phase === "error") {
    return (
      <div className="ingest-progress ingest-error" role="alert">
        <strong>Ingest failed:</strong> {progress.message}
      </div>
    );
  }

  if (progress.phase === "done") {
    return (
      <div className="ingest-progress ingest-done" role="status">
        {progress.deduped ? (
          <>Duplicate detected — artifact already in dossier (content hash matched).</>
        ) : (
          <>Artifact #{progress.artifactId} ingested successfully.</>
        )}
      </div>
    );
  }

  // phase === "running"
  const { completedSteps, currentStep, detail } = progress;
  return (
    <div className="ingest-progress" role="status" aria-live="polite">
      <ul className="ingest-steps" aria-label="Ingest pipeline progress">
        {INGEST_STEPS.map((step) => {
          const done = completedSteps.has(step);
          const active = currentStep === step && !done;
          return (
            <li
              key={step}
              className={`ingest-step${done ? " step-done" : ""}${active ? " step-active" : ""}`}
              aria-label={`Step ${step}: ${done ? "complete" : active ? "in progress" : "pending"}`}
            >
              <span className="step-icon" aria-hidden="true">
                {done ? "✓" : active ? "…" : "○"}
              </span>
              <span className="step-name">{step}</span>
              {done && step === "summarized" && detail && (
                <span className="step-detail">{detail}</span>
              )}
              {done && step !== "summarized" && detail && completedSteps.size === INGEST_STEPS.indexOf(step) + 1 && (
                <span className="step-detail">{detail}</span>
              )}
              {active && <span className="spinner" aria-label="Loading" />}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ProvenanceCard — shown when an advisor clicks a source_artifact_ids badge
// ─────────────────────────────────────────────────────────────────────────────

function ProvenanceCard({
  artifact,
  onClose,
}: {
  artifact: Artifact;
  onClose: () => void;
}) {
  return (
    <div className="provenance-card" role="complementary" aria-label={`Provenance for artifact ${artifact.artifact_id}`}>
      <div className="provenance-head">
        <strong>Artifact #{artifact.artifact_id}</strong>
        <button
          type="button"
          className="ghost"
          onClick={onClose}
          aria-label="Close provenance panel"
        >
          Close
        </button>
      </div>
      <dl className="profile-dl">
        <dt>Filename</dt>
        <dd>{artifact.original_filename}</dd>
        <dt>Kind</dt>
        <dd>{artifact.kind}</dd>
        <dt>Ingested</dt>
        <dd>{formatTs(artifact.ingested_at)}</dd>
        {artifact.summary && (
          <>
            <dt>Summary</dt>
            <dd>{artifact.summary}</dd>
          </>
        )}
        {artifact.sensitivity_tags.length > 0 && (
          <>
            <dt>Sensitivity</dt>
            <dd>{artifact.sensitivity_tags.join(", ")}</dd>
          </>
        )}
      </dl>
      <div className="provenance-actions">
        <a
          href={rawArtifactUrl(artifact.artifact_id)}
          download={artifact.original_filename}
          className="button"
          aria-label={`Download raw file ${artifact.original_filename}`}
        >
          Download original
        </a>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ProfileEditPanel — manual (no-LLM) profile editor
// ─────────────────────────────────────────────────────────────────────────────

function ProfileEditPanel({
  profile,
  disabled,
  onSave,
  onCancel,
}: {
  profile: ClientProfile | null;
  disabled: boolean;
  onSave: (edits: ProfileEdits) => void;
  onCancel: () => void;
}) {
  const [risk, setRisk] = useState(profile?.risk_tolerance ?? "unknown");
  const [goals, setGoals] = useState(profile?.investment_goals.join(", ") ?? "");
  const [family, setFamily] = useState(profile?.family_context ?? "");
  const [prefs, setPrefs] = useState(profile?.stated_preferences ?? "");
  const [summary, setSummary] = useState(profile?.summary ?? "");

  function save() {
    onSave({
      risk_tolerance: risk,
      investment_goals: goals
        .split(",")
        .map((g) => g.trim())
        .filter(Boolean),
      family_context: family,
      stated_preferences: prefs,
      summary,
    });
  }

  return (
    <div className="proposal-edit">
      <label>
        Risk tolerance
        <select
          value={risk}
          onChange={(e) => setRisk(e.target.value)}
          className="field-select"
          aria-label="Risk tolerance"
        >
          <option value="conservative">conservative</option>
          <option value="moderate">moderate</option>
          <option value="aggressive">aggressive</option>
          <option value="unknown">unknown</option>
        </select>
      </label>
      <label>
        Goals (comma-separated)
        <input
          value={goals}
          onChange={(e) => setGoals(e.target.value)}
          aria-label="Investment goals"
        />
      </label>
      <label>
        Family context
        <input
          value={family}
          onChange={(e) => setFamily(e.target.value)}
          aria-label="Family context"
        />
      </label>
      <label>
        Preferences
        <input
          value={prefs}
          onChange={(e) => setPrefs(e.target.value)}
          aria-label="Stated preferences"
        />
      </label>
      <label>
        Summary
        <textarea
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          rows={3}
          aria-label="Profile summary"
        />
      </label>
      <div className="proposal-actions">
        <button type="button" onClick={save} disabled={disabled}>
          Save to profile
        </button>
        <button
          type="button"
          className="ghost"
          onClick={onCancel}
          disabled={disabled}
          aria-label="Cancel profile edit"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ProposalCard — HITL review with diff view and edit-then-accept
// ─────────────────────────────────────────────────────────────────────────────

type FieldDiff = { label: string; current: string; proposed: string };
type DiffToken = { text: string; type: "same" | "removed" | "added" };

// Word-level diff via longest-common-subsequence.
function diffWords(oldStr: string, newStr: string): DiffToken[] {
  const a = oldStr.trim().split(/\s+/).filter(Boolean);
  const b = newStr.trim().split(/\s+/).filter(Boolean);
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      dp[i][j] =
        a[i] === b[j]
          ? dp[i + 1][j + 1] + 1
          : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const tokens: DiffToken[] = [];
  let i = 0;
  let j = 0;
  while (i < m && j < n) {
    if (a[i] === b[j]) {
      tokens.push({ text: a[i], type: "same" });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      tokens.push({ text: a[i], type: "removed" });
      i++;
    } else {
      tokens.push({ text: b[j], type: "added" });
      j++;
    }
  }
  while (i < m) tokens.push({ text: a[i++], type: "removed" });
  while (j < n) tokens.push({ text: b[j++], type: "added" });
  return tokens;
}

function computeDiffs(p: Proposal, cur: ClientProfile | null): FieldDiff[] {
  const norm = (s: string) => (s || "").trim();
  const rows: [string, string, string][] = [
    ["Risk tolerance", cur?.risk_tolerance ?? "", p.risk_tolerance],
    ["Goals", cur?.investment_goals.join(", ") ?? "", p.investment_goals.join(", ")],
    ["Family context", cur?.family_context ?? "", p.family_context],
    ["Preferences", cur?.stated_preferences ?? "", p.stated_preferences],
    ["Summary", cur?.summary ?? "", p.summary],
  ];
  return rows
    .filter(([, current, proposed]) => norm(current) !== norm(proposed))
    .map(([label, current, proposed]) => ({
      label,
      current: current || "—",
      proposed: proposed || "—",
    }));
}

function ProposalCard({
  proposal,
  current,
  onAccept,
  onReject,
  disabled,
}: {
  proposal: Proposal;
  current: ClientProfile | null;
  onAccept: (edits?: ProposalEdits) => void;
  onReject: () => void;
  disabled: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [risk, setRisk] = useState(proposal.risk_tolerance);
  const [goals, setGoals] = useState(proposal.investment_goals.join(", "));
  const [family, setFamily] = useState(proposal.family_context);
  const [prefs, setPrefs] = useState(proposal.stated_preferences);
  const [summary, setSummary] = useState(proposal.summary);

  const diffs = computeDiffs(proposal, current);

  function acceptEdited() {
    onAccept({
      risk_tolerance: risk,
      investment_goals: goals
        .split(",")
        .map((g) => g.trim())
        .filter(Boolean),
      family_context: family,
      stated_preferences: prefs,
      summary,
    });
  }

  return (
    <div className="proposal-card">
      <div className="proposal-head">
        <span className="proposal-id" title={proposal.proposal_id}>
          {proposal.client_id} · proposed {formatTs(proposal.proposed_at)}
        </span>
        {proposal.source_artifact_ids.length > 0 && (
          <span className="proposal-sources" aria-label="Source artifacts for this proposal">
            Sources:{" "}
            {proposal.source_artifact_ids.map((id) => (
              <span key={id} className="badge badge-artifact">
                #{id}
              </span>
            ))}
          </span>
        )}
      </div>

      {!editing ? (
        diffs.length === 0 ? (
          <p className="empty">No changes from the current profile.</p>
        ) : (
          <dl className="profile-dl proposal-diff">
            {diffs.map((d) => (
              <Fragment key={d.label}>
                <dt>{d.label}</dt>
                <dd>
                  {diffWords(d.current, d.proposed).map((t, idx) => (
                    <span key={idx} className={`diff-${t.type}`}>
                      {t.text}{" "}
                    </span>
                  ))}
                </dd>
              </Fragment>
            ))}
          </dl>
        )
      ) : (
        <div className="proposal-edit">
          <label>
            Risk tolerance
            <select
              value={risk}
              onChange={(e) => setRisk(e.target.value)}
              className="field-select"
              aria-label="Proposed risk tolerance"
            >
              <option value="conservative">conservative</option>
              <option value="moderate">moderate</option>
              <option value="aggressive">aggressive</option>
              <option value="unknown">unknown</option>
            </select>
          </label>
          <label>
            Goals (comma-separated)
            <input
              value={goals}
              onChange={(e) => setGoals(e.target.value)}
              aria-label="Proposed investment goals"
            />
          </label>
          <label>
            Family context
            <input
              value={family}
              onChange={(e) => setFamily(e.target.value)}
              aria-label="Proposed family context"
            />
          </label>
          <label>
            Preferences
            <input
              value={prefs}
              onChange={(e) => setPrefs(e.target.value)}
              aria-label="Proposed stated preferences"
            />
          </label>
          <label>
            Summary
            <textarea
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              rows={3}
              aria-label="Proposed profile summary"
            />
          </label>
        </div>
      )}

      <div className="proposal-actions">
        {!editing ? (
          <>
            <button
              type="button"
              onClick={() => onAccept()}
              disabled={disabled}
              aria-label="Accept proposal"
            >
              Accept
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => setEditing(true)}
              disabled={disabled}
              aria-label="Edit proposal before accepting"
            >
              Edit
            </button>
            <button
              type="button"
              className="ghost"
              onClick={onReject}
              disabled={disabled}
              aria-label="Reject proposal"
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={acceptEdited}
              disabled={disabled}
              aria-label="Save edits and accept proposal"
            >
              Save &amp; Accept
            </button>
            <button
              type="button"
              className="ghost"
              onClick={() => setEditing(false)}
              disabled={disabled}
              aria-label="Discard edits"
            >
              Discard edits
            </button>
          </>
        )}
      </div>
    </div>
  );
}
