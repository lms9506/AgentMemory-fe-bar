import {
  type DragEvent,
  type FormEvent,
  useCallback,
  useEffect,
  useState,
} from "react";
import {
  type Artifact,
  type ClientInfo,
  type ClientProfile,
  type Health,
  type IngestEvent,
  type ManagedMemorySearchResult,
  type Proposal,
  type ProposalEdits,
  type ProfileEdits,
  type RetrievedChunk,
  acceptProposal,
  fetchAdvisors,
  fetchArtifact,
  fetchArtifacts,
  fetchClients,
  fetchHealth,
  fetchProfile,
  fetchDistillStatus,
  fetchProposals,
  ingestArtifact,
  rejectProposal,
  saveProfileEdit,
  searchManagedMemory,
  sendChatStream,
  triggerDistill,
} from "./api";

import { TopNav } from "./components/TopNav";
import { ClientBanner } from "./components/ClientBanner";
import { TabBar, type TabId } from "./components/TabBar";
import { OverviewTab } from "./components/OverviewTab";
import { TimelineTab } from "./components/TimelineTab";
import { BrainstormTab } from "./components/BrainstormTab";
import { ProfileTab } from "./components/ProfileTab";
import { ProvenanceDrawer } from "./components/ProvenanceDrawer";
import { type IngestProgress } from "./components/IngestPanel";

const DEFAULT_ADVISOR = "advisor_demo_01";

// The ordered steps in an ingest pipeline run — kept here for runIngest handler.
const INGEST_STEPS = ["saved", "extracted", "embedded", "summarized", "proposed"] as const;
type IngestStep = (typeof INGEST_STEPS)[number];

