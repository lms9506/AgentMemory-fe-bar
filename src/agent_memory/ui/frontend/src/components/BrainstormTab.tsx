import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { MessageSquare, Brain, Send, ArrowUpRight } from "lucide-react";
import { type Artifact, type RetrievedChunk, type ManagedMemorySearchResult } from "../api";
import { EmptyState } from "./EmptyState";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

interface BrainstormTabProps {
  clientId: string;
  chatMessages: ChatMessage[];
  streamingReply: string | null;
  busy: boolean;
  message: string;
  retrieved: RetrievedChunk[];
  managedMemory: ManagedMemorySearchResult | null;
  artifacts: Artifact[];
  onMessageChange: (m: string) => void;
  onChat: (e: FormEvent) => void;
  onSuggestion: (text: string) => void;
  onOpenArtifact?: (artifactId: number) => void;
}

/** Turn "client_0000_risk_update_form.pdf" into "Risk Update Form". */
function prettyArtifactTitle(a: Artifact): string {
  const raw = a.original_filename || "";
  const stem = raw.replace(/\.[^.]+$/, "");
  const stripped = stem.replace(/^client_\d+_/i, "");
  const words = stripped.split(/[_\-]+/).filter(Boolean);
  if (words.length === 0) return raw || `Artifact #${a.artifact_id}`;
  return words
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

/**
 * Strip document-letterhead lines from the top of chunk content so the meaningful
 * signal surfaces first in the retrieval preview. Removes leading firm-header lines
 * ("MERIDIAN WEALTH PARTNERS…", "Registered Investment Adviser…", "Custodian:…",
 * "Form ADV Part 2…", "Prepared by/for advisor:…", "Document:…", "Account:…",
 * "Client:…") but keeps them out of the way regardless of casing. Falls back to the
 * original text if trimming would leave nothing.
 */
function trimBoilerplate(content: string): string {
  const skip = [
    /^meridian\b/i,
    /^registered investment adviser\b/i,
    /^custodian:/i,
    /^form adv\b/i,
    /^prepared (?:by|for)\b/i,
    /^document:/i,
    /^account\b/i,
    /^client:/i,
    /^advisor of record:/i,
    /^statement period:/i,
  ];
  const lines = content.split(/\n/);
  let i = 0;
  while (i < lines.length && (lines[i].trim() === "" || skip.some((r) => r.test(lines[i].trim())))) {
    i++;
  }
  const trimmed = lines.slice(i).join(" ").replace(/\s+/g, " ").trim();
  return trimmed.length > 20 ? trimmed : content.replace(/\s+/g, " ").trim();
}

interface RelevanceBucket {
  label: string;
  cls: string;
}
function scoreBucket(score: number): RelevanceBucket {
  if (score >= 0.7) return { label: "Strong match", cls: "bg-databricks-moss/15 text-databricks-moss" };
  if (score >= 0.55) return { label: "Fair match", cls: "bg-databricks-honey/20 text-[#a37f00]" };
  return { label: "Weak match", cls: "bg-[var(--color-border)] text-databricks-slate" };
}

const SUGGESTIONS = [
  "Prep for our next meeting — what should I cover?",
  "Explore this client's risk profile and any red flags.",
  "Summarize the full dossier in 3 bullet points.",
];

export function BrainstormTab({
  clientId,
  chatMessages,
  streamingReply,
  busy,
  message,
  retrieved,
  managedMemory,
  artifacts,
  onMessageChange,
  onChat,
  onSuggestion,
  onOpenArtifact,
}: BrainstormTabProps) {
  const artifactById = new Map(artifacts.map((a) => [a.artifact_id, a]));
  const bottomRef = useRef<HTMLDivElement>(null);
  const [composerFocused, setComposerFocused] = useState(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, streamingReply]);

  const hasChat = chatMessages.length > 0 || streamingReply !== null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-start">
      {/* ── Chat pane (left, span 2) ── */}
      <div className="md:col-span-2 rounded-xl border border-[var(--color-border)] bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)] border-t-2 border-t-databricks-navy flex flex-col overflow-hidden min-h-[480px]">
        <div className="px-4 py-3 border-b border-[var(--color-border)]">
          <h2 className="text-base font-semibold text-databricks-navy">Brainstorm</h2>
          <p className="text-xs text-databricks-slate mt-0.5">
            Considerations only — not financial advice.
          </p>
        </div>

        {/* Thread */}
        <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3 min-h-0">
          {!hasChat ? (
            clientId ? (
              <div className="flex flex-col items-center justify-center gap-4 py-8">
                <EmptyState
                  icon={MessageSquare}
                  text="Ask a question about this client's dossier."
                />
                <div className="flex flex-wrap justify-center gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      className="text-xs px-3 py-1.5 rounded-full border border-[var(--color-border)] text-databricks-navy hover:bg-[var(--color-databricks-cloud)] hover:border-databricks-navy/30 transition-colors duration-150"
                      onClick={() => onSuggestion(s)}
                      aria-label={`Use suggestion: ${s}`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <EmptyState icon={MessageSquare} text="Select a client to begin brainstorming." />
            )
          ) : (
            <>
              {chatMessages.map((m, idx) => (
                <div
                  key={idx}
                  className={[
                    "flex",
                    m.role === "user" ? "justify-end" : "justify-start",
                  ].join(" ")}
                >
                  <div
                    className={[
                      "max-w-[80%] px-4 py-2.5 rounded-xl text-sm",
                      m.role === "user"
                        ? "bg-databricks-navy text-white rounded-tr-sm"
                        : "bg-[var(--color-databricks-cloud)] text-databricks-navy rounded-tl-sm",
                    ].join(" ")}
                  >
                    {m.role === "user" ? (
                      <span>{m.text}</span>
                    ) : (
                      <div className="md leading-relaxed">
                        <ReactMarkdown>{m.text}</ReactMarkdown>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {streamingReply !== null && (
                <div className="flex justify-start">
                  <div className="max-w-[80%] px-4 py-2.5 rounded-xl rounded-tl-sm bg-[var(--color-databricks-cloud)] text-databricks-navy text-sm">
                    <div className="text-xs text-databricks-slate flex items-center gap-1.5 mb-1.5">
                      <span>Smart Advise</span>
                      {busy && (
                        <span
                          className="inline-block w-3 h-3 border-2 border-[var(--color-border)] border-t-databricks-red rounded-full"
                          style={{ animation: "spin 0.7s linear infinite" }}
                          aria-label="Streaming response"
                        />
                      )}
                    </div>
                    <div className="md leading-relaxed">
                      <ReactMarkdown>{streamingReply}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </>
          )}
        </div>

        {/* Composer */}
        <form
          className={[
            "flex gap-2 px-4 py-3 border-t border-[var(--color-border)] transition-colors duration-150",
            composerFocused ? "bg-[var(--color-surface-muted)]" : "bg-white",
          ].join(" ")}
          onSubmit={onChat}
        >
          <textarea
            className="flex-1 resize-none min-h-[2.5rem] max-h-32 px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm text-databricks-navy placeholder:text-databricks-slate focus:outline-none focus:border-databricks-navy/40 transition-colors duration-150 overflow-y-auto"
            value={message}
            onChange={(e) => onMessageChange(e.target.value)}
            onFocus={() => setComposerFocused(true)}
            onBlur={() => setComposerFocused(false)}
            onKeyDown={(e: KeyboardEvent<HTMLTextAreaElement>) => {
              if (e.key === "Enter" && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
                e.preventDefault();
                if (!busy && message.trim() && clientId) {
                  void onChat(e as unknown as FormEvent);
                }
              }
            }}
            placeholder={
              clientId
                ? "Ask about the client's goals, circumstances, history… (Enter to send)"
                : "Select a client first"
            }
            aria-label="Chat message"
            disabled={busy || !clientId}
            rows={1}
          />
          <button
            type="submit"
            className="shrink-0 bg-databricks-red hover:bg-[#e02f1c] text-white p-2 rounded-lg shadow-sm transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-databricks-red/30"
            disabled={busy || !message.trim() || !clientId}
            aria-label="Send message"
          >
            <Send className="w-4 h-4" aria-hidden="true" />
          </button>
        </form>
      </div>

      {/* ── Retrieval inspector (right, span 1) ── */}
      <div className="md:col-span-1 flex flex-col gap-4">
        {/* Semantic chunks (Lakebase pgvector) */}
        <div className="rounded-xl border border-[var(--color-border)] bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)] border-t-2 border-t-databricks-navy overflow-hidden">
          <div className="px-4 py-3 border-b border-[var(--color-border)]">
            <div className="flex items-center gap-2">
              <Brain className="w-4 h-4 text-databricks-slate" aria-hidden="true" />
              <h3 className="text-base font-semibold text-databricks-navy">Retrieval inspector</h3>
            </div>
            <p className="text-xs text-databricks-slate mt-0.5">
              What Smart Advise pulled from the dossier — click a source to open it.
            </p>
          </div>
          <div className="p-2">
            {retrieved.length === 0 ? (
              <div className="px-2 py-4">
                <EmptyState icon={Brain} text="Send a message to see what was recalled." />
              </div>
            ) : (
              <ul className="flex flex-col gap-1">
                {retrieved.map((r) => {
                  const art = artifactById.get(r.artifact_id);
                  const label = art ? prettyArtifactTitle(art) : `Artifact #${r.artifact_id}`;
                  const bucket = scoreBucket(r.score);
                  const canOpen = !!(art && onOpenArtifact);
                  const preview = trimBoilerplate(r.content);
                  return (
                    <li key={r.chunk_id}>
                      <button
                        type="button"
                        disabled={!canOpen}
                        onClick={() => art && onOpenArtifact?.(art.artifact_id)}
                        className={[
                          "w-full text-left px-3 py-2.5 rounded-lg transition-colors duration-150 group",
                          canOpen
                            ? "hover:bg-[var(--color-surface-muted)] cursor-pointer focus:outline-none focus:bg-[var(--color-surface-muted)] focus:ring-2 focus:ring-databricks-navy/10"
                            : "cursor-default",
                        ].join(" ")}
                        aria-label={canOpen ? `Open ${label}` : label}
                        title={art?.original_filename ?? undefined}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm font-semibold text-databricks-navy truncate">
                            {label}
                          </span>
                          {canOpen && (
                            <ArrowUpRight
                              className="w-3.5 h-3.5 text-databricks-slate opacity-0 group-hover:opacity-100 shrink-0 transition-opacity duration-150"
                              aria-hidden="true"
                            />
                          )}
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <span
                            className={[
                              "text-[0.65rem] font-medium px-1.5 py-0.5 rounded-full",
                              bucket.cls,
                            ].join(" ")}
                          >
                            {bucket.label}
                          </span>
                          <span className="text-[0.68rem] font-mono text-databricks-slate tabular-nums">
                            {r.score.toFixed(2)}
                          </span>
                        </div>
                        <p className="text-xs text-databricks-slate leading-relaxed mt-1.5 line-clamp-2">
                          {preview}
                        </p>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>

        {/* Managed memory hits — second lane */}
        {managedMemory?.enabled && (
          <div className="rounded-xl border border-[var(--color-border)] bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)] border-t-2 border-t-databricks-orange overflow-hidden">
            <div className="px-4 py-3 border-b border-[var(--color-border)]">
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-databricks-orange" aria-hidden="true" />
                <h3 className="text-base font-semibold text-databricks-navy">Managed memory</h3>
                <span className="text-[0.6rem] font-medium px-1.5 py-0.5 rounded-full bg-databricks-orange/10 text-databricks-orange uppercase tracking-wide">
                  Beta
                </span>
              </div>
              <p className="text-xs text-databricks-slate mt-0.5">
                Distilled profile memories retrieved from the UC memory store.
              </p>
            </div>
            <div className="p-2">
              {managedMemory.hits.length === 0 ? (
                <div className="px-2 py-3">
                  <p className="text-xs text-databricks-slate">
                    No managed-memory hits for this query.
                  </p>
                </div>
              ) : (
                <ul className="flex flex-col gap-1">
                  {managedMemory.hits.map((h) => (
                    <li key={h.id}>
                      <div className="px-3 py-2.5 rounded-lg">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm font-semibold text-databricks-navy truncate">
                            {h.id.replace(/^\/?memories\//, "").replace(/\.md$/, "") || "profile"}
                          </span>
                          <span className="text-[0.68rem] font-mono text-databricks-slate tabular-nums shrink-0">
                            {h.score.toFixed(2)}
                          </span>
                        </div>
                        <p className="text-xs text-databricks-slate leading-relaxed mt-1 line-clamp-3">
                          {h.content}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
