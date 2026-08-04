import { useState } from "react";
import { User, Sparkles } from "lucide-react";
import {
  type ClientProfile,
  type Proposal,
  type ProfileEdits,
  type ProposalEdits,
  formatTs,
} from "../api";
import { ProposalCard } from "./ProposalCard";
import { EmptyState } from "./EmptyState";

// ─── ProfileEditPanel — manual profile editor ───────────────────────────────

interface ProfileEditPanelProps {
  profile: ClientProfile | null;
  disabled: boolean;
  onSave: (edits: ProfileEdits) => void;
  onCancel: () => void;
}

function ProfileEditPanel({ profile, disabled, onSave, onCancel }: ProfileEditPanelProps) {
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

  const inputCls =
    "mt-1 px-2.5 py-1.5 border border-[var(--color-border)] rounded-lg text-sm text-databricks-navy w-full focus:outline-none focus:border-databricks-navy/40 transition-colors duration-150";

  return (
    <div className="flex flex-col gap-3">
      <label className="flex flex-col text-xs font-medium text-databricks-slate gap-0.5">
        Risk tolerance
        <select
          value={risk}
          onChange={(e) => setRisk(e.target.value)}
          className={inputCls}
          aria-label="Risk tolerance"
        >
          <option value="conservative">conservative</option>
          <option value="moderate">moderate</option>
          <option value="aggressive">aggressive</option>
          <option value="unknown">unknown</option>
        </select>
      </label>
      <label className="flex flex-col text-xs font-medium text-databricks-slate gap-0.5">
        Goals (comma-separated)
        <input className={inputCls} value={goals} onChange={(e) => setGoals(e.target.value)} aria-label="Investment goals" />
      </label>
      <label className="flex flex-col text-xs font-medium text-databricks-slate gap-0.5">
        Family context
        <input className={inputCls} value={family} onChange={(e) => setFamily(e.target.value)} aria-label="Family context" />
      </label>
      <label className="flex flex-col text-xs font-medium text-databricks-slate gap-0.5">
        Preferences
        <input className={inputCls} value={prefs} onChange={(e) => setPrefs(e.target.value)} aria-label="Stated preferences" />
      </label>
      <label className="flex flex-col text-xs font-medium text-databricks-slate gap-0.5">
        Summary
        <textarea
          className={inputCls}
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          rows={3}
          aria-label="Profile summary"
        />
      </label>
      <div className="flex gap-2 mt-2">
        <button
          type="button"
          className="bg-databricks-red hover:bg-[#e02f1c] text-white font-medium text-sm px-3.5 py-1.5 rounded-md shadow-sm transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={save}
          disabled={disabled}
          aria-label="Save profile changes"
        >
          Save to profile
        </button>
        <button
          type="button"
          className="border border-databricks-navy/20 text-databricks-navy hover:bg-[var(--color-databricks-cloud)] text-sm font-medium px-3.5 py-1.5 rounded-md transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
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

// ─── ProfileTab ──────────────────────────────────────────────────────────────

interface ProfileTabProps {
  clientId: string;
  profile: ClientProfile | null;
  proposals: Proposal[];
  editingProfile: boolean;
  busy: boolean;
  distilling: boolean;
  distillMsg: string | null;
  onEditProfile: () => void;
  onCancelEdit: () => void;
  onProfileSave: (edits: ProfileEdits) => void;
  onProposalAccept: (proposalId: string, edits?: ProposalEdits) => void;
  onProposalReject: (proposalId: string) => void;
  onTriggerDistill: () => void;
  onOpenArtifact: (artifactId: number) => void;
}

function ProfileField({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 py-2.5 border-b border-[var(--color-border)] last:border-0">
      <span className="text-xs font-medium uppercase tracking-wider text-databricks-slate">
        {label}
      </span>
      <span className="text-sm text-databricks-navy leading-relaxed">{value || "—"}</span>
    </div>
  );
}

export function ProfileTab({
  clientId,
  profile,
  proposals,
  editingProfile,
  busy,
  distilling,
  distillMsg,
  onEditProfile,
  onCancelEdit,
  onProfileSave,
  onProposalAccept,
  onProposalReject,
  onTriggerDistill,
  onOpenArtifact,
}: ProfileTabProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-start">
      {/* ── Profile card (left, span 2) ── */}
      <div className="md:col-span-2 rounded-xl border border-[var(--color-border)] bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)] border-t-2 border-t-databricks-navy overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
          <h2 className="text-base font-semibold text-databricks-navy">Distilled client profile</h2>
          {clientId && !editingProfile && (
            <button
              type="button"
              className="border border-databricks-navy/20 text-databricks-navy hover:bg-[var(--color-databricks-cloud)] text-sm font-medium px-3 py-1 rounded-md transition-colors duration-150 disabled:opacity-50"
              disabled={busy}
              onClick={onEditProfile}
              aria-label="Edit profile manually"
            >
              Edit
            </button>
          )}
        </div>
        <div className="px-4 py-4">
          {editingProfile ? (
            <ProfileEditPanel
              profile={profile}
              disabled={busy}
              onSave={onProfileSave}
              onCancel={onCancelEdit}
            />
          ) : !profile ? (
            <EmptyState
              icon={User}
              text='No profile yet — click "Edit", "Trigger distillation", or wait for the nightly job.'
            />
          ) : (
            <dl className="m-0">
              <ProfileField label="Risk tolerance" value={profile.risk_tolerance} />
              <ProfileField label="Goals" value={profile.investment_goals.join(", ")} />
              <ProfileField label="Family context" value={profile.family_context} />
              <ProfileField label="Preferences" value={profile.stated_preferences} />
              <ProfileField label="Summary" value={profile.summary} />
              <ProfileField label="Distilled at" value={formatTs(profile.distilled_at)} />

              {profile.source_artifact_ids.length > 0 && (
                <>
                  <dt className="text-xs font-medium uppercase tracking-wider text-databricks-slate mt-2.5">
                    Source artifacts
                  </dt>
                  <dd className="mt-1.5 flex flex-wrap gap-1.5">
                    {profile.source_artifact_ids.map((aid) => (
                      <button
                        key={aid}
                        type="button"
                        className="text-[0.68rem] font-medium px-2 py-0.5 rounded-full bg-[var(--color-databricks-cloud)] text-databricks-navy border border-[var(--color-border)] hover:bg-[var(--color-border)] transition-colors duration-150"
                        aria-label={`View provenance for artifact ${aid}`}
                        onClick={() => onOpenArtifact(aid)}
                      >
                        #{aid}
                      </button>
                    ))}
                  </dd>
                </>
              )}
            </dl>
          )}
        </div>
      </div>

      {/* ── Proposals column (right, span 1) ── */}
      <div className="md:col-span-1 flex flex-col gap-4">
        {/* Distillation trigger */}
        <div className="rounded-xl border border-[var(--color-border)] bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)] border-t-2 border-t-databricks-navy overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
            <h3 className="text-base font-semibold text-databricks-navy">Pending proposals</h3>
            {proposals.length > 0 && (
              <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full bg-databricks-red text-white text-[0.65rem] font-bold">
                {proposals.length}
              </span>
            )}
          </div>

          <div className="px-4 py-3">
            <p className="text-xs text-databricks-slate mb-3 leading-relaxed">
              The nightly distillation job proposes profile updates from recent artifacts.{" "}
              <strong className="font-semibold text-databricks-navy">Accept</strong> commits to Delta,{" "}
              <strong className="font-semibold text-databricks-navy">Edit</strong> lets you correct fields first,{" "}
              <strong className="font-semibold text-databricks-navy">Reject</strong> drops the proposal. Every outcome writes an audit row.
            </p>
            <button
              type="button"
              className="w-full border border-databricks-navy/20 text-databricks-navy hover:bg-[var(--color-databricks-cloud)] text-sm font-medium px-3.5 py-1.5 rounded-md transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={distilling || !clientId}
              onClick={onTriggerDistill}
              aria-label="Trigger distillation job"
            >
              {distilling ? (
                <span className="flex items-center justify-center gap-2">
                  <span
                    className="inline-block w-3.5 h-3.5 border-2 border-[var(--color-border)] border-t-databricks-red rounded-full"
                    style={{ animation: "spin 0.7s linear infinite" }}
                    aria-hidden="true"
                  />
                  Generating…
                </span>
              ) : (
                "Trigger distillation"
              )}
            </button>
            {distillMsg && (
              <p className="mt-2 text-xs text-databricks-slate leading-relaxed">{distillMsg}</p>
            )}
          </div>
        </div>

        {/* Proposal cards */}
        {!clientId || proposals.length === 0 ? (
          <div className="rounded-xl border border-[var(--color-border)] bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)] px-4 py-4">
            <EmptyState
              icon={Sparkles}
              text={
                clientId
                  ? "No pending proposals for this client."
                  : "Select a client to review proposals."
              }
            />
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {proposals.map((p) => (
              <ProposalCard
                key={p.proposal_id}
                proposal={p}
                current={profile}
                disabled={busy}
                onAccept={(edits) => onProposalAccept(p.proposal_id, edits)}
                onReject={() => onProposalReject(p.proposal_id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