export default function App() {
  // ── Identity ──────────────────────────────────────────────────────────────
  const [clientId, setClientId] = useState("");
  const [advisorId, setAdvisorId] = useState(DEFAULT_ADVISOR);
  const [clients, setClients] = useState<ClientInfo[]>([]);
  const [advisors, setAdvisors] = useState<string[]>([]);

  // ── Tab ───────────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  // ── Data ──────────────────────────────────────────────────────────────────
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [profile, setProfile] = useState<ClientProfile | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [storage, setStorage] = useState<Health | null>(null);

  // ── Ingest ────────────────────────────────────────────────────────────────
  const [ingestProgress, setIngestProgress] = useState<IngestProgress>({ phase: "idle" });
  const [noteText, setNoteText] = useState("");

  // ── Provenance drawer ─────────────────────────────────────────────────────
  const [provenanceArtifact, setProvenanceArtifact] = useState<Artifact | null>(null);
  const [provenanceLoading, setProvenanceLoading] = useState(false);

  // ── Chat / retrieval ──────────────────────────────────────────────────────
  const [chatMessages, setChatMessages] = useState<Array<{ role: "user" | "assistant"; text: string }>>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [streamingReply, setStreamingReply] = useState<string | null>(null);
  const [retrieved, setRetrieved] = useState<RetrievedChunk[]>([]);
  const [managedMemory, setManagedMemory] = useState<ManagedMemorySearchResult | null>(null);

  // ── Profile edit ──────────────────────────────────────────────────────────
  const [editingProfile, setEditingProfile] = useState(false);

  // ── Distillation ──────────────────────────────────────────────────────────
  const [distilling, setDistilling] = useState(false);
  const [distillMsg, setDistillMsg] = useState<string | null>(null);

  // ── Global error ──────────────────────────────────────────────────────────
  const [error, setError] = useState<string | null>(null);

  // ── Bootstrap ────────────────────────────────────────────────────────────

  useEffect(() => {
    fetchClients()
      .then((cs) => {
        setClients(cs);
        if (cs.length > 0) setClientId(cs[0].id);
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

  // ── Client / advisor ──────────────────────────────────────────────────────

  function handleClientChange(newClient: string) {
    setClientId(newClient);
    setArtifacts([]);
    setRetrieved([]);
    setManagedMemory(null);
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
    setManagedMemory(null);
    setStreamingReply(null);
  }

  // ── Ingest ────────────────────────────────────────────────────────────────

  async function runIngest(file: File) {
    if (!clientId) return;
    setIngestProgress({
      phase: "running",
      completedSteps: new Set<IngestStep>(),
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
            completedSteps.add(e.step as IngestStep);
            const idx = INGEST_STEPS.indexOf(e.step as IngestStep);
            const nextStep =
              idx >= 0 && idx < INGEST_STEPS.length - 1
                ? INGEST_STEPS[idx + 1]
                : null;
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
    const file = e.dataTransfer.files[0];
    if (file) void runIngest(file);
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) void runIngest(file);
    e.target.value = "";
  }

  function runIngestText() {
    const text = noteText.trim();
    if (!clientId || !text) return;
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const file = new File([text], `typed_note_${stamp}.txt`, { type: "text/plain" });
    void runIngest(file);
    setNoteText("");
  }

  // ── Provenance ────────────────────────────────────────────────────────────

  async function loadProvenance(artifactId: number) {
    setProvenanceLoading(true);
    setProvenanceArtifact(null);
    try {
      const art = await fetchArtifact(artifactId);
      setProvenanceArtifact(art);
    } catch {
      // non-fatal
    } finally {
      setProvenanceLoading(false);
    }
  }

  // ── Chat ──────────────────────────────────────────────────────────────────

  async function onChat(e: FormEvent) {
    e.preventDefault();
    if (!message.trim() || !clientId) return;
    const userText = message.trim();
    setBusy(true);
    setStreamingReply("");
    setError(null);
    setMessage("");
    setChatMessages((prev) => [...prev, { role: "user", text: userText }]);

    // Kick off managed memory search in parallel with the chat stream
    const mmPromise = searchManagedMemory(clientId, userText, 3).catch(() => null);

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

      // Resolve managed memory once chat is done
      const mm = await mmPromise;
      if (mm) setManagedMemory(mm);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
      setStreamingReply(null);
    }
  }

  function onSuggestion(text: string) {
    setMessage(text);
    setActiveTab("brainstorm");
  }

  // ── Proposals ─────────────────────────────────────────────────────────────

  async function onProposalAccept(proposalId: string, edits?: ProposalEdits) {
    setBusy(true);
    setError(null);
    try {
      await acceptProposal(proposalId, advisorId, edits);
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
      setProposals((prev) => prev.filter((x) => x.proposal_id !== proposalId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  // ── Profile edit ──────────────────────────────────────────────────────────

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

  // ── Distillation ──────────────────────────────────────────────────────────

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

  // ── Tab action CTAs from banner ───────────────────────────────────────────

  function handleTabAction(action: "ingest" | "brainstorm") {
    if (action === "ingest") setActiveTab("timeline");
    if (action === "brainstorm") setActiveTab("brainstorm");
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-[var(--color-surface-muted)] font-sans">
      <TopNav
        advisorId={advisorId}
        advisors={advisors}
        onAdvisorChange={handleAdvisorChange}
      />

      <ClientBanner
        clients={clients}
        clientId={clientId}
        onClientChange={handleClientChange}
        artifactCount={artifacts.length}
        pendingCount={proposals.length}
        activeTab={activeTab}
        onTabAction={handleTabAction}
      />

      <TabBar
        active={activeTab}
        onChange={setActiveTab}
        pendingCount={proposals.length}
      />

      {/* Global error banner */}
      {error && (
        <div
          className="max-w-screen-xl mx-auto mt-4 mx-6 px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-databricks-lava text-sm flex items-start justify-between gap-4"
          role="alert"
        >
          <span>{error}</span>
          <button
            type="button"
            className="shrink-0 text-xs font-medium underline hover:no-underline"
            onClick={() => setError(null)}
            aria-label="Dismiss error"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Tab panels */}
      <main className="max-w-screen-xl mx-auto px-6 py-6">
        {activeTab === "overview" && (
          <div role="tabpanel" id="tabpanel-overview" aria-labelledby="tab-overview">
            <OverviewTab
              artifacts={artifacts}
              profile={profile}
              proposals={proposals}
              clientId={clientId}
              onNavigate={setActiveTab}
              onOpenArtifact={(a) => void loadProvenance(a.artifact_id)}
            />
          </div>
        )}

        {activeTab === "timeline" && (
          <div role="tabpanel" id="tabpanel-timeline" aria-labelledby="tab-timeline">
            <TimelineTab
              clientId={clientId}
              artifacts={artifacts}
              ingestProgress={ingestProgress}
              noteText={noteText}
              storage={storage}
              onNoteChange={setNoteText}
              onFileDrop={handleFileDrop}
              onFileSelect={handleFileSelect}
              onNoteSubmit={runIngestText}
              onOpenArtifact={(a) => void loadProvenance(a.artifact_id)}
            />
          </div>
        )}

        {activeTab === "brainstorm" && (
          <div role="tabpanel" id="tabpanel-brainstorm" aria-labelledby="tab-brainstorm">
            <BrainstormTab
              clientId={clientId}
              chatMessages={chatMessages}
              streamingReply={streamingReply}
              busy={busy}
              message={message}
              retrieved={retrieved}
              managedMemory={managedMemory}
              artifacts={artifacts}
              onMessageChange={setMessage}
              onChat={(e) => void onChat(e)}
              onSuggestion={onSuggestion}
              onOpenArtifact={(id) => void loadProvenance(id)}
            />
          </div>
        )}

        {activeTab === "profile" && (
          <div role="tabpanel" id="tabpanel-profile" aria-labelledby="tab-profile">
            <ProfileTab
              clientId={clientId}
              profile={profile}
              proposals={proposals}
              editingProfile={editingProfile}
              busy={busy}
              distilling={distilling}
              distillMsg={distillMsg}
              onEditProfile={() => setEditingProfile(true)}
              onCancelEdit={() => setEditingProfile(false)}
              onProfileSave={(edits) => void onProfileSave(edits)}
              onProposalAccept={(id, edits) => void onProposalAccept(id, edits)}
              onProposalReject={(id) => void onProposalReject(id)}
              onTriggerDistill={() => void onTriggerDistill()}
              onOpenArtifact={(id) => void loadProvenance(id)}
            />
          </div>
        )}
      </main>

      {/* Provenance drawer — global overlay */}
      <ProvenanceDrawer
        artifact={provenanceArtifact}
        loading={provenanceLoading}
        onClose={() => {
          setProvenanceArtifact(null);
          setProvenanceLoading(false);
        }}
      />
    </div>
  );
}
